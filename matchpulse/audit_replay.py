"""Bounded subprocess entry for replaying frozen inputs with the saved engine source."""
from pathlib import Path
import json
import sys
from .storage import Store
from .engine import Engine
from .contracts import canonical


def main():
    directory=Path(sys.argv[1]);s=Store(':memory:');e=Engine(s)
    e.seed(json.loads((directory/'PACKET.json').read_text()))
    for line in (directory/'DELIVERIES.jsonl').read_text().splitlines():e.ingest(json.loads(line))
    for deal in json.loads((directory/'TRANSACTIONS.json').read_text())['records']:e.deal(deal)
    print(canonical(e.snapshot()));s.close()


if __name__=='__main__':main()
