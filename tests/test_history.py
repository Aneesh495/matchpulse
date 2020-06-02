import unittest
from matchpulse.engine import Engine
from matchpulse.storage import Store
from matchpulse.demo import packet,deliveries,later_deal
from matchpulse.contracts import ContractError

class History(unittest.TestCase):
    def setUp(self):
        self.s=Store(':memory:');self.e=Engine(self.s);self.e.seed(packet())
        for event in deliveries():self.e.ingest(event)
        self.e.deal(later_deal())
    def tearDown(self):self.s.close()
    def test_as_of_excludes_later_sale_and_future_estimate(self):
        before=self.e.history('demo-p9','2024-06-08T20:01:51Z')
        self.assertEqual(len(before['estimates']),1)
        self.assertEqual(before['transactions'],[])
        self.assertEqual(len(before['context']['facts']),2)
        self.assertEqual(self.e.history('demo-p9','2024-06-08T19:00:00Z')['estimates'],[])
        self.assertEqual(len(self.e.history('demo-p9')['transactions']),1)
    def test_comparison_and_freshness_policy(self):
        result=self.e.compare(['demo-p1','demo-p9'])
        self.assertEqual(len(result['players']),2)
        self.assertEqual(result['players'][0]['estimates'][-1]['freshness']['state'],'historical')
        with self.assertRaises(ContractError):self.e.compare(['demo-p1']*2)
        with self.assertRaises(ContractError):self.e.compare(['a','b','c','d'])
