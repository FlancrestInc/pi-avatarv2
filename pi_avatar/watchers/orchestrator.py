import time

from pi_avatar.core import StateStore
from pi_avatar.modes import RoutineState, evaluate
from pi_avatar.parsers import ParseError, parse_value

from .base import SourceReader


class WatcherOrchestrator:
    def __init__(self, config):
        self.config = config
        self.store = StateStore(config)
        self.source_reader = SourceReader(config)
        self.routine_state = RoutineState(seed=config.mode.get("seed"))

    def poll_once(self):
        value = None

        if self.config.source.type != "none":
            source_result = self.source_reader.read()
            if not source_result.ok:
                return self.store.write("offline", source_result.detail)
            try:
                value = parse_value(source_result.content, self.config.parser)
            except ParseError as exc:
                return self.store.write("error", f"Parse error: {exc}")
            if self.source_reader.is_stale():
                return self.store.write("offline", "Source data is stale", source_value=value)

        decision = evaluate(self.config, value=value, routine_state=self.routine_state)
        return self.store.write(
            decision.state,
            decision.detail,
            fps_override=decision.fps_override,
            source_value=decision.source_value,
        )

    def run_forever(self):
        self.store.write("booting", "Avatar monitor starting")
        print(f"monitor starting: config={self.config.config_file}", flush=True)

        while True:
            changed = self.poll_once()
            if changed:
                print(f"state updated: {self.config.state_file}", flush=True)
            time.sleep(self.config.source.poll_seconds)

