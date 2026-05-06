import json
from dataclasses import dataclass
from pathlib import Path

from .state import StateWriter


@dataclass(frozen=True)
class AvatarState:
    state: str
    detail: str = ""
    fps_override: float | None = None
    updated: str | None = None
    source_value: object | None = None


@dataclass(frozen=True)
class AnimationState:
    name: str
    frame_paths: list[Path]
    fps: float


class StateStore:
    def __init__(self, config):
        self.config = config
        self.writer = StateWriter(config.state_file)

    def read(self):
        return read_avatar_state(self.config)

    def write(self, state, detail="", fps_override=None, source_value=None):
        return self.writer.write(state, detail, fps_override=fps_override, source_value=source_value)


def frame_sort_key(path):
    stem = path.stem
    return (0, int(stem)) if stem.isdigit() else (1, path.name)


def list_frame_paths(folder):
    folder = Path(folder)
    return sorted(folder.glob("*.png"), key=frame_sort_key) if folder.exists() else []


def read_avatar_state(config):
    try:
        data = json.loads(config.state_file.read_text())
    except Exception:
        offline = "offline" if "offline" in config.states else config.default_state
        return AvatarState(offline, "State file unavailable")

    state = data.get("state", config.default_state)
    if state not in config.states:
        return AvatarState(config.default_state, "Unknown state")

    fps_override = data.get("fps_override")
    try:
        fps_override = None if fps_override in (None, "") else float(fps_override)
    except (TypeError, ValueError):
        fps_override = None

    return AvatarState(
        state=state,
        detail=data.get("detail", ""),
        fps_override=fps_override,
        updated=data.get("updated"),
        source_value=data.get("source_value"),
    )


def load_animation_states(config):
    animations = []
    for state in config.states:
        folder = config.asset_dir / state
        frame_paths = list_frame_paths(folder)
        animations.append(AnimationState(state, frame_paths, config.state_fps.get(state, 8)))
    return animations


def require_default_animation(config, animations):
    for animation in animations:
        if animation.name == config.default_state and animation.frame_paths:
            return
    raise RuntimeError(f"No frames found for default state: {config.default_state}")
