#!/usr/bin/env python3

import argparse
import os

from pi_avatar.config import ConfigError, load_config


def main():
    parser = argparse.ArgumentParser(description="Validate a Pi Avatar YAML config")
    parser.add_argument("--config", required=True, help="Path to avatar.yaml")
    args = parser.parse_args()

    try:
        config = load_config(os.environ, path=args.config)
    except ConfigError as exc:
        raise SystemExit(f"invalid: {exc}") from exc

    print(f"valid: {config.config_file}")


if __name__ == "__main__":
    main()
