#!/usr/bin/env python3

import argparse
import os

from pi_avatar.config import ConfigError, load_config
from pi_avatar.watchers.orchestrator import WatcherOrchestrator


def poll_once(config, source_reader, writer, routine_state):
    orchestrator = WatcherOrchestrator(config)
    orchestrator.source_reader = source_reader
    orchestrator.store.writer = writer
    orchestrator.routine_state = routine_state
    return orchestrator.poll_once()


def run_monitor(config):
    WatcherOrchestrator(config).run_forever()


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
