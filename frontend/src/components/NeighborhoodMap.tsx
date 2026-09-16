"use client";

import { Map as MapLibreMap } from "maplibre-gl";
import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";

type Point = { id: number; longitude: number; latitude: number; label: string };

type Props = {
  points?: Point[];
  highlight?: string | null;
  height?: number;
  onSelectNeighborhood?: (code: string) => void;
  onSelectPoint?: (id: number) => void;
};

// Free vector basemap, no API key (https://openfreemap.org).
const STYLE_URL = "https://tiles.openfreemap.org/styles/positron";
let geojsonPromise: Promise<GeoJSON.FeatureCollection> | null = null;


export default function NeighborhoodMap({ points = [], highlight = null, height = 460, onSelectNeighborhood, onSelectPoint }: Props) {
  const container = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const [ready, setReady] = useState(false);
  const [hover, setHover] = useState<{ x: number; y: number; text: string } | null>(null);
  const handlers = useRef({ onSelectNeighborhood, onSelectPoint });
  useEffect(() => {
    handlers.current = { onSelectNeighborhood, onSelectPoint };
  });

  useEffect(() => {
    if (!container.current) return;
    const map = new MapLibreMap({
      container: container.current,
      style: STYLE_URL,
      center: [-73.95, 40.7],
      zoom: 9.6,
      attributionControl: { compact: true },
    });
    mapRef.current = map;

    map.on("load", async () => {
      geojsonPromise ??= api<GeoJSON.FeatureCollection>("/neighborhoods/geojson");
      const data = await geojsonPromise;
      map.addSource("hoods", { type: "geojson", data, promoteId: "code" });
      map.addLayer({
        id: "hood-fill",
        type: "fill",
        source: "hoods",
        paint: {
          "fill-color": [
            "case",
            ["==", ["get", "score"], null],
            "#e7e5e4",
            ["interpolate", ["linear"], ["get", "score"], 25, "#e11d48", 45, "#f59e0b", 55, "#a3e635", 70, "#059669"],
          ],
          "fill-opacity": ["case", ["boolean", ["feature-state", "hover"], false], 0.75, 0.5],
        },
      });
      map.addLayer({ id: "hood-line", type: "line", source: "hoods", paint: { "line-color": "#ffffff", "line-width": 0.6 } });
      map.addLayer({
        id: "hood-highlight",
        type: "line",
        source: "hoods",
        paint: { "line-color": "#1c1917", "line-width": 2.5 },
        filter: ["==", ["get", "code"], ""],
      });
      map.addSource("points", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
      map.addLayer({
        id: "point-circles",
        type: "circle",
        source: "points",
        paint: { "circle-radius": 5, "circle-color": "#1c1917", "circle-stroke-color": "#fff", "circle-stroke-width": 1.5 },
      });

      let hovered: string | number | undefined;
      map.on("mousemove", (e) => {
        const pt = map.queryRenderedFeatures(e.point, { layers: ["point-circles"] })[0];
        const hood = map.queryRenderedFeatures(e.point, { layers: ["hood-fill"] })[0];
        if (hovered !== undefined) map.setFeatureState({ source: "hoods", id: hovered }, { hover: false });
        hovered = hood?.id;
        if (hovered !== undefined) map.setFeatureState({ source: "hoods", id: hovered }, { hover: true });
        const p = hood?.properties as { name?: string; score?: number; rank?: number } | undefined;
        const text = pt
          ? String(pt.properties?.label)
          : p?.name
            ? `${p.name} — score ${p.score == null ? "n/a" : Math.round(p.score)}${p.rank ? ` (#${p.rank})` : ""}`
            : "";
        map.getCanvas().style.cursor = pt || hood ? "pointer" : "";
        setHover(text ? { x: e.point.x, y: e.point.y, text } : null);
      });
      map.on("mouseout", () => setHover(null));
      map.on("click", (e) => {
        const pt = map.queryRenderedFeatures(e.point, { layers: ["point-circles"] })[0];
        if (pt && handlers.current.onSelectPoint) return handlers.current.onSelectPoint(Number(pt.properties?.id));
        const hood = map.queryRenderedFeatures(e.point, { layers: ["hood-fill"] })[0];
        if (hood && handlers.current.onSelectNeighborhood) handlers.current.onSelectNeighborhood(String(hood.properties?.code));
      });
      setReady(true);
    });
    return () => map.remove();
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map) return;
    const src = map.getSource("points") as unknown as { setData: (d: GeoJSON.FeatureCollection) => void } | undefined;
    src?.setData({
      type: "FeatureCollection",
      features: points.map((p) => ({
        type: "Feature",
        geometry: { type: "Point", coordinates: [p.longitude, p.latitude] },
        properties: { id: p.id, label: p.label },
      })),
    });
  }, [ready, points]);

  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map) return;
    map.setFilter("hood-highlight", ["==", ["get", "code"], highlight ?? ""]);
    if (!highlight || !geojsonPromise) return;
    geojsonPromise.then((data) => {
      const f = data.features.find((x) => x.properties?.code === highlight);
      if (!f) return;
      const coords = JSON.stringify(f.geometry).match(/-?\d+\.\d+,-?\d+\.\d+/g) ?? [];
      const xy = coords.map((c) => c.split(",").map(Number));
      const xs = xy.map((c) => c[0]);
      const ys = xy.map((c) => c[1]);
      map.fitBounds([[Math.min(...xs), Math.min(...ys)], [Math.max(...xs), Math.max(...ys)]], { padding: 60, maxZoom: 14, duration: 600 });
    });
  }, [ready, highlight]);

  return (
    <div className="relative overflow-hidden rounded-xl border border-stone-200 bg-stone-100" style={{ height }}>
      {/* Inline size: maplibre-gl.css sets position:relative on this element, which beats layered Tailwind classes. */}
      <div ref={container} style={{ width: "100%", height: "100%" }} />
      {hover && (
        <div
          className="pointer-events-none absolute z-10 max-w-64 rounded-md bg-stone-900 px-2 py-1 text-xs text-white shadow"
          style={{ left: hover.x + 12, top: hover.y + 12 }}
        >
          {hover.text}
        </div>
      )}
      <div className="absolute left-2 top-2 z-10 flex items-center gap-2 rounded-md bg-white/90 px-2 py-1 text-[11px] text-stone-600 shadow-sm">
        Growth score
        <span className="h-2 w-24 rounded-full" style={{ background: "linear-gradient(90deg,#e11d48,#f59e0b,#a3e635,#059669)" }} />
        <span>low → high</span>
      </div>
    </div>
  );
}
