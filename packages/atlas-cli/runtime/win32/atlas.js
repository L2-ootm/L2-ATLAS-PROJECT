#!/usr/bin/env node
"use strict";

const fs = require("node:fs");
const path = require("node:path");
const { spawnSync } = require("node:child_process");

const root = path.resolve(__dirname, "..");
const python = path.join(root, "python", "python.exe");
const gateway = path.join(root, "native", "atlas-core-rs", "target", "release", "atlas-gateway.exe");
const tui = path.join(root, "services", "atlas-tui", "atlas-tui.exe");

for (const [label, file] of [["embedded Python", python], ["Rust gateway", gateway], ["terminal UI", tui]]) {
  if (!fs.existsSync(file)) {
    process.stderr.write(`ATLAS runtime is incomplete: ${label} is missing (${file})\n`);
    process.exit(1);
  }
}

const env = {
  ...process.env,
  ATLAS_GATEWAY_BIN: process.env.ATLAS_GATEWAY_BIN || gateway,
  ATLAS_RELEASE_ROOT: root,
  ATLAS_TUI_BIN: process.env.ATLAS_TUI_BIN || tui,
  PYTHONDONTWRITEBYTECODE: "1",
  PYTHONNOUSERSITE: "1",
  PYTHONUTF8: "1",
};
const result = spawnSync(python, ["-s", "-m", "atlas_runtime.cli.main", ...process.argv.slice(2)], {
  cwd: process.cwd(),
  env,
  stdio: "inherit",
  windowsHide: true,
});
if (result.error) throw result.error;
process.exit(result.status ?? 1);
