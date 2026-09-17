"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import NeighborhoodMap from "@/components/NeighborhoodMap";
import { Card, ErrorNote, PageHeader, ScoreBadge, buttonCls, ghostButtonCls, inputCls } from "@/components/ui";
import { api, useApi, type NeighborhoodRow } from "@/lib/api";
import { BOROUGHS, PILLAR_ORDER, PILLAR_SHORT, money, pct } from "@/lib/format";

type Weights = { weights: Record<string, number>; defaults: Record<string, number>; pillars: Record<string, { label: string; description: string }> };
type Backtest = { results?: { horizon: string; neighborhoods: number; spearman_valuation_gap: number; spearman_momentum: number; spearman_combined: number; top_quintile_growth: number; bottom_quintile_growth: number }[]; error?: string };

export default function NeighborhoodsPage() {
  const router = useRouter();
  const hoods = useApi<NeighborhoodRow[]>("/neighborhoods");
  const [borough, setBorough] = useState("");
  const [query, setQuery] = useState("");
  const [condoOnly, setCondoOnly] = useState(true);
  const [sortKey, setSortKey] = useState("score");

  const rows = useMemo(() => {
    const list = (hoods.data ?? []).filter(
      (h) =>
        (!borough || h.borough === borough) &&
        (!query || h.name.toLowerCase().includes(query.toLowerCase())) &&
        (!condoOnly || (h.metrics.condo_sales_per_year ?? 0) >= 10),
    );
    const val = (h: NeighborhoodRow) => (sortKey === "score" ? h.score : sortKey in h.pillars ? h.pillars[sortKey] : h.metrics[sortKey]);
    return [...list].sort((a, b) => (val(b) ?? -Infinity) - (val(a) ?? -Infinity));
  }, [hoods.data, borough, query, condoOnly, sortKey]);

  // The "active condo markets" filter can hide the very top of the citywide ranking (thin sales data =
  // unreliable score), which otherwise looks like the list is missing rows at the start for no reason.
  const hiddenAboveVisible = condoOnly && rows.length > 0 ? (rows[0].rank ?? 1) - 1 : 0;

  return (
    <>
      <PageHeader
        title="Neighborhood growth scores"
        subtitle="Which neighborhoods have the most room and the most catalysts to grow over the next 10–20 years. Click a row or the map for the full profile."
        action={<Link className={ghostButtonCls} href="/compare">Compare two neighborhoods</Link>}
      />
      <ErrorNote error={hoods.error} />
      <div className="grid gap-4 xl:grid-cols-[1fr_440px]">
        <div className="min-w-0 space-y-3">
          <div className="flex flex-wrap items-center gap-3 rounded-xl border border-stone-200 bg-white p-3 text-sm">
            <input className={`${inputCls} max-w-56`} placeholder="Search neighborhood" value={query} onChange={(e) => setQuery(e.target.value)} />
            <select className={`${inputCls} max-w-40`} value={borough} onChange={(e) => setBorough(e.target.value)}>
              <option value="">All boroughs</option>
              {BOROUGHS.map((b) => <option key={b}>{b}</option>)}
            </select>
            <label className="flex items-center gap-1.5 text-stone-700" title="At least 10 condo sales per year">
              <input type="checkbox" checked={condoOnly} onChange={(e) => setCondoOnly(e.target.checked)} /> Active condo markets only
            </label>
            <span className="ml-auto text-xs text-stone-500">
              {rows.length} of {hoods.data?.length ?? 0} neighborhoods
              {hiddenAboveVisible > 0 && ` (#1–${hiddenAboveVisible} hidden: too few condo sales to score reliably)`}
            </span>
          </div>
          <div className="overflow-x-auto rounded-xl border border-stone-200 bg-white">
            <table className="w-full text-sm tabular-nums">
              <thead className="border-b border-stone-200 bg-stone-50 text-xs text-stone-600">
                <tr>
                  <th className="px-3 py-2 text-left font-medium">#</th>
                  <th className="px-3 py-2 text-left font-medium">Neighborhood</th>
                  <SortTh k="score" label="Score" sortKey={sortKey} setSortKey={setSortKey} />
                  {PILLAR_ORDER.map((p) => <SortTh key={p} k={p} label={PILLAR_SHORT[p]} sortKey={sortKey} setSortKey={setSortKey} />)}
                  <SortTh k="flood_risk_penalty" label="Flood" sortKey={sortKey} setSortKey={setSortKey} />
                  <SortTh k="condo_value" label="Typical condo" sortKey={sortKey} setSortKey={setSortKey} />
                  <SortTh k="gross_rent_yield" label="Gross yield" sortKey={sortKey} setSortKey={setSortKey} />
                  <SortTh k="active_listings" label="Listings" sortKey={sortKey} setSortKey={setSortKey} />
                </tr>
              </thead>
              <tbody className="divide-y divide-stone-100">
                {rows.map((h) => (
                  <tr key={h.code} className="cursor-pointer hover:bg-stone-50" onClick={() => router.push(`/neighborhoods/${h.code}`)}>
                    <td className="px-3 py-1.5 text-stone-500">{h.rank ?? "—"}</td>
                    <td className="px-3 py-1.5">
                      <div className="font-medium text-stone-900">{h.name}</div>
                      <div className="text-xs text-stone-500">{h.borough}{h.coverage < 0.8 ? ` · ${pct(h.coverage, 0)} data coverage` : ""}</div>
                    </td>
                    <td className="px-3 py-1.5 text-right"><ScoreBadge score={h.score} /></td>
                    {PILLAR_ORDER.map((p) => (
                      <td key={p} className="px-3 py-1.5 text-right text-stone-700">{h.pillars[p] == null ? "—" : Math.round(h.pillars[p]!)}</td>
                    ))}
                    <td className={`px-3 py-1.5 text-right ${h.pillars.flood_risk_penalty ? "text-rose-700" : "text-stone-400"}`}>
                      {h.pillars.flood_risk_penalty ? h.pillars.flood_risk_penalty.toFixed(1) : "0"}
                    </td>
                    <td className="px-3 py-1.5 text-right">{money(h.metrics.condo_value, true)}</td>
                    <td className="px-3 py-1.5 text-right">{pct(h.metrics.gross_rent_yield, 1)}</td>
                    <td className="px-3 py-1.5 text-right">{h.active_listings || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
        <div className="space-y-4 xl:sticky xl:top-16 xl:self-start">
          <NeighborhoodMap height={380} onSelectNeighborhood={(c) => router.push(`/neighborhoods/${c}`)} />
          <WeightsCard onSaved={hoods.reload} />
          <BacktestCard />
        </div>
      </div>
    </>
  );
}

function SortTh({ k, label, sortKey, setSortKey }: { k: string; label: string; sortKey: string; setSortKey: (k: string) => void }) {
  return (
    <th className="whitespace-nowrap px-3 py-2 text-right font-medium">
      <button className={`hover:text-stone-900 ${sortKey === k ? "text-stone-900 underline" : ""}`} onClick={() => setSortKey(k)}>{label}</button>
    </th>
  );
}

function WeightsCard({ onSaved }: { onSaved: () => void }) {
  const { data, setData } = useApi<Weights>("/weights");
  const [saving, setSaving] = useState(false);
  if (!data) return null;
  const keys = [...PILLAR_ORDER, "flood_risk_penalty"];

  async function save(weights: Record<string, number>) {
    setSaving(true);
    try {
      const res = await api<{ weights: Record<string, number> }>("/weights", { method: "PUT", body: JSON.stringify(weights) });
      setData({ ...data!, weights: res.weights });
      onSaved();
    } finally {
      setSaving(false);
    }
  }

  return (
    <Card title="Score weights" action={
      <div className="flex gap-2">
        <button className="text-xs text-stone-500 hover:text-stone-900" onClick={() => save(data.defaults)} disabled={saving}>Reset</button>
        <button className={buttonCls} onClick={() => save(data.weights)} disabled={saving}>{saving ? "Rescoring…" : "Apply"}</button>
      </div>
    }>
      <div className="space-y-2">
        {keys.map((k) => (
          <label key={k} className="grid grid-cols-[120px_1fr_32px] items-center gap-2 text-sm" title={data.pillars[k]?.description}>
            <span className="text-stone-700">{PILLAR_SHORT[k]}</span>
            <input type="range" min={0} max={40} step={5} value={data.weights[k] ?? 0}
              onChange={(e) => setData({ ...data, weights: { ...data.weights, [k]: Number(e.target.value) } })} />
            <span className="text-right tabular-nums text-stone-600">{data.weights[k]}</span>
          </label>
        ))}
      </div>
      <p className="mt-2 text-xs text-stone-500">Pillar weights are relative. Flood risk is a penalty in points for neighborhoods with 50%+ of their area in the 2050s floodplain (scaled down below that).</p>
    </Card>
  );
}

function BacktestCard() {
  const { data } = useApi<Backtest>("/backtest");
  if (!data?.results?.length) return null;
  return (
    <Card title="Does the score predict growth? (backtest)">
      <p className="mb-2 text-xs text-stone-600">
        Using only data available at the start of each period: rank correlation with the next 10 years of condo value growth per neighborhood (+1 is perfect, 0 is none).
      </p>
      <table className="w-full text-xs tabular-nums">
        <thead className="text-stone-500">
          <tr>
            <th className="text-left font-normal">Period</th>
            <th className="text-right font-normal">Valuation gap</th>
            <th className="text-right font-normal">Momentum</th>
            <th className="text-right font-normal">Top vs bottom 20%</th>
          </tr>
        </thead>
        <tbody>
          {data.results.map((r) => (
            <tr key={r.horizon} className="border-t border-stone-100">
              <td className="py-1">{r.horizon}</td>
              <td className={`py-1 text-right ${r.spearman_valuation_gap > 0 ? "text-emerald-700" : "text-rose-700"}`}>{r.spearman_valuation_gap.toFixed(2)}</td>
              <td className={`py-1 text-right ${r.spearman_momentum > 0 ? "text-emerald-700" : "text-rose-700"}`}>{r.spearman_momentum.toFixed(2)}</td>
              <td className="py-1 text-right">{pct(r.top_quintile_growth, 1)} vs {pct(r.bottom_quintile_growth, 1)}/yr</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="mt-2 text-xs text-stone-500">Cheaper-than-borough neighborhoods consistently outgrew; recent momentum tended to reverse. That&apos;s why valuation gap carries more weight than momentum by default.</p>
    </Card>
  );
}
