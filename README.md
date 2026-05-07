# Avatar State Display

General-purpose animated avatar state display. The core monitor reads a YAML config, evaluates time/value/routine rules, writes `state.json`, and renderer backends display PNG frame folders from `assets/<state>/*.png`.

The project keeps Raspberry Pi fullscreen display support, but Pi hardware is now one renderer option rather than the center of the application.

## Architecture

- `pi_avatar.core`: shared state model, state store, and animation-state discovery.
- `pi_avatar.config`: YAML config loading and validation.
- `pi_avatar.watchers`: watcher source modules for `file`, `url`, and `none`, plus `WatcherOrchestrator`.
- `pi_avatar.parsers` and `pi_avatar.modes`: safe value extraction and time/value/routine state decisions.
- `pi_avatar.renderers.pi`: fullscreen pygame renderer with framebuffer fallback for Pi displays.
- `pi_avatar.renderers.web`: browser preview renderer with the same state store and asset folders.
- `monitor.py`, `renderer.py`, and `web_preview.py`: compatibility CLI entrypoints.

Renderers consume the same `AvatarState` contract: `state`, `detail`, `fps_override`, `updated`, and `source_value`.

This project intentionally leaves out the Clawhub/OpenClaw status-agent side of the original Clawvitar project.

## Run Locally

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
python validate_config.py --config examples/avatar.routine.yaml
python monitor.py --config examples/avatar.routine.yaml
```

Generate placeholder frames for development:

```bash
python make_test_assets.py --output assets
```

For real spritesheets, adapt `source-assets/manifest.example.json` and run `process_assets.py`.

## Pi Renderer Mode

Run the monitor, browser renderer, and Pi fullscreen renderer quietly with the startup script:

```bash
./scripts/start-avatar.sh --config examples/avatar.routine.yaml
```

Process output is written under `logs/` instead of cluttering the terminal. To install that startup script as a boot service:

```bash
sudo ./scripts/start-avatar.sh --install-service --config /etc/pi-avatar/avatar.yaml
```

You can still run the monitor and Pi fullscreen renderer separately:

```bash
python monitor.py --config examples/avatar.routine.yaml
python renderer.py --config examples/avatar.routine.yaml
```

`renderer.py` is a compatibility wrapper around `pi_avatar.renderers.pi`. On a Pi it opens a fullscreen pygame display and falls back to `/dev/fb0` when SDL display setup is unavailable.

For systemd installation on a Pi:

```bash
sudo ./scripts/install-pi.sh
sudo systemctl restart pi-avatar-monitor pi-avatar-renderer pi-avatar-web
```

Edit `/etc/pi-avatar/avatar.yaml` for your monitor rules.

## Web Preview Mode

The web preview serves the same state file and asset folders in a browser:

```bash
python make_test_assets.py --output assets
python web_preview.py --config examples/avatar.routine.yaml --host 127.0.0.1 --port 8080
```

Open `http://127.0.0.1:8080` for the full-window avatar display.

Open `http://127.0.0.1:8080/config` to edit the YAML-backed configuration from the browser. The configuration page includes controls for avatar paths and states, source watchers, parsers, routine/value/time modes, Pi display settings, manual state overrides, and sprite import.

The root display page uses the full browser window and preserves the avatar frame aspect ratio with `object-fit: contain`.

## Dashboard Documentation

Start with the [Dashboard Guide](docs/dashboard.md) for a tour of the web interface and recommended workflow.

- [Settings](docs/dashboard-settings.md): all configurable YAML-backed controls, including avatar, source, parser, display, and mode settings.
- [Manual State](docs/dashboard-manual-state.md): force states, add detail text, and test FPS overrides.
- [Sprite Import](docs/dashboard-sprites.md): upload spritesheets, preview frames, and write processed assets.
- [YAML Editor](docs/dashboard-yaml.md): edit raw YAML directly and understand validation rules.
- [Pi Display](docs/pi-display.md): configure physical display output and keep it aligned with the web view.

## Config Shape

- `avatar`: state file, asset directory, available states, default state, optional FPS per state.
- `display`: Pi renderer enablement, size, fullscreen mode, framebuffer path, background color, detail text, and scale mode.
- `web`: browser renderer bind host and port, for example `host: 0.0.0.0` and `port: 8080` for LAN access.
- `source`: `none`, `file`, or `url`.
- `parser`: `raw`, `json_path`, or `regex`, with `cast: string | number | bool`.
- `mode`: `time`, `value`, or `routine`.

See `examples/` for complete configs.

## Sprite Import

The `/config` sprite tab can upload a background image and a spritesheet or sprite page into `source-assets/uploads`, preview parsed frames, and process them into the configured `assets/<state>/*.png` output. It supports grid parsing and explicit frame rectangles, matching the manifest shape used by `process_assets.py`. See [Sprite Import](docs/dashboard-sprites.md) for the full workflow.

## Watchers

Watcher config lives under `source`:

```yaml
source:
  type: file
  path: /tmp/avatar-value.json
  poll_seconds: 1
  stale_seconds: 30
```

```yaml
source:
  type: url
  url: http://localhost:9100/metrics.json
  poll_seconds: 2
  timeout_seconds: 2
```

Use `source.type: none` for routine or time-only avatars. New watcher types should be added under `pi_avatar.watchers` and dispatched by `SourceReader`.

## Tests

```bash
python -m unittest -v
```
