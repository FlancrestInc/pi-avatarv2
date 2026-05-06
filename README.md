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

Run the monitor and Pi fullscreen renderer separately:

```bash
python monitor.py --config examples/avatar.routine.yaml
python renderer.py --config examples/avatar.routine.yaml
```

`renderer.py` is a compatibility wrapper around `pi_avatar.renderers.pi`. On a Pi it opens a fullscreen pygame display and falls back to `/dev/fb0` when SDL display setup is unavailable.

For systemd installation on a Pi:

```bash
sudo ./scripts/install-pi.sh
sudo systemctl restart pi-avatar-monitor pi-avatar-renderer
```

Edit `/etc/pi-avatar/avatar.yaml` for your monitor rules.

## Web Preview Mode

The web preview serves the same state file and asset folders in a browser:

```bash
python make_test_assets.py --output assets
python web_preview.py --config examples/avatar.routine.yaml --host 127.0.0.1 --port 8080
```

Open `http://127.0.0.1:8080`. The preview includes a control panel for manually selecting configured states such as `idle`, `thinking`, `working`, `success`, `error`, and `offline`. Manual selections write through the same state store used by the monitor, so the Pi renderer and web renderer can watch the same `state.json`.

## Config Shape

- `avatar`: state file, asset directory, available states, default state, optional FPS per state.
- `source`: `none`, `file`, or `url`.
- `parser`: `raw`, `json_path`, or `regex`, with `cast: string | number | bool`.
- `mode`: `time`, `value`, or `routine`.

See `examples/` for complete configs.

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
