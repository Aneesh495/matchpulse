"""Recompute held-out model outputs and scores without importing training or model code."""
from __future__ import annotations
import hashlib
import json
import math
from pathlib import Path


def require(condition,message):
    if not condition:raise ValueError(message)


def logistic(x):
    return (1/(1+math.exp(-x))) if x>=0 else math.exp(x)/(1+math.exp(x))


def recurrent(model,sequence):
    n,h=model['inputs'],model['hidden'];p=model['parameters']
    r=n*h;b=r+h*h;v=b+h;c=v+2*h;state=[0.]*h
    for x in sequence:
        updated=[]
        for j in range(h):
            total=p[b+j]
            total+=sum(w*value for w,value in zip(p[j*n:(j+1)*n],x))
            total+=sum(p[r+j*h+k]*state[k] for k in range(h))
            updated.append(math.tanh(total))
        state=updated
    return [logistic(p[c+k]+sum(p[v+k*h+j]*state[j] for j in range(h))) for k in range(2)]


def dense(model,x):
    n,h,o=model['inputs'],model['hidden'],model['outputs'];p=model['parameters']
    b=n*h;v=b+h;c=v+h*o
    hidden=[math.tanh(p[b+j]+sum(p[j*n+i]*x[i] for i in range(n))) for j in range(h)]
    return [p[c+k]+sum(p[v+k*h+j]*hidden[j] for j in range(h)) for k in range(o)]


def likelihood(mu,log_sigma,lower,upper):
    sigma=math.exp(max(-5,min(5,log_sigma)))
    if lower==upper:
        return math.log(sigma)+.5*((lower-mu)/sigma)**2+.5*math.log(2*math.pi)
    lo=(lower-mu)/sigma if lower is not None else -math.inf
    hi=(upper-mu)/sigma if upper is not None else math.inf
    if lo>0:prob=.5*math.erfc(lo/math.sqrt(2))-.5*math.erfc(hi/math.sqrt(2))
    else:prob=.5*math.erfc(-hi/math.sqrt(2))-.5*math.erfc(-lo/math.sqrt(2))
    return -math.log(max(1e-14,prob))


def verify_training(path:Path)->dict:
    config=json.loads((path/'CONFIG.json').read_text());require(config['mode']=='synthetic','training data mode changed')
    summary=[]
    for seed in config['seeds']:
        raw=(path/f'inputs-{seed}.json').read_bytes();inputs=json.loads(raw)
        frozen=json.dumps(inputs,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
        sets=[{r['id'] for r in inputs[k]} for k in ['rating_train','rating_validation','rating_test','fee_train','fee_validation','fee_test']]
        for i,left in enumerate(sets):
            for right in sets[i+1:]:require(left.isdisjoint(right),'training split identity overlap')
        rating=json.loads((path/f'rating-{seed}.json').read_text());fee=json.loads((path/f'fee-{seed}.json').read_text())
        for saved in [rating,fee]:
            require(saved['input_hash']==hashlib.sha256(frozen).hexdigest(),'training input identity changed')
            require(saved['model']['parameters']!=saved['training_initial'],'parameters unchanged')
            require(saved['model']['optimizer']['step']>0,'optimizer made no steps')
            require(all(math.isfinite(x) for x in saved['model']['parameters']),'nonfinite saved parameters')
            require(saved['report']['gradient_max']>0,'no gradient observed')
            require(saved['report']['training_loss'][-1]<saved['report']['training_loss'][0],'training did not improve')
        predictions=rating['predictions'];require(len(predictions)==80,'held-out rating workload incomplete')
        squared=[];losses=[]
        for row,prediction in zip(inputs['rating_test'],predictions):
            require(row['id']==prediction['id'],'rating held-out identity mismatch')
            actual=recurrent(rating['model'],row['sequence'])
            require(max(abs(a-b) for a,b in zip(actual,prediction['probabilities']))<1e-10,'saved temporal inference mismatch')
            p,y=actual[0],row['targets'][0];squared.append((p-y)**2);losses.append(-y*math.log(max(p,1e-12))-(1-y)*math.log(max(1-p,1e-12)))
        require(abs(sum(squared)/len(squared)-rating['report']['test']['brier'])<1e-10,'rating Brier summary mismatch')
        require(abs(sum(losses)/len(losses)-rating['report']['test']['log_loss'])<1e-10,'rating log-loss summary mismatch')
        conditionals=[];hazards=[]
        require(len(fee['predictions'])==120,'held-out transaction workload incomplete')
        for row,prediction in zip(inputs['fee_test'],fee['predictions']):
            require(row['id']==prediction['id'],'fee test identity mismatch')
            output=dense(fee['model'],row['features']);prob=logistic(output[0])
            require(abs(prob-prediction['probability'])<1e-10 and abs(output[1]-prediction['mu'])<1e-10,'saved fee inference mismatch')
            hazards.append((prob-row['move'])**2)
            if row['move']:
                nll=likelihood(output[1],output[2],row['lower'],row['upper']);conditionals.append(nll)
                require(abs(nll-prediction['conditional_nll'])<1e-10,'censoring likelihood mismatch')
            else:require(prediction['conditional_nll'] is None,'non-move received fee label')
        require(abs(sum(hazards)/len(hazards)-fee['report']['move']['brier'])<1e-10,'hazard summary mismatch')
        require(abs(sum(conditionals)/len(conditionals)-fee['report']['conditional_nll'])<1e-10,'conditional NLL summary mismatch')
        summary.append(dict(seed=seed,rating_brier=sum(squared)/len(squared),fee_nll=sum(conditionals)/len(conditionals)))
    return dict(status='passed',profile='synthetic-diagnostic',seeds=summary,full_acceptance='blocked')


if __name__=='__main__':
    import sys
    try:print(json.dumps(verify_training(Path(sys.argv[1])),sort_keys=True))
    except (ValueError,KeyError,OSError) as exc:print(str(exc),file=sys.stderr);sys.exit(1)
