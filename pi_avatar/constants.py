from pathlib import Path

DEFAULT_CONFIG_FILE = Path("/etc/pi-avatar/avatar.yaml")
DEFAULT_STATE_FILE = Path("/var/lib/pi-avatar/state.json")
DEFAULT_ASSET_DIR = Path("/opt/pi-avatar/assets")
DEFAULT_ENV_FILE = Path("/etc/pi-avatar/avatar.env")

SCREEN_WIDTH = 800
SCREEN_HEIGHT = 480
FPS = 8
STATE_CHECK_SECONDS = 0.1
DEFAULT_STATE = "idle"

VALID_STATES = [
    "booting",
    "idle",
    "thinking",
    "working",
    "success",
    "error",
    "offline",
]

STATE_FPS = {
    "booting": 10,
    "idle": 4,
    "thinking": 8,
    "working": 14,
    "success": 8,
    "error": 10,
    "offline": 4,
}
