import json
from pathlib import Path
import tempfile
import unittest
from matchpulse.engine import Engine
from matchpulse.storage import Store
from test_storage import store
from test_contracts import event
from test_ratings import FIXTURE,lineups
from matchpulse.contracts import canonical


class Publication(unittest.TestCase):
    def engine(self):
        s=store()
        s.db.execute("UPDATE fixtures SET body=? WHERE id='m1'",(canonical(FIXTURE),))
        s.db.execute("INSERT INTO persons VALUES('p2','Keeper',NULL,NULL)")
        s.db.execute("INSERT INTO persons VALUES('p3','Unused',NULL,NULL)")
        return Engine(s)

    def test_restart_and_exactly_once(self):
        e=self.engine()
        for line in lineups(): e.ingest(line.wire())
        before=e.s.stream()
        result=e.ingest(lineups()[0].wire())
        self.assertTrue(result["duplicate"])
        self.assertEqual(before,e.s.stream())
        for point in ("after-journal","before-commit"):
            with self.assertRaises(RuntimeError):
                e.ingest(event(kind="end",event_id="end",ordinal=9,second=600).wire(),point)
            self.assertEqual(len(e.s.events("m1")),2)
        e.ingest(event(kind="end",event_id="end",ordinal=9,second=600).wire())
        self.assertEqual(len(e.ticker()),2)
        self.assertEqual(e.ticker()[0]["status"],"unavailable")
        e.s.close()

    def test_old_snapshot_is_immutable(self):
        e=self.engine()
        for line in lineups():e.ingest(line.wire())
        e.ingest(event(kind="goal",event_id="g",ordinal=3,second=30).wire())
        e.ingest(event(kind="retract",event_id="v",ordinal=4,second=40,payload=dict(target="g")).wire())
        self.assertEqual(e.match("m1",version=3)["score"],[1,0])
        self.assertEqual(e.match("m1")["score"],[0,0])
        self.assertIn("invalidation",[r["kind"] for r in e.s.stream()])
        e.s.close()
