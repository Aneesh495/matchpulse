import unittest
from matchpulse.valuation import Deal, FXVintage
from matchpulse.contracts import ContractError


def deal(**kw):
    return Deal.parse(dict(id="d1", person_id="p1",kind="permanent",disclosure="undisclosed",effective_at="2024-07-01T00:00:00Z",known_at="2024-07-02T00:00:00Z",currency="EUR",guaranteed=None,lower=None,upper=None,addons_upper=None,source_url="https://example.org/club",source_id="club",mode="archive",**kw))


class Fees(unittest.TestCase):
    def test_undisclosed_is_not_zero(self):
        base=deal().wire(); base["guaranteed"]=0
        with self.assertRaises(ContractError): Deal.parse(base)

    def test_no_move_no_fee(self):
        base=deal().wire();base.update(kind="none",disclosure="not-applicable")
        self.assertFalse(Deal.parse(base).comparable)
        base["guaranteed"]=0
        with self.assertRaises(ContractError): Deal.parse(base)

    def test_optional_terms_separate(self):
        base=deal().wire();base.update(disclosure="exact",guaranteed=51.3e6,addons_upper=6e6,ancillary_costs=3.4e6)
        self.assertEqual(Deal.parse(base).guaranteed,51.3e6)

    def test_frozen_fx(self):
        f=FXVintage("GBP",1.2,"2024-01-01","2024-01-02T00:00:00Z","ECB")
        with self.assertRaises(ContractError): f.convert(10,"2024-01-01T00:00:00Z")
        self.assertEqual(f.convert(10,"2024-01-03T00:00:00Z"),12)
