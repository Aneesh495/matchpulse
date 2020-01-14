import unittest
from matchpulse.contracts import ContractError, Envelope, Feature, instant


def event(**kw):
    raw = dict(match_id="m1", event_id="e1", revision=1, ordinal=1,
        occurred_at="2024-01-01T12:00:00Z", received_at="2024-01-01T12:00:01Z",
        published_at=None, provider="test", license_id="cc0", mode="synthetic",
        kind="pass", player_id="p1", team_id="t1")
    return Envelope.parse({**raw, **kw})


class Contracts(unittest.TestCase):
    def test_timezones(self):
        self.assertEqual(instant("2024-01-01T13:00:00+01:00"), instant("2024-01-01T12:00:00Z"))
        with self.assertRaises(ContractError):
            instant("2024-01-01")

    def test_nan_and_boolean(self):
        for v in (float("nan"), True, -1, 121):
            with self.assertRaises(ContractError):
                event(payload={"x": v})

    def test_no_silent_xg_definition(self):
        with self.assertRaises(ContractError):
            event(payload={"xg": 0.5})

    def test_no_future(self):
        with self.assertRaises(ContractError):
            Feature("score", 1, "2024-01-02T00:00:00Z", "goal").as_of("2024-01-01T00:00:00Z")

    def test_duplicate_ignores_delivery_time(self):
        self.assertEqual(event().fact_hash(), event(received_at="2024-01-01T12:00:02Z").fact_hash())

    def test_received_clock(self):
        with self.assertRaises(ContractError):
            event(published_at="2024-01-01T12:00:03Z")
