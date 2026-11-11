"""Focused checks for the revised shadow rule and context-matched baseline."""
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"reference/src"))
from val_memory import Observation,VALConfig,VALMemory
from revision_benchmark import make_engine,switch_context,dataset


class RevisionChecks(unittest.TestCase):
    def test_shadow_band_has_one_score_scale(self):
        for h in [0,.005,.01,.05,.10,.14,.15,.4,.9,1]:
            engine=VALMemory(VALConfig(("a",),(0.05,),shadow_policy="raw_interval"))
            result=engine.observe(Observation("x","example",(1,0),(1,),h))
            theta=.1+.8*.05
            expected="active" if h>theta else "shadow" if .12*.05<h<=theta else "discarded"
            self.assertEqual(result["destination"],expected)

    def test_amplification_ablation_preserves_admission_and_archival(self):
        stream,_=dataset(1,64,8,"focused",0)
        left=make_engine("selective_consistent")
        right=make_engine("selective_consistent_no_amp")
        for item in stream:
            a=left.observe(item)
            b=right.observe(item)
            self.assertEqual((a["gate"],a["destination"]),(b["gate"],b["destination"]))
        self.assertEqual([e.id for e in left.active+left.shadows],[e.id for e in right.active+right.shadows])

    def test_context_quotas_keep_budget_and_remove_excess(self):
        stream,_=dataset(1,320,8,"focused",0)
        engine=make_engine("quota_context")
        for item in stream:
            engine.observe(item)
        self.assertEqual(engine.quotas,[96,13,10,9])
        switch_context(engine,"quota_context")
        self.assertEqual(engine.quotas,[13,96,10,9])
        for k,quota in enumerate(engine.quotas):
            self.assertLessEqual(sum(e.primary==k for e in engine.active),quota)
        self.assertLessEqual(len(engine.active),128)

    def test_context_is_not_applied_to_fixed_controls(self):
        for policy in ["selective_consistent","quota_fixed"]:
            engine=make_engine(policy)
            before=engine.snapshot()
            switch_context(engine,policy)
            self.assertEqual(before,engine.snapshot())

    def test_every_policy_uses_the_same_episode_ceiling(self):
        from revision_benchmark import POLICIES
        for policy in POLICIES:
            engine=make_engine(policy)
            self.assertEqual(engine.config.active_capacity+engine.config.shadow_capacity,128)

    def test_error_levels_change_only_routing(self):
        left,q_left=dataset(7,64,12,'focused',0)
        right,q_right=dataset(7,64,12,'focused',.2)
        self.assertEqual(q_left,q_right)
        for a,b in zip(left,right):
            self.assertEqual((a.id,a.text,a.vector,a.entropy),(b.id,b.text,b.vector,b.entropy))
        self.assertTrue(any(a.routing!=b.routing for a,b in zip(left,right)))


if __name__=="__main__":
    unittest.main()
