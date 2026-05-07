import shutil
import subprocess


RENDERER_SERVICE = "pi-avatar-renderer.service"


def run_systemctl(command, runner=None):
    if runner is not None:
        return runner(command)
    if shutil.which("systemctl") is None:
        return None
    return subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)


def reconcile_pi_renderer_service(previous_config, next_config, runner=None):
    previous_enabled = None if previous_config is None else previous_config.display.pi_enabled
    next_enabled = next_config.display.pi_enabled

    if previous_enabled == next_enabled and previous_config is not None:
        return None

    action = "restart" if next_enabled else "stop"
    return run_systemctl(["systemctl", action, RENDERER_SERVICE], runner=runner)
