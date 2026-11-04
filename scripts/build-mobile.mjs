import { cp, mkdir, rm, copyFile } from "node:fs/promises";
import { existsSync } from "node:fs";

const out = new URL("../www/", import.meta.url);
await rm(out, { recursive: true, force: true });
await mkdir(out, { recursive: true });

for (const name of ["index.html","manifest.webmanifest","app-icon.svg","sw.js"]) {
  await copyFile(new URL("../"+name, import.meta.url), new URL(name, out));
}
if (existsSync(new URL("../data/", import.meta.url))) {
  await cp(new URL("../data/", import.meta.url), new URL("data/", out), { recursive: true });
}
console.log("LOCK IN mobile web bundle prepared in www/");
