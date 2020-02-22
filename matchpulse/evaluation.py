"""Chronological group splits and proper scores never use test labels for fitting."""
from __future__ import annotations
from collections import defaultdict
import math
import random
from .contracts import ContractError,instant


def rolling_split(records:list[dict],train_end:str,validation_end:str,test_end:str,held_out_clubs:set[str]|None=None)->dict[str,list[dict]]:
    bounds=list(map(instant,[train_end,validation_end,test_end]))
    if bounds!=sorted(bounds) or len(set(bounds))!=3:raise ContractError("split boundaries must increase")
    result={"train":[],"validation":[],"test":[],"excluded":[]}
    held_out_clubs=held_out_clubs or set()
    for record in records:
        feature=instant(record["feature_known_at"]);label=instant(record["label_known_at"])
        if label<feature:raise ContractError("label predates forecast")
        window=instant(record["window_end"])
        if window<=bounds[0] and label<=bounds[0] and record["club"] not in held_out_clubs:
            result["train"].append(record)
        elif bounds[0]<window<=bounds[1] and label<=bounds[1] and record["club"] not in held_out_clubs:
            result["validation"].append(record)
        elif bounds[1]<window<=bounds[2] and label<=bounds[2]:
            result["test"].append(record)
        else:result["excluded"].append(record)
    return result


def brier(probabilities:list[float],targets:list[float])->float:
    if not probabilities or len(probabilities)!=len(targets):raise ContractError("empty or mismatched evaluation")
    if any(not math.isfinite(p) or not 0<=p<=1 for p in probabilities):raise ContractError("invalid probability")
    return sum((p-y)**2 for p,y in zip(probabilities,targets))/len(targets)


def log_loss(probabilities:list[float],targets:list[float])->float:
    brier(probabilities,targets)
    return -sum(y*math.log(max(p,1e-12))+(1-y)*math.log(max(1-p,1e-12)) for p,y in zip(probabilities,targets))/len(targets)


def calibration(probabilities:list[float],targets:list[float],bins:int=5)->list[dict]:
    brier(probabilities,targets)
    result=[]
    for i in range(bins):
        ids=[j for j,p in enumerate(probabilities) if min(bins-1,int(p*bins))==i]
        result.append(dict(lower=i/bins,upper=(i+1)/bins,n=len(ids),prediction=sum(probabilities[j] for j in ids)/len(ids) if ids else None,frequency=sum(targets[j] for j in ids)/len(ids) if ids else None))
    return result


def cluster_bootstrap(differences:list[float],groups:list[str],seed:int=29,repetitions:int=200)->dict:
    if len(differences)!=len(groups) or not differences:raise ContractError("invalid bootstrap units")
    grouped=defaultdict(list)
    for d,g in zip(differences,groups):
        if not math.isfinite(d):raise ContractError("nonfinite comparison")
        grouped[g].append(d)
    units=sorted(grouped)
    if len(units)<2:raise ContractError("bootstrap needs at least two independent groups")
    rng=random.Random(seed);estimates=[]
    for _ in range(repetitions):
        samples=[rng.choice(units) for _ in units]
        values=[d for unit in samples for d in grouped[unit]]
        estimates.append(sum(values)/len(values))
    estimates.sort()
    return dict(mean=sum(differences)/len(differences),lower=estimates[int(.025*repetitions)],upper=estimates[min(repetitions-1,int(.975*repetitions))],groups=len(units),repetitions=repetitions,seed=seed)


def ridge_plus_minus(designs:list[list[float]],outcomes:list[float],penalty:float=10)->list[float]:
    if not designs or len(designs)!=len(outcomes) or penalty<=0:raise ContractError("invalid ridge design")
    n=len(designs[0])
    if n>100 or any(len(row)!=n for row in designs):raise ContractError("bounded consistent plus-minus design required")
    a=[[sum(x[i]*x[j] for x in designs)+(penalty if i==j else 0) for j in range(n)]+[sum(x[i]*y for x,y in zip(designs,outcomes))] for i in range(n)]
    for c in range(n):
        pivot=max(range(c,n),key=lambda r:abs(a[r][c]));a[c],a[pivot]=a[pivot],a[c]
        scale=a[c][c]
        if abs(scale)<1e-12:raise ContractError("singular regularized design")
        a[c]=[v/scale for v in a[c]]
        for r in range(n):
            if r!=c:
                factor=a[r][c];a[r]=[v-factor*w for v,w in zip(a[r],a[c])]
    return [row[-1] for row in a]
