import unittest
from matchpulse.ratings import RatingReducer, effective_events
from test_contracts import event

FIXTURE = dict(id="m1",home_id="t1",away_id="t2",home="Home",away="Away",mode="synthetic",trusted=True,
    players=[dict(id="p1",name="Striker",role="ST",team_id="t1"),dict(id="p2",name="Keeper",role="GK",team_id="t2"),dict(id="p3",name="Unused",role="CM",team_id="t1")])


def lineups():
    return [event(event_id="l1",kind="lineup",payload=dict(role="ST")),event(event_id="l2",kind="lineup",ordinal=2,player_id="p2",team_id="t2",payload=dict(role="GK"))]


class Ratings(unittest.TestCase):
    def test_unused_and_late_exposure(self):
        es = lineups() + [event(event_id="end",kind="end",ordinal=9,second=600)]
        r = RatingReducer(FIXTURE).run(es)
        self.assertEqual(r["players"][0]["minutes"], 10)
        self.assertEqual(r["players"][0]["status"], "provisional")
        self.assertIsNone(r["players"][2]["rating"])

    def test_var_and_delivery_permutation(self):
        goal = event(event_id="g",kind="goal",ordinal=4,second=20,payload=dict(xg=0.3,xg_definition="test"))
        var = event(event_id="v",kind="retract",ordinal=5,second=30,payload=dict(target="g",reason="VAR offside"))
        end = event(event_id="end",kind="end",ordinal=9,second=600)
        r = RatingReducer(FIXTURE)
        self.assertEqual(r.run(lineups()+[goal])["score"], [1,0])
        a = r.run(lineups()+[goal,var,end]); b = r.run([end,var,goal]+lineups())
        self.assertEqual(a, b)
        self.assertEqual(a["score"], [0,0])
        self.assertEqual(a["players"][0]["contribution"], 0)

    def test_save_red_and_role(self):
        es = lineups()+[event(kind="save",event_id="s",ordinal=3,second=30,player_id="p2",team_id="t2",payload=dict(xg=0.5,xg_definition="test")),event(kind="role",event_id="r",ordinal=4,second=60,payload=dict(role="WG")),event(kind="red",event_id="red",ordinal=5,second=90)]
        out = RatingReducer(FIXTURE).run(es)
        self.assertEqual(out["players"][1]["contribution"], 0.25)
        self.assertEqual(out["players"][0]["role"], "WG")
        self.assertTrue(out["players"][0]["red"])

    def test_shootout_excluded(self):
        es=lineups()+[event(kind="goal",period=5,second=10,payload=dict(xg=0.8,xg_definition="penalty"))]
        self.assertEqual(RatingReducer(FIXTURE).run(es)["score"],[0,0])
