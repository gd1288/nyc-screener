// maplibre-gl v6 is ESM-only and locates its worker via `new URL(..., import.meta.url)`,
// which Next.js's bundler doesn't resolve inside node_modules. We copy the worker and its
// sibling chunk (which it imports by relative path) into public/ and point maplibre at them
// with setWorkerUrl() — see src/lib/maplibre-worker.ts.
import { copyFileSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = dirname(dirname(fileURLToPath(import.meta.url)));
const src = join(root, "node_modules", "maplibre-gl", "dist");
const dest = join(root, "public", "maplibre");

mkdirSync(dest, { recursive: true });
for (const file of ["maplibre-gl-worker.mjs", "maplibre-gl-shared.mjs"]) {
  copyFileSync(join(src, file), join(dest, file));
}
