from copy import deepcopy
import json
import math
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import unittest

from val_memory import (Observation, VALConfig, VALMemory, SQLiteStore,
                        RevisionConflict, allocate_ranks, offline_plan, relational_entropy,
                        rem_temperature)
from val_memory.benchmark import counterexamples, run_benchmark
from val_memory.maths import normalized_vector


def config(**kwargs):
    return VALConfig(("a", "b"), (0.05, 0.95), **kwargs)


def episode(identifier="x", *, h=0.6, routing=(1, 0), vector=(1, 0)):
    return Observation(identifier, "synthetic fact", vector, routing, h)


class EntropyTests(unittest.TestCase):
    def test_equivalent_to_pair_sum(self):
        rng = random.Random(7)
        for size in range(2, 11):
            weights = [rng.random() for _ in range(size)]
            p = [x/sum(weights) for x in weights]
            direct = -sum(p[i]*p[j]*math.log2(p[i]*p[j])
                          for i in range(size) for j in range(size) if i != j)
            self.assertAlmostEqual(direct, relational_entropy(weights, normalized=False))

    def test_uniform_four_is_not_one(self):
        self.assertAlmostEqual(relational_entropy([1, 1, 1, 1]), 0.75)

    def test_degenerate_distribution(self):
        self.assertEqual(relational_entropy([1, 0]), 0)
        self.assertEqual(relational_entropy([1]), 0)

    def test_invalid_probabilities(self):
        for p in ([], [0, 0], [-1, 1], [float("nan"), 1], [True, 1]):
            with self.subTest(p=p), self.assertRaises(ValueError):
                relational_entropy(p)

    def test_large_vector_normalization(self):
        vector = normalized_vector([1e308, 1e308])
        self.assertAlmostEqual(sum(x*x for x in vector), 1)

    def test_zero_vector_rejected(self):
        with self.assertRaises(ValueError):
            normalized_vector([0, 0])


class ControllerTests(unittest.TestCase):
    def test_domain_selectivity(self):
        engine = VALMemory(config())
        self.assertTrue(engine.observe(episode("a"))["gate"])
        self.assertFalse(engine.observe(episode("b", routing=(0, 1)))["gate"])

    def test_equal_lambdas_recover_scalar(self):
        engine = VALMemory(VALConfig(("a", "b"), (0.5, 0.5)))
        # Independent scalar gate, including the strict equality boundary.
        scalar_threshold = 0.10 + (0.90 - 0.10) * 0.5
        for i, h in enumerate([0, 0.2, 0.5, 0.8, 1]):
            for k in range(2):
                result = engine.observe(episode(f"{i}-{k}", h=h, routing=(1-k, k)))
                self.assertEqual(result["gate"], h > scalar_threshold)

    def test_strict_gate_at_threshold(self):
        engine = VALMemory(config())
        self.assertFalse(engine.observe(episode(h=engine.threshold(0)))["gate"])

    def test_no_unstated_endpoint_override(self):
        engine = VALMemory(VALConfig(("a", "b"), (0, 1)))
        self.assertFalse(engine.observe(episode("low", h=0))["gate"])
        self.assertTrue(engine.observe(episode("high", h=1, routing=(0, 1)))["gate"])

    def test_literal_amplification(self):
        engine = VALMemory(config())
        result = engine.observe(episode(h=0.4))
        self.assertAlmostEqual(result["effective_entropy"], 1.855*0.4)

    def test_urgency_uses_previous_baseline(self):
        engine = VALMemory(config(baseline_prior=0.4, baseline_rate=1))
        self.assertAlmostEqual(engine.observe(episode(h=0.4))["urgency"], 0.5)
        self.assertGreater(engine.observe(episode("next", h=0.6))["urgency"], 0.5)

    def test_adaptation_has_no_baseline_scale_artifact(self):
        engine = VALMemory(config(baseline_prior=0.4))
        engine.apply_gradient([1, -1], learning_rate=1)
        self.assertEqual([engine.urgency(0.4, k) for k in range(2)], [0.5, 0.5])

    def test_gradient_maximizes_value(self):
        engine = VALMemory(VALConfig(("a", "b"), (0.5, 0.5)))
        engine.apply_gradient([-1, 0.5], learning_rate=0.1)
        self.assertEqual(engine.lambdas, [0.4, 0.55])

    def test_cost_gradient_and_projection(self):
        engine = VALMemory(config())
        self.assertEqual(engine.apply_gradient([0, 10], cost_gradient=[10, 0]), [0, 1])

    def test_invalid_gradient_preserves_state(self):
        engine = VALMemory(config())
        before = engine.snapshot()
        with self.assertRaises(ValueError):
            engine.apply_gradient([1, float("nan")])
        self.assertEqual(before, engine.snapshot())

    def test_invalid_observation_preserves_state(self):
        engine = VALMemory(config())
        before = engine.snapshot()
        with self.assertRaises(ValueError):
            engine.observe(episode(h=float("nan")))
        self.assertEqual(before, engine.snapshot())

    def test_impulse_and_exact_decay(self):
        engine = VALMemory(config(alpha_base=2, beta_base=0.3))
        engine.observe(episode(h=0.5), dt=0)
        engine.observe(episode("decay", h=0, routing=(0, 1)), dt=2)
        self.assertAlmostEqual(engine.mass[0][0], math.exp(-0.6))

    def test_fifo_and_pool_bounds(self):
        engine = VALMemory(config(active_capacity=3, shadow_capacity=2))
        for i in range(20):
            engine.observe(episode(str(i), routing=(1, 0) if i % 2 else (0, 1)))
        self.assertEqual(len(engine.active), 3)
        self.assertEqual(len(engine.shadows), 2)
        self.assertEqual([e.id for e in engine.active], ["15", "17", "19"])

    def test_paper_shadow_score_gap_is_visible(self):
        paper = VALMemory(config(shadow_policy="paper"))
        raw = VALMemory(config(shadow_policy="raw_interval"))
        # h=.1 fails raw gate, but 1.855*h exceeds the same threshold .14.
        self.assertEqual(paper.observe(episode(h=0.1))["destination"], "discarded")
        self.assertEqual(raw.observe(episode(h=0.1))["destination"], "shadow")

    def test_new_configuration_defaults_to_consistent_raw_interval(self):
        engine = VALMemory(config())
        self.assertEqual(engine.config.shadow_policy, "raw_interval")
        self.assertEqual(engine.observe(episode(h=0.1))["destination"], "shadow")

    def test_raw_interval_has_no_gap_at_active_threshold(self):
        engine = VALMemory(config())
        threshold = engine.threshold(0)
        self.assertEqual(engine.observe(episode('below', h=math.nextafter(threshold, 0)))["destination"], "shadow")
        self.assertEqual(engine.observe(episode('equal', h=threshold))["destination"], "shadow")
        self.assertEqual(engine.observe(episode('above', h=math.nextafter(threshold, 1)))["destination"], "active")
        low = engine.config.shadow_global*engine.lambdas[0]
        self.assertEqual(engine.observe(episode('lower', h=low))["destination"], "discarded")

    def test_query_is_read_only(self):
        engine = VALMemory(config())
        engine.observe(episode())
        before = engine.snapshot()
        self.assertEqual(engine.query((1, 0), (1, 0), entropy=0.7)["hits"][0]["id"], "x")
        self.assertEqual(before, engine.snapshot())

    def test_shadow_resonance_requires_evidence(self):
        engine = VALMemory(config())
        engine.observe(episode(h=0.05))
        self.assertEqual(engine.query((1, 0), (1, 0), entropy=0)["hits"], [])
        result = engine.query((1, 0), (1, 0), entropy=1)
        self.assertEqual(result["hits"][0]["source"], "shadow")
        self.assertFalse(result["eureka_proxy"])

    def test_joint_resonance_counts_a_joint_event(self):
        engine = VALMemory(config())
        engine.observe(episode("a", h=0.05))
        engine.observe(episode("b", h=0.3, routing=(0, 1)))
        self.assertEqual(engine.query((1, 0), (0.5, 0.5), entropy=1)["cross_resonance_pairs"], [["a", "b"]])

    def test_embedding_dimension_locked(self):
        engine = VALMemory(config())
        engine.observe(episode())
        before = engine.snapshot()
        with self.assertRaises(ValueError):
            engine.observe(episode("bad", vector=(1, 2, 3)))
        self.assertEqual(before, engine.snapshot())

    def test_retained_duplicate_id_rejected(self):
        engine = VALMemory(config())
        engine.observe(episode())
        with self.assertRaises(ValueError):
            engine.observe(episode())

    def test_memberships_and_graph_degree_limit(self):
        engine = VALMemory(config(max_degree=1))
        for i in range(5):
            engine.observe(episode(str(i), routing=(0.6, 0.4)))
        graph = engine.graph()
        self.assertEqual(len(graph["bridge_nodes"]), 5)
        counts = {}
        for edge in graph["edges"]:
            for key in ("left", "right"):
                counts[edge[key]] = counts.get(edge[key], 0)+1
        self.assertTrue(all(count <= 1 for count in counts.values()))

    def test_coupled_rates_optional(self):
        engine = VALMemory(config(couple_rates=True))
        self.assertGreater(engine.rates(0)[0], engine.rates(1)[0])
        self.assertLess(engine.rates(0)[1], engine.rates(1)[1])

    def test_zero_capacities_keep_no_episodes(self):
        engine = VALMemory(config(active_capacity=0, shadow_capacity=0))
        engine.observe(episode())
        self.assertEqual((engine.active, engine.shadows), ([], []))


class PersistenceAndPlanTests(unittest.TestCase):
    def test_saved_legacy_policy_remains_legacy_after_restore(self):
        legacy = VALMemory(config(shadow_policy="paper"))
        state = json.loads(json.dumps(legacy.snapshot()))
        restored = VALMemory.restore(state)
        self.assertEqual(restored.config.shadow_policy, "paper")
        self.assertEqual(restored.observe(episode(h=0.1))["destination"], "discarded")

    def test_snapshot_roundtrip_and_continuation(self):
        engine = VALMemory(config())
        engine.observe(episode())
        restored = VALMemory.restore(json.loads(json.dumps(engine.snapshot())))
        self.assertEqual(engine.snapshot(), restored.snapshot())
        for i in range(8):
            self.assertEqual(engine.observe(episode(str(i), h=0.2)),
                             restored.observe(episode(str(i), h=0.2)))
        self.assertEqual(engine.snapshot(), restored.snapshot())

    def test_corrupt_snapshots_rejected(self):
        engine = VALMemory(config())
        engine.observe(episode())
        for modify in (lambda s: s.update(schema_version=77),
                       lambda s: s.update(lambdas=[0.5]),
                       lambda s: s.update(mass=[[float("nan"), 0], [0, 0]]),
                       lambda s: s["active"][0].update(vector=[2, 0]),
                       lambda s: s["active"][0].update(domains=[7]),
                       lambda s: s.update(sequence=999)):
            state = deepcopy(engine.snapshot())
            modify(state)
            with self.subTest(state=state), self.assertRaises(ValueError):
                VALMemory.restore(state)

    def test_sqlite_conflict_does_not_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            store = SQLiteStore(Path(directory)/"state.sqlite")
            engine = VALMemory(config())
            self.assertEqual(store.save(engine, expected_revision=0), 1)
            left, revision = store.load()
            right, stale_revision = store.load()
            left.observe(episode())
            self.assertEqual(store.save(left, expected_revision=revision), 2)
            with self.assertRaises(RevisionConflict):
                store.save(right, expected_revision=stale_revision)
            latest, _ = store.load()
            self.assertEqual(latest.sequence, 1)

    def test_missing_database_is_not_created_by_read(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"missing.sqlite"
            with self.assertRaises(FileNotFoundError):
                SQLiteStore(path).load()
            self.assertFalse(path.exists())

    def test_budget_and_rank_zero_boundary(self):
        self.assertEqual(allocate_ranks([0, 0], total_budget=0), [0, 0])
        ranks = allocate_ranks([0, 0.05, 1], total_budget=13, rank_cap=7)
        self.assertEqual(sum(ranks), 13)
        self.assertTrue(all(0 <= x <= 7 for x in ranks))

    def test_rank_allocations_deterministic_and_bounded(self):
        for budget in range(100):
            ranks = allocate_ranks([0, 0.1, 0.5, 1], total_budget=budget, rank_cap=32)
            self.assertLessEqual(sum(ranks), budget)
            self.assertTrue(all(isinstance(x, int) and 0 <= x <= 32 for x in ranks))
            self.assertGreaterEqual(ranks[0], ranks[-1])

    def test_temperature_floor(self):
        self.assertEqual(rem_temperature(0, 0), 0.05)
        self.assertAlmostEqual(rem_temperature(0.1, 0.3), 0.16)

    def test_plan_is_read_only_and_training_not_run(self):
        engine = VALMemory(config())
        engine.observe(episode(h=0.05))
        before = engine.snapshot()
        plan = offline_plan(engine)
        self.assertEqual(plan["phase_II"]["status"], "not_run")
        self.assertEqual(engine.snapshot(), before)


class AuditAndCLITests(unittest.TestCase):
    def test_counterexamples(self):
        result = counterexamples()
        case = result["strict_superiority"]
        self.assertLess(case["vector_weighted_density"], case["scalar_weighted_density"])
        self.assertLess(result["density_monotonicity"]["after"], result["density_monotonicity"]["before"])
        self.assertLess(result["uniform_score_shadow_ratio"]["shadow_to_active"], 0.1)

    def test_benchmark_repeatable_and_has_unfavorable_cases(self):
        args = dict(seeds=2, observations=40, queries=8, capacity=8, shadow_capacity=8)
        left = run_benchmark(**args)
        right = run_benchmark(**args)
        self.assertEqual(left, right)
        self.assertEqual(len(left["rows"]), 84)
        self.assertTrue(any(x["policy"] == "A1_fixed" and x["delta_vs_scalar_mean"] < 0
                            for x in left["summaries"]))

    def run_cli(self, *args):
        return subprocess.run([sys.executable, "-m", "val_memory", *args], capture_output=True, text=True)

    def test_cli_demo_query_plan_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)/"demo"
            demo = self.run_cli("demo", "--output", str(output))
            self.assertEqual(demo.returncode, 0, demo.stderr)
            query = self.run_cli("query", "--state", str(output/"memory.sqlite"),
                                 "--vector", "[1,0,0,0]", "--routing", "[1,0,0,0]", "--entropy", "0.8")
            self.assertEqual(query.returncode, 0, query.stderr)
            self.assertTrue(json.loads(query.stdout)["hits"])
            self.assertEqual(self.run_cli("inspect", "--state", str(output/"memory.sqlite")).returncode, 0)
            self.assertEqual(self.run_cli("plan", "--state", str(output/"memory.sqlite"),
                                         "--output", str(output/"new_plan.json")).returncode, 0)
            self.assertEqual(self.run_cli("demo", "--output", str(output)).returncode, 2)

    def test_cli_ingest_roundtrip_and_bad_input_is_atomic(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            cfg = path/"config.json"
            cfg.write_text(json.dumps({"domains":["a","b"], "lambdas":[0.05,0.95]}))
            source = path/"events.jsonl"
            from dataclasses import asdict
            source.write_text(json.dumps(asdict(episode()))+"\n")
            state = path/"new.sqlite"
            result = self.run_cli("ingest", "--config", str(cfg), "--input", str(source), "--state", str(state))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(SQLiteStore(state).load()[0].sequence, 1)
            source.write_text(json.dumps(asdict(episode()))+"\n{\"bad\": 1}\n")
            bad_state = path/"bad.sqlite"
            result = self.run_cli("ingest", "--config", str(cfg), "--input", str(source), "--state", str(bad_state))
            self.assertEqual(result.returncode, 2)
            self.assertFalse(bad_state.exists())

    def test_invalid_configs(self):
        for kwargs in ({"lambdas":(0.5,)}, {"lambdas":(-0.1,0.5)}, {"active_capacity":True},
                       {"shadow_capacity":-1}, {"theta_min":0.9, "theta_max":0.1},
                       {"delta_max":float("inf")}, {"domains":("a","a")}, {"shadow_policy":"unknown"}):
            values = dict(domains=("a","b"), lambdas=(0.1,0.9))
            values.update(kwargs)
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                VALConfig(**values)


if __name__ == "__main__":
    unittest.main()
