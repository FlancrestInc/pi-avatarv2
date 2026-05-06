# Manual State

The Manual State tab lets you force the avatar into a configured state from the browser. It replaces the old preview sidebar controls and writes directly to the shared state file.

Related pages: [Dashboard Guide](dashboard.md), [Settings](dashboard-settings.md), [Sprite Import](dashboard-sprites.md), [YAML Editor](dashboard-yaml.md).

## What It Changes

Manual state controls write this state payload through the same state store used by the monitor:

```json
{
  "state": "working",
  "detail": "Optional detail",
  "fps_override": 14
}
```

The web display and Pi renderer both read that state file, so manual changes are useful for previewing and troubleshooting states across both outputs.

## Controls

| Control | Meaning |
| --- | --- |
| State buttons | One button for each configured `avatar.states` entry. Clicking a button writes that state. |
| Detail | Optional text attached to the state. The web display shows it as status text, and the Pi renderer can show it when `display.show_detail` is enabled. |
| FPS override | Optional temporary animation speed for this manual state. Leave blank to use `avatar.state_fps`. |
| Preview | Live animation preview of the current state using the same frame folders as the main display. |
| State metadata | Shows the current state and update time when available. |

## How To Use It

1. Open `/config`.
2. Go to Manual State.
3. Optionally enter detail text and an FPS override.
4. Click a state button.
5. Check the preview and the root display page.

## Notes

- Manual state is not a permanent mode rule. It writes the current `state.json` value.
- If `monitor.py` is running, the monitor may overwrite manual state on its next poll.
- If a state button appears but the preview is blank, check that `avatar.asset_dir/<state>/` contains PNG frames.
- If the state is rejected, confirm that the state name is listed in `avatar.states`.
