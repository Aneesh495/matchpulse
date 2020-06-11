"""Masked causal recurrent score/concede estimator, trained from random initialization."""
from __future__ import annotations
import math
import random
from .contracts import ContractError,finite
from .numerics import Adam,bernoulli
from .ratings import sigmoid


class Temporal:
    def __init__(self,inputs:int=12,hidden:int=4,seed:int=1):
        if not 1<=inputs<=64 or not 1<=hidden<=32:raise ContractError("temporal shape bounds")
        self.inputs,self.hidden,self.seed=inputs,hidden,seed
        rng=random.Random(seed)
        n=inputs*hidden+hidden*hidden+hidden+2*hidden+2
        self.parameters=[rng.gauss(0,0.15) for _ in range(n)]
        self.optimizer=Adam(n,0.008)

    def forward(self,sequence:list[list[float]])->tuple[list[float],list[list[float]]]:
        if not sequence or len(sequence)>64:raise ContractError("bounded nonempty temporal sequence required")
        n,h=self.inputs,self.hidden;p=self.parameters
        r=n*h;b=r+h*h;v=b+h;c=v+2*h
        states=[[0.0]*h]
        for x in sequence:
            if len(x)!=n or any(not math.isfinite(v) for v in x):raise ContractError("invalid temporal input")
            last=states[-1]
            states.append([math.tanh(sum(p[j*n+i]*x[i] for i in range(n))+sum(p[r+j*h+k]*last[k] for k in range(h))+p[b+j]) for j in range(h)])
        return [sum(p[v+k*h+j]*states[-1][j] for j in range(h))+p[c+k] for k in range(2)],states

    def gradient(self,sequence:list[list[float]],states:list[list[float]],dy:list[float])->list[float]:
        n,h=self.inputs,self.hidden;p=self.parameters
        r=n*h;b=r+h*h;v=b+h;c=v+2*h
        g=[0.0]*len(p)
        for k in range(2):
            g[c+k]=dy[k]
            for j in range(h):g[v+k*h+j]=dy[k]*states[-1][j]
        dh=[sum(dy[k]*p[v+k*h+j] for k in range(2)) for j in range(h)]
        for t in range(len(sequence)-1,-1,-1):
            x=sequence[t];prev=states[t];current=states[t+1]
            dz=[dh[j]*(1-current[j]**2) for j in range(h)]
            for j in range(h):
                g[b+j]+=dz[j]
                for i in range(n):g[j*n+i]+=dz[j]*x[i]
                for k in range(h):g[r+j*h+k]+=dz[j]*prev[k]
            dh=[sum(dz[j]*p[r+j*h+k] for j in range(h)) for k in range(h)]
        return g

    def fit_one(self,sequence:list[list[float]],targets:list[float])->tuple[float,float]:
        out,states=self.forward(sequence)
        terms=[bernoulli(o,y) for o,y in zip(out,targets)]
        gradient=self.gradient(sequence,states,[term[1] for term in terms])
        norm=self.optimizer.update(self.parameters,gradient)
        return sum(term[0] for term in terms),norm

    def predict(self,sequence:list[list[float]])->list[float]:
        return list(map(sigmoid,self.forward(sequence)[0]))

    def state(self)->dict:
        return dict(kind="masked-temporal-v1",inputs=self.inputs,hidden=self.hidden,seed=self.seed,
            parameters=list(self.parameters),optimizer=dict(m=list(self.optimizer.m),v=list(self.optimizer.v),step=self.optimizer.step,rate=self.optimizer.rate))

    @classmethod
    def restore(cls,raw:dict)->Temporal:
        if not isinstance(raw,dict) or raw.get('kind')!='masked-temporal-v1' or any(type(raw.get(k)) is not int for k in ('inputs','hidden','seed')):
            raise ContractError('invalid temporal checkpoint kind or shape')
        model=cls(raw['inputs'],raw['hidden'],raw['seed'])
        params=raw.get('parameters')
        if not isinstance(params,list) or len(params)!=len(model.parameters):
            raise ContractError('invalid temporal parameter shape')
        model.parameters=[finite(v,-1e12,1e12,'temporal parameter') for v in params]
        model.optimizer=Adam.restore(raw.get('optimizer'),len(params))
        return model
