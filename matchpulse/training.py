"""Seeded CPU learning diagnostics. Synthetic generators are never actual-data evidence."""
from __future__ import annotations
import json
import math
from pathlib import Path
import random
import time
from .contracts import ContractError, canonical, digest
from .evaluation import brier,log_loss,calibration,cluster_bootstrap
from .numerics import Dense,atomic_json,bernoulli,gaussian_interval
from .ratings import sigmoid
from .temporal import Temporal
from .checkpoint import EpochTrainer,implementation_identity

SEEDS=(11,29,47)


def rating_samples(seed:int,n:int)->list[dict]:
    rng=random.Random(seed);records=[]
    for i in range(n):
        role=i%8;sequence=[];carry=0.0
        for t in range(8):
            x=rng.uniform(-1,1);y=rng.uniform(-1,1);supported=rng.random()>.15
            sequence.append([x if supported else 0,y if supported else 0,float(supported),t/8]+[float(r==role) for r in range(8)])
            carry=.65*carry+.35*(x if supported else 0)
        p=sigmoid(-1+1.5*carry+0.15*(role-3.5))
        q=sigmoid(-1.5-1.3*carry)
        records.append(dict(id=f"s{seed}-r{i}",group=f"s{seed}-r{i}",role=role,sequence=sequence,targets=[float(rng.random()<p),float(rng.random()<q)],truth=[p,q],mode="synthetic"))
    return records


def fee_samples(seed:int,n:int)->list[dict]:
    rng=random.Random(seed);result=[]
    for i in range(n):
        age=rng.uniform(-1,1);minutes=rng.uniform(-1,1);contract=rng.uniform(-1,1);form=rng.uniform(-1,1)
        mask=[float(rng.random()>.1) for _ in range(4)]
        features=[x*m for x,m in zip([age,minutes,contract,form],mask)]+mask
        move=rng.random()<sigmoid(-.8+.6*minutes-.6*contract+.2*form)
        log_fee=max(0,2.3-.4*age+.8*minutes+.4*contract+.1*form+rng.gauss(0,.35)) if move else None
        censored=move and rng.random()<.3
        lower=max(0,log_fee-.2) if censored else log_fee
        upper=log_fee+.2 if censored else log_fee
        result.append(dict(id=f"s{seed}-f{i}",group=f"s{seed}-f{i}",features=features,move=float(move),lower=lower,upper=upper,mode="synthetic",disclosure="interval" if censored else "exact" if move else "not-applicable"))
    return result


def fee_loss(output:list[float],row:dict)->tuple[float,list[float]]:
    hazard,dh=bernoulli(output[0],row["move"])
    nll,df=gaussian_interval(output[1],output[2],row["lower"],row["upper"]) if row["move"] else (0.0,[0.0,0.0])
    return hazard+nll,[dh,*df]


def scores(probabilities:list[float],targets:list[float])->dict:
    return dict(log_loss=log_loss(probabilities,targets),brier=brier(probabilities,targets),calibration=calibration(probabilities,targets))


def train_diagnostic(out:Path,resume:bool=False,interrupt_after_epochs:int|None=None)->dict:
    if resume:
        if not out.is_dir() or (out/'REPORT.json').exists():
            raise ContractError('resume needs an incomplete existing training run')
    else:out.mkdir(parents=True,exist_ok=False)
    start=time.monotonic();reports=[]
    config=dict(protocol="diagnostic-v1",mode="synthetic",seeds=SEEDS,rating_epochs=6,fee_epochs=8,training_source="authored-generator-v1",stop_seconds=120)
    if resume:
        if canonical(json.loads((out/'CONFIG.json').read_text()))!=canonical(config) or json.loads((out/'SOURCE.json').read_text())!=implementation_identity():
            raise ContractError('training source or configuration changed since checkpoint')
    else:
        atomic_json(out/'CONFIG.json',config);atomic_json(out/'SOURCE.json',implementation_identity())
        identities={}
        for seed in SEEDS:
            inputs=dict(rating_train=rating_samples(seed,180),rating_validation=rating_samples(seed+1000,60),rating_test=rating_samples(seed+2000,80),
                fee_train=fee_samples(seed+3000,300),fee_validation=fee_samples(seed+4000,100),fee_test=fee_samples(seed+5000,120))
            atomic_json(out/f'inputs-{seed}.json',inputs);identities[str(seed)]=digest(inputs)
        atomic_json(out/'INPUT_IDENTITIES.json',identities)
    identities=json.loads((out/'INPUT_IDENTITIES.json').read_text())
    trainer=EpochTrainer(out,resume,interrupt_after_epochs)
    for seed in SEEDS:
        inputs=json.loads((out/f'inputs-{seed}.json').read_text())
        if digest(inputs)!=identities[str(seed)]:raise ContractError('frozen training inputs changed')
        rtrain,rtest=inputs['rating_train'],inputs['rating_test'];ftrain,ftest=inputs['fee_train'],inputs['fee_test']
        sampler=random.Random(seed+7000)
        temporal,initial,losses,rmin,rmax=trainer.fit('rating',seed,Temporal(seed=seed),rtrain,6,sampler,digest(inputs),lambda model,row:model.fit_one(row['sequence'],row['targets']))
        predictions=[dict(id=row["id"],group=row["group"],role=row["role"],probabilities=temporal.predict(row["sequence"]),targets=row["targets"]) for row in rtest]
        probabilities=[r["probabilities"][0] for r in predictions];targets=[r["targets"][0] for r in predictions]
        marginal=sum(r["targets"][0] for r in rtrain)/len(rtrain)
        delta=[(p-y)**2-(marginal-y)**2 for p,y in zip(probabilities,targets)]
        rating_report=dict(training_loss=losses,gradient_max=rmax,parameters_changed=initial!=temporal.parameters,
            test=scores(probabilities,targets),baseline=scores([marginal]*len(targets),targets),
            brier_difference=cluster_bootstrap(delta,[r["group"] for r in predictions]),
            by_role={str(role):scores([p["probabilities"][0] for p in predictions if p["role"]==role],[p["targets"][0] for p in predictions if p["role"]==role]) for role in range(8)})
        rating_saved=dict(model=temporal.state(),config=config,input_hash=digest(inputs),sampler_rng=sampler.getstate(),training_initial=initial,report=rating_report,predictions=predictions)
        rating_path=out/f'rating-{seed}.json'
        if rating_path.exists():
            if canonical(json.loads(rating_path.read_text()))!=canonical(rating_saved):raise ContractError('completed rating artifact changed')
        else:atomic_json(rating_path,rating_saved)
        fee,fee_initial,fee_losses,fmin,fmax=trainer.fit('fee',seed,Dense(8,8,3,seed),ftrain,8,sampler,digest(inputs),lambda model,row:model.fit_one(row['features'],lambda output:fee_loss(output,row)))
        fp=[]
        for row in ftest:
            output=fee.forward(row["features"])[0]
            fp.append(dict(id=row["id"],move=row["move"],probability=sigmoid(output[0]),mu=output[1],log_sigma=output[2],lower=row["lower"],upper=row["upper"],conditional_nll=gaussian_interval(output[1],output[2],row["lower"],row["upper"])[0] if row["move"] else None))
        hazard_prior=sum(r["move"] for r in ftrain)/len(ftrain)
        observed=[r["lower"] for r in ftrain if r["move"] and r["disclosure"]=="exact"]
        baseline_mu=sum(observed)/len(observed);baseline_sigma=math.sqrt(sum((v-baseline_mu)**2 for v in observed)/len(observed))
        moved=[p for p in fp if p["move"]]
        fee_report=dict(training_loss=fee_losses,gradient_max=fmax,parameters_changed=fee_initial!=fee.parameters,
            move=scores([p["probability"] for p in fp],[p["move"] for p in fp]),
            baseline_move=scores([hazard_prior]*len(fp),[p["move"] for p in fp]),
            conditional_nll=sum(p["conditional_nll"] for p in moved)/len(moved),
            baseline_conditional_nll=sum(gaussian_interval(baseline_mu,math.log(baseline_sigma),p["lower"],p["upper"])[0] for p in moved)/len(moved),
            test_moves=len(moved),test_records=len(fp),baseline_exact_disclosure_only=True)
        fee_saved=dict(model=fee.state(),config=config,input_hash=digest(inputs),sampler_rng=sampler.getstate(),training_initial=fee_initial,report=fee_report,predictions=fp)
        fee_path=out/f'fee-{seed}.json'
        if fee_path.exists():
            if canonical(json.loads(fee_path.read_text()))!=canonical(fee_saved):raise ContractError('completed fee artifact changed')
        else:atomic_json(fee_path,fee_saved)
        if not rating_report["parameters_changed"] or not fee_report["parameters_changed"] or min(rmin,fmin)<=0:
            raise ContractError("learning proof failed")
        if losses[-1]>=losses[0] or fee_losses[-1]>=fee_losses[0]:raise ContractError("training objective did not decrease")
        reports.append(dict(seed=seed,rating=rating_report,fee=fee_report))
    report=dict(protocol=config["protocol"],mode="synthetic",elapsed_seconds=time.monotonic()-start,full_acceptance="blocked",seeds=reports)
    atomic_json(out/"REPORT.json",report)
    return report
