import sqlite3
import unittest
from matchpulse.storage import Store
from matchpulse.contracts import canonical, ContractError
from test_contracts import event


def store(path=":memory:"):
    s = Store(path)
    s.db.execute("INSERT INTO sources VALUES(?,?,?,?,?,?,?)", ("cc0", "synthetic", "test", "https://creativecommons.org/publicdomain/zero/1.0/", 1, None, "2024-01-01T00:00:00Z"))
    s.db.execute("INSERT INTO fixtures VALUES(?,?)", ("m1", canonical(dict(id="m1", home_id="t1", away_id="t2", mode="synthetic"))))
    s.db.execute("INSERT INTO persons VALUES(?,?,?,?)", ("p1", "Same name", None, None))
    return s


class Journal(unittest.TestCase):
    def test_deduplicate_and_collision(self):
        s = store()
        with s.transaction():
            self.assertEqual(s.append(event()), (1, True))
            self.assertEqual(s.append(event()), (1, False))
            with self.assertRaises(ContractError):
                s.append(event(kind="goal"))
        self.assertEqual(len(s.events("m1")), 1)
        s.close()

    def test_atomic_rollback_and_append_only(self):
        s = store()
        with self.assertRaises(RuntimeError):
            with s.transaction():
                s.append(event())
                s.publish("delta", {"value": 7})
                raise RuntimeError("power loss")
        self.assertEqual(s.events("m1"), [])
        self.assertEqual(s.stream(), [])
        with s.transaction():
            s.append(event())
        with self.assertRaises(sqlite3.IntegrityError):
            s.db.execute("DELETE FROM journal")
        s.close()

    def test_as_seen(self):
        s = store()
        with s.transaction():
            s.append(event())
            s.append(event(revision=2, kind="goal", received_at="2024-01-02T00:00:00Z"))
        self.assertEqual(len(s.events("m1", "2024-01-01T23:59:59Z")), 1)
        self.assertEqual(len(s.events("m1")), 2)
        s.close()
