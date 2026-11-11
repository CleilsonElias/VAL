"""Controlled revision study for VAL. Python standard library only.

Uses the unchanged 0.1.0 numerical core. The main revision uses raw_interval
archival, available but not the default in 0.1.0. Context signals are supplied
equally to adaptive thresholds and adaptive quotas. No task motivation is learned.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import platform
import random
import statistics
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"reference/src"))
from val_memory import VALMemory, VALConfig
from val_memory.benchmark import DOMAINS, QuotaFIFO
from val_memory import Observation
from val_memory.maths import normalized_vector

POLICIES = (
    "uniform_legacy", "selective_legacy", "uniform_consistent", "selective_consistent",
    "selective_consistent_no_amp", "adaptive_consistent", "quota_fixed", "quota_context", "uniform_fifo",
)


def dataset(seed, observations, queries, scenario, routing_error):
    """Keep facts, scores and query targets fixed when only router error changes."""
    rng=random.Random(seed)
    route_rng=random.Random(10000+seed)
    stream=[]
    labels=[]
    for i in range(observations):
        true_domain=rng.randrange(4)
        vector=normalized_vector(rng.gauss(0,1) for _ in range(12))
        code=f"Synthetic code {rng.getrandbits(48):012x}"
        score=rng.uniform(.05,.85)
        corrupt=route_rng.random()<routing_error
        offset=route_rng.randint(1,3)  # Draw regardless of corruption probability.
        routed=(true_domain+offset)%4 if corrupt else true_domain
        routing=[.04]*4
        routing[routed]=.88
        stream.append(Observation(f"fact-{i:04}",code,vector,tuple(routing),score))
        labels.append(true_domain)
    target_domain=1 if scenario=='shifted' else 0
    candidates=[i for i,k in enumerate(labels)
                if (scenario=='diffuse' or k==target_domain)
                and (scenario!='shifted' or i>=observations//2)]
    if not candidates:
        raise ValueError('insufficient seeded observations for target domain')
    query_set=[]
    for _ in range(queries):
        i=rng.choice(candidates)
        item=stream[i]
        vector=normalized_vector(x+rng.gauss(0,.02) for x in item.vector)
        routing=[.04]*4
        routing[labels[i]]=.88
        query_set.append((item.id,vector,routing))
    return stream,query_set


def make_engine(policy):
    if policy in ("quota_fixed", "quota_context"):
        return QuotaFIFO(128)
    if policy == "uniform_fifo":
        return VALMemory(VALConfig(DOMAINS, (0.0,)*4, theta_min=0, theta_max=1,
                                   active_capacity=128, shadow_capacity=0, delta_max=0))
    focus = (0.05, 0.9, 0.9, 0.9)
    lambdas = (sum(focus)/4,)*4 if policy.startswith("uniform_") else focus
    return VALMemory(VALConfig(
        DOMAINS, lambdas, shadow_policy="paper" if policy.endswith("legacy") else "raw_interval",
        delta_max=0 if policy.endswith("no_amp") else 0.9))


def switch_context(engine, policy):
    if policy == "adaptive_consistent":
        engine.apply_gradient([1, -1, 1, 1], learning_rate=0.9)
    elif policy == "quota_context":
        # Same external target signal, domain 0 -> 1; permute fixed quota budget.
        engine.quotas[0], engine.quotas[1] = engine.quotas[1], engine.quotas[0]
        retained = []
        for k, quota in enumerate(engine.quotas):
            pool = [x for x in engine.active if x.primary == k]
            retained.extend(pool[-quota:] if quota else [])
        engine.counters["active_evicted"] += len(engine.active)-len(retained)
        engine.active = sorted(retained, key=lambda x: x.sequence)


def run_study(seeds=16, observations=320, queries=96):
    if seeds < 2 or observations < 32 or queries < 1:
        raise ValueError("need seeds>=2, observations>=32, queries>=1")
    start = time.perf_counter()
    rows = []
    for scenario in ("focused", "shifted", "diffuse"):
        for routing_error in (0.0, 0.2):
            for seed in range(seeds):
                stream, query_set = dataset(seed, observations, queries, scenario, routing_error)
                for policy in POLICIES:
                    engine = make_engine(policy)
                    for i, item in enumerate(stream):
                        if scenario == "shifted" and i == observations//2:
                            switch_context(engine, policy)
                        engine.observe(item)
                    correct, active_correct, shadow_correct = 0, 0, 0
                    for expected, vector, routing in query_set:
                        result = engine.query(vector, routing, entropy=0.7, limit=1)
                        if result["hits"] and result["hits"][0]["id"] == expected:
                            correct += 1
                            active_correct += result["hits"][0]["source"] == "active"
                            shadow_correct += result["hits"][0]["source"] == "shadow"
                    stats = engine.stats()
                    assert len(engine.active)+len(engine.shadows) <= 128
                    rows.append(dict(
                        scenario=scenario, routing_error=routing_error, seed=seed, policy=policy,
                        recall=correct/queries, active_recall=active_correct/queries,
                        shadow_recall=shadow_correct/queries, active=len(engine.active), shadows=len(engine.shadows),
                        payload_bytes=stats["retained_payload_bytes"], lambdas=stats["lambdas"],
                        admissions=stats["counters"]["gate_accepted"],
                    ))
                if (seed+1) % 4 == 0:
                    print(f"{scenario} / routing_error={routing_error}: seeds {seed+1}/{seeds}", flush=True)
    summaries = []
    for scenario in ("focused", "shifted", "diffuse"):
        for routing_error in (0.0, 0.2):
            for policy in POLICIES:
                group = [r for r in rows if (r["scenario"],r["routing_error"],r["policy"]) ==
                         (scenario,routing_error,policy)]
                summaries.append(dict(scenario=scenario,routing_error=routing_error,policy=policy,
                    recall_mean=statistics.mean(r["recall"] for r in group),
                    recall_sd=statistics.stdev(r["recall"] for r in group),
                    active_mean=statistics.mean(r["active"] for r in group),
                    shadows_mean=statistics.mean(r["shadows"] for r in group),
                    payload_bytes_mean=statistics.mean(r["payload_bytes"] for r in group)))
    pairs = (("selective_consistent","uniform_consistent"),
             ("selective_consistent","selective_legacy"),
             ("selective_consistent","selective_consistent_no_amp"),
             ("selective_consistent","quota_fixed"),
             ("adaptive_consistent","quota_context"),
             ("adaptive_consistent","selective_consistent"))
    contrasts = []
    for scenario in ("focused", "shifted", "diffuse"):
        for routing_error in (0.0,0.2):
            selected = [r for r in rows if (r["scenario"],r["routing_error"])==(scenario,routing_error)]
            for left,right in pairs:
                a={r["seed"]:r["recall"] for r in selected if r["policy"]==left}
                b={r["seed"]:r["recall"] for r in selected if r["policy"]==right}
                diffs=[a[s]-b[s] for s in range(seeds)]
                mean=statistics.mean(diffs)
                sd=statistics.stdev(diffs)
                half=1.96*sd/math.sqrt(seeds)
                contrasts.append(dict(scenario=scenario,routing_error=routing_error,left=left,right=right,
                                      delta=mean,sd=sd,descriptive_normal_interval=[mean-half,mean+half]))
    return dict(schema_version=1,study="VAL manuscript revision 2026-11-11",created_at=datetime.now(timezone.utc).isoformat(),
                settings=dict(seeds=seeds,observations=observations,queries=queries,dimension=12,
                              active_shadow_caps=[64,64],total_episode_ceiling=128,
                              score_distribution="Uniform(0.05,0.85), externally supplied"),
                python=platform.python_version(),runtime_seconds=time.perf_counter()-start,
                policies=list(POLICIES),rows=rows,summaries=summaries,contrasts=contrasts,
                assumptions=["same streams and queries within each condition and seed",
                    "underlying episodes, scores and queries are held fixed across routing error levels; only routing changes",
                    "all policies use total ceiling 128; quotas/FIFO use all slots as active",
                    "quotas fixed and context-based use same initial target information as selective thresholds",
                    "adaptive thresholds and adaptive quotas receive exactly the same target-change signal",
                    "labels of individual queried episodes are never given to admission policies",
                    "score is independent of relevance and vector; no trained semantic encoder",
                    "router error affects ingestion; query routing is uncorrupted",
                    "equal slot ceilings, not equal actual bytes or resident RAM",
                    "intervals are descriptive seed variation, without multiplicity correction"],
                core_hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest()
                             for p in sorted((ROOT/"reference/src/val_memory").glob("*.py"))})


if __name__ == "__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--seeds",type=int,default=16)
    parser.add_argument("--observations",type=int,default=320)
    parser.add_argument("--queries",type=int,default=96)
    parser.add_argument("--output",type=Path,default=ROOT/"results/revision_study.json")
    args=parser.parse_args()
    if args.output.exists():
        parser.error("output exists; choose a new path")
    data=run_study(args.seeds,args.observations,args.queries)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(dict(runs=len(data["rows"]),seconds=data["runtime_seconds"],output=str(args.output))))
