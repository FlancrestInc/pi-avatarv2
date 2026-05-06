#!/usr/bin/env python3

import argparse
import os
import time

from pi_avatar.config import ConfigError, load_config
from pi_avatar.modes import RoutineState, evaluate
from pi_avatar.parsers import ParseError, parse_value
from pi_avatar.sources import SourceReader
from pi_avatar.state import StateWriter


def poll_once(config, source_reader, writer, routine_state):
    value = None

    if config.source.type != "none":
        source_result = source_reader.read()
        if not source_result.ok:
            return writer.write("offline", source_result.detail)
        try:
            value = parse_value(source_result.content, config.parser)
        except ParseError as exc:
            return writer.write("error", f"Parse error: {exc}")
        if source_reader.is_stale():
            return writer.write("offline", "Source data is stale", source_value=value)

    decision = evaluate(config, value=value, routine_state=routine_state)
    return writer.write(
        decision.state,
        decision.detail,
        fps_override=decision.fps_override,
        source_value=decision.source_value,
    )


def run_monitor(config):
    writer = StateWriter(config.state_file)
    source_reader = SourceReader(config)
    routine_state = RoutineState(seed=config.mode.get("seed"))
    writer.write("booting", "Avatar monitor starting")
    print(f"monitor starting: config={config.config_file}", flush=True)

    while True:
        changed = poll_once(config, source_reader, writer, routine_state)
        if changed:
            print(f"state updated: {config.state_file}", flush=True)
        time.sleep(config.source.poll_seconds)


def main():
    parser = argparse.ArgumentParser(description="Run the Pi Avatar monitor")
    parser.add_argument("--config", help="Path to avatar.yaml")
    args = parser.parse_args()

    try:
        run_monitor(load_config(os.environ, path=args.config))
    except ConfigError as exc:
        raise SystemExit(f"Configuration error: {exc}") from exc


if __name__ == "__main__":
    main()
