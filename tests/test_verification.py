import math
import unittest
from matchpulse.verify import replay_equal


class CrossPlatformReplay(unittest.TestCase):
    def test_only_machine_rounding_is_permitted(self):
        value=.025156935928568568
        one=math.nextafter(value,math.inf)
        two=math.nextafter(one,math.inf)
        three=math.nextafter(two,math.inf)
        self.assertTrue(replay_equal({'p':[value]}, {'p':[one]}))
        self.assertTrue(replay_equal(value,two))
        for changed in (three,value+1e-10,-value,float('nan'),float('inf')):
            self.assertFalse(replay_equal(value,changed))

    def test_structure_and_nonfloating_values_remain_exact(self):
        original={'version':37,'known_at':'2024-06-08T20:01:51Z','supported':True,'missing':None,'values':[.5]}
        for key,value in [('version',38),('version',37.0),('known_at','2024-06-09T20:01:51Z'),('supported',1),('missing',0),('values',[.5,.5])]:
            self.assertFalse(replay_equal(original,{**original,key:value}))
        self.assertFalse(replay_equal(original,{**original,'extra':None}))
        self.assertTrue(replay_equal(original,original))
