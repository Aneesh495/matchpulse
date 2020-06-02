"""Source-bound contract, registration and coarse availability assertions."""
from __future__ import annotations
from dataclasses import asdict, dataclass
import json
from .contracts import ContractError, ROLES, canonical, finite, identifier, instant
from .storage import Store


@dataclass(frozen=True)
class ContextFact:
    id: str
    revision: int
    person_id: str
    kind: str
    valid_from: str
    valid_to: str | None
    known_at: str
    source_id: str
    source_url: str
    confidence: float
    details: dict
    withdrawn: bool = False

    @classmethod
    def parse(cls, raw: dict) -> ContextFact:
        try:
            fact = cls(**raw)
        except TypeError as exc:
            raise ContractError(str(exc)) from exc
        for key in ('id', 'person_id', 'source_id'):
            identifier(getattr(fact, key), key)
        if type(fact.revision) is not int or not 1 <= fact.revision <= 100000:
            raise ContractError('invalid context revision')
        if type(fact.withdrawn) is not bool:
            raise ContractError('withdrawn must be Boolean')
        start, end = instant(fact.valid_from), instant(fact.valid_to) if fact.valid_to else None
        if end and end <= start:
            raise ContractError('empty context interval')
        known = instant(fact.known_at)
        finite(fact.confidence, 0, 1, 'source confidence')
        if not isinstance(fact.source_url, str) or not fact.source_url.startswith('https://') or len(fact.source_url) > 2048:
            raise ContractError('context needs a bounded HTTPS evidence URL')
        if not isinstance(fact.details, dict) or len(canonical(fact.details)) > 4096:
            raise ContractError('invalid context details')
        allowed = {
            'contract': {'team_id', 'expires_at'},
            'registration': {'team_id', 'registration_kind', 'parent_team_id'},
            'availability': {'status'},
            'role': {'team_id', 'role'},
        }
        if fact.kind not in allowed or set(fact.details) - allowed[fact.kind]:
            raise ContractError('unsupported context kind or fields')
        d = dict(fact.details)
        if fact.kind != 'availability':
            identifier(d.get('team_id'), 'team_id')
        if fact.kind == 'contract':
            d['expires_at'] = instant(d.get('expires_at'))
            if d['expires_at'] <= start:
                raise ContractError('contract expiry precedes its start')
            if end is None or end > d['expires_at']:
                raise ContractError('contract validity must end by its expiry')
        if fact.kind == 'registration':
            if d.get('registration_kind') not in {'active', 'loan', 'youth', 'reserve', 'unknown'}:
                raise ContractError('invalid registration kind')
            if 'parent_team_id' in d:
                identifier(d['parent_team_id'], 'loan parent')
                if d['registration_kind'] != 'loan':
                    raise ContractError('loan parent requires a loan registration')
        if fact.kind == 'availability' and d.get('status') not in {'available', 'injured', 'suspended', 'unknown'}:
            raise ContractError('invalid coarse availability status')
        if fact.kind == 'role' and d.get('role') not in ROLES:
            raise ContractError('invalid sourced role')
        return cls(**{**asdict(fact), 'valid_from': start, 'valid_to': end, 'known_at': known, 'details': d})


class ContextLedger:
    def __init__(self, store: Store):
        self.s = store

    def append(self, raw: dict) -> bool:
        fact = ContextFact.parse(raw)
        source = self.s.source(fact.source_id)
        if fact.known_at < instant(source['acquired_at']):
            raise ContractError('context knowledge predates source acquisition')
        if not self.s.db.execute('SELECT 1 FROM persons WHERE id=?', (fact.person_id,)).fetchone():
            raise ContractError('context needs a canonical person')
        rows = self.s.db.execute('SELECT body FROM context_assertions WHERE id=?', (fact.id,)).fetchall()
        body = canonical(asdict(fact))
        for row in rows:
            prior = json.loads(row[0])
            if (prior['person_id'], prior['kind'], prior['source_id']) != (fact.person_id, fact.kind, fact.source_id):
                raise ContractError('context identity collision')
            if prior['revision'] == fact.revision:
                if row[0] != body:
                    raise ContractError('context revision collision')
                return False
        self.s.db.execute('INSERT INTO context_assertions(id,revision,person_id,kind,known_at,valid_from,valid_to,source_id,body) VALUES(?,?,?,?,?,?,?,?,?)',
            (fact.id, fact.revision, fact.person_id, fact.kind, fact.known_at, fact.valid_from, fact.valid_to, fact.source_id, body))
        return True

    def view(self, person_id: str, valid_at: str, known_at: str) -> dict:
        valid, known = instant(valid_at), instant(known_at)
        selected = {}
        rows = self.s.db.execute('SELECT body FROM context_assertions WHERE person_id=? AND known_at<=? ORDER BY revision DESC,seq DESC', (person_id, known))
        for row in rows:
            fact = json.loads(row[0])
            selected.setdefault(fact['id'], fact)
        # Select the current assertion before interval filtering. A corrected or
        # withdrawn interval cannot resurrect its older version.
        facts = [f for f in selected.values() if not f['withdrawn'] and f['valid_from'] <= valid and (f['valid_to'] is None or valid < f['valid_to'])]
        for f in facts:
            f['mode'] = self.s.source(f['source_id'])['mode']
        grouped = {kind: [f for f in facts if f['kind'] == kind] for kind in ('contract', 'registration', 'availability', 'role')}
        conflicts = [kind for kind, values in grouped.items() if len({canonical(f['details']) for f in values}) > 1]
        return dict(person_id=person_id, valid_at=valid, known_at=known, facts=facts,
            unsupported=[k for k, v in grouped.items() if not v], conflicts=conflicts)
