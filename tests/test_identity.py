import unittest
from matchpulse.identity import Identity, candidate_key
from matchpulse.contracts import ContractError
from test_storage import store


class Identities(unittest.TestCase):
    def test_names_do_not_merge(self):
        s = store(); i = Identity(s)
        i.add_person(dict(id="p2", name="Same name"))
        self.assertEqual(s.db.execute("SELECT count(*) FROM persons").fetchone()[0], 2)
        i.bind("a", "1", "p1", "2023-01-01T00:00:00Z", "2023-01-01T00:00:00Z", "vendor assertion")
        with self.assertRaises(ContractError):
            i.bind("a", "1", "p2", "2023-01-01T00:00:00Z", "2024-01-01T00:00:00Z", "same name")
        i.bind("a", "1", "p2", "2023-01-01T00:00:00Z", "2024-01-01T00:00:00Z", "reviewed birth certificate mismatch", action="split")
        self.assertEqual(i.resolve("a", "1", "2023-06-01T00:00:00Z", "2023-06-01T00:00:00Z"), "p1")
        self.assertEqual(i.resolve("a", "1", "2023-06-01T00:00:00Z", "2024-06-01T00:00:00Z"), "p2")
        self.assertEqual(len(i.history()), 2); s.close()

    def test_transfer_not_known_early(self):
        s = store(); i = Identity(s)
        i.register(dict(id="r1", person_id="p1", team_id="t2", valid_from="2024-07-01T00:00:00Z", known_at="2024-06-20T00:00:00Z", kind="loan", source_id="cc0"))
        self.assertEqual(i.roster("t2", "2024-06-30T00:00:00Z", "2024-07-01T00:00:00Z"), [])
        self.assertEqual(i.roster("t2", "2024-07-01T00:00:00Z", "2024-06-19T00:00:00Z"), [])
        self.assertEqual(i.roster("t2", "2024-07-01T00:00:00Z", "2024-06-21T00:00:00Z")[0]["kind"], "loan")
        s.close()
