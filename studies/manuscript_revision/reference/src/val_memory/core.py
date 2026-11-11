"""VAL as a domain-selective, bounded external-memory controller.

The manuscript supplies a hypothesis, not a trained model. Engineering closures
and deliberate corrections are listed in docs/FORMALISM.md.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from itertools import combinations
import json
import math

from .maths import (cosine, finite, normalized_vector, positive_int,
                    probabilities, relational_entropy, sigmoid, unit_interval)


@dataclass(frozen=True)
class VALConfig:
    domains: tuple[str, ...]
    lambdas: tuple[float, ...]
    theta_min: float = 0.10
    theta_max: float = 0.90
    delta_max: float = 0.90
    shadow_global: float = 0.12
    shadow_policy: str = "paper"
    baseline_prior: float = 0.45
    baseline_rate: float = 0.05
    urgency_gain: float = 6.0
    alpha_base: float = 1.0
    beta_base: float = 0.02
    couple_rates: bool = False
    active_capacity: int = 64
    shadow_capacity: int = 64
    membership_min: float = 0.30
    edge_min: float = 0.75
    max_degree: int = 6
    resonance_threshold: float = 0.35

    def __post_init__(self) -> None:
        domains = tuple(self.domains)
        if (not domains or any(not isinstance(x, str) or not x.strip() for x in domains)
                or len(set(domains)) != len(domains)):
            raise ValueError("domains must be unique nonempty strings")
        values = tuple(unit_interval(x, "lambda") for x in self.lambdas)
        if len(values) != len(domains):
            raise ValueError("one lambda is required per domain")
        object.__setattr__(self, "domains", domains)
        object.__setattr__(self, "lambdas", values)
        for name in ("theta_min", "theta_max", "shadow_global", "baseline_prior",
                     "baseline_rate", "membership_min", "edge_min", "resonance_threshold"):
            object.__setattr__(self, name, unit_interval(getattr(self, name), name))
        if self.theta_min >= self.theta_max or self.baseline_rate == 0:
            raise ValueError("theta_min < theta_max and baseline_rate > 0 are required")
        for name in ("delta_max", "urgency_gain", "alpha_base", "beta_base"):
            value = finite(getattr(self, name), name)
            if value < 0 or value > 1e6:
                raise ValueError(f"{name} must be in [0, 1e6]")
            object.__setattr__(self, name, value)
        for name in ("active_capacity", "shadow_capacity", "max_degree"):
            positive_int(getattr(self, name), name, allow_zero=True)
        if self.shadow_policy not in {"paper", "raw_interval"}:
            raise ValueError("shadow_policy must be paper or raw_interval")
        if not isinstance(self.couple_rates, bool):
            raise ValueError("couple_rates must be boolean")

    @classmethod
    def from_dict(cls, data: dict) -> "VALConfig":
        return cls(**data)


@dataclass(frozen=True)
class Observation:
    id: str
    text: str
    vector: tuple[float, ...]
    routing: tuple[float, ...]
    entropy: float | None = None


@dataclass(frozen=True)
class Episode:
    id: str
    text: str
    vector: tuple[float, ...]
    primary: int
    domains: tuple[int, ...]
    raw_entropy: float
    effective_entropy: float
    sequence: int


class VALMemory:
    """Single-threaded state. SQLite CAS storage handles competing writers.

    Inputs supply fixed-space embeddings and domain routing. An optional entropy
    input separates relational scoring from routing; fallback uses routing H_R.
    Retention is FIFO within each pool. The mass state is distinct from retention.
    """

    SCHEMA_VERSION = 1

    def __init__(self, config: VALConfig):
        self.config = config
        self.lambdas = list(config.lambdas)
        self.raw_baselines = [config.baseline_prior] * len(config.domains)
        self.baseline_counts = [0] * len(config.domains)
        self.dimension: int | None = None
        self.mass: list[list[float]] = []
        self.active: list[Episode] = []
        self.shadows: list[Episode] = []
        self.sequence = 0
        self.counters = dict(observed=0, gate_accepted=0, gate_rejected=0,
                             discarded=0, active_evicted=0, shadow_evicted=0)

    def threshold(self, domain: int) -> float:
        value = self.lambdas[domain]
        return self.config.theta_min + (self.config.theta_max - self.config.theta_min) * value

    def amplification(self, domain: int) -> float:
        return 1 + (1 - self.lambdas[domain]) * self.config.delta_max

    def urgency(self, entropy: float, domain: int) -> float:
        h = unit_interval(entropy, "entropy")
        # Rescale historical raw scores with CURRENT lambda: no scale-jump novelty.
        delta = (h - self.raw_baselines[domain]) * self.amplification(domain)
        return sigmoid(self.config.urgency_gain * delta)

    def rates(self, domain: int) -> tuple[float, float]:
        if not self.config.couple_rates:
            return self.config.alpha_base, self.config.beta_base
        value = self.lambdas[domain]
        return (self.config.alpha_base * (2 - value),
                self.config.beta_base * (0.1 + 0.9 * value))

    def _inputs(self, vector, routing, entropy):
        vector = normalized_vector(vector)
        routing = probabilities(routing)
        if len(routing) != len(self.config.domains):
            raise ValueError("routing length differs from domain count")
        if self.dimension is not None and len(vector) != self.dimension:
            raise ValueError("embedding dimension differs from stored state")
        h = relational_entropy(routing) if entropy is None else unit_interval(entropy, "entropy")
        domain = max(range(len(routing)), key=routing.__getitem__)
        return vector, routing, h, domain

    def observe(self, observation: Observation, *, dt: float = 1.0) -> dict:
        if not isinstance(observation.id, str) or not observation.id.strip():
            raise ValueError("observation id must be nonempty")
        if not isinstance(observation.text, str):
            raise ValueError("text must be a string")
        if any(x.id == observation.id for x in self.active + self.shadows):
            raise ValueError("duplicate id among retained episodes")
        vector, routing, h, domain = self._inputs(
            observation.vector, observation.routing, observation.entropy)
        dt = finite(dt, "dt")
        if not 0 <= dt <= 1e6:
            raise ValueError("dt must be in [0, 1e6]")
        threshold = self.threshold(domain)
        effective_h = h * self.amplification(domain)
        gate = h > threshold  # Literal strict Eq. VAL-1; no endpoint override.
        omega = self.urgency(h, domain)  # Uses history BEFORE this observation.
        membership = tuple(i for i, p in enumerate(routing)
                           if i == domain or p >= self.config.membership_min)
        if self.dimension is None:
            self.dimension = len(vector)
            self.mass = [[0.0] * self.dimension for _ in self.config.domains]
        new_mass = []
        for k, old_mass in enumerate(self.mass):
            alpha, beta = self.rates(k)
            decay = math.exp(-beta * dt)
            impulse = alpha * h if gate and k == domain else 0.0
            values = [decay * old + impulse * x for old, x in zip(old_mass, vector)]
            if any(not math.isfinite(x) for x in values):
                raise ValueError("memory mass overflow")
            new_mass.append(values)
        # No mutation before numerical validation above (except zero initialization).
        self.mass = new_mass
        self.sequence += 1
        self.counters["observed"] += 1
        self.counters["gate_accepted" if gate else "gate_rejected"] += 1
        episode = Episode(observation.id, observation.text, vector, domain, membership,
                          h, effective_h, self.sequence)
        low = self.config.shadow_global * self.lambdas[domain]
        if gate and self.config.active_capacity:
            destination = "active"
            self.active.append(episode)
            if len(self.active) > self.config.active_capacity:
                self.active.pop(0)
                self.counters["active_evicted"] += 1
        else:
            shadow_ok = (low < effective_h < threshold if self.config.shadow_policy == "paper"
                         else low < h <= threshold)
            if not gate and shadow_ok and self.config.shadow_capacity:
                destination = "shadow"
                self.shadows.append(episode)
                if len(self.shadows) > self.config.shadow_capacity:
                    self.shadows.pop(0)
                    self.counters["shadow_evicted"] += 1
            else:
                destination = "discarded"
                self.counters["discarded"] += 1
        rate = self.config.baseline_rate
        self.raw_baselines[domain] += rate * (h - self.raw_baselines[domain])
        self.baseline_counts[domain] += 1
        return dict(id=episode.id, domain=self.config.domains[domain], gate=gate,
                    threshold=threshold, raw_entropy=h, effective_entropy=effective_h,
                    urgency=omega, destination=destination)

    def apply_gradient(self, utility_gradient, *, cost_gradient=None, learning_rate=0.1) -> list[float]:
        """Projected ASCENT on V-K, equivalent to descent on L=-V+K.

        Gradients are supplied by the host; the controller does not infer latent
        motivation. Hard gate gradients are not estimated by this method.
        """
        utility = tuple(finite(x, "utility gradient") for x in utility_gradient)
        cost = ((0.0,) * len(self.lambdas) if cost_gradient is None else
                tuple(finite(x, "cost gradient") for x in cost_gradient))
        eta = finite(learning_rate, "learning_rate")
        if not 0 <= eta <= 1e6 or len(utility) != len(self.lambdas) or len(cost) != len(utility):
            raise ValueError("invalid learning rate or gradient length")
        proposed = [finite(x + eta * (u - c), "updated lambda")
                    for x, u, c in zip(self.lambdas, utility, cost)]
        self.lambdas = [max(0.0, min(1.0, x)) for x in proposed]
        return list(self.lambdas)

    def query(self, vector, routing, *, entropy=None, limit=5, include_shadows=True) -> dict:
        positive_int(limit, "limit")
        vector, _, h, _ = self._inputs(vector, routing, entropy)
        hits = []
        resonant_domains = set()
        for pool_name, pool in (("active", self.active), ("shadow", self.shadows)):
            if pool_name == "shadow" and not include_shadows:
                continue
            for episode in pool:
                similarity = cosine(vector, episode.vector)
                resonance = similarity * self.urgency(h, episode.primary)
                if similarity <= 0 or (pool_name == "shadow" and
                                       resonance <= self.config.resonance_threshold):
                    continue
                if pool_name == "shadow":
                    resonant_domains.add(episode.primary)
                hits.append(dict(id=episode.id, text=episode.text, source=pool_name,
                                 cosine=similarity, resonance=resonance,
                                 domain=self.config.domains[episode.primary]))
        hits.sort(key=lambda x: (-x["cosine"], x["id"]))
        pairs = [[self.config.domains[i], self.config.domains[j]]
                 for i, j in combinations(sorted(resonant_domains), 2)]
        return dict(hits=hits[:limit], cross_resonance_pairs=pairs,
                    eureka_proxy=bool(pairs),
                    interpretation="joint shadow retrieval condition; no insight-quality claim")

    def graph(self) -> dict:
        edges = []
        degrees = [0] * len(self.active)
        candidates = []
        for i, j in combinations(range(len(self.active)), 2):
            weight = cosine(self.active[i].vector, self.active[j].vector)
            if weight >= self.config.edge_min:
                candidates.append((weight, i, j))
        for weight, i, j in sorted(candidates, key=lambda x: (-x[0], x[1], x[2])):
            if degrees[i] < self.config.max_degree and degrees[j] < self.config.max_degree:
                degrees[i] += 1
                degrees[j] += 1
                edges.append(dict(left=self.active[i].id, right=self.active[j].id,
                                  weight=weight, cross_domain=(self.active[i].primary !=
                                                              self.active[j].primary)))
        densities = []
        for k in range(len(self.config.domains)):
            ids = {x.id for x in self.active if k in x.domains}
            count = sum(e["left"] in ids and e["right"] in ids for e in edges)
            possible = len(ids) * (len(ids) - 1) // 2
            densities.append(count / possible if possible else 0.0)
        return dict(edges=edges, density_by_domain=densities,
                    bridge_nodes=[x.id for x in self.active if len(x.domains) > 1])

    def stats(self) -> dict:
        graph = self.graph()
        payload = [asdict(x) for x in self.active + self.shadows]
        return dict(lambdas=list(self.lambdas), active=len(self.active), shadows=len(self.shadows),
                    active_by_domain=[sum(x.primary == k for x in self.active)
                                      for k in range(len(self.config.domains))],
                    shadow_by_domain=[sum(x.primary == k for x in self.shadows)
                                      for k in range(len(self.config.domains))],
                    counters=dict(self.counters), baseline_counts=list(self.baseline_counts),
                    raw_baselines=list(self.raw_baselines), density_by_domain=graph["density_by_domain"],
                    cross_domain_edges=sum(x["cross_domain"] for x in graph["edges"]),
                    mass_norms=[math.sqrt(math.fsum(x*x for x in row)) for row in self.mass],
                    retained_payload_bytes=len(json.dumps(payload, ensure_ascii=False).encode()),
                    schema_version=self.SCHEMA_VERSION)

    def snapshot(self) -> dict:
        return dict(schema_version=self.SCHEMA_VERSION, config=asdict(self.config),
                    lambdas=list(self.lambdas), raw_baselines=list(self.raw_baselines),
                    baseline_counts=list(self.baseline_counts), dimension=self.dimension,
                    mass=[list(row) for row in self.mass], sequence=self.sequence,
                    active=[asdict(x) for x in self.active], shadows=[asdict(x) for x in self.shadows],
                    counters=dict(self.counters))

    @classmethod
    def restore(cls, state: dict) -> "VALMemory":
        if state.get("schema_version") != cls.SCHEMA_VERSION:
            raise ValueError("unsupported state schema")
        engine = cls(VALConfig.from_dict(state["config"]))
        count = len(engine.config.domains)
        engine.lambdas = [unit_interval(x, "lambda") for x in state["lambdas"]]
        engine.raw_baselines = [unit_interval(x, "baseline") for x in state["raw_baselines"]]
        engine.baseline_counts = [positive_int(x, "count", allow_zero=True)
                                  for x in state["baseline_counts"]]
        if any(len(x) != count for x in (engine.lambdas, engine.raw_baselines, engine.baseline_counts)):
            raise ValueError("state domain lengths differ")
        dimension = state["dimension"]
        if dimension is not None:
            positive_int(dimension, "dimension")
        engine.dimension = dimension
        engine.sequence = positive_int(state["sequence"], "sequence", allow_zero=True)
        engine.mass = [[finite(x, "mass") for x in row] for row in state["mass"]]
        if ((dimension is None and engine.mass) or
                (dimension is not None and (len(engine.mass) != count or
                 any(len(row) != dimension for row in engine.mass)))):
            raise ValueError("invalid memory mass shape")
        ids = set()
        for name, capacity in (("active", engine.config.active_capacity),
                               ("shadows", engine.config.shadow_capacity)):
            episodes = []
            for record in state[name]:
                episode = Episode(**record)
                if (not isinstance(episode.id, str) or not episode.id.strip() or episode.id in ids
                        or not isinstance(episode.text, str)):
                    raise ValueError("invalid or duplicate episode")
                positive_int(episode.primary, "primary", allow_zero=True)
                positive_int(episode.sequence, "episode sequence")
                if episode.primary >= count or episode.sequence > engine.sequence:
                    raise ValueError("invalid episode domain or sequence")
                memberships = tuple(episode.domains)
                if (not memberships or episode.primary not in memberships or
                        len(set(memberships)) != len(memberships)):
                    raise ValueError("invalid memberships")
                for k in memberships:
                    positive_int(k, "membership", allow_zero=True)
                    if k >= count:
                        raise ValueError("membership outside domain range")
                vector = normalized_vector(episode.vector)
                if dimension is None or len(vector) != dimension:
                    raise ValueError("invalid episode vector dimension")
                # Reject altered norms instead of silently changing saved vectors.
                if any(abs(a-b) > 1e-10 for a, b in zip(vector, episode.vector)):
                    raise ValueError("stored vector is not normalized")
                raw = unit_interval(episode.raw_entropy, "raw entropy")
                eff = finite(episode.effective_entropy, "effective entropy")
                if not 0 <= eff <= 1 + engine.config.delta_max:
                    raise ValueError("invalid effective entropy")
                episodes.append(Episode(episode.id, episode.text, tuple(episode.vector),
                                        episode.primary, memberships, raw, eff, episode.sequence))
                ids.add(episode.id)
            if len(episodes) > capacity or any(a.sequence >= b.sequence
                                              for a, b in zip(episodes, episodes[1:])):
                raise ValueError("capacity or FIFO order invalid")
            setattr(engine, name, episodes)
        if set(state["counters"]) != set(engine.counters):
            raise ValueError("invalid counters")
        engine.counters = {k: positive_int(v, k, allow_zero=True) for k, v in state["counters"].items()}
        if (engine.counters["observed"] != engine.sequence or
                sum(engine.baseline_counts) != engine.sequence or
                engine.counters["gate_accepted"] + engine.counters["gate_rejected"] != engine.sequence):
            raise ValueError("inconsistent counters")
        return engine

