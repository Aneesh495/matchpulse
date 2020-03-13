import unittest
from matchpulse.adapters import statsbomb_archive
from matchpulse.contracts import ContractError
from matchpulse.storage import Store
from matchpulse.engine import Engine


class ArchiveAdapter(unittest.TestCase):
    def test_normalized_path_does_not_import_future_positions(self):
        events=[dict(id='xi',type=dict(name='Starting XI'),team=dict(id=1),tactics=dict(lineup=[dict(player=dict(id=7),position=dict(id=23))])),dict(id='shot',period=1,timestamp='00:15:00.000',type=dict(name='Shot'),player=dict(id=7),team=dict(id=1),location=[110,40],shot=dict(statsbomb_xg=.4,outcome=dict(name='Goal'))),dict(id='end',period=2,timestamp='00:45:00.000',type=dict(name='Half End'),team=dict(id=1))]
        lineups=[dict(team_id=1,lineup=[dict(player_id=7,player_name='Archive schema test',positions=[dict(position_id=1,from_='80:00')])])]
        meta=dict(match_id=1,kickoff='2024-01-01T12:00:00Z',complete=True,home_team=dict(home_team_id=1,home_team_name='A'),away_team=dict(away_team_id=2,away_team_name='B'))
        rights=dict(id='local-test',mode='archive',local_research_authorized=True,terms_url='https://example.org/test')
        result=statsbomb_archive(events,lineups,meta,rights,'2024-01-03T00:00:00Z')
        self.assertEqual(result['packet']['fixtures'][0]['players'][0]['role'],'ST')
        self.assertTrue(all(e['published_at'] is None for e in result['events']))
        s=Store(':memory:');engine=Engine(s);engine.seed(result['packet'])
        for e in result['events']:engine.ingest(e)
        self.assertEqual(engine.matches()[0]['score'],[1,0]);self.assertEqual(engine.ticker()[0]['status'],'unavailable');s.close()
        rights['local_research_authorized']=False
        with self.assertRaises(ContractError):statsbomb_archive(events,lineups,meta,rights,'2024-01-03T00:00:00Z')
