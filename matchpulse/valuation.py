"""Fee observations and conditional research estimates have different types."""
from __future__ import annotations
from dataclasses import dataclass, asdict
from datetime import datetime
import math
from .contracts import ContractError, canonical, digest, finite, identifier, instant

VALUE_MODEL = "synthetic-persistence-residual-v1"
TARGET = "guaranteed consideration conditional on a reported permanent move in next window"


@dataclass(frozen=True)
class Deal:
    id: str
    person_id: str
    kind: str
    disclosure: str
    effective_at: str
    known_at: str
    currency: str
    guaranteed: float | None
    lower: float | None
    upper: float | None
    addons_upper: float | None
    source_url: str
    source_id: str
    mode: str
    publication_precision: str = "instant"
    ancillary_costs: float | None = None
    wage: float | None = None

    @classmethod
    def parse(cls, raw: dict) -> Deal:
        try:
            d = cls(**raw)
        except TypeError as exc:
            raise ContractError(str(exc)) from exc
        for v in (d.id, d.person_id, d.source_id):
            identifier(v)
        instant(d.effective_at); instant(d.known_at)
        if d.kind not in {"permanent", "loan", "free", "swap", "none"}:
            raise ContractError("unknown deal kind")
        if d.disclosure not in {"exact", "interval", "undisclosed", "not-applicable"}:
            raise ContractError("unknown fee disclosure")
        if d.currency not in {"EUR", "GBP", "USD"} or d.mode not in {"synthetic", "archive"}:
            raise ContractError("unsupported currency or observation mode")
        if not d.source_url.startswith("https://"):
            raise ContractError("deal needs evidence URL")
        for k in ("guaranteed", "lower", "upper", "addons_upper", "ancillary_costs", "wage"):
            v = getattr(d, k)
            if v is not None:
                finite(v, 0, 1e10, k)
        if d.disclosure == "undisclosed" and any(v is not None for v in (d.guaranteed, d.lower, d.upper)):
            raise ContractError("undisclosed fee cannot contain an invented value")
        if d.disclosure == "exact" and d.guaranteed is None:
            raise ContractError("exact disclosure needs guaranteed amount")
        if d.disclosure == "interval":
            if d.guaranteed is not None or d.lower is None or d.upper is None or d.upper < d.lower:
                raise ContractError("invalid censored interval")
        if d.kind == "none" and (d.disclosure != "not-applicable" or d.guaranteed is not None):
            raise ContractError("no move has no observed fee")
        if d.kind == "free" and (d.disclosure != "exact" or d.guaranteed != 0):
            raise ContractError("free move must have explicit zero guaranteed fee")
        if d.publication_precision not in {"instant", "day-conservative"}:
            raise ContractError("unknown publication precision")
        return d

    def wire(self) -> dict:
        return asdict(self)

    @property
    def comparable(self) -> bool:
        return self.kind in {"permanent", "free"}


@dataclass(frozen=True)
class FXVintage:
    currency: str
    eur_per_unit: float
    rate_date: str
    known_at: str
    source: str

    def convert(self, amount: float, cutoff: str) -> float:
        if instant(self.known_at) > instant(cutoff):
            raise ContractError("future FX vintage")
        finite(self.eur_per_unit, 0.00001, 100000, "FX rate")
        finite(amount, 0, 1e10, "amount")
        return amount * self.eur_per_unit


def diagnostic_estimate(person: dict, rating: dict, previous: dict | None, match: dict) -> dict:
    """An explicit synthetic residual demonstration, never a real-money model."""
    base = person.get("synthetic_prior_eur")
    available = match["mode"] == "synthetic" and base is not None and rating["rating"] is not None
    common = dict(person_id=person["id"], name=person["name"], team_id=person["team_id"],
        role=rating["role"], match_id=match["id"], known_at=match["known_at"],
        model_id=VALUE_MODEL, currency="EUR", price_vintage=match["date"],
        horizon="next transfer window", target=TARGET, mode=match["mode"],
        reason="Synthetic diagnostic only; not calibrated to actual transfers",
        source_version=match["version"], rating_model_id=match["model_id"],
        observed_fee=None)
    if not available:
        return {**common, "status": "unavailable", "median": None, "interval": None,
            "prior_interval": None, "delta": None, "move_probability": None,
            "attribution": [], "reason": "No validated fee model or eligible evidence"}
    finite(base, 0, 1e9, "prior")
    # Recompute against the fixture's frozen prior. Revisions do not compound a match twice.
    shrink = rating["minutes"] / (rating["minutes"] + 900)
    residual = max(-0.015, min(0.015, rating["contribution"] * shrink * 0.08))
    median = round(base * math.exp(residual), 2)
    interval = [round(median * 0.45, 2), round(median * 2.2, 2)]
    old = previous["median"] if previous and previous.get("median") is not None else base
    return {**common, "status": "unchanged" if median == old else "diagnostic",
        "median": median, "interval": interval,
        "prior_interval": previous["interval"] if previous else [base * 0.45, base * 2.2],
        "delta": round(median - old, 2), "move_probability": 0.12,
        "attribution": [dict(feature="frozen synthetic prior", value=base),
            dict(feature="exposure-shrunk match residual", value=round(median-base, 2))]}
