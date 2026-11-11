"""Resource-bounded offline plans. No adapter training or generation is implied."""

from __future__ import annotations

from itertools import combinations
import math

from .core import VALMemory
from .maths import cosine, finite, positive_int, unit_interval


def allocate_ranks(lambdas, *, base_rank=4, lambda_floor=0.05, rank_cap=32, total_budget=64):
    positive_int(base_rank, "base_rank")
    positive_int(rank_cap, "rank_cap", allow_zero=True)
    positive_int(total_budget, "total_budget", allow_zero=True)
    floor = unit_interval(lambda_floor, "lambda_floor")
    if floor == 0:
        raise ValueError("lambda_floor must be positive")
    values = tuple(unit_interval(x, "lambda") for x in lambdas)
    if not values:
        raise ValueError("lambdas must be nonempty")
    targets = [min(rank_cap, math.ceil(base_rank / max(floor, x))) for x in values]
    if sum(targets) <= total_budget:
        return targets
    quotas = [total_budget * x / sum(targets) for x in targets]
    ranks = [math.floor(x) for x in quotas]
    for k in sorted(range(len(ranks)), key=lambda k: (-(quotas[k] - ranks[k]), k))[:total_budget-sum(ranks)]:
        ranks[k] += 1
    return ranks


def rem_temperature(lambda_k, lambda_j, *, base=0.8, minimum=0.05):
    base = finite(base, "base temperature")
    minimum = finite(minimum, "minimum temperature")
    if base < 0 or minimum < 0:
        raise ValueError("temperatures must be nonnegative")
    return max(minimum, base * (unit_interval(lambda_k) + unit_interval(lambda_j)) / 2)


def offline_plan(engine: VALMemory, *, cluster_min=0.85, total_rank_budget=64, rank_cap=32):
    cluster_min = unit_interval(cluster_min, "cluster_min")
    clusters = []
    for k, domain in enumerate(engine.config.domains):
        groups = []
        for episode in sorted((x for x in engine.shadows if x.primary == k),
                              key=lambda x: (-x.effective_entropy, x.id)):
            group = next((g for g in groups if cosine(g[0].vector, episode.vector) >= cluster_min), None)
            if group is None:
                groups.append([episode])
            else:
                group.append(episode)
        clusters.extend(dict(domain=domain, representative=g[0].id, ids=[x.id for x in g]) for g in groups)
    ranks = allocate_ranks(engine.lambdas, total_budget=total_rank_budget, rank_cap=rank_cap)
    pairs = [dict(domains=[engine.config.domains[i], engine.config.domains[j]],
                  temperature=rem_temperature(engine.lambdas[i], engine.lambdas[j]))
             for i, j in combinations(range(len(engine.lambdas)), 2)]
    return dict(
        phase_I=dict(status="planned_only", shadow_clusters=clusters),
        phase_II=dict(status="not_run", rank_plan=ranks, total_rank=sum(ranks),
                      note="rank_cap must also respect actual layer dimensions; no LoRA weights trained"),
        phase_III=dict(status="planned_only", pairs=pairs, note="no generated hypotheses or verified insights"),
        phase_IV=dict(status="applied_during_ingestion", shadow_policy=engine.config.shadow_policy),
    )

