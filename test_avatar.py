import json
import os
import tempfile
import time
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

from pi_avatar.config import ConfigError, load_config
from pi_avatar.modes import RoutineState, evaluate_routine, evaluate_time, evaluate_value
from pi_avatar.parsers import ParseError, parse_value
from pi_avatar.sources import SourceReader
from pi_avatar.state import StateWriter
import monitor
import renderer
from pi_avatar.renderers import web
from pi_avatar import services


def write_config(tmpdir, body):
    path = Path(tmpdir) / "avatar.yaml"
    path.write_text(body)
    return path


class AvatarMonitorTests(unittest.TestCase):
    def test_load_config_defaults_to_routine(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = write_config(tmpdir, "")
            config = load_config(env={}, path=config_path)

        self.assertEqual(config.default_state, "idle")
        self.assertEqual(config.source.type, "none")
        self.assertEqual(config.mode["type"], "routine")
        self.assertEqual(config.web.host, "0.0.0.0")
        self.assertEqual(config.web.port, 8080)

    def test_load_config_rejects_unknown_value_rule_state(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = write_config(
                tmpdir,
                """
mode:
  type: value
  rules:
    - state: dancing
""",
            )

            with self.assertRaises(ConfigError):
                load_config(env={}, path=config_path)

    def test_display_config_controls_pi_renderer_settings(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = write_config(
                tmpdir,
                """
display:
  pi_enabled: false
  width: 1024
  height: 600
  fullscreen: false
  framebuffer: /tmp/fb0
  background_color: "#112233"
  show_detail: false
  scale_mode: cover
""",
            )
            config = load_config(env={}, path=config_path)

        self.assertFalse(config.display.pi_enabled)
        self.assertEqual(config.display.width, 1024)
        self.assertEqual(config.display.height, 600)
        self.assertFalse(config.display.fullscreen)
        self.assertEqual(config.display.framebuffer, "/tmp/fb0")
        self.assertEqual(config.display.background_color, "#112233")
        self.assertFalse(config.display.show_detail)
        self.assertEqual(config.display.scale_mode, "cover")

    def test_web_config_controls_bind_host_and_port(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = write_config(
                tmpdir,
                """
web:
  host: 0.0.0.0
  port: 9090
""",
            )
            config = load_config(env={}, path=config_path)

        self.assertEqual(config.web.host, "0.0.0.0")
        self.assertEqual(config.web.port, 9090)

    def test_web_renderer_main_uses_config_host_and_port(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = write_config(
                tmpdir,
                """
web:
  host: 0.0.0.0
  port: 9090
""",
            )

            with mock.patch("sys.argv", ["web_preview.py", "--config", str(config_path)]), mock.patch(
                "pi_avatar.renderers.web.run_web_renderer"
            ) as run_web_renderer:
                web.main()

        self.assertEqual(run_web_renderer.call_args.kwargs["host"], "0.0.0.0")
        self.assertEqual(run_web_renderer.call_args.kwargs["port"], 9090)

    def test_reconcile_pi_renderer_service_starts_when_enabled(self):
        calls = []

        class Config:
            class display:
                pi_enabled = True

        services.reconcile_pi_renderer_service(None, Config(), runner=lambda command: calls.append(command))

        self.assertEqual(calls, [["systemctl", "restart", "pi-avatar-renderer.service"]])

    def test_reconcile_pi_renderer_service_stops_when_disabled(self):
        calls = []

        class Config:
            class display:
                pi_enabled = False

        services.reconcile_pi_renderer_service(None, Config(), runner=lambda command: calls.append(command))

        self.assertEqual(calls, [["systemctl", "stop", "pi-avatar-renderer.service"]])

    def test_start_script_supports_quiet_service_install_and_web(self):
        script = Path("scripts/start-avatar.sh").read_text()

        self.assertIn("--install-service", script)
        self.assertIn("pi-avatar-web.service", script)
        self.assertIn(">/dev/null", script)

    def test_start_script_runs_from_project_root_and_uses_pid_dir(self):
        script = Path("scripts/start-avatar.sh").read_text()

        self.assertIn('cd "${ROOT_DIR}"', script)
        self.assertIn('PID_DIR="${PID_DIR:-${ROOT_DIR}/run}"', script)
        self.assertIn('stop_existing', script)
        self.assertIn('CONFIG_FILE="$(resolve_path "${CONFIG_FILE}")"', script)

    def test_start_script_installed_service_uses_dedicated_pi_units(self):
        script = Path("scripts/start-avatar.sh").read_text()

        self.assertIn("pi-avatar-monitor.service pi-avatar-web.service pi-avatar-renderer.service", script)
        self.assertIn("ExecStart=/usr/bin/systemctl start pi-avatar-monitor.service pi-avatar-web.service", script)
        self.assertIn("ExecStart=/usr/bin/systemctl start --no-block pi-avatar-renderer.service", script)
        self.assertNotIn("ExecStart=/usr/bin/env bash ${ROOT_DIR}/scripts/start-avatar.sh --foreground", script)

    def test_renderer_units_do_not_block_in_start_pre(self):
        script = Path("scripts/start-avatar.sh").read_text()
        unit = Path("systemd/pi-avatar-renderer.service").read_text()

        for text in (script, unit):
            self.assertNotIn("ExecStartPre", text)
            self.assertNotIn("setterm", text)

    def test_renderer_logs_startup_context_before_display_open(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = write_config(tmpdir, "")
            config = load_config(env={}, path=config_path)

            with mock.patch("builtins.print") as printer:
                renderer.log_startup_context(config)

        messages = [call.args[0] for call in printer.call_args_list]
        self.assertTrue(any("renderer starting" in message for message in messages))
        self.assertTrue(any("asset_dir=" in message for message in messages))

    def test_parse_json_path_and_numeric_cast(self):
        value = parse_value('{"cpu": {"percent": 72.5}}', load_config(env={}, path=Path("/missing")).parser)
        self.assertEqual(value, '{"cpu": {"percent": 72.5}}')

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = write_config(
                tmpdir,
                """
parser:
  type: json_path
  path: $.cpu.percent
  cast: number
""",
            )
            config = load_config(env={}, path=config_path)

        self.assertEqual(parse_value('{"cpu": {"percent": 72.5}}', config.parser), 72.5)

    def test_parse_regex_bool(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = write_config(
                tmpdir,
                """
parser:
  type: regex
  pattern: "ready=(true|false)"
  cast: bool
""",
            )
            config = load_config(env={}, path=config_path)

        self.assertTrue(parse_value("ready=true", config.parser))
        with self.assertRaises(ParseError):
            parse_value("missing", config.parser)

    def test_file_source_reads_content_and_detects_stale_mtime(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            source = Path(tmpdir) / "value.txt"
            source.write_text("42")
            old = time.time() - 20
            os.utime(source, (old, old))
            config_path = write_config(
                tmpdir,
                f"""
source:
  type: file
  path: {source}
  stale_seconds: 5
""",
            )
            config = load_config(env={}, path=config_path)
            reader = SourceReader(config)
            result = reader.read()

            self.assertTrue(result.ok)
            self.assertEqual(result.content, "42")
            self.assertTrue(reader.is_stale(now=time.time()))

    def test_value_mode_uses_ordered_rules_and_fps(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = write_config(
                tmpdir,
                """
mode:
  type: value
  rules:
    - when: {gte: 90}
      state: error
      fps: 12
    - when: {gte: 60}
      state: working
    - state: idle
""",
            )
            config = load_config(env={}, path=config_path)

        decision = evaluate_value(config, 95)
        self.assertEqual(decision.state, "error")
        self.assertEqual(decision.fps_override, 12)
        self.assertEqual(evaluate_value(config, 75).state, "working")
        self.assertEqual(evaluate_value(config, 10).state, "idle")

    def test_time_mode_uses_nearest_matching_window(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = write_config(
                tmpdir,
                """
mode:
  type: time
  timezone: UTC
  fallback: {state: idle}
  triggers:
    - time: "17:00"
      windows:
        - before_seconds: 3600
          state: thinking
        - before_seconds: 300
          after_seconds: 600
          state: success
""",
            )
            config = load_config(env={}, path=config_path)

        self.assertEqual(evaluate_time(config, now=datetime.fromisoformat("2026-05-06T16:30:00+00:00")).state, "thinking")
        self.assertEqual(evaluate_time(config, now=datetime.fromisoformat("2026-05-06T16:58:00+00:00")).state, "success")
        self.assertEqual(evaluate_time(config, now=datetime.fromisoformat("2026-05-06T12:00:00+00:00")).state, "idle")

    def test_routine_mode_sequence_advances_after_duration(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = write_config(
                tmpdir,
                """
mode:
  type: routine
  strategy: sequence
  steps:
    - state: idle
      duration_seconds: 5
    - state: thinking
      duration_seconds: 5
""",
            )
            config = load_config(env={}, path=config_path)

        state = RoutineState()
        with mock.patch("pi_avatar.modes.time.time", return_value=100):
            self.assertEqual(evaluate_routine(config, state).state, "idle")
        with mock.patch("pi_avatar.modes.time.time", return_value=104):
            self.assertEqual(evaluate_routine(config, state).state, "idle")
        with mock.patch("pi_avatar.modes.time.time", return_value=106):
            self.assertEqual(evaluate_routine(config, state).state, "thinking")

    def test_monitor_writes_parsed_value_decision(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "state.json"
            source = Path(tmpdir) / "value.json"
            source.write_text('{"cpu": {"percent": 65}}')
            config_path = write_config(
                tmpdir,
                f"""
avatar:
  state_file: {state_file}
source:
  type: file
  path: {source}
parser:
  type: json_path
  path: $.cpu.percent
  cast: number
mode:
  type: value
  rules:
    - when: {{gte: 60}}
      state: working
      fps: 14
    - state: idle
""",
            )
            config = load_config(env={}, path=config_path)

            monitor.poll_once(config, SourceReader(config), StateWriter(state_file), RoutineState())
            payload = json.loads(state_file.read_text())

        self.assertEqual(payload["state"], "working")
        self.assertEqual(payload["fps_override"], 14)
        self.assertEqual(payload["source_value"], 65.0)

    def test_renderer_reads_extended_state_and_rejects_unknown(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "state.json"
            config_path = write_config(tmpdir, f"avatar:\n  state_file: {state_file}\n")
            config = load_config(env={}, path=config_path)

            state_file.write_text(json.dumps({"state": "working", "detail": "busy", "fps_override": "13"}))
            self.assertEqual(renderer.read_state(config), ("working", "busy", 13.0))

            state_file.write_text(json.dumps({"state": "dancing"}))
            self.assertEqual(renderer.read_state(config), ("idle", "Unknown state", None))

    def test_installer_and_services_are_pi_only(self):
        root = Path(__file__).resolve().parent
        installer = (root / "scripts" / "install-pi.sh").read_text()
        monitor_service = (root / "systemd" / "pi-avatar-monitor.service").read_text()

        self.assertIn("avatar.yaml", installer)
        self.assertIn("validate_config.py", installer)
        self.assertIn("--config /etc/pi-avatar/avatar.yaml", monitor_service)
        self.assertNotIn("openclaw", installer.lower())
        self.assertNotIn("openclaw", monitor_service.lower())


if __name__ == "__main__":
    unittest.main()
