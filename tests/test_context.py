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

class ContextImport(unittest.TestCase):
    def test_packet_atomicity_and_idempotence(self):
        from matchpulse.engine import Engine
        s=store();e=Engine(s)
        bad=contract(id='bad',person_id='unknown')
        with self.assertRaises(ContractError):e.seed({'context':[contract(),bad]},publish_context=True)
        self.assertEqual(s.db.execute('SELECT count(*) FROM context_assertions').fetchone()[0],0)
        self.assertEqual(s.stream(),[])
        e.seed({'context':[contract()]},publish_context=True)
        e.seed({'context':[contract()]},publish_context=True)
        self.assertEqual(len(s.stream()),1);s.close()

class CoverageCounts(unittest.TestCase):
    def test_registration_unknown_and_conflicting_denominators(self):
        from matchpulse.engine import Engine
        from matchpulse.demo import packet
        from matchpulse.storage import Store
        s=Store(':memory:');e=Engine(s);e.seed(packet())
        self.assertEqual(e.coverage()['roster']['by_registration']['active'],24)
        raw=packet()['context'][0]
        e.append_context({**raw,'id':'conflicting-registration','details':dict(team_id='other',registration_kind='loan')})
        coverage=e.coverage()
        self.assertEqual(coverage['roster']['by_registration']['ambiguous'],1)
        self.assertEqual(sum(coverage['roster']['by_registration'].values()),24)
        self.assertEqual(coverage['training_eligible_transactions'],0);s.close()

class PacketContracts(unittest.TestCase):
    def test_invalid_source_and_duplicate_roster_roll_back(self):
        import copy
        from matchpulse.engine import Engine
        from matchpulse.demo import packet
        from matchpulse.storage import Store
        s=Store(':memory:');e=Engine(s)
        p=packet();p['sources'][0]['terms_url']='javascript:alert(1)'
        with self.assertRaises(ContractError):e.seed(p)
        p=packet();p['fixtures'][0]['players'].append(copy.deepcopy(p['fixtures'][0]['players'][0]))
        with self.assertRaises(ContractError):e.seed(p)
        self.assertEqual(s.db.execute('SELECT count(*) FROM sources').fetchone()[0],0)
        with self.assertRaises(ContractError):e.seed({'ignored_records':[]})
        s.close()
