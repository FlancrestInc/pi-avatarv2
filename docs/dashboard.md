# Dashboard Guide

The web dashboard has two browser entry points:

- `http://127.0.0.1:8080/` shows the avatar display.
- `http://127.0.0.1:8080/config` opens the configuration dashboard.

Start the dashboard with:

```bash
python web_preview.py --config examples/avatar.routine.yaml --host 127.0.0.1 --port 8080
```

Use the same config file path that your monitor and renderer use. The dashboard edits that YAML file, reloads the web renderer configuration, and keeps manual state changes flowing through the same `state.json` file used by the monitor and Pi renderer.

## Dashboard Sections

- [Settings](dashboard-settings.md): avatar paths, states, source readers, parsers, display options, and mode rules.
- [Manual State](dashboard-manual-state.md): temporarily force a state, detail text, or FPS override.
- [Sprite Import](dashboard-sprites.md): upload spritesheets, preview parsed frames, and write processed assets.
- [YAML Editor](dashboard-yaml.md): inspect and edit the raw config file directly.
- [Pi Display](pi-display.md): configure the physical Pi renderer and keep it aligned with the web display.

## Save Behavior

The Settings and YAML tabs both write to the loaded YAML config file. Before saving, the server validates the new config using the same loader used by the monitor and renderers. If validation fails, the dashboard returns an error and leaves the current config in place.

Saving updates the web server's active config immediately. Long-running monitor or Pi renderer processes may need to be restarted if they do not watch the config file themselves.

## Recommended Workflow

1. Start with [Settings](dashboard-settings.md) and confirm `avatar.state_file`, `avatar.asset_dir`, states, and default state.
2. Use [Sprite Import](dashboard-sprites.md) to generate frames for each state.
3. Use [Manual State](dashboard-manual-state.md) to check every state animation.
4. Configure routine, value, or time behavior in [Settings](dashboard-settings.md#mode-settings).
5. If using hardware, confirm [Pi Display](pi-display.md) settings.

## Paths

Relative paths are resolved from the process working directory. For local development from the repository root, `state/state.json`, `assets`, and `source-assets/uploads` are the usual paths. For an installed Pi service, paths are typically absolute, such as `/etc/pi-avatar/avatar.yaml`, `/var/lib/pi-avatar/state.json`, and `/opt/pi-avatar/assets`.
