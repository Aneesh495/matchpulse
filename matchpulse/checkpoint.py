"""Epoch-boundary checkpoints bind model, optimizer, sampler and frozen inputs."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import random
import resource
import sys
import time
from .contracts import ContractError, canonical, digest
from .numerics import atomic_json


def implementation_identity() -> dict:
    base=Path(__file__).parent
    names=('checkpoint.py','training.py','numerics.py','temporal.py','evaluation.py','ratings.py','contracts.py')
    return {name:hashlib.sha256((base/name).read_bytes()).hexdigest() for name in names}


def tuples(value):
    return tuple(tuples(v) for v in value) if isinstance(value,list) else value


class EpochTrainer:
    def __init__(self,directory:Path,resume:bool,interrupt_after_epochs:int|None=None):
        self.out=directory
        self.source=implementation_identity()
        self.resume=resume
        self.started=time.monotonic()
        self.executed=0
        self.interrupt_after=interrupt_after_epochs

    def fit(self,stage:str,seed:int,model,rows:list[dict],epochs:int,sampler:random.Random,input_hash:str,step):
        path=self.out/f'checkpoint-{stage}-{seed}.json'
        if path.exists():
            if not self.resume:raise ContractError('checkpoint exists outside resume mode')
            saved=json.loads(path.read_text())
            if saved.get('source')!=self.source or saved.get('input_hash')!=input_hash or saved.get('stage')!=stage or saved.get('seed')!=seed or saved.get('epochs')!=epochs:
                raise ContractError('checkpoint source, inputs or protocol mismatch')
            count=saved.get('completed_epochs')
            if type(count) is not int or not 0<=count<=epochs or len(saved.get('losses',[]))!=count:
                raise ContractError('invalid epoch progress')
            restored=type(model).restore(saved.get('model'))
            if (restored.inputs,restored.hidden,restored.seed,getattr(restored,"outputs",2))!=(model.inputs,model.hidden,model.seed,getattr(model,"outputs",2)):
                raise ContractError('checkpoint model shape or seed mismatch')
            if restored.optimizer.step!=count*len(rows) or saved.get('initial')!=model.parameters:
                raise ContractError('checkpoint optimizer clock or random initialization mismatch')
            model=restored
            try:sampler.setstate(tuples(saved['sampler_rng']))
            except (ValueError,TypeError,KeyError) as exc:raise ContractError('invalid sampler RNG checkpoint') from exc
            initial=saved['initial'];losses=list(saved['losses'])
            low,high=saved['gradient_min'],saved['gradient_max']
        else:
            count=0;initial=list(model.parameters);losses=[];low=float('inf');high=0.0
        for epoch in range(count,epochs):
            order=list(range(len(rows)));sampler.shuffle(order);total=0.0
            for index in order:
                loss,norm=step(model,rows[index]);total+=loss;low=min(low,norm);high=max(high,norm)
            losses.append(total/len(rows))
            saved=dict(format='matchpulse-epoch-v1',stage=stage,seed=seed,epochs=epochs,completed_epochs=epoch+1,
                source=self.source,input_hash=input_hash,model=model.state(),initial=initial,losses=losses,
                gradient_min=low,gradient_max=high,sampler_rng=sampler.getstate())
            atomic_json(path,saved)
            usage=resource.getrusage(resource.RUSAGE_SELF)
            peak=usage.ru_maxrss*(1 if sys.platform=='darwin' else 1024)
            with (self.out/'EPOCHS.jsonl').open('a') as log:
                log.write(canonical(dict(stage=stage,seed=seed,epoch=epoch+1,checkpoint_hash=digest(saved),peak_rss_bytes=peak))+'\n')
            self.executed+=1
            if peak>200_000_000 or time.monotonic()-self.started>120:
                raise ContractError('training resource ceiling exceeded; epoch checkpoint preserved')
            if self.interrupt_after is not None and self.executed>=self.interrupt_after:
                raise InterruptedError('injected interruption after durable epoch checkpoint')
        return model,initial,losses,low,high
