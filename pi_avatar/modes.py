import random
import time
from dataclasses import dataclass
from datetime import datetime, time as day_time, timedelta
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class AvatarDecision:
    state: str
    detail: str = ""
    fps_override: float | None = None
    source_value: object | None = None


def evaluate(config, value=None, now=None, routine_state=None):
    mode_type = config.mode["type"]
    if mode_type == "value":
        return evaluate_value(config, value)
    if mode_type == "time":
        return evaluate_time(config, now=now)
    return evaluate_routine(config, routine_state=routine_state)


def evaluate_value(config, value):
    for rule in config.mode["rules"]:
        when = rule.get("when")
        if when is None or _matches(value, when):
            return _decision_from_item(rule, config, source_value=value)
    return AvatarDecision(config.default_state, source_value=value)


def _matches(value, when):
    if not isinstance(when, dict):
        return False
    try:
        if "lt" in when and not value < when["lt"]:
            return False
        if "lte" in when and not value <= when["lte"]:
            return False
        if "gt" in when and not value > when["gt"]:
            return False
        if "gte" in when and not value >= when["gte"]:
            return False
        if "min" in when and not value >= when["min"]:
            return False
        if "max" in when and not value <= when["max"]:
            return False
    except TypeError:
        return False
    if "eq" in when and not value == when["eq"]:
        return False
    if "contains" in when and str(when["contains"]) not in str(value):
        return False
    return True


def evaluate_time(config, now=None):
    mode = config.mode
    zone_name = mode.get("timezone")
    tz = ZoneInfo(zone_name) if zone_name else None
    current = now or datetime.now(tz)
    if tz:
        current = current.astimezone(tz)
    elif current.tzinfo is None:
        current = current.astimezone()

    best = None
    for trigger in mode["triggers"]:
        trigger_at = _nearest_trigger_datetime(current, trigger["time"])
        delta = (trigger_at - current).total_seconds()
        for window in trigger.get("windows", []) or []:
            before = float(window.get("before_seconds", 0))
            after = float(window.get("after_seconds", 0))
            if -after <= delta <= before:
                distance = abs(delta)
                if best is None or distance <= best[0]:
                    best = (distance, window, trigger, delta)

    if best:
        _distance, window, trigger, delta = best
        item = dict(window)
        item.setdefault("detail", trigger.get("detail", f"{trigger['time']} trigger"))
        if "{seconds}" in item.get("detail", ""):
            item["detail"] = item["detail"].format(seconds=max(0, int(delta)))
        return _decision_from_item(item, config)

    fallback = mode.get("fallback", {"state": config.default_state})
    return _decision_from_item(fallback, config)


def _nearest_trigger_datetime(current, value):
    hour, minute, second = _parse_time(value)
    base = current.replace(hour=hour, minute=minute, second=second, microsecond=0)
    candidates = [base - timedelta(days=1), base, base + timedelta(days=1)]
    return min(candidates, key=lambda item: abs((item - current).total_seconds()))


def _parse_time(value):
    parts = str(value).split(":")
    if len(parts) not in (2, 3):
        raise ValueError(f"Invalid trigger time: {value}")
    hour = int(parts[0])
    minute = int(parts[1])
    second = int(parts[2]) if len(parts) == 3 else 0
    day_time(hour, minute, second)
    return hour, minute, second


class RoutineState:
    def __init__(self, seed=None):
        self.index = -1
        self.step_started = 0.0
        self.random = random.Random(seed)


def evaluate_routine(config, routine_state=None):
    routine_state = routine_state or RoutineState()
    steps = config.mode["steps"]
    now = time.time()
    current = steps[routine_state.index] if routine_state.index >= 0 else None
    duration = float(current.get("duration_seconds", 1)) if current else 0

    if current is None or now - routine_state.step_started >= duration:
        routine_state.index = _next_routine_index(config, routine_state)
        routine_state.step_started = now
        current = steps[routine_state.index]

    return _decision_from_item(current, config)


def _next_routine_index(config, routine_state):
    steps = config.mode["steps"]
    strategy = config.mode.get("strategy", "sequence")
    if strategy == "sequence":
        return (routine_state.index + 1) % len(steps)
    if strategy == "random":
        return routine_state.random.randrange(len(steps))
    weights = [float(step.get("weight", 1)) for step in steps]
    return routine_state.random.choices(range(len(steps)), weights=weights, k=1)[0]


def _decision_from_item(item, config, source_value=None):
    return AvatarDecision(
        state=item.get("state", config.default_state),
        detail=item.get("detail", ""),
        fps_override=item.get("fps"),
        source_value=source_value,
    )
