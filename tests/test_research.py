import unittest
from matchpulse.temporal import Temporal
from matchpulse.evaluation import ridge_plus_minus,cluster_bootstrap,rolling_split


class Research(unittest.TestCase):
    def test_bptt_finite_difference_and_causality(self):
        m=Temporal(2,2,7);xs=[[.2,.4],[-.3,.5],[.7,-.2]]
        out,states=m.forward(xs);g=m.gradient(xs,states,[.3,-.8])
        for i in range(len(g)):
            old=m.parameters[i];m.parameters[i]=old+1e-6;a=m.forward(xs)[0];m.parameters[i]=old-1e-6;b=m.forward(xs)[0];m.parameters[i]=old
            self.assertAlmostEqual(g[i],sum(w*(u-v)/2e-6 for w,u,v in zip([.3,-.8],a,b)),places=7)
        prefix=m.predict(xs[:2]);xs.append([100,100]);self.assertEqual(prefix,m.predict(xs[:2]))

    def test_collinear_plus_minus(self):
        beta=ridge_plus_minus([[1,1],[1,1]],[2,2],2)
        self.assertAlmostEqual(beta[0],2/3);self.assertAlmostEqual(beta[1],2/3)

    def test_bootstrap_groups(self):
        result=cluster_bootstrap([1,2,3,4],["a","a","b","b"])
        self.assertEqual(result["groups"],2)
        self.assertEqual(result["mean"],2.5)

    def test_label_publication_after_cutoff_excluded(self):
        r=dict(feature_known_at="2023-01-01T00:00:00Z",label_known_at="2025-01-01T00:00:00Z",window_end="2023-07-01T00:00:00Z",club="a")
        split=rolling_split([r],"2023-08-01T00:00:00Z","2024-01-01T00:00:00Z","2024-08-01T00:00:00Z")
        self.assertEqual(split["train"],[]);self.assertEqual(split["excluded"],[r])
