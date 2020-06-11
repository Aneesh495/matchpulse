import json
from pathlib import Path
import tempfile
import unittest
from matchpulse.training import train_diagnostic
from matchpulse.contracts import ContractError
from matchpulse.verify_training import verify_training
from matchpulse.numerics import Adam

class Resume(unittest.TestCase):
    def test_interrupted_and_uninterrupted_models_are_identical(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);full=root/'full';resumed=root/'resumed'
            train_diagnostic(full)
            with self.assertRaises(InterruptedError):train_diagnostic(resumed,interrupt_after_epochs=9)
            before=(resumed/'rating-11.json').read_bytes()
            # A stale uncommitted temporary file must not prevent recovery.
            (resumed/'checkpoint-fee-11.json.tmp').write_text('incomplete')
            train_diagnostic(resumed,resume=True)
            self.assertEqual(before,(resumed/'rating-11.json').read_bytes())
            for name in ('rating','fee'):
                for seed in (11,29,47):self.assertEqual((full/f'{name}-{seed}.json').read_bytes(),(resumed/f'{name}-{seed}.json').read_bytes())
            epochs=[json.loads(line) for line in (resumed/'EPOCHS.jsonl').read_text().splitlines()]
            identities=[(e['stage'],e['seed'],e['epoch']) for e in epochs]
            self.assertEqual(len(identities),42);self.assertEqual(len(set(identities)),42)
            self.assertEqual(verify_training(resumed)['status'],'passed')
            with self.assertRaises(ContractError):train_diagnostic(resumed,resume=True)

    def test_changed_inputs_and_invalid_optimizer_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            out=Path(temp)/'run'
            with self.assertRaises(InterruptedError):train_diagnostic(out,interrupt_after_epochs=1)
            p=out/'inputs-11.json';raw=json.loads(p.read_text());raw['rating_train'][0]['targets']=[1,1];raw['rating_train'][0]['sequence'][0][0]=999;p.write_text(json.dumps(raw))
            with self.assertRaises(ContractError):train_diagnostic(out,resume=True)
        with self.assertRaises(ContractError):Adam.restore(dict(m=[0],v=[-1],step=1,rate=.01),1)
