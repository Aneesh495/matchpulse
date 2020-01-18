"""Canonical envelopes use UTC instants and normalized 120 by 80 pitch units."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import math
import re
from typing import Any


class ContractError(ValueError):
    pass


def canonical(value: Any) -> str:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (ValueError, TypeError) as exc:
        raise ContractError("nonfinite or unserializable value") from exc


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def instant(value: str) -> str:
    if not isinstance(value, str):
        raise ContractError("timestamp must be an ISO UTC string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ContractError("invalid timestamp") from exc
    if parsed.tzinfo is None:
        raise ContractError("timezone required")
    return parsed.astimezone(timezone.utc).isoformat(timespec="microseconds")


def identifier(value: str, label: str = "id") -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", value):
        raise ContractError(f"invalid {label}")
    return value


def finite(value: Any, low: float, high: float, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ContractError(f"{label} must be numeric")
    if not math.isfinite(value) or not low <= value <= high:
        raise ContractError(f"{label} outside [{low}, {high}]")
    return float(value)


KINDS = frozenset({"lineup", "pass", "carry", "shot", "save", "goal", "own_goal",
    "recovery", "duel", "pressure", "loss", "yellow", "red", "substitution",
    "role", "phase", "end", "retract", "foul", "offside", "clearance"})
ROLES = frozenset({"GK", "CB", "FB", "DM", "CM", "AM", "WG", "ST"})
MODES = frozenset({"synthetic", "archive", "delayed", "live"})


@dataclass(frozen=True)
class Envelope:
    match_id: str
    event_id: str
    revision: int
    ordinal: int
    occurred_at: str
    published_at: str | None
    received_at: str
    provider: str
    license_id: str
    mode: str
    kind: str
    team_id: str | None = None
    player_id: str | None = None
    period: int = 1
    second: float = 0.0
    payload: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def parse(cls, raw: dict[str, Any]) -> Envelope:
        if not isinstance(raw, dict):
            raise ContractError("event must be an object")
        try:
            e = cls(**raw)
        except TypeError as exc:
            raise ContractError(str(exc)) from exc
        for name in ("match_id", "event_id", "provider", "license_id"):
            identifier(getattr(e, name), name)
        for name in ("team_id", "player_id"):
            if getattr(e, name) is not None:
                identifier(getattr(e, name), name)
        for name in ("revision", "ordinal", "period"):
            n = getattr(e, name)
            if type(n) is not int or n < 1:
                raise ContractError(f"{name} must be a positive integer")
        if e.period > 5 or e.ordinal > 1000000 or e.revision > 100000:
            raise ContractError("bounded match envelope exceeded")
        if e.kind not in KINDS or e.mode not in MODES:
            raise ContractError("unsupported kind or mode")
        for name in ("occurred_at", "received_at"):
            instant(getattr(e, name))
        if e.published_at is not None:
            if instant(e.published_at) > instant(e.received_at):
                raise ContractError("publication cannot follow receipt")
        if instant(e.occurred_at) > instant(e.received_at):
            raise ContractError("occurrence cannot follow receipt")
        finite(e.second, 0, 10800, "second")
        if not isinstance(e.payload, dict) or len(canonical(e.payload)) > 65536:
            raise ContractError("invalid or oversized payload")
        for key in ("x", "end_x"):
            if key in e.payload:
                finite(e.payload[key], 0, 120, key)
        for key in ("y", "end_y"):
            if key in e.payload:
                finite(e.payload[key], 0, 80, key)
        if "xg" in e.payload:
            finite(e.payload["xg"], 0, 1, "xg")
            if not e.payload.get("xg_definition"):
                raise ContractError("xG needs a model definition")
        if e.kind in {"role", "lineup"} and e.payload.get("role") not in ROLES:
            raise ContractError("role required")
        if e.kind == "retract":
            identifier(e.payload.get("target"), "retraction target")
        return cls(**{**asdict(e), "occurred_at": instant(e.occurred_at),
            "published_at": instant(e.published_at) if e.published_at else None,
            "received_at": instant(e.received_at)})

    def wire(self) -> dict[str, Any]:
        return asdict(self)

    def fact_hash(self) -> str:
        value = self.wire()
        value.pop("received_at")
        return digest(value)

    @property
    def clock(self) -> tuple[int, float, int, str]:
        return self.period, self.second, self.ordinal, self.event_id


@dataclass(frozen=True)
class Feature:
    name: str
    value: float | None
    known_at: str
    source_id: str
    support: str = "observed"

    def as_of(self, cutoff: str) -> float | None:
        if instant(self.known_at) > instant(cutoff):
            raise ContractError(f"future feature: {self.name}")
        if self.support not in {"observed", "estimated", "unsupported", "missing"}:
            raise ContractError("unknown support status")
        if self.value is None:
            return None
        finite(self.value, -1e12, 1e12, self.name)
        if self.support in {"unsupported", "missing"}:
            raise ContractError("unsupported feature has a value")
        return self.value
