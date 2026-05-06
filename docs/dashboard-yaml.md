# YAML Editor

The YAML tab exposes the raw config file loaded by the web dashboard. Use it when you need direct control over fields that are easier to edit as YAML, or when you want to review exactly what the Settings tab will save.

Related pages: [Dashboard Guide](dashboard.md), [Settings](dashboard-settings.md), [Manual State](dashboard-manual-state.md), [Sprite Import](dashboard-sprites.md), [Pi Display](pi-display.md).

## Save Behavior

When you click Save Config from the YAML tab:

1. The dashboard parses the YAML.
2. The server validates it with `pi_avatar.config.load_config`.
3. If validation passes, the YAML is written to the active config file.
4. The web server reloads its in-memory config.

If parsing or validation fails, the server returns an error and keeps the current config file unchanged.

## Complete Example

```yaml
avatar:
  state_file: state/state.json
  asset_dir: assets
  default_state: idle
  states: [booting, idle, thinking, working, success, error, offline]
  state_fps:
    idle: 4
    working: 14

display:
  pi_enabled: true
  width: 800
  height: 480
  fullscreen: true
  framebuffer: /dev/fb0
  background_color: "#000000"
  show_detail: true
  scale_mode: contain

source:
  type: url
  url: http://localhost:9100/metrics.json
  poll_seconds: 2
  timeout_seconds: 2

parser:
  type: json_path
  path: $.cpu.percent
  cast: number

mode:
  type: value
  rules:
    - when: {gte: 90}
      state: error
      detail: CPU high
      fps: 12
    - when: {gte: 60}
      state: working
      detail: CPU busy
      fps: 14
    - state: idle
      detail: CPU normal
```

## Validation Rules

- `avatar.states` must be a non-empty list of state names.
- `avatar.default_state` must be included in `avatar.states`.
- `avatar.state_fps` can only reference configured states and values must be positive.
- `source.type` must be `none`, `file`, or `url`.
- `source.path` is required for file sources.
- `source.url` is required for URL sources.
- `source.poll_seconds`, `source.timeout_seconds`, and `source.stale_seconds` must be positive when present.
- `parser.type` must be `raw`, `json_path`, or `regex`.
- `parser.path` is required for `json_path`.
- `parser.pattern` is required for `regex`.
- `parser.cast` must be `string`, `number`, or `bool`.
- `display.width` and `display.height` must be positive integers.
- `display.scale_mode` must be `contain`, `cover`, or `stretch`.
- `mode.type` must be `routine`, `value`, or `time`.
- Routine mode requires a non-empty `steps` list.
- Value mode requires a non-empty `rules` list.
- Time mode requires a non-empty `triggers` list.

## When To Use YAML Directly

Use the YAML tab when:

- You want to paste a config from `examples/`.
- You need to reorder large rule lists quickly.
- You are copying a known-good config between devices.
- You want to review the exact file before restarting monitor or renderer services.

Use the Settings tab when you are making small, ordinary changes and want form controls for common fields.
