import argparse
import base64
import json
import mimetypes
import os
import tempfile
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
from pathlib import Path
from urllib.parse import unquote, urlparse

import yaml
from PIL import Image

from pi_avatar.assets import AssetManifestError, process_manifest
from pi_avatar.config import ConfigError, load_config
from pi_avatar.core import StateStore, load_animation_states


DISPLAY_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Avatar Display</title>
  <style>
    :root { color-scheme: dark; --bg: #101112; --text: #f4f1e8; --muted: #b9b3a6; --line: #303438; --accent: #4fc3a1; }
    * { box-sizing: border-box; }
    body { margin: 0; min-height: 100vh; background: var(--bg); color: var(--text); font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; overflow: hidden; }
    main { width: 100vw; height: 100vh; display: grid; place-items: center; background: #050607; }
    img { width: 100vw; height: 100vh; object-fit: contain; display: block; }
    .status { position: fixed; left: 14px; bottom: 12px; color: var(--muted); font-size: 13px; text-shadow: 0 1px 3px #000; max-width: calc(100vw - 28px); }
    .config-link { position: fixed; right: 12px; top: 12px; color: var(--muted); border: 1px solid var(--line); background: rgba(16,17,18,.72); padding: 7px 10px; text-decoration: none; font-size: 13px; }
    .config-link:hover { color: white; border-color: var(--accent); }
  </style>
</head>
<body>
  <main><img id="frame" alt="Avatar animation frame"></main>
  <a class="config-link" href="/config">Config</a>
  <div id="status" class="status"></div>
  <script>
    const frame = document.getElementById("frame");
    const statusEl = document.getElementById("status");
    let config = null, currentState = null, frameIndex = 0, lastState = null, lastFrameAt = 0;

    async function getJson(path, options) {
      const response = await fetch(path, options);
      if (!response.ok) throw new Error(await response.text());
      return response.json();
    }

    async function loadConfig() {
      config = await getJson("/api/animations");
      document.body.style.background = config.display?.background_color || "#050607";
      frame.style.objectFit = config.display?.scale_mode === "cover" ? "cover" : config.display?.scale_mode === "stretch" ? "fill" : "contain";
    }

    async function loadState() {
      currentState = await getJson("/api/state");
      statusEl.textContent = currentState.detail || "";
      if (lastState !== currentState.state) { frameIndex = 0; lastState = currentState.state; }
    }

    function tick(timestamp) {
      if (config && currentState) {
        const animation = config.animations[currentState.state] || config.animations[config.default_state] || [];
        const fps = currentState.fps_override || config.state_fps[currentState.state] || 8;
        if (animation.length && timestamp - lastFrameAt >= 1000 / fps) {
          frame.src = animation[frameIndex % animation.length] + `?t=${Date.now()}`;
          frameIndex += 1;
          lastFrameAt = timestamp;
        }
      }
      requestAnimationFrame(tick);
    }

    loadConfig().then(loadState).then(() => {
      setInterval(() => loadState().catch(console.error), 1000);
      requestAnimationFrame(tick);
    }).catch((error) => { statusEl.textContent = String(error.message || error); });
  </script>
</body>
</html>
"""


CONFIG_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Avatar Configuration</title>
  <style>
    :root {
      color-scheme: dark;
      --bg: #111314;
      --panel: #1b1e20;
      --panel-2: #23272a;
      --text: #f5f2eb;
      --muted: #b7b0a4;
      --line: #383e42;
      --accent: #45c39d;
      --danger: #f16d6d;
      --warn: #e1b650;
    }
    * { box-sizing: border-box; }
    body { margin: 0; min-height: 100vh; background: var(--bg); color: var(--text); font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
    header { min-height: 56px; display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 10px 18px; border-bottom: 1px solid var(--line); background: #17191b; position: sticky; top: 0; z-index: 3; }
    h1 { margin: 0; font-size: 18px; }
    h2 { margin: 0 0 12px; font-size: 16px; }
    h3 { margin: 16px 0 8px; font-size: 14px; color: var(--muted); }
    main { display: grid; grid-template-columns: 220px minmax(0, 1fr); min-height: calc(100vh - 56px); }
    nav { border-right: 1px solid var(--line); background: #17191b; padding: 14px; }
    nav button { width: 100%; text-align: left; margin-bottom: 8px; }
    section { display: none; padding: 20px; max-width: 1180px; }
    section.active { display: block; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 14px; }
    .panel { border: 1px solid var(--line); background: var(--panel); padding: 14px; border-radius: 6px; }
    label { display: grid; gap: 6px; color: var(--muted); font-size: 13px; margin-bottom: 10px; }
    input, select, textarea, button { font: inherit; }
    input, select, textarea { width: 100%; min-height: 36px; border: 1px solid var(--line); background: #101214; color: var(--text); padding: 7px 9px; border-radius: 4px; }
    input[type="checkbox"] { width: auto; min-height: auto; }
    textarea { min-height: 116px; resize: vertical; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 12px; }
    button { border: 1px solid var(--line); background: var(--panel-2); color: var(--text); min-height: 36px; padding: 7px 10px; border-radius: 4px; cursor: pointer; }
    button:hover, button.active { border-color: var(--accent); color: white; background: #243d35; }
    .row { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
    .state-buttons { display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: 8px; }
    .preview-shell { display: grid; place-items: center; min-height: 320px; border: 1px solid var(--line); background: #050607; overflow: hidden; }
    .preview-shell img { width: 100%; height: min(58vh, 520px); object-fit: contain; }
    .frames { display: grid; grid-template-columns: repeat(auto-fill, minmax(96px, 1fr)); gap: 8px; margin-top: 10px; }
    .frames img { width: 100%; aspect-ratio: 5 / 3; object-fit: contain; background: #050607; border: 1px solid var(--line); }
    .muted { color: var(--muted); font-size: 13px; }
    .error { color: var(--danger); }
    .ok { color: var(--accent); }
    .split { display: grid; grid-template-columns: minmax(0, 1fr) minmax(320px, 460px); gap: 14px; }
    @media (max-width: 860px) {
      main, .split { grid-template-columns: 1fr; }
      nav { border-right: 0; border-bottom: 1px solid var(--line); display: flex; gap: 8px; overflow: auto; }
      nav button { min-width: 140px; }
      section { padding: 14px; }
    }
  </style>
</head>
<body>
  <header>
    <h1>Avatar Configuration</h1>
    <div class="row"><a href="/"><button type="button">Display</button></a><button id="save" type="button">Save Config</button></div>
  </header>
  <main>
    <nav id="tabs">
      <button data-tab="settings" class="active">Settings</button>
      <button data-tab="state">Manual State</button>
      <button data-tab="sprites">Sprites</button>
      <button data-tab="raw">YAML</button>
    </nav>
    <section id="settings" class="active">
      <div class="grid">
        <div class="panel">
          <h2>Avatar</h2>
          <label>State file <input id="avatar.state_file"></label>
          <label>Asset directory <input id="avatar.asset_dir"></label>
          <label>Default state <select id="avatar.default_state"></select></label>
          <label>States <input id="avatar.states" placeholder="idle,thinking,working"></label>
          <label>State FPS <textarea id="avatar.state_fps"></textarea></label>
        </div>
        <div class="panel">
          <h2>Source</h2>
          <label>Type <select id="source.type"><option>none</option><option>file</option><option>url</option></select></label>
          <label>Path <input id="source.path"></label>
          <label>URL <input id="source.url"></label>
          <label>Poll seconds <input id="source.poll_seconds" type="number" min="0.01" step="0.1"></label>
          <label>Timeout seconds <input id="source.timeout_seconds" type="number" min="0.01" step="0.1"></label>
          <label>Stale seconds <input id="source.stale_seconds" type="number" min="0.01" step="0.1"></label>
        </div>
        <div class="panel">
          <h2>Parser</h2>
          <label>Type <select id="parser.type"><option>raw</option><option>json_path</option><option>regex</option></select></label>
          <label>JSON path <input id="parser.path" placeholder="$.status"></label>
          <label>Regex pattern <input id="parser.pattern"></label>
          <label>Regex group <input id="parser.group"></label>
          <label>Cast <select id="parser.cast"><option>string</option><option>number</option><option>bool</option></select></label>
        </div>
        <div class="panel">
          <h2>Display</h2>
          <label class="row"><input id="display.pi_enabled" type="checkbox"> Enable Pi display</label>
          <label class="row"><input id="display.fullscreen" type="checkbox"> Fullscreen</label>
          <label class="row"><input id="display.show_detail" type="checkbox"> Show detail text on Pi</label>
          <label>Width <input id="display.width" type="number" min="1" step="1"></label>
          <label>Height <input id="display.height" type="number" min="1" step="1"></label>
          <label>Framebuffer <input id="display.framebuffer"></label>
          <label>Background color <input id="display.background_color" type="color"></label>
          <label>Scale mode <select id="display.scale_mode"><option>contain</option><option>cover</option><option>stretch</option></select></label>
        </div>
      </div>
      <div class="panel" style="margin-top:14px">
        <h2>Mode</h2>
        <div class="grid">
          <label>Type <select id="mode.type"><option>routine</option><option>value</option><option>time</option></select></label>
          <label>Strategy <select id="mode.strategy"><option>sequence</option><option>random</option><option>weighted_random</option></select></label>
          <label>Timezone <input id="mode.timezone" placeholder="UTC or America/New_York"></label>
        </div>
        <div class="grid">
          <label>Routine steps <textarea id="mode.steps"></textarea></label>
          <label>Value rules <textarea id="mode.rules"></textarea></label>
          <label>Time triggers <textarea id="mode.triggers"></textarea></label>
          <label>Time fallback <textarea id="mode.fallback"></textarea></label>
        </div>
      </div>
    </section>
    <section id="state">
      <div class="split">
        <div class="panel">
          <h2>Manual State</h2>
          <div id="stateButtons" class="state-buttons"></div>
          <label style="margin-top:12px">Detail <input id="manualDetail"></label>
          <label>FPS override <input id="manualFps" type="number" min="0.01" step="0.1"></label>
          <p id="stateMeta" class="muted"></p>
        </div>
        <div class="preview-shell"><img id="manualPreview" alt="Current avatar preview"></div>
      </div>
    </section>
    <section id="sprites">
      <div class="split">
        <div class="panel">
          <h2>Sprite Import</h2>
          <label>Background image <input id="spriteBackground" type="file" accept="image/*"></label>
          <label>Spritesheet or sprite page <input id="spriteSheet" type="file" accept="image/*"></label>
          <div class="grid">
            <label>State <input id="spriteState"></label>
            <label>Mode <select id="spriteMode"><option>grid</option><option>frames</option></select></label>
            <label>Canvas width <input id="canvasWidth" type="number" min="1" value="800"></label>
            <label>Canvas height <input id="canvasHeight" type="number" min="1" value="480"></label>
            <label>Frame width <input id="frameWidth" type="number" min="1" value="128"></label>
            <label>Frame height <input id="frameHeight" type="number" min="1" value="128"></label>
            <label>Columns <input id="columns" type="number" min="1" value="8"></label>
            <label>Frame count <input id="frameCount" type="number" min="1" value="8"></label>
            <label>Position X <input id="posX" type="number" value="0"></label>
            <label>Position Y <input id="posY" type="number" value="0"></label>
            <label>Scale <input id="spriteScale" type="number" min="0.01" step="0.1" value="1"></label>
          </div>
          <label>Explicit frames JSON <textarea id="explicitFrames" placeholder='[{"x":0,"y":0,"w":128,"h":128}]'></textarea></label>
          <div class="row"><button id="previewSprites" type="button">Preview Frames</button><button id="applySprites" type="button">Process Assets</button></div>
          <p class="muted">Uploads are stored under source-assets/uploads. Processing writes PNG frames into the configured asset directory.</p>
        </div>
        <div class="panel">
          <h2>Preview</h2>
          <p id="spriteStatus" class="muted"></p>
          <div id="spriteFrames" class="frames"></div>
        </div>
      </div>
    </section>
    <section id="raw">
      <div class="panel">
        <h2>YAML</h2>
        <textarea id="rawYaml" style="min-height:520px"></textarea>
      </div>
    </section>
  </main>
  <script>
    const $ = (id) => document.getElementById(id);
    let rawConfig = {}, uploadedBackground = "", uploadedSheet = "", animations = null, manualState = null;
    let frameIndex = 0, lastFrameAt = 0, lastState = null;

    async function getJson(path, options) {
      const response = await fetch(path, options);
      if (!response.ok) throw new Error(await response.text());
      return response.json();
    }
    function parseJson(value, fallback) {
      if (!value.trim()) return fallback;
      return JSON.parse(value);
    }
    function setValue(id, value) {
      const el = $(id);
      if (!el) return;
      if (el.type === "checkbox") el.checked = Boolean(value);
      else el.value = value ?? "";
    }
    function num(id) {
      const value = $(id).value;
      return value === "" ? undefined : Number(value);
    }
    function csv(value) {
      return value.split(",").map((item) => item.trim()).filter(Boolean);
    }
    function fillDefaults() {
      rawConfig.avatar ??= {};
      rawConfig.source ??= {};
      rawConfig.parser ??= {};
      rawConfig.mode ??= {};
      rawConfig.display ??= {};
    }
    function hydrate() {
      fillDefaults();
      const states = rawConfig.avatar.states || [];
      $("avatar.default_state").innerHTML = states.map((state) => `<option>${state}</option>`).join("");
      setValue("avatar.state_file", rawConfig.avatar.state_file);
      setValue("avatar.asset_dir", rawConfig.avatar.asset_dir);
      setValue("avatar.default_state", rawConfig.avatar.default_state);
      setValue("avatar.states", states.join(", "));
      setValue("avatar.state_fps", JSON.stringify(rawConfig.avatar.state_fps || {}, null, 2));
      for (const key of ["type","path","url","poll_seconds","timeout_seconds","stale_seconds"]) setValue(`source.${key}`, rawConfig.source[key]);
      for (const key of ["type","path","pattern","group","cast"]) setValue(`parser.${key}`, rawConfig.parser[key]);
      for (const key of ["pi_enabled","fullscreen","show_detail","width","height","framebuffer","background_color","scale_mode"]) setValue(`display.${key}`, rawConfig.display[key]);
      setValue("mode.type", rawConfig.mode.type || "routine");
      setValue("mode.strategy", rawConfig.mode.strategy || "sequence");
      setValue("mode.timezone", rawConfig.mode.timezone);
      setValue("mode.steps", JSON.stringify(rawConfig.mode.steps || [], null, 2));
      setValue("mode.rules", JSON.stringify(rawConfig.mode.rules || [], null, 2));
      setValue("mode.triggers", JSON.stringify(rawConfig.mode.triggers || [], null, 2));
      setValue("mode.fallback", JSON.stringify(rawConfig.mode.fallback || {}, null, 2));
      $("spriteState").value = rawConfig.avatar.default_state || states[0] || "idle";
      $("rawYaml").value = window.currentYaml || "";
    }
    function collect() {
      const states = csv($("avatar.states").value);
      const config = {
        avatar: {
          state_file: $("avatar.state_file").value,
          asset_dir: $("avatar.asset_dir").value,
          default_state: $("avatar.default_state").value || states[0],
          states,
          state_fps: parseJson($("avatar.state_fps").value, {})
        },
        source: {
          type: $("source.type").value,
          path: $("source.path").value || undefined,
          url: $("source.url").value || undefined,
          poll_seconds: num("source.poll_seconds") || 1,
          timeout_seconds: num("source.timeout_seconds") || 2,
          stale_seconds: num("source.stale_seconds")
        },
        parser: {
          type: $("parser.type").value,
          path: $("parser.path").value || undefined,
          pattern: $("parser.pattern").value || undefined,
          group: $("parser.group").value || 1,
          cast: $("parser.cast").value || "string"
        },
        display: {
          pi_enabled: $("display.pi_enabled").checked,
          fullscreen: $("display.fullscreen").checked,
          show_detail: $("display.show_detail").checked,
          width: num("display.width") || 800,
          height: num("display.height") || 480,
          framebuffer: $("display.framebuffer").value || "/dev/fb0",
          background_color: $("display.background_color").value || "#000000",
          scale_mode: $("display.scale_mode").value || "contain"
        },
        mode: { type: $("mode.type").value }
      };
      if (config.mode.type === "routine") {
        config.mode.strategy = $("mode.strategy").value;
        config.mode.steps = parseJson($("mode.steps").value, []);
      } else if (config.mode.type === "value") {
        config.mode.rules = parseJson($("mode.rules").value, []);
      } else {
        config.mode.timezone = $("mode.timezone").value || undefined;
        config.mode.fallback = parseJson($("mode.fallback").value, {});
        config.mode.triggers = parseJson($("mode.triggers").value, []);
      }
      return config;
    }
    async function loadAll() {
      const payload = await getJson("/api/config");
      rawConfig = payload.config;
      window.currentYaml = payload.yaml;
      hydrate();
      animations = await getJson("/api/animations");
      $("manualPreview").style.objectFit = animations.display?.scale_mode === "cover" ? "cover" : animations.display?.scale_mode === "stretch" ? "fill" : "contain";
      await refreshStateControls();
    }
    async function refreshStateControls() {
      if (!animations) return;
      manualState = await getJson("/api/state");
      $("stateMeta").textContent = [manualState.state, manualState.updated ? `updated ${manualState.updated}` : ""].filter(Boolean).join(" | ");
      $("manualDetail").value = manualState.detail || "";
      $("manualFps").value = manualState.fps_override || "";
      $("stateButtons").innerHTML = animations.states.map((state) => `<button type="button" data-state="${state}" class="${state === manualState.state ? "active" : ""}">${state}</button>`).join("");
      for (const button of $("stateButtons").querySelectorAll("button")) button.onclick = () => setManualState(button.dataset.state);
      if (lastState !== manualState.state) { frameIndex = 0; lastState = manualState.state; }
    }
    async function setManualState(state) {
      await getJson("/api/state", { method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({state, detail: $("manualDetail").value, fps_override: $("manualFps").value || null}) });
      await refreshStateControls();
    }
    function tick(timestamp) {
      if (animations && manualState) {
        const frames = animations.animations[manualState.state] || animations.animations[animations.default_state] || [];
        const fps = manualState.fps_override || animations.state_fps[manualState.state] || 8;
        if (frames.length && timestamp - lastFrameAt >= 1000 / fps) {
          $("manualPreview").src = frames[frameIndex % frames.length] + `?t=${Date.now()}`;
          frameIndex += 1;
          lastFrameAt = timestamp;
        }
      }
      requestAnimationFrame(tick);
    }
    async function upload(id) {
      if (!$(id).files.length) return "";
      const form = new FormData();
      form.append("file", $(id).files[0]);
      return (await getJson("/api/sprites/upload", {method: "POST", body: form})).path;
    }
    async function spriteSpec() {
      uploadedBackground ||= await upload("spriteBackground");
      uploadedSheet ||= await upload("spriteSheet");
      const spec = {
        canvas: { width: num("canvasWidth"), height: num("canvasHeight") },
        background: uploadedBackground,
        state: $("spriteState").value,
        sheet: uploadedSheet,
        mode: $("spriteMode").value,
        frame_width: num("frameWidth"),
        frame_height: num("frameHeight"),
        columns: num("columns"),
        frame_count: num("frameCount"),
        position: { x: num("posX") || 0, y: num("posY") || 0 },
        scale: num("spriteScale") || 1,
        frames: parseJson($("explicitFrames").value, [])
      };
      return spec;
    }
    async function previewSprites(apply) {
      $("spriteStatus").textContent = "Processing...";
      const payload = await getJson(apply ? "/api/sprites/process" : "/api/sprites/preview", { method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(await spriteSpec()) });
      $("spriteStatus").textContent = apply ? `Wrote ${payload.frames.length} frames to ${payload.output}` : `${payload.frames.length} preview frames`;
      $("spriteFrames").innerHTML = payload.frames.map((src) => `<img src="${src}" alt="Sprite frame preview">`).join("");
      animations = await getJson("/api/animations");
    }
    $("save").onclick = async () => {
      const fromRaw = document.querySelector("section.active")?.id === "raw";
      const body = fromRaw ? { yaml: $("rawYaml").value } : { config: collect() };
      const payload = await getJson("/api/config", { method: "PUT", headers: {"Content-Type": "application/json"}, body: JSON.stringify(body) });
      rawConfig = payload.config;
      window.currentYaml = payload.yaml;
      hydrate();
      animations = await getJson("/api/animations");
      $("manualPreview").style.objectFit = animations.display?.scale_mode === "cover" ? "cover" : animations.display?.scale_mode === "stretch" ? "fill" : "contain";
    };
    $("previewSprites").onclick = () => previewSprites(false).catch((error) => $("spriteStatus").innerHTML = `<span class="error">${error.message || error}</span>`);
    $("applySprites").onclick = () => previewSprites(true).catch((error) => $("spriteStatus").innerHTML = `<span class="error">${error.message || error}</span>`);
    $("spriteBackground").onchange = () => { uploadedBackground = ""; };
    $("spriteSheet").onchange = () => { uploadedSheet = ""; };
    $("tabs").onclick = (event) => {
      if (!event.target.dataset.tab) return;
      for (const button of $("tabs").querySelectorAll("button")) button.classList.toggle("active", button === event.target);
      for (const section of document.querySelectorAll("section")) section.classList.toggle("active", section.id === event.target.dataset.tab);
    };
    $("avatar.states").onchange = () => {
      const states = csv($("avatar.states").value);
      $("avatar.default_state").innerHTML = states.map((state) => `<option>${state}</option>`).join("");
    };
    loadAll().then(() => requestAnimationFrame(tick)).catch((error) => alert(error.message || error));
    setInterval(() => refreshStateControls().catch(console.error), 1000);
  </script>
</body>
</html>
"""


def _clean_mapping(value):
    if isinstance(value, dict):
        return {key: _clean_mapping(item) for key, item in value.items() if item is not None}
    if isinstance(value, list):
        return [_clean_mapping(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    return value


def _config_to_dict(config):
    return _clean_mapping(
        {
            "avatar": asdict(config.avatar),
            "source": asdict(config.source),
            "parser": asdict(config.parser),
            "mode": config.mode,
            "display": asdict(config.display),
        }
    )


def _safe_upload_name(filename):
    name = Path(filename or "upload.png").name.replace("\\", "_").replace("/", "_")
    return name if name and not name.startswith(".") else "upload.png"


def _parse_multipart(body, content_type):
    marker = "boundary="
    if marker not in content_type:
        raise ValueError("Missing multipart boundary")
    boundary = ("--" + content_type.split(marker, 1)[1].split(";", 1)[0].strip().strip('"')).encode()
    parts = {}
    for chunk in body.split(boundary):
        if chunk.startswith(b"\r\n"):
            chunk = chunk[2:]
        if chunk.endswith(b"--\r\n"):
            chunk = chunk[:-4]
        elif chunk.endswith(b"--"):
            chunk = chunk[:-2]
        if chunk.endswith(b"\r\n"):
            chunk = chunk[:-2]
        if not chunk:
            continue
        header_blob, _, data = chunk.partition(b"\r\n\r\n")
        headers = header_blob.decode("utf-8", "replace").split("\r\n")
        disposition = next((header for header in headers if header.lower().startswith("content-disposition:")), "")
        if "name=" not in disposition:
            continue
        name = disposition.split("name=", 1)[1].split(";", 1)[0].strip().strip('"')
        filename = ""
        if "filename=" in disposition:
            filename = disposition.split("filename=", 1)[1].split(";", 1)[0].strip().strip('"')
        parts[name] = {"filename": filename, "data": data}
    return parts


def _frame_data_url(image):
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def _sprite_manifest(payload):
    state = payload.get("state")
    if not state:
        raise AssetManifestError("Sprite state is required")
    if not payload.get("background"):
        raise AssetManifestError("Background image is required")
    if not payload.get("sheet"):
        raise AssetManifestError("Spritesheet image is required")
    spec = {
        "sheet": payload.get("sheet"),
        "mode": payload.get("mode", "grid"),
        "position": payload.get("position", {}),
        "scale": payload.get("scale", 1),
    }
    if spec["mode"] == "grid":
        for key in ("frame_width", "frame_height", "columns", "frame_count"):
            spec[key] = payload.get(key)
    else:
        spec["frames"] = payload.get("frames") or []
    return {
        "canvas": payload.get("canvas") or {"width": 800, "height": 480},
        "background": payload.get("background"),
        "states": {state: spec},
    }


class AvatarWebHandler(BaseHTTPRequestHandler):
    server_version = "AvatarPreview/2.0"

    @property
    def config(self):
        return self.server.config

    @property
    def store(self):
        return self.server.state_store

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/":
            return self._send_text(DISPLAY_HTML, "text/html")
        if path == "/config":
            return self._send_text(CONFIG_HTML, "text/html")
        if path == "/api/state":
            return self._send_json(self.store.read().__dict__)
        if path == "/api/animations":
            return self._send_json(self._animation_payload())
        if path == "/api/config":
            return self._send_json(self._config_payload())
        if path.startswith("/assets/"):
            return self._send_asset(path.removeprefix("/assets/"))
        self.send_error(404, "Not found")

    def do_POST(self):
        path = urlparse(self.path).path
        if path == "/api/state":
            return self._post_state()
        if path == "/api/sprites/upload":
            return self._post_sprite_upload()
        if path == "/api/sprites/preview":
            return self._post_sprite_preview(process=False)
        if path == "/api/sprites/process":
            return self._post_sprite_preview(process=True)
        self.send_error(404, "Not found")

    def do_PUT(self):
        if urlparse(self.path).path != "/api/config":
            return self.send_error(404, "Not found")
        try:
            payload = self._read_json()
            if "yaml" in payload:
                data = yaml.safe_load(payload["yaml"]) or {}
                raw = yaml.safe_dump(data, sort_keys=False)
            else:
                data = payload.get("config") or {}
                raw = yaml.safe_dump(_clean_mapping(data), sort_keys=False)
            with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as file:
                file.write(raw)
                temp_path = Path(file.name)
            try:
                load_config(os.environ, path=temp_path)
            finally:
                temp_path.unlink(missing_ok=True)
            self.config.config_file.parent.mkdir(parents=True, exist_ok=True)
            self.config.config_file.write_text(raw)
            self.server.replace_config(load_config(os.environ, path=self.config.config_file))
            return self._send_json(self._config_payload())
        except (ConfigError, OSError, yaml.YAMLError, ValueError) as exc:
            return self._send_json({"error": str(exc)}, status=400)

    def _post_state(self):
        try:
            payload = self._read_json()
        except ValueError:
            return self.send_error(400, "Invalid JSON")

        state = payload.get("state")
        if state not in self.config.states:
            return self.send_error(400, "Unknown state")

        self.store.write(state, payload.get("detail", ""), fps_override=payload.get("fps_override"))
        return self._send_json(self.store.read().__dict__)

    def _post_sprite_upload(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
            parts = _parse_multipart(self.rfile.read(length), self.headers.get("Content-Type", ""))
            upload = parts.get("file")
            if not upload:
                raise ValueError("Missing file")
            upload_dir = Path("source-assets/uploads")
            upload_dir.mkdir(parents=True, exist_ok=True)
            path = upload_dir / _safe_upload_name(upload["filename"])
            path.write_bytes(upload["data"])
            return self._send_json({"path": str(path.relative_to(Path("source-assets")))})
        except (OSError, ValueError) as exc:
            return self._send_json({"error": str(exc)}, status=400)

    def _post_sprite_preview(self, process):
        try:
            payload = self._read_json()
            manifest = _sprite_manifest(payload)
            if process:
                process_manifest(manifest, "source-assets", self.config.asset_dir)
                state = next(iter(manifest["states"]))
                frames = [f"/assets/{state}/{path.name}" for path in sorted((self.config.asset_dir / state).glob("*.png"))]
                return self._send_json({"frames": frames, "output": str(self.config.asset_dir / state)})
            with tempfile.TemporaryDirectory() as tmpdir:
                process_manifest(manifest, "source-assets", tmpdir)
                state = next(iter(manifest["states"]))
                frames = [_frame_data_url(Image.open(path)) for path in sorted((Path(tmpdir) / state).glob("*.png"))]
                return self._send_json({"frames": frames, "output": tmpdir})
        except (AssetManifestError, OSError, ValueError, json.JSONDecodeError) as exc:
            return self._send_json({"error": str(exc)}, status=400)

    def log_message(self, format, *args):
        print(f"{self.address_string()} - {format % args}", flush=True)

    def _read_json(self):
        length = int(self.headers.get("Content-Length", "0"))
        try:
            return json.loads(self.rfile.read(length).decode("utf-8") or "{}")
        except json.JSONDecodeError as exc:
            raise ValueError("Invalid JSON") from exc

    def _config_payload(self):
        yaml_text = self.config.config_file.read_text() if self.config.config_file.exists() else ""
        return {"path": str(self.config.config_file), "config": _config_to_dict(self.config), "yaml": yaml_text}

    def _animation_payload(self):
        animations = {}
        for animation in load_animation_states(self.config):
            animations[animation.name] = [f"/assets/{animation.name}/{path.name}" for path in animation.frame_paths]
        return {
            "states": self.config.states,
            "default_state": self.config.default_state,
            "state_fps": self.config.state_fps,
            "animations": animations,
            "display": asdict(self.config.display),
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

    def replace_config(self, config):
        self.config = config
        self.state_store = StateStore(config)


def run_web_renderer(config, host="127.0.0.1", port=8080):
    server = AvatarWebServer((host, port), config)
    print(f"web preview running at http://{host}:{port}", flush=True)
    print(f"configuration UI running at http://{host}:{port}/config", flush=True)
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
