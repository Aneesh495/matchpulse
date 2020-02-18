import math
import unittest
from matchpulse.numerics import Dense,bernoulli,gaussian_interval


class Gradients(unittest.TestCase):
    def test_analytic_network_against_finite_difference(self):
        m=Dense(3,4,2,17);x=[.2,-.4,.5]
        output,h=m.forward(x);g=m.gradient(x,h,[.4,-.8])
        eps=1e-6
        for i in range(len(g)):
            old=m.parameters[i]
            m.parameters[i]=old+eps;y1=m.forward(x)[0]
            m.parameters[i]=old-eps;y2=m.forward(x)[0]
            m.parameters[i]=old
            numeric=sum(a*(b-c)/(2*eps) for a,b,c in zip([.4,-.8],y1,y2))
            self.assertAlmostEqual(g[i],numeric,places=7)

    def test_censor_likelihood_gradient(self):
        for lower,upper in [(1.,1.),(.3,1.7),(None,1.2),(.7,None)]:
            loss,g=gaussian_interval(.6,-.3,lower,upper)
            for i in range(2):
                a=[.6,-.3];b=a.copy();a[i]+=1e-6;b[i]-=1e-6
                diff=(gaussian_interval(*a,lower,upper)[0]-gaussian_interval(*b,lower,upper)[0])/2e-6
                self.assertAlmostEqual(diff,g[i],places=5)

    def test_learning_and_checkpoint_resume(self):
        m=Dense(1,4,1,3);before=m.parameters.copy()
        for _ in range(100):
            for x,y in [([-1.],0.),([1.],1.)]:
                m.fit_one(x,lambda o:(bernoulli(o[0],y)[0],[bernoulli(o[0],y)[1]]))
        self.assertNotEqual(before,m.parameters)
        self.assertLess(bernoulli(m.forward([-1.])[0][0],0)[0],.1)
        r=Dense.restore(m.state());self.assertEqual(m.forward([.5]),r.forward([.5]))
        loss=lambda o:(o[0]**2,[2*o[0]])
        m.fit_one([.3],loss);r.fit_one([.3],loss)
        self.assertEqual(m.parameters,r.parameters)
