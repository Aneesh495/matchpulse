"""Small auditable numerical primitives for bounded CPU diagnostics."""
from __future__ import annotations
import json
import math
import os
from pathlib import Path
import random
from .contracts import ContractError, canonical, finite
from .ratings import sigmoid


def softplus(x: float) -> float:
    return max(x,0)+math.log1p(math.exp(-abs(x)))


def bernoulli(logit: float, target: float) -> tuple[float,float]:
    finite(target,0,1,"Bernoulli target")
    return softplus(logit)-target*logit,sigmoid(logit)-target


def gaussian_interval(mu: float, log_sigma: float, lower: float | None, upper: float | None) -> tuple[float,list[float]]:
    """NLL on log1p fee measured in millions. Missing bounds mean censoring."""
    if lower is None and upper is None:
        return 0.0,[0.0,0.0]
    sigma=math.exp(max(-5,min(5,log_sigma)))
    if lower is not None and upper is not None and lower==upper:
        z=(lower-mu)/sigma
        return math.log(sigma)+0.5*z*z+0.5*math.log(2*math.pi),[-z/sigma,1-z*z]
    if lower is not None and upper is not None and upper<lower:
        raise ContractError("inverted censor interval")
    zl=(lower-mu)/sigma if lower is not None else -math.inf
    zu=(upper-mu)/sigma if upper is not None else math.inf
    cdf=lambda z:0.5*math.erfc(-z/math.sqrt(2))
    pdf=lambda z:math.exp(-0.5*z*z)/math.sqrt(2*math.pi)
    # Survival differences avoid catastrophic cancellation in the positive tail.
    probability=(0.5*math.erfc(zl/math.sqrt(2))-0.5*math.erfc(zu/math.sqrt(2))) if zl>0 else cdf(zu)-cdf(zl)
    probability=max(1e-14,probability)
    pl,pu=pdf(zl),pdf(zu)
    gradient_mu=(pu-pl)/(sigma*probability)
    term_l=zl*pl if math.isfinite(zl) else 0
    term_u=zu*pu if math.isfinite(zu) else 0
    gradient_sigma=(term_u-term_l)/probability
    return -math.log(probability),[gradient_mu,gradient_sigma if -5<log_sigma<5 else 0]


class Adam:
    def __init__(self, n: int, rate: float=0.01):
        self.m=[0.0]*n;self.v=[0.0]*n;self.step=0;self.rate=rate

    def update(self, parameters: list[float], gradient: list[float]) -> float:
        if len(gradient)!=len(parameters) or len(self.m)!=len(parameters):
            raise ContractError("optimizer shape mismatch")
        norm=math.sqrt(sum(g*g for g in gradient))
        if not math.isfinite(norm):
            raise ContractError("nonfinite gradient")
        scale=min(1,5/max(norm,1e-12))
        self.step+=1
        for i,g in enumerate(gradient):
            g*=scale
            self.m[i]=0.9*self.m[i]+0.1*g
            self.v[i]=0.999*self.v[i]+0.001*g*g
            corrected_m=self.m[i]/(1-0.9**self.step)
            corrected_v=self.v[i]/(1-0.999**self.step)
            parameters[i]-=self.rate*corrected_m/(math.sqrt(corrected_v)+1e-8)
        return norm


class Dense:
    def __init__(self, inputs: int, hidden: int, outputs: int, seed: int):
        if not 1<=inputs<=128 or not 1<=hidden<=64 or not 1<=outputs<=8:
            raise ContractError("network bounds exceeded")
        self.inputs,self.hidden,self.outputs=inputs,hidden,outputs
        self.seed=seed
        rng=random.Random(seed)
        self.parameters=[rng.gauss(0,1/math.sqrt(inputs)) for _ in range(hidden*inputs)]+[0.0]*hidden+[rng.gauss(0,1/math.sqrt(hidden)) for _ in range(outputs*hidden)]+[0.0]*outputs
        self.optimizer=Adam(len(self.parameters))

    def forward(self,x:list[float])->tuple[list[float],list[float]]:
        if len(x)!=self.inputs or any(not math.isfinite(v) for v in x):
            raise ContractError("invalid model input")
        n,h,o=self.inputs,self.hidden,self.outputs
        b=n*h;v=b+h;c=v+h*o;p=self.parameters
        hidden=[math.tanh(sum(p[j*n+i]*x[i] for i in range(n))+p[b+j]) for j in range(h)]
        return [sum(p[v+k*h+j]*hidden[j] for j in range(h))+p[c+k] for k in range(o)],hidden

    def gradient(self,x:list[float],hidden:list[float],dy:list[float])->list[float]:
        n,h,o=self.inputs,self.hidden,self.outputs
        if len(dy)!=o:raise ContractError("output gradient shape mismatch")
        b=n*h;v=b+h;c=v+h*o
        g=[0.0]*len(self.parameters)
        dh=[sum(dy[k]*self.parameters[v+k*h+j] for k in range(o))*(1-hidden[j]**2) for j in range(h)]
        for j in range(h):
            for i in range(n):g[j*n+i]=dh[j]*x[i]
            g[b+j]=dh[j]
        for k in range(o):
            for j in range(h):g[v+k*h+j]=dy[k]*hidden[j]
            g[c+k]=dy[k]
        return g

    def fit_one(self,x:list[float],loss_fn)->tuple[float,float]:
        output,hidden=self.forward(x)
        loss,dy=loss_fn(output)
        if not math.isfinite(loss):raise ContractError("nonfinite objective")
        gradient=self.gradient(x,hidden,dy)
        norm=self.optimizer.update(self.parameters,gradient)
        return loss,norm

    def state(self)->dict:
        return dict(kind="dense-tanh-v1",inputs=self.inputs,hidden=self.hidden,outputs=self.outputs,seed=self.seed,
            parameters=self.parameters,optimizer=dict(m=self.optimizer.m,v=self.optimizer.v,step=self.optimizer.step,rate=self.optimizer.rate))

    @classmethod
    def restore(cls,raw:dict)->Dense:
        model=cls(raw["inputs"],raw["hidden"],raw["outputs"],raw["seed"])
        params=raw["parameters"]
        if len(params)!=len(model.parameters) or any(not math.isfinite(p) for p in params):
            raise ContractError("invalid checkpoint parameters")
        model.parameters=list(params)
        state=raw["optimizer"]
        if len(state["m"])!=len(params) or len(state["v"])!=len(params):raise ContractError("invalid optimizer shape")
        model.optimizer.m=list(state["m"]);model.optimizer.v=list(state["v"])
        model.optimizer.step=state["step"];model.optimizer.rate=state["rate"]
        return model


def atomic_json(path:Path,value:dict)->None:
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_name(path.name+".tmp")
    with temp.open("x") as out:
        out.write(canonical(value)+"\n");out.flush();os.fsync(out.fileno())
    os.replace(temp,path)
