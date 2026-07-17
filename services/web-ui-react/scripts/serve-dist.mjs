#!/usr/bin/env node

import { createReadStream, existsSync, statSync } from "node:fs";
import { createServer } from "node:http";
import { extname, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";

const args = process.argv.slice(2);
const option = (name, fallback) => {
  const index = args.indexOf(name);
  return index >= 0 && args[index + 1] ? args[index + 1] : fallback;
};

const host = option("--host", "127.0.0.1");
const port = Number.parseInt(option("--port", "5173"), 10);
if (!Number.isInteger(port) || port < 1 || port > 65535) {
  throw new Error(`invalid --port: ${option("--port", "")}`);
}

const root = resolve(fileURLToPath(new URL("../dist", import.meta.url)));
const indexFile = resolve(root, "index.html");
if (!existsSync(indexFile)) throw new Error(`cockpit bundle missing: ${indexFile}`);

const mime = new Map([
  [".css", "text/css; charset=utf-8"],
  [".html", "text/html; charset=utf-8"],
  [".ico", "image/x-icon"],
  [".js", "text/javascript; charset=utf-8"],
  [".json", "application/json; charset=utf-8"],
  [".png", "image/png"],
  [".svg", "image/svg+xml"],
  [".woff", "font/woff"],
  [".woff2", "font/woff2"],
]);

function resolveRequest(url) {
  let pathname;
  try {
    pathname = decodeURIComponent(new URL(url || "/", "http://atlas.local").pathname);
  } catch {
    return null;
  }
  const candidate = resolve(root, `.${pathname}`);
  if (candidate !== root && !candidate.startsWith(`${root}${sep}`)) return null;
  if (existsSync(candidate) && statSync(candidate).isFile()) return candidate;
  return extname(pathname) ? null : indexFile;
}

const server = createServer((request, response) => {
  const file = resolveRequest(request.url);
  if (!file) {
    response.writeHead(404, { "content-type": "text/plain; charset=utf-8" });
    response.end("Not found\n");
    return;
  }
  response.writeHead(200, {
    "cache-control": file === indexFile ? "no-cache" : "public, max-age=31536000, immutable",
    "content-type": mime.get(extname(file).toLowerCase()) || "application/octet-stream",
    "x-content-type-options": "nosniff",
  });
  createReadStream(file).pipe(response);
});

server.listen(port, host, () => {
  process.stdout.write(`ATLAS cockpit serving ${root} on http://${host}:${port}\n`);
});
