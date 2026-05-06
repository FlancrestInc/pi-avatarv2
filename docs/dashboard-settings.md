# Dashboard Settings

The Settings tab edits the structured parts of the YAML config. It is the safest place to change common options because the dashboard writes valid YAML and the server validates the result before saving.

Related pages: [Dashboard Guide](dashboard.md), [Manual State](dashboard-manual-state.md), [Sprite Import](dashboard-sprites.md), [YAML Editor](dashboard-yaml.md), [Pi Display](pi-display.md).

## Avatar Settings

These controls define where the avatar stores state and which animation states are available.

| Control | YAML field | Meaning |
| --- | --- | --- |
| State file | `avatar.state_file` | JSON file shared by the monitor, web display, manual controls, and Pi renderer. |
| Asset directory | `avatar.asset_dir` | Directory containing one folder per state, such as `assets/idle/*.png`. |
| Default state | `avatar.default_state` | Fallback state used when the current state is missing or invalid. Must be listed in `avatar.states`. |
| States | `avatar.states` | Comma-separated state names that the app can render. Each state should have a matching asset folder. |
| State FPS | `avatar.state_fps` | JSON object of per-state animation speeds, such as `{"idle": 4, "working": 14}`. |

Example:

```yaml
avatar:
  state_file: state/state.json
  asset_dir: assets
  default_state: idle
  states: [booting, idle, thinking, working, success, error, offline]
  state_fps:
    idle: 4
    working: 14
```

If a state has no `state_fps` entry, the app uses the built-in default for known states or falls back to `8`.

## Source Settings

The source tells the monitor where to read outside data from. Routine and time modes can use `none`; value mode usually needs `file` or `url`.

| Control | YAML field | Meaning |
| --- | --- | --- |
| Type | `source.type` | `none`, `file`, or `url`. |
| Path | `source.path` | Required when type is `file`. The monitor reads this file as source content. |
| URL | `source.url` | Required when type is `url`. The monitor fetches this URL as source content. |
| Poll seconds | `source.poll_seconds` | How often the monitor reads the source. Must be positive. |
| Timeout seconds | `source.timeout_seconds` | URL request timeout. Must be positive. |
| Stale seconds | `source.stale_seconds` | Optional age limit for file sources. If the file is older than this, the source is treated as stale. |

File source example:

```yaml
source:
  type: file
  path: /tmp/avatar-value.json
  poll_seconds: 1
  stale_seconds: 30
```

URL source example:

```yaml
source:
  type: url
  url: http://localhost:9100/metrics.json
  poll_seconds: 2
  timeout_seconds: 2
```

Use `source.type: none` when the avatar does not need outside data.

## Parser Settings

The parser converts raw source content into the value used by value-mode rules.

| Control | YAML field | Meaning |
| --- | --- | --- |
| Type | `parser.type` | `raw`, `json_path`, or `regex`. |
| JSON path | `parser.path` | Required for `json_path`. Paths start with `$.`, such as `$.cpu.percent`. |
| Regex pattern | `parser.pattern` | Required for `regex`. Uses Python regular expression syntax. |
| Regex group | `parser.group` | Regex capture group to return. Can be a number such as `1` or a named group. |
| Cast | `parser.cast` | Converts the parsed value to `string`, `number`, or `bool`. |

Parser examples:

```yaml
parser:
  type: raw
  cast: string
```

```yaml
parser:
  type: json_path
  path: $.cpu.percent
  cast: number
```

```yaml
parser:
  type: regex
  pattern: "ready=(true|false)"
  group: 1
  cast: bool
```

Boolean casts accept `1`, `true`, `yes`, and `on` as true values, and `0`, `false`, `no`, and `off` as false values.

## Display Settings

Display settings control how frames are sized and how the Pi renderer behaves. See [Pi Display](pi-display.md) for hardware-focused details.

| Control | YAML field | Meaning |
| --- | --- | --- |
| Enable Pi display | `display.pi_enabled` | Allows `renderer.py` to run the Pi display. If false, the Pi renderer exits without opening the display. |
| Fullscreen | `display.fullscreen` | Opens the pygame renderer fullscreen when enabled. |
| Show detail text on Pi | `display.show_detail` | Draws the state detail text along the bottom of the Pi display. |
| Width | `display.width` | Pygame display width. |
| Height | `display.height` | Pygame display height. |
| Framebuffer | `display.framebuffer` | Framebuffer path used by the fallback renderer, usually `/dev/fb0`. |
| Background color | `display.background_color` | Fill color behind letterboxed frames, written as a hex color. |
| Scale mode | `display.scale_mode` | `contain`, `cover`, or `stretch`. |

Scale modes:

- `contain`: fit the whole frame without distortion. Empty space is filled with the background color.
- `cover`: fill the whole display without distortion. Some image edges may be cropped.
- `stretch`: fill the whole display by resizing directly. This can distort the image.

## Mode Settings

Mode settings decide which state the monitor writes.

| Control | YAML field | Meaning |
| --- | --- | --- |
| Type | `mode.type` | `routine`, `value`, or `time`. |
| Strategy | `mode.strategy` | Routine-only: `sequence`, `random`, or `weighted_random`. |
| Timezone | `mode.timezone` | Time-mode timezone, such as `UTC` or `America/New_York`. |
| Routine steps | `mode.steps` | JSON list of routine step objects. |
| Value rules | `mode.rules` | JSON list of value rule objects. |
| Time triggers | `mode.triggers` | JSON list of time trigger objects. |
| Time fallback | `mode.fallback` | JSON object used when no time trigger window matches. |

The dashboard uses JSON textareas for rule lists because mode entries can contain nested objects. When saved, those JSON structures are written back into the YAML config.

### Routine Mode

Routine mode cycles through configured steps without reading external source data.

Each step supports:

- `state`: state to display.
- `duration_seconds`: how long to stay on that state.
- `detail`: optional detail text.
- `fps`: optional temporary FPS override.
- `weight`: used by `weighted_random`.

Example Routine steps textarea:

```json
[
  {"state": "idle", "duration_seconds": 8, "weight": 5},
  {"state": "thinking", "duration_seconds": 4, "weight": 2},
  {"state": "success", "duration_seconds": 2, "weight": 1}
]
```

Routine strategies:

- `sequence`: move through steps in order.
- `random`: choose a random step each time.
- `weighted_random`: choose randomly using each step's `weight`, defaulting to `1`.

### Value Mode

Value mode compares the parsed source value against ordered rules. The first matching rule wins.

Rules support:

- `when`: optional condition object. If omitted, the rule always matches.
- `state`: state to display.
- `detail`: optional detail text.
- `fps`: optional temporary FPS override.

Supported `when` operators:

- `lt`, `lte`, `gt`, `gte`: numeric comparisons.
- `min`, `max`: aliases for lower and upper numeric bounds.
- `eq`: exact comparison.
- `contains`: substring check against the string form of the value.

Example Value rules textarea:

```json
[
  {"when": {"gte": 90}, "state": "error", "detail": "CPU high", "fps": 12},
  {"when": {"gte": 60}, "state": "working", "detail": "CPU busy", "fps": 14},
  {"state": "idle", "detail": "CPU normal"}
]
```

### Time Mode

Time mode compares the current time to trigger windows.

Top-level time fields:

- `timezone`: optional timezone name.
- `fallback`: state object used when no window matches.
- `triggers`: list of trigger objects.

Each trigger supports:

- `time`: required `HH:MM` or `HH:MM:SS` time.
- `detail`: optional detail text shared by windows.
- `windows`: list of windows around the trigger time.

Each window supports:

- `before_seconds`: number of seconds before the trigger that the window starts.
- `after_seconds`: number of seconds after the trigger that the window remains active.
- `state`: state to display while matched.
- `detail`: optional detail text.
- `fps`: optional temporary FPS override.

Example Time triggers textarea:

```json
[
  {
    "time": "17:00",
    "detail": "Five o'clock in {seconds} seconds",
    "windows": [
      {"before_seconds": 3600, "state": "thinking", "detail": "Almost time", "fps": 8},
      {"before_seconds": 300, "after_seconds": 900, "state": "success", "detail": "It is time", "fps": 12}
    ]
  }
]
```

If a detail string includes `{seconds}`, it is replaced with the number of seconds until the trigger, never less than zero.
