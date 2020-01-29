"""Forward-only contribution baseline with exposure shrinkage and explicit support."""
from __future__ import annotations
from dataclasses import asdict, dataclass, field
import math
from typing import Callable
from .contracts import ContractError, Envelope, ROLES

MODEL_ID = "contribution-context-v1"
ROLE_PRIOR = {"GK": 0.0, "CB": 0.0, "FB": 0.0, "DM": 0.0,
              "CM": 0.0, "AM": 0.0, "WG": 0.0, "ST": 0.0}
SUPPORT = {"goals": "observed", "shots": "conditional", "passing": "conditional",
    "carrying": "conditional", "cards": "observed", "role": "sourced",
    "xg": "provider-defined only", "off_ball_runs": "unsupported",
    "intent": "unsupported", "physical_load": "unsupported", "tracking": "unsupported",
    "passing_options": "unsupported", "defensive_coverage": "unsupported"}


def sigmoid(x: float) -> float:
    if x >= 0:
        return 1 / (1 + math.exp(-min(x, 700)))
    ex = math.exp(max(x, -700))
    return ex / (1 + ex)


def context_probability(x: float, y: float, score_diff: int, advantage: int) -> tuple[float, float]:
    """Uncalibrated local reference: near-term score/concede opportunity proxies."""
    distance = math.hypot(120 - x, (40 - y) * 0.6)
    score = sigmoid(-1.9 - distance / 22 - score_diff * 0.04 + advantage * 0.12)
    concede = sigmoid(-5.2 + (120 - x) / 35 + score_diff * 0.04 - advantage * 0.12)
    return score, concede


@dataclass
class PlayerState:
    id: str
    name: str
    team_id: str
    role: str
    active: bool = False
    appeared: bool = False
    minutes: float = 0.0
    contribution: float = 0.0
    reasons: list[dict] = field(default_factory=list)
    red: bool = False
    role_history: list[dict] = field(default_factory=list)

    def view(self, final: bool, trusted: bool) -> dict:
        m = self.minutes
        has_rating = self.appeared and m > 0
        shrunk = self.contribution / math.sqrt((m + 30) / 90)
        rating = 6 + 2 * math.tanh(shrunk * 2.5) if has_rating else None
        radius = min(3.0, 1.96 * math.sqrt(30 / (m + 30)) + 0.25) if has_rating else None
        status = "nonparticipant" if not self.appeared else ("provisional" if not final or m < 15 or not trusted else "final-baseline")
        return {"id": self.id, "name": self.name, "team_id": self.team_id, "role": self.role,
            "minutes": round(m, 4), "active": self.active, "red": self.red,
            "rating": round(rating, 4) if has_rating else None,
            "interval": [round(max(0, rating - radius), 4), round(min(10, rating + radius), 4)] if has_rating else None,
            "contribution": round(self.contribution, 8), "status": status,
            "uncertainty": "Uncalibrated event-only support band; off-ball context unavailable",
            "reasons": sorted(self.reasons, key=lambda r: abs(r["value"]), reverse=True)[:12],
            "role_history": self.role_history}


def effective_events(events: list[Envelope]) -> tuple[list[Envelope], list[dict]]:
    latest: dict[tuple[str, str], Envelope] = {}
    changes = []
    for e in events:
        key = (e.provider, e.event_id)
        old = latest.get(key)
        if old is None or e.revision > old.revision:
            latest[key] = e
            if old:
                changes.append({"kind": "revision", "event_id": e.event_id,
                    "old_revision": old.revision, "new_revision": e.revision})
    removed = set()
    for e in latest.values():
        if e.kind == "retract":
            target = (e.provider, e.payload["target"])
            if target not in latest:
                changes.append({"kind": "pending-retraction", "event_id": e.event_id, "target": target[1]})
            removed.add(target)
            changes.append({"kind": "retraction", "event_id": e.event_id, "target": target[1], "reason": e.payload.get("reason", "provider correction")})
    return sorted((e for k, e in latest.items() if k not in removed and e.kind != "retract"), key=lambda e: e.clock), changes


class RatingReducer:
    def __init__(self, fixture: dict, probability: Callable = context_probability, model_id: str = MODEL_ID):
        self.fixture = fixture
        self.probability = probability
        self.model_id = model_id

    def run(self, envelopes: list[Envelope]) -> dict:
        events, corrections = effective_events(envelopes)
        teams = [self.fixture["home_id"], self.fixture["away_id"]]
        players = {p["id"]: PlayerState(p["id"], p["name"], p["team_id"], p["role"]) for p in self.fixture.get("players", [])}
        score, reds = dict.fromkeys(teams, 0), dict.fromkeys(teams, 0)
        last_period, last_second, elapsed = 1, 0.0, 0.0
        final, interrupted = False, False
        action_values, unsupported = [], set()
        for e in events:
            if e.period == 5:
                # Shootouts never change regulation score or individual match contribution.
                continue
            if e.period < last_period:
                raise ContractError("event ordering invariant")
            dt = e.second - last_second if e.period == last_period else e.second
            if dt < 0:
                raise ContractError("negative elapsed exposure")
            for p in players.values():
                if p.active:
                    p.minutes += dt / 60
            elapsed += dt
            last_period, last_second = e.period, e.second
            if final and e.kind not in {"end", "phase"}:
                raise ContractError("action after match end")
            if e.kind == "lineup":
                if not e.player_id or e.player_id not in players:
                    raise ContractError("lineup player outside fixture roster")
                p = players[e.player_id]
                p.role = e.payload["role"]
                p.active = e.payload.get("starter", True)
                p.appeared = p.active
                p.role_history.append(dict(period=e.period, second=e.second, role=p.role))
                continue
            if e.kind == "substitution":
                off, on = players.get(e.payload.get("off")), players.get(e.payload.get("on"))
                if off is None or on is None or not off.active or on.active or on.appeared or off.team_id != on.team_id:
                    raise ContractError("invalid substitution")
                off.active, on.active, on.appeared = False, True, True
                on.role = e.payload.get("role", off.role)
                if on.role not in ROLES:
                    raise ContractError("invalid replacement role")
                on.role_history.append(dict(period=e.period, second=e.second, role=on.role))
                continue
            if e.kind == "end":
                final = not e.payload.get("interrupted", False)
                interrupted = not final
                continue
            if e.kind == "phase":
                continue
            p = players.get(e.player_id)
            if p is None:
                unsupported.add(e.kind)
                continue
            if e.team_id != p.team_id or not p.active:
                raise ContractError("action by inactive player or wrong team")
            if e.kind == "role":
                p.role = e.payload["role"]
                p.role_history.append(dict(period=e.period, second=e.second, role=p.role))
                p.reasons.append(dict(event_id=e.event_id, revision=e.revision, code="ROLE_REVISED", value=0.0))
                continue
            opponent = teams[1] if p.team_id == teams[0] else teams[0]
            diff = score[p.team_id] - score[opponent]
            advantage = reds[opponent] - reds[p.team_id]
            data = e.payload
            x, y = data.get("x"), data.get("y")
            before, after, value, reason = None, None, 0.0, e.kind.upper()
            if e.kind in {"pass", "carry", "loss", "recovery", "duel", "clearance", "pressure"}:
                if x is None or y is None:
                    unsupported.add(e.kind + ":location")
                    continue
                before = self.probability(x, y, diff, advantage)
                ex, ey = data.get("end_x", x), data.get("end_y", y)
                success = data.get("success")
                if success is None and e.kind in {"pass", "duel"}:
                    unsupported.add(e.kind + ":outcome")
                    continue
                lost = e.kind == "loss" or success is False
                after = self.probability(ex, ey, diff, advantage)
                if lost:
                    after = (-after[1], -after[0])
                value = (after[0] - before[0]) - (after[1] - before[1])
                if e.kind == "pressure":
                    # Event-only pressure lacks causal recovery assignment.
                    value = 0.0
                    reason = "PRESSURE_CONTEXT_UNSUPPORTED"
            elif e.kind in {"shot", "goal"}:
                xg = data.get("xg")
                outcome = 1 if e.kind == "goal" or data.get("outcome") == "goal" else 0
                if xg is None:
                    unsupported.add("shot:xg")
                    value = 0.0
                    reason = "GOAL_QUALITY_UNAVAILABLE" if outcome else "SHOT_QUALITY_UNAVAILABLE"
                else:
                    opportunity = self.probability(x or 100, y or 40, diff, advantage)[0]
                    value = (xg - opportunity) + 0.5 * (outcome - xg)
                    before, after = [opportunity, 0], [xg, 0]
                    reason = "SHOT_QUALITY_PLUS_OUTCOME_RESIDUAL"
                score[p.team_id] += outcome
            elif e.kind == "save":
                if p.role != "GK":
                    reason = "OUTFIELD_SAVE_PROVISIONAL"
                xg = data.get("xg")
                if xg is None:
                    unsupported.add("save:quality")
                    continue
                value = 0.5 * xg
                reason = "SAVE_QUALITY_RESIDUAL"
            elif e.kind == "own_goal":
                score[opponent] += 1
                value, reason = -0.3, "OWN_GOAL_ASSOCIATION"
            elif e.kind == "red":
                if p.red:
                    raise ContractError("duplicate dismissal without revision")
                reds[p.team_id] += 1
                p.red, p.active = True, False
                value, reason = -0.18, "DISMISSAL_BASELINE"
            elif e.kind == "yellow":
                value, reason = -0.02, "CAUTION_BASELINE"
            elif e.kind == "foul":
                value, reason = -0.01, "FOUL_BASELINE"
            elif e.kind == "offside":
                value, reason = -0.01, "OFFSIDE_BASELINE"
            record = dict(event_id=e.event_id, revision=e.revision, player_id=p.id,
                role=p.role, code=reason, value=round(value, 10), before=before, after=after,
                known_at=e.received_at, occurred_at=e.occurred_at, source=e.license_id)
            p.contribution += value
            p.reasons.append(record)
            action_values.append(record)
        trusted = self.fixture.get("trusted", False)
        return dict(id=self.fixture["id"], home=self.fixture["home"], away=self.fixture["away"],
            home_id=teams[0], away_id=teams[1], competition=self.fixture.get("competition", "Unknown"),
            mode=self.fixture["mode"], date=self.fixture.get("date"), score=[score[t] for t in teams],
            period=last_period, second=last_second, elapsed_seconds=elapsed,
            status="finished" if final else "interrupted" if interrupted else "in-progress" if events else "scheduled",
            players=[p.view(final, trusted) for p in players.values()], corrections=corrections,
            model_id=self.model_id, support=SUPPORT, unsupported_events=sorted(unsupported),
            action_values=action_values, event_count=len(events), received_count=len(envelopes),
            known_at=max((e.received_at for e in envelopes), default=None),
            latest_occurred_at=max((e.occurred_at for e in events), default=None))
