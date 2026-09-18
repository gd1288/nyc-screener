import { setWorkerUrl } from "maplibre-gl";

// See scripts/copy-maplibre-worker.mjs for why these are copied into public/ rather than
// resolved from node_modules directly.
setWorkerUrl("/maplibre/maplibre-gl-worker.mjs");
