"""Paired synthetic retrieval tests and executable counterexamples.

No benchmark labels are provided to the admission policies. A3 alone receives
the explicitly named external task-domain signal at a context switch. Synthetic
scores are independent of fact relevance and are not measured neural entropies.
"""

from __future__ import annotations

from dataclasses import asdict
import math
import platform
import random
import statistics

from .core import Observation, VALConfig, VALMemory
from .maths import normalized_vector, positive_int, unit_interval

DOMAINS = ("mathematics", "biology", "language", "spatial")
POLICIES = ("scalar_mean", "A1_fixed", "A2_broad", "A3_context", "quota_fifo",
            "A1_no_amplification", "A1_no_shadows")


class QuotaFIFO(VALMemory):
    """Simple competing allocation using the entire active+shadow slot budget."""

    def __init__(self, capacity):
        super().__init__(VALConfig(DOMAINS, (0.0,) * 4, theta_min=0, theta_max=1,
                                   delta_max=0, active_capacity=capacity, shadow_capacity=0))
        weights = (0.75, 0.10, 0.075, 0.075)
        raw = [capacity * w for w in weights]
        self.quotas = [math.floor(x) for x in raw]
        for k in sorted(range(4), key=lambda k: (-(raw[k]-self.quotas[k]), k))[:capacity-sum(self.quotas)]:
            self.quotas[k] += 1

    def observe(self, observation, *, dt=1.0):
        primary = max(range(4), key=observation.routing.__getitem__)
        if self.quotas[primary] == 0:
            previous = list(self.active)
            old_evictions = self.counters["active_evicted"]
            result = super().observe(observation, dt=dt)
            self.active = previous
            self.counters["active_evicted"] = old_evictions + 1
            result["destination"] = "not_retained_by_quota"
            return result
        pool = [x for x in self.active if x.primary == primary]
        if len(pool) >= self.quotas[primary] and pool:
            self.active.remove(pool[0])
            self.counters["active_evicted"] += 1
        result = super().observe(observation, dt=dt)
        return result


def make_engine(policy, capacity, shadow_capacity):
    focus = (0.05, 0.90, 0.90, 0.90)
    values = (sum(focus) / 4,) * 4 if policy == "scalar_mean" else focus
    if policy == "A2_broad":
        values = (0.20,) * 4
    if policy == "quota_fifo":
        return QuotaFIFO(capacity + shadow_capacity)
    return VALMemory(VALConfig(
        DOMAINS, values, active_capacity=capacity,
        shadow_capacity=0 if policy == "A1_no_shadows" else shadow_capacity,
        delta_max=0 if policy == "A1_no_amplification" else 0.90))


def _dataset(seed, observations, queries, scenario, routing_error):
    rng = random.Random(seed)
    stream = []
    labels = []
    for i in range(observations):
        true_domain = rng.randrange(4)
        routed = ((true_domain + rng.randint(1, 3)) % 4
                  if rng.random() < routing_error else true_domain)
        routing = [0.04] * 4
        routing[routed] = 0.88
        vector = normalized_vector(rng.gauss(0, 1) for _ in range(12))
        # A random episodic code is recoverable only if its episode is retained.
        record = Observation(f"fact-{i:04}", f"Synthetic code {rng.getrandbits(48):012x}",
                             vector, tuple(routing), rng.uniform(0.05, 0.85))
        stream.append(record)
        labels.append(true_domain)
    domain = 1 if scenario == "shifted" else 0
    candidates = [i for i, label in enumerate(labels)
                  if (scenario == "diffuse" or label == domain)
                  and (scenario != "shifted" or i >= observations // 2)]
    if not candidates:
        raise ValueError("too few observations for this seeded domain condition")
    query_set = []
    for _ in range(queries):
        i = rng.choice(candidates)
        observation = stream[i]
        noisy = normalized_vector(x + rng.gauss(0, 0.02) for x in observation.vector)
        routing = [0.04] * 4
        routing[labels[i]] = 0.88
        query_set.append((observation.id, noisy, routing))
    return stream, query_set


def run_benchmark(*, seeds=8, observations=320, queries=48, capacity=64, shadow_capacity=64):
    for name, value in (("seeds", seeds), ("observations", observations), ("queries", queries), ("capacity", capacity)):
        positive_int(value, name)
    positive_int(shadow_capacity, "shadow_capacity", allow_zero=True)
    if seeds < 2 or observations < 32:
        raise ValueError("at least 2 seeds and 32 observations are required")
    rows = []
    for scenario in ("focused", "shifted", "diffuse"):
        for routing_error in (0.0, 0.2):
            for seed in range(seeds):
                stream, query_set = _dataset(seed, observations, queries, scenario, routing_error)
                for policy in POLICIES:
                    engine = make_engine(policy, capacity, shadow_capacity)
                    for i, record in enumerate(stream):
                        if policy == "A3_context" and scenario == "shifted" and i == observations // 2:
                            # Known task signal, maximizing V=-lambda_target+sum_other lambda.
                            engine.apply_gradient([1, -1, 1, 1], learning_rate=0.9)
                        engine.observe(record)
                    hits = 0
                    shadow_hits = 0
                    resonance_events = 0
                    for expected_id, vector, routing in query_set:
                        result = engine.query(vector, routing, entropy=0.70, limit=1)
                        if result["hits"] and result["hits"][0]["id"] == expected_id:
                            hits += 1
                            shadow_hits += result["hits"][0]["source"] == "shadow"
                        resonance_events += result["eureka_proxy"]
                    metrics = engine.stats()
                    rows.append(dict(
                        scenario=scenario, routing_error=routing_error, seed=seed, policy=policy,
                        recall_at_1=hits/queries, shadow_recall_at_1=shadow_hits/queries,
                        cross_resonance_rate=resonance_events/queries,
                        admission_rate=metrics["counters"]["gate_accepted"]/observations,
                        active=metrics["active"], shadows=metrics["shadows"],
                        payload_bytes=metrics["retained_payload_bytes"],
                        active_by_domain=metrics["active_by_domain"], lambdas=metrics["lambdas"]))
    summaries = []
    for scenario in ("focused", "shifted", "diffuse"):
        for routing_error in (0.0, 0.2):
            selected = [r for r in rows if r["scenario"] == scenario and r["routing_error"] == routing_error]
            baseline = {r["seed"]: r["recall_at_1"] for r in selected if r["policy"] == "scalar_mean"}
            for policy in POLICIES:
                data = [r for r in selected if r["policy"] == policy]
                recall = [r["recall_at_1"] for r in data]
                differences = [r["recall_at_1"] - baseline[r["seed"]] for r in data]
                mean_diff = statistics.mean(differences)
                halfwidth = 1.96 * statistics.stdev(differences) / math.sqrt(seeds)
                summaries.append(dict(
                    scenario=scenario, routing_error=routing_error, policy=policy,
                    recall_mean=statistics.mean(recall), recall_sd=statistics.stdev(recall),
                    delta_vs_scalar_mean=mean_diff,
                    paired_normal_95_interval=[mean_diff-halfwidth, mean_diff+halfwidth],
                    payload_bytes_mean=statistics.mean(r["payload_bytes"] for r in data),
                    active_mean=statistics.mean(r["active"] for r in data),
                    shadows_mean=statistics.mean(r["shadows"] for r in data),
                    admission_rate_mean=statistics.mean(r["admission_rate"] for r in data)))
    return dict(
        schema_version=1, python=platform.python_version(),
        settings=dict(seeds=seeds, observations=observations, queries=queries,
                      dimension=12, active_capacity=capacity, shadow_capacity=shadow_capacity),
        scope="synthetic episodic retrieval only; exact vectors, externally supplied scores and routing",
        fairness="identical stream and queries per seed; same total slot ceiling except no-shadow ablation",
        limitations=["equal slot ceilings, not equal realized storage bytes or admissions",
                     "quota baseline uses active+shadow budget as active FIFO slots; payload bytes reported per policy",
                     "mean lambda is matched for scalar vs A1, not across all policies",
                     "A3 receives external task context, not learned intrinsic motivation",
                     "normal intervals are descriptive seed variability, not population-valid confidence guarantees",
                     "no training, language task, creativity, consciousness or biological test"],
        summaries=summaries, rows=rows)


def counterexamples():
    config = VALConfig(("focus", "peripheral"), (0.05, 0.95), beta_base=0)
    vectorial = VALMemory(config)
    scalar = VALMemory(VALConfig.from_dict({**asdict(config), "lambdas": [0.5, 0.5]}))
    for i in range(2):
        obs = Observation(f"p{i}", "peripheral fact", (1.0, 0.0), (0.0, 1.0), 0.6)
        vectorial.observe(obs)
        scalar.observe(obs)
    density_val = vectorial.graph()["density_by_domain"]
    density_scalar = scalar.graph()["density_by_domain"]
    weighted_val = sum(r/l for r, l in zip(density_val, vectorial.lambdas))
    weighted_scalar = sum(r/l for r, l in zip(density_scalar, scalar.lambdas))
    density_engine = VALMemory(VALConfig(("only",), (0.0,), edge_min=0.9))
    for i in range(2):
        density_engine.observe(Observation(str(i), "same direction", (1, 0), (1,), 0.6))
    before = density_engine.graph()["density_by_domain"][0]
    density_engine.observe(Observation("2", "new direction", (0, 1), (1,), 0.6))
    after = density_engine.graph()["density_by_domain"][0]
    vectorial.raw_baselines = [0.4, 0.4]
    stationary_urgency = [vectorial.urgency(0.4, k) for k in range(2)]
    lam, dmax, lo, hi, shadow_global = 0.05, 0.9, 0.1, 0.9, 0.12
    theta = lo + (hi-lo)*lam
    amp = 1+(1-lam)*dmax
    shadow_probability = max(0, theta/amp - shadow_global*lam/amp)
    return dict(
        strict_superiority=dict(lambdas=[0.05, 0.95], scalar_lambda=0.5,
                                inputs="two collinear peripheral-domain episodes, h=0.6",
                                vector_active=len(vectorial.active), scalar_active=len(scalar.active),
                                vector_weighted_density=weighted_val, scalar_weighted_density=weighted_scalar,
                                conclusion="weighted density can be LOWER under vector inhibition"),
        density_monotonicity=dict(before=before, after=after,
                                  conclusion="adding an isolated node reduces normalized edge density"),
        stationary_urgency=dict(values=stationary_urgency,
                                conclusion="at calibrated mean, urgency is 0.5 for both lambdas"),
        uniform_score_shadow_ratio=dict(assumption="independent raw h uniform on [0,1], unbounded retention",
                                        active_probability=1-theta, shadow_probability=shadow_probability,
                                        shadow_to_active=shadow_probability/(1-theta),
                                        conclusion="shadow/active >10 does not follow from low lambda"),
        bounded_proxy=dict(assumptions="K domains, densities in [0,1], lambda regularizer epsilon>0",
                           upper_bound="sum rho_k/max(lambda_k,epsilon) <= K/epsilon",
                           conclusion="this regularized proxy cannot diverge indefinitely"))

