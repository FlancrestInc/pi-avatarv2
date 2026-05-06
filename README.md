# Pi Avatar Monitor V2

Pi-only animated avatar monitor. The monitor reads a YAML config, evaluates time/value/routine rules, writes `state.json`, and the renderer displays PNG frame folders from `assets/<state>/*.png`.

This project intentionally leaves out the Clawhub/OpenClaw status-agent side of the original Clawvitar project.

## Run Locally

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
python validate_config.py --config examples/avatar.routine.yaml
python monitor.py --config examples/avatar.routine.yaml
```

The renderer expects prepared frames under `assets/<state>/*.png`:

```bash
python make_test_assets.py --output assets
python renderer.py --config examples/avatar.routine.yaml
```

For real spritesheets, adapt `source-assets/manifest.example.json` and run `process_assets.py`.

## Config Shape

- `avatar`: state file, asset directory, available states, default state, optional FPS per state.
- `source`: `none`, `file`, or `url`.
- `parser`: `raw`, `json_path`, or `regex`, with `cast: string | number | bool`.
- `mode`: `time`, `value`, or `routine`.

See `examples/` for complete configs.

## Tests

```bash
python -m unittest -v
```

## Pi Install

```bash
sudo ./scripts/install-pi.sh
sudo systemctl restart pi-avatar-monitor pi-avatar-renderer
```

Edit `/etc/pi-avatar/avatar.yaml` for your monitor rules.
