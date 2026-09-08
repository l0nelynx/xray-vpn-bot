import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";
import path from "node:path";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const children = [];
let stopping = false;
function stop() {
  if (stopping) return;
  stopping = true;
  for (const child of children) child.kill();
}
function start(cwd, args) {
  const child = spawn(process.execPath, args, {
    cwd,
    stdio: "inherit",
    windowsHide: true,
  });
  children.push(child);
  child.on("exit", (code) => {
    if (!stopping) {
      process.exitCode = code || 0;
      stop();
    }
  });
  child.on("error", (error) => {
    console.error(error.message);
    process.exitCode = 1;
    stop();
  });
}
start(root, ["scripts/support-mock-server.mjs"]);
for (const [app, port] of [
  ["dashboard", "5173"],
  ["miniapp", "5174"],
]) {
  start(path.join(root, "web/apps", app), [
    "node_modules/vite/bin/vite.js",
    "--mode",
    "mock",
    "--host",
    "127.0.0.1",
    "--port",
    port,
    "--strictPort",
  ]);
}
process.on("SIGINT", stop);
process.on("SIGTERM", stop);
