"""Bounded newline-delimited request protocol owned by the Go server process."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys
import traceback
from .contracts import ContractError, canonical
from .storage import Store
from .engine import Engine
from . import demo

MAX_REQUEST=1024*1024


def dispatch(engine: Engine, op: str, args: dict):
    if op=="state": return engine.snapshot()
    if op=="match": return engine.match(args["id"],args.get("version"),args.get("as_of"))
    if op=="matches": return engine.matches()
    if op=="history": return engine.history(args["id"])
    if op=="coverage": return engine.coverage()
    if op=="stream": return engine.s.stream(int(args.get("after",0)),int(args.get("limit",128)))
    if op=="ticker": return engine.ticker(args.get("as_of"))
    if op=="ingest": return engine.ingest(args)
    if op=="deal": return engine.deal(args)
    if op=="step": return demo.step(engine,bool(args.get("finish",False)))
    raise ContractError("unknown operation")


def main():
    parser=argparse.ArgumentParser();parser.add_argument("--db",default="runtime/matchpulse.db")
    opts=parser.parse_args()
    store=Store(opts.db);engine=Engine(store);engine.seed(demo.packet())
    try:
        while True:
            line=sys.stdin.buffer.readline(MAX_REQUEST+1)
            if not line:break
            if len(line)>MAX_REQUEST:
                raise ContractError("RPC frame exceeds bound")
            try:
                raw=json.loads(line)
                data=dispatch(engine,raw["op"],raw.get("args",{}))
                result=dict(ok=True,data=data)
            except (ContractError,ValueError,KeyError,TypeError) as exc:
                result=dict(ok=False,error=str(exc),code="invalid-request")
            except Exception:
                traceback.print_exc(file=sys.stderr)
                result=dict(ok=False,error="internal error",code="internal")
            print(canonical(result),flush=True)
    finally:
        store.close()


if __name__=="__main__":main()
