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

class CompletedCorrections(unittest.TestCase):
    def test_revised_completion_retracts_estimates(self):
        s=Store(':memory:');e=Engine(s);e.seed(packet())
        for ev in deliveries():e.ingest(ev)
        end=deliveries()[-1]
        revised={**end,'revision':2,'received_at':'2024-06-09T00:00:00Z','payload':{'interrupted':True}}
        e.ingest(revised)
        self.assertTrue(all(x['status']=='unavailable' for x in e.ticker()))
        self.assertIsNone(e.ticker()[0]['median'])
        self.assertEqual(e.match(MATCH_ID,version=37)['status'],'finished')
        self.assertIn('ticker-retraction',[r['kind'] for r in s.stream()]);s.close()

    def test_corrected_completed_match_does_not_compound_prior(self):
        s=Store(':memory:');e=Engine(s);e.seed(packet())
        for ev in deliveries():e.ingest(ev)
        prior={x['person_id']:x for x in e.ticker()}
        goal=next(x for x in deliveries() if x['event_id']=='goal-final' and x['revision']==2)
        revised={**goal,'revision':3,'received_at':'2024-06-09T00:00:00Z','payload':{**goal['payload'],'reason':'metadata-only correction'}}
        e.ingest(revised)
        for x in e.ticker():
            self.assertEqual(x['median'],prior[x['person_id']]['median']);self.assertEqual(x['delta'],0)
        s.close()
