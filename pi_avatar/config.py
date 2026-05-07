from dataclasses import dataclass
from datetime import time as day_time
from pathlib import Path

import yaml

from .constants import (
    DEFAULT_ASSET_DIR,
    DEFAULT_CONFIG_FILE,
    DEFAULT_ENV_FILE,
    DEFAULT_STATE,
    DEFAULT_STATE_FILE,
    STATE_FPS,
    VALID_STATES,
)


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class AvatarConfig:
    state_file: Path
    asset_dir: Path
    default_state: str
    states: list[str]
    state_fps: dict[str, float]


@dataclass(frozen=True)
class SourceConfig:
    type: str
    path: Path | None = None
    url: str | None = None
    poll_seconds: float = 1.0
    timeout_seconds: float = 2.0
    stale_seconds: float | None = None


@dataclass(frozen=True)
class ParserConfig:
    type: str = "raw"
    path: str | None = None
    pattern: str | None = None
    group: int | str = 1
    cast: str = "string"


@dataclass(frozen=True)
class DisplayConfig:
    pi_enabled: bool = True
    width: int = 800
    height: int = 480
    fullscreen: bool = True
    framebuffer: str = "/dev/fb0"
    background_color: str = "#000000"
    show_detail: bool = True
    scale_mode: str = "contain"


@dataclass(frozen=True)
class WebConfig:
    host: str = "0.0.0.0"
    port: int = 8080


@dataclass(frozen=True)
class Config:
    config_file: Path
    env_file: Path
    avatar: AvatarConfig
    source: SourceConfig
    parser: ParserConfig
    mode: dict
    display: DisplayConfig
    web: WebConfig

    @property
    def state_file(self):
        return self.avatar.state_file

    @property
    def asset_dir(self):
        return self.avatar.asset_dir

    @property
    def states(self):
        return self.avatar.states

    @property
    def default_state(self):
        return self.avatar.default_state

    @property
    def state_fps(self):
        return self.avatar.state_fps


def _path(value, default):
    return Path(value) if value not in (None, "") else Path(default)


def _positive_float(value, field):
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ConfigError(f"{field} must be a number") from exc
    if parsed <= 0:
        raise ConfigError(f"{field} must be positive")
    return parsed


def _nonnegative_float(value, field):
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ConfigError(f"{field} must be a number") from exc
    if parsed < 0:
        raise ConfigError(f"{field} must be non-negative")
    return parsed


def _bool(value, field):
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in ("1", "true", "yes", "on"):
            return True
        if lowered in ("0", "false", "no", "off"):
            return False
    raise ConfigError(f"{field} must be a boolean")


def _positive_int(value, field):
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ConfigError(f"{field} must be an integer") from exc
    if parsed <= 0:
        raise ConfigError(f"{field} must be positive")
    return parsed


def _validate_time(value, field):
    try:
        parts = [int(part) for part in str(value).split(":")]
        if len(parts) == 2:
            day_time(parts[0], parts[1])
        elif len(parts) == 3:
            day_time(parts[0], parts[1], parts[2])
        else:
            raise ValueError
    except ValueError as exc:
        raise ConfigError(f"{field} must be HH:MM or HH:MM:SS") from exc


def _load_yaml(path):
    if not Path(path).exists():
        return {}
    try:
        data = yaml.safe_load(Path(path).read_text())
    except yaml.YAMLError as exc:
        raise ConfigError(f"Invalid YAML in {path}: {exc}") from exc
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ConfigError("Config root must be a mapping")
    return data


def _avatar_config(data, env):
    raw = data.get("avatar", {}) or {}
    if not isinstance(raw, dict):
        raise ConfigError("avatar must be a mapping")

    states = list(raw.get("states") or VALID_STATES)
    if not states or not all(isinstance(state, str) and state for state in states):
        raise ConfigError("avatar.states must be a non-empty list of state names")

    default_state = raw.get("default_state", DEFAULT_STATE)
    if default_state not in states:
        raise ConfigError("avatar.default_state must be included in avatar.states")

    state_fps = {state: float(fps) for state, fps in STATE_FPS.items() if state in states}
    for state, fps in (raw.get("state_fps", {}) or {}).items():
        if state not in states:
            raise ConfigError(f"state_fps references unknown state: {state}")
        state_fps[state] = _positive_float(fps, f"state_fps.{state}")

    return AvatarConfig(
        state_file=_path(env.get("STATE_FILE", raw.get("state_file")), DEFAULT_STATE_FILE),
        asset_dir=_path(env.get("ASSET_DIR", raw.get("asset_dir")), DEFAULT_ASSET_DIR),
        default_state=default_state,
        states=states,
        state_fps=state_fps,
    )


def _source_config(data):
    raw = data.get("source", {}) or {}
    if not isinstance(raw, dict):
        raise ConfigError("source must be a mapping")

    source_type = raw.get("type", "none")
    if source_type not in ("none", "file", "url"):
        raise ConfigError("source.type must be one of: none, file, url")

    path = raw.get("path")
    url = raw.get("url")
    if source_type == "file" and not path:
        raise ConfigError("source.path is required for file sources")
    if source_type == "url" and not url:
        raise ConfigError("source.url is required for url sources")

    stale_seconds = raw.get("stale_seconds")
    return SourceConfig(
        type=source_type,
        path=Path(path) if path else None,
        url=url,
        poll_seconds=_positive_float(raw.get("poll_seconds", 1.0), "source.poll_seconds"),
        timeout_seconds=_positive_float(raw.get("timeout_seconds", 2.0), "source.timeout_seconds"),
        stale_seconds=None if stale_seconds in (None, "") else _positive_float(stale_seconds, "source.stale_seconds"),
    )


def _parser_config(data):
    raw = data.get("parser", {}) or {}
    if not isinstance(raw, dict):
        raise ConfigError("parser must be a mapping")

    parser_type = raw.get("type", "raw")
    if parser_type not in ("raw", "json_path", "regex"):
        raise ConfigError("parser.type must be one of: raw, json_path, regex")
    if parser_type == "json_path" and not raw.get("path"):
        raise ConfigError("parser.path is required for json_path")
    if parser_type == "regex" and not raw.get("pattern"):
        raise ConfigError("parser.pattern is required for regex")

    cast = raw.get("cast", "string")
    if cast not in ("string", "number", "bool"):
        raise ConfigError("parser.cast must be one of: string, number, bool")

    return ParserConfig(
        type=parser_type,
        path=raw.get("path"),
        pattern=raw.get("pattern"),
        group=raw.get("group", 1),
        cast=cast,
    )


def _display_config(data):
    raw = data.get("display", {}) or {}
    if not isinstance(raw, dict):
        raise ConfigError("display must be a mapping")

    scale_mode = raw.get("scale_mode", "contain")
    if scale_mode not in ("contain", "cover", "stretch"):
        raise ConfigError("display.scale_mode must be one of: contain, cover, stretch")

    return DisplayConfig(
        pi_enabled=_bool(raw.get("pi_enabled", True), "display.pi_enabled"),
        width=_positive_int(raw.get("width", 800), "display.width"),
        height=_positive_int(raw.get("height", 480), "display.height"),
        fullscreen=_bool(raw.get("fullscreen", True), "display.fullscreen"),
        framebuffer=str(raw.get("framebuffer", "/dev/fb0") or "/dev/fb0"),
        background_color=str(raw.get("background_color", "#000000") or "#000000"),
        show_detail=_bool(raw.get("show_detail", True), "display.show_detail"),
        scale_mode=scale_mode,
    )


def _web_config(data):
    raw = data.get("web", {}) or {}
    if not isinstance(raw, dict):
        raise ConfigError("web must be a mapping")

    host = str(raw.get("host", "0.0.0.0") or "0.0.0.0")
    return WebConfig(
        host=host,
        port=_positive_int(raw.get("port", 8080), "web.port"),
    )


def _mode_config(data, avatar):
    raw = data.get("mode", {"type": "routine", "steps": [{"state": avatar.default_state, "duration_seconds": 10}]})
    if not isinstance(raw, dict):
        raise ConfigError("mode must be a mapping")

    mode_type = raw.get("type")
    if mode_type not in ("time", "value", "routine"):
        raise ConfigError("mode.type must be one of: time, value, routine")

    def check_state(item, context):
        state = item.get("state", avatar.default_state)
        if state not in avatar.states:
            raise ConfigError(f"{context} references unknown state: {state}")

    if mode_type == "value":
        rules = raw.get("rules")
        if not isinstance(rules, list) or not rules:
            raise ConfigError("mode.rules must be a non-empty list for value mode")
        for index, rule in enumerate(rules):
            if not isinstance(rule, dict):
                raise ConfigError(f"mode.rules[{index}] must be a mapping")
            when = rule.get("when")
            if when is not None and not isinstance(when, dict):
                raise ConfigError(f"mode.rules[{index}].when must be a mapping")
            check_state(rule, f"mode.rules[{index}]")
    elif mode_type == "routine":
        steps = raw.get("steps")
        if not isinstance(steps, list) or not steps:
            raise ConfigError("mode.steps must be a non-empty list for routine mode")
        if raw.get("strategy", "sequence") not in ("sequence", "random", "weighted_random"):
            raise ConfigError("mode.strategy must be one of: sequence, random, weighted_random")
        for index, step in enumerate(steps):
            if not isinstance(step, dict):
                raise ConfigError(f"mode.steps[{index}] must be a mapping")
            check_state(step, f"mode.steps[{index}]")
            _positive_float(step.get("duration_seconds", 1), f"mode.steps[{index}].duration_seconds")
            if "weight" in step:
                _positive_float(step["weight"], f"mode.steps[{index}].weight")
    else:
        triggers = raw.get("triggers")
        if not isinstance(triggers, list) or not triggers:
            raise ConfigError("mode.triggers must be a non-empty list for time mode")
        for index, trigger in enumerate(triggers):
            if not isinstance(trigger, dict):
                raise ConfigError(f"mode.triggers[{index}] must be a mapping")
            if not trigger.get("time"):
                raise ConfigError(f"mode.triggers[{index}].time is required")
            _validate_time(trigger["time"], f"mode.triggers[{index}].time")
            for window_index, window in enumerate(trigger.get("windows", []) or []):
                if not isinstance(window, dict):
                    raise ConfigError(f"mode.triggers[{index}].windows[{window_index}] must be a mapping")
                check_state(window, f"mode.triggers[{index}].windows[{window_index}]")
                if "before_seconds" in window:
                    _nonnegative_float(
                        window["before_seconds"],
                        f"mode.triggers[{index}].windows[{window_index}].before_seconds",
                    )
                if "after_seconds" in window:
                    _nonnegative_float(
                        window["after_seconds"],
                        f"mode.triggers[{index}].windows[{window_index}].after_seconds",
                    )

    return raw


def load_config(env=None, path=None):
    env = env or {}
    config_file = _path(path or env.get("CONFIG_FILE"), DEFAULT_CONFIG_FILE)
    data = _load_yaml(config_file)
    avatar = _avatar_config(data, env)

    return Config(
        config_file=config_file,
        env_file=_path(env.get("ENV_FILE"), DEFAULT_ENV_FILE),
        avatar=avatar,
        source=_source_config(data),
        parser=_parser_config(data),
        mode=_mode_config(data, avatar),
        display=_display_config(data),
        web=_web_config(data),
    )
