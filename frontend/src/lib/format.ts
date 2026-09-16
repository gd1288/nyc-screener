export const money = (v: number | null | undefined, compact = false) =>
  v == null
    ? "—"
    : new Intl.NumberFormat("en-US", {
        style: "currency",
        currency: "USD",
        maximumFractionDigits: compact && Math.abs(v) >= 1_000_000 ? 2 : 0,
        notation: compact ? "compact" : "standard",
      }).format(v);

export const pct = (v: number | null | undefined, digits = 1, signed = false) =>
  v == null ? "—" : `${signed && v > 0 ? "+" : ""}${(v * 100).toFixed(digits)}%`;

export const num = (v: number | null | undefined, digits = 0) =>
  v == null ? "—" : v.toLocaleString("en-US", { maximumFractionDigits: digits });

export const date = (iso: string | null | undefined) =>
  iso ? new Date(iso.length === 10 ? `${iso}T00:00:00` : iso).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" }) : "—";

export const dateTime = (iso: string | null | undefined) =>
  iso ? new Date(iso).toLocaleString("en-US", { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" }) : "—";

export function metricValue(v: number | null | undefined, fmt: string) {
  if (v == null) return "—";
  if (fmt === "pct") return pct(v, 1);
  if (fmt === "money") return money(v);
  if (fmt === "km") return `${v.toFixed(2)} km`;
  return num(v, 1);
}

/** Score 0-100 -> tailwind classes for a colored pill. */
export function scoreTone(score: number | null | undefined) {
  if (score == null) return "bg-stone-100 text-stone-500 ring-stone-200";
  if (score >= 65) return "bg-emerald-50 text-emerald-800 ring-emerald-200";
  if (score >= 50) return "bg-lime-50 text-lime-800 ring-lime-200";
  if (score >= 35) return "bg-amber-50 text-amber-800 ring-amber-200";
  return "bg-rose-50 text-rose-800 ring-rose-200";
}

export const BOROUGHS = ["Manhattan", "Brooklyn", "Queens", "Bronx", "Staten Island"];

export const PILLAR_ORDER = ["valuation", "development", "infrastructure", "demographics", "momentum", "commercial", "quality"];

export const PILLAR_SHORT: Record<string, string> = {
  valuation: "Valuation gap",
  development: "Development",
  infrastructure: "Infrastructure",
  demographics: "Demographics",
  momentum: "Momentum",
  commercial: "Commercial",
  quality: "Safety",
  flood_risk_penalty: "Flood risk",
};
