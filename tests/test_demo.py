import tempfile
import unittest
from pathlib import Path
from matchpulse.storage import Store
from matchpulse.engine import Engine
from matchpulse.demo import packet,deliveries,later_deal,step,MATCH_ID


class Walkthrough(unittest.TestCase):
    def test_full_path_and_restart(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/"state.db"
            s=Store(path);e=Engine(s);e.seed(packet())
            seen=[]
            for ev in deliveries():
                result=e.ingest(ev);seen.append(result["snapshot"])
            self.assertIn([1,0],[r["score"] for r in seen])
            self.assertEqual(e.match(MATCH_ID)["score"],[1,0])
            self.assertEqual(len(e.ticker()),23)
            self.assertIsNone(next(p for p in e.match(MATCH_ID)["players"] if p["id"]=="demo-p24")["rating"])
            self.assertGreater(next(p for p in e.match(MATCH_ID)["players"] if p["id"]=="demo-p1")["contribution"],0)
            e.deal(later_deal())
            self.assertEqual(e.history("demo-p9")["transactions"][0]["guaranteed"],19e6)
            before=e.snapshot();s.close()
            s=Store(path);e=Engine(s);self.assertEqual(before,e.snapshot());s.close()

    def test_steps_are_idempotent_after_finish(self):
        s=Store(":memory:");e=Engine(s);e.seed(packet())
        step(e,True);a=step(e);b=step(e)
        self.assertTrue(a["done"]);self.assertEqual(a["snapshot"],b["snapshot"])
        s.close()
