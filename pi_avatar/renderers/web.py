import argparse
import json
import mimetypes
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

from pi_avatar.config import load_config
from pi_avatar.core import StateStore, load_animation_states


INDEX_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Avatar Preview</title>
  <style>
    :root {
      color-scheme: dark;
      --bg: #141516;
      --panel: #24272a;
      --panel-2: #1d2022;
      --text: #f4f1e8;
      --muted: #b9b3a6;
      --accent: #4fc3a1;
      --line: #3a3f43;
      --danger: #f16d6d;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      background: var(--bg);
      color: var(--text);
      font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }
    main {
      display: grid;
      grid-template-columns: minmax(0, 1fr) 320px;
      min-height: 100vh;
    }
    .stage {
      display: grid;
      place-items: center;
      padding: 32px;
      background:
        linear-gradient(90deg, rgba(255,255,255,.035) 1px, transparent 1px),
        linear-gradient(rgba(255,255,255,.035) 1px, transparent 1px);
      background-size: 40px 40px;
    }
    .viewport {
      width: min(100%, 960px);
      aspect-ratio: 5 / 3;
      background: #050607;
      border: 1px solid var(--line);
      display: grid;
      place-items: center;
      overflow: hidden;
    }
    .viewport img {
      width: 100%;
      height: 100%;
      object-fit: contain;
      image-rendering: auto;
    }
    aside {
      border-left: 1px solid var(--line);
      background: var(--panel-2);
      padding: 20px;
      overflow: auto;
    }
    h1 {
      font-size: 20px;
      margin: 0 0 18px;
      font-weight: 700;
    }
    .meta, .detail {
      color: var(--muted);
      font-size: 13px;
      line-height: 1.5;
      margin: 8px 0 18px;
      min-height: 20px;
    }
    .state {
      display: inline-flex;
      align-items: center;
      min-height: 30px;
      padding: 4px 10px;
      border: 1px solid var(--line);
      background: var(--panel);
      font-weight: 700;
      margin-bottom: 10px;
    }
    .buttons {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 8px;
      margin-bottom: 18px;
    }
    button {
      border: 1px solid var(--line);
      background: var(--panel);
      color: var(--text);
      min-height: 38px;
      padding: 8px 10px;
      cursor: pointer;
      font: inherit;
    }
    button:hover, button.active {
      border-color: var(--accent);
      color: white;
      background: #263d36;
    }
    input {
      width: 100%;
      min-height: 38px;
      border: 1px solid var(--line);
      background: #111315;
      color: var(--text);
      padding: 8px 10px;
      font: inherit;
      margin-bottom: 8px;
    }
    .error { color: var(--danger); }
    @media (max-width: 820px) {
      main { grid-template-columns: 1fr; }
      aside { border-left: 0; border-top: 1px solid var(--line); }
      .stage { padding: 16px; }
    }
  </style>
</head>
<body>
  <main>
    <section class="stage">
      <div class="viewport"><img id="frame" alt="Avatar animation frame"></div>
    </section>
    <aside>
      <h1>Avatar Preview</h1>
      <div id="state" class="state">loading</div>
      <div id="detail" class="detail"></div>
      <div id="buttons" class="buttons"></div>
      <input id="customDetail" placeholder="Optional detail text">
      <button id="refresh">Refresh</button>
      <div id="meta" class="meta"></div>
      <div id="error" class="meta error"></div>
    </aside>
  </main>
  <script>
    const frame = document.getElementById("frame");
    const stateEl = document.getElementById("state");
    const detailEl = document.getElementById("detail");
    const metaEl = document.getElementById("meta");
    const errorEl = document.getElementById("error");
    const buttonsEl = document.getElementById("buttons");
    const detailInput = document.getElementById("customDetail");
    const refreshButton = document.getElementById("refresh");
    let config = null;
    let currentState = null;
    let frameIndex = 0;
    let lastState = null;
    let lastFrameAt = 0;

    async function getJson(path, options) {
      const response = await fetch(path, options);
      if (!response.ok) throw new Error(await response.text());
      return response.json();
    }

    function setError(error) {
      errorEl.textContent = error ? String(error.message || error) : "";
    }

    async function loadConfig() {
      config = await getJson("/api/animations");
      buttonsEl.innerHTML = "";
      config.states.forEach((state) => {
        const button = document.createElement("button");
        button.textContent = state;
        button.onclick = () => setState(state);
        button.dataset.state = state;
        buttonsEl.appendChild(button);
      });
    }

    async function loadState() {
      currentState = await getJson("/api/state");
      stateEl.textContent = currentState.state;
      detailEl.textContent = currentState.detail || "";
      metaEl.textContent = [
        currentState.updated ? `updated: ${currentState.updated}` : "",
        currentState.source_value !== null && currentState.source_value !== undefined ? `source: ${currentState.source_value}` : ""
      ].filter(Boolean).join(" | ");
      for (const button of buttonsEl.querySelectorAll("button")) {
        button.classList.toggle("active", button.dataset.state === currentState.state);
      }
      if (lastState !== currentState.state) {
        frameIndex = 0;
        lastState = currentState.state;
      }
    }

    async function setState(state) {
      await getJson("/api/state", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({state, detail: detailInput.value})
      });
      await loadState();
    }

    function tick(timestamp) {
      try {
        if (config && currentState) {
          const animation = config.animations[currentState.state] || config.animations[config.default_state] || [];
          const fps = currentState.fps_override || config.state_fps[currentState.state] || 8;
          if (animation.length && timestamp - lastFrameAt >= 1000 / fps) {
            frame.src = animation[frameIndex % animation.length] + `?t=${Date.now()}`;
            frameIndex += 1;
            lastFrameAt = timestamp;
          }
        }
      } catch (error) {
        setError(error);
      }
      requestAnimationFrame(tick);
    }

    refreshButton.onclick = () => loadState().catch(setError);
    loadConfig()
      .then(loadState)
      .then(() => {
        setInterval(() => loadState().catch(setError), 1000);
        requestAnimationFrame(tick);
      })
      .catch(setError);
  </script>
</body>
</html>
"""


class AvatarWebHandler(BaseHTTPRequestHandler):
    server_version = "AvatarPreview/1.0"

    @property
    def config(self):
        return self.server.config

    @property
    def store(self):
        return self.server.state_store

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/":
            return self._send_text(INDEX_HTML, "text/html")
        if path == "/api/state":
            return self._send_json(self.store.read().__dict__)
        if path == "/api/animations":
            return self._send_json(self._animation_payload())
        if path.startswith("/assets/"):
            return self._send_asset(path.removeprefix("/assets/"))
        self.send_error(404, "Not found")

    def do_POST(self):
        path = urlparse(self.path).path
        if path != "/api/state":
            return self.send_error(404, "Not found")

        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
        except (ValueError, json.JSONDecodeError):
            return self.send_error(400, "Invalid JSON")

        state = payload.get("state")
        if state not in self.config.states:
            return self.send_error(400, "Unknown state")

        self.store.write(state, payload.get("detail", ""), fps_override=payload.get("fps_override"))
        return self._send_json(self.store.read().__dict__)

    def log_message(self, format, *args):
        print(f"{self.address_string()} - {format % args}", flush=True)

    def _animation_payload(self):
        animations = {}
        for animation in load_animation_states(self.config):
            animations[animation.name] = [f"/assets/{animation.name}/{path.name}" for path in animation.frame_paths]
        return {
            "states": self.config.states,
            "default_state": self.config.default_state,
            "state_fps": self.config.state_fps,
            "animations": animations,
        }

    def _send_asset(self, relative):
        parts = [part for part in unquote(relative).split("/") if part]
        if len(parts) != 2:
            return self.send_error(404, "Asset not found")
        state, filename = parts
        if state not in self.config.states or "/" in filename or filename.startswith("."):
            return self.send_error(404, "Asset not found")
        path = (self.config.asset_dir / state / filename).resolve()
        asset_root = self.config.asset_dir.resolve()
        try:
            path.relative_to(asset_root)
        except ValueError:
            return self.send_error(404, "Asset not found")
        if not path.exists():
            return self.send_error(404, "Asset not found")
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(path.stat().st_size))
        self.end_headers()
        with path.open("rb") as file:
            self.wfile.write(file.read())

    def _send_json(self, payload, status=200):
        raw = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _send_text(self, text, content_type):
        raw = text.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


class AvatarWebServer(ThreadingHTTPServer):
    def __init__(self, address, config):
        super().__init__(address, AvatarWebHandler)
        self.config = config
        self.state_store = StateStore(config)


def run_web_renderer(config, host="127.0.0.1", port=8080):
    server = AvatarWebServer((host, port), config)
    print(f"web preview running at http://{host}:{port}", flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()


def main():
    parser = argparse.ArgumentParser(description="Run the browser avatar preview")
    parser.add_argument("--config", help="Path to avatar.yaml")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host")
    parser.add_argument("--port", default=8080, type=int, help="Bind port")
    args = parser.parse_args()

    config = load_config(os.environ, path=args.config)
    run_web_renderer(config, host=args.host, port=args.port)


if __name__ == "__main__":
    main()

