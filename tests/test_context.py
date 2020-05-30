import sqlite3
import unittest
from matchpulse.context import ContextLedger
from matchpulse.contracts import ContractError
from test_storage import store


def contract(**kw):
    return {**dict(id='contract-p1',revision=1,person_id='p1',kind='contract',valid_from='2024-01-01T00:00:00Z',valid_to='2025-01-01T00:00:00Z',known_at='2024-01-02T00:00:00Z',source_id='cc0',source_url='https://example.org/fictional-contract',confidence=.8,details=dict(team_id='t1',expires_at='2025-01-01T00:00:00Z')),**kw}


class Context(unittest.TestCase):
    def test_bitemporal_correction_and_no_resurrection(self):
        s=store();c=ContextLedger(s)
        self.assertTrue(c.append(contract()));self.assertFalse(c.append(contract()))
        c.append(contract(revision=2,known_at='2024-02-01T00:00:00Z',valid_from='2024-03-01T00:00:00Z'))
        self.assertEqual(len(c.view('p1','2024-01-15T00:00:00Z','2024-01-20T00:00:00Z')['facts']),1)
        self.assertEqual(c.view('p1','2024-01-15T00:00:00Z','2024-02-02T00:00:00Z')['facts'],[])
        c.append(contract(revision=3,known_at='2024-03-01T00:00:00Z',withdrawn=True))
        self.assertEqual(c.view('p1','2024-06-01T00:00:00Z','2024-06-01T00:00:00Z')['facts'],[])
        with self.assertRaises(sqlite3.IntegrityError):s.db.execute('DELETE FROM context_assertions')
        s.close()

    def test_expiry_source_and_coarse_availability(self):
        s=store();c=ContextLedger(s)
        for bad in [contract(known_at='2023-12-01T00:00:00Z'),contract(details=dict(team_id='t1',expires_at='2023-01-01T00:00:00Z')),contract(kind='availability',details=dict(status='injured',diagnosis='unsupported medical detail'))]:
            with self.assertRaises(ContractError):c.append(bad)
        c.append(contract(kind='availability',details=dict(status='suspended')))
        view=c.view('p1','2024-06-01T00:00:00Z','2024-06-01T00:00:00Z')
        self.assertEqual(view['facts'][0]['details']['status'],'suspended')
        self.assertIn('contract',view['unsupported']);s.close()

    def test_conflicts_remain_visible_and_expiry_exclusive(self):
        s=store();c=ContextLedger(s);c.append(contract())
        c.append(contract(id='conflicting-contract',details=dict(team_id='t2',expires_at='2025-01-01T00:00:00Z')))
        self.assertIn('contract',c.view('p1','2024-06-01T00:00:00Z','2024-06-01T00:00:00Z')['conflicts'])
        self.assertEqual(c.view('p1','2025-01-01T00:00:00Z','2025-01-01T00:00:00Z')['facts'],[]);s.close()
