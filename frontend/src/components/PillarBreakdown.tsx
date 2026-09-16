"use client";

import { useState } from "react";
import type { PillarDetail } from "@/lib/api";
import { PILLAR_ORDER, metricValue, pct } from "@/lib/format";

function barColor(score: number | null | undefined) {
  if (score == null) return "bg-stone-300";
  if (score >= 65) return "bg-emerald-500";
  if (score >= 50) return "bg-lime-500";
  if (score >= 35) return "bg-amber-500";
  return "bg-rose-500";
}

export default function PillarBreakdown({
  pillars,
  sources,
}: {
  pillars: Record<string, PillarDetail>;
  sources?: Record<string, { as_of: string; source: string }>;
}) {
  const [open, setOpen] = useState<string | null>(null);
  const flood = pillars.flood_risk_penalty;

  return (
    <div className="space-y-1">
      {PILLAR_ORDER.filter((k) => pillars[k]).map((key) => {
        const p = pillars[key];
        const isOpen = open === key;
        return (
          <div key={key} className="rounded-lg">
            <button onClick={() => setOpen(isOpen ? null : key)} className="grid w-full grid-cols-[1fr_auto] items-center gap-x-3 rounded-md px-2 py-1.5 text-left hover:bg-stone-50 sm:grid-cols-[200px_1fr_auto]">
              <span className="text-sm text-stone-800">
                {p.label} <span className="text-xs text-stone-400">×{p.weight}</span>
              </span>
              <span className="order-3 col-span-2 mt-1 h-2 overflow-hidden rounded-full bg-stone-100 sm:order-none sm:col-span-1 sm:mt-0">
                <span className={`block h-full rounded-full ${barColor(p.score)}`} style={{ width: `${p.score ?? 0}%` }} />
              </span>
              <span className="w-16 text-right text-sm font-medium tabular-nums">{p.score == null ? "no data" : Math.round(p.score)}</span>
            </button>
            {isOpen && p.metrics && (
              <table className="mb-2 ml-2 w-[calc(100%-0.5rem)] text-xs">
                <thead className="text-stone-500">
                  <tr>
                    <th className="py-1 text-left font-normal">Metric</th>
                    <th className="py-1 text-right font-normal">Value</th>
                    <th className="py-1 text-right font-normal" title="Percentile among NYC neighborhoods, direction-adjusted: 100 = best">Pctile</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(p.metrics).map(([mk, m]) => (
                    <tr key={mk} className="border-t border-stone-100">
                      <td className="py-1 pr-2 text-stone-700">
                        {m.label}
                        {!m.higher_is_better && <span className="text-stone-400"> (lower is better)</span>}
                        {sources?.[mk] && <span className="block text-[10px] text-stone-400">{sources[mk].source} · {sources[mk].as_of}</span>}
                      </td>
                      <td className="py-1 text-right tabular-nums">{metricValue(m.value, m.fmt)}</td>
                      <td className="py-1 text-right tabular-nums">{m.percentile == null ? "—" : Math.round(m.percentile)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        );
      })}
      {flood && (
        <div className="flex items-center justify-between rounded-md px-2 py-1.5 text-sm">
          <span className="text-stone-800">
            {flood.label}
            <span className="block text-xs text-stone-500">{pct(flood.floodplain_share ?? 0, 0)} of area in the 2050s 100-year floodplain</span>
          </span>
          <span className={`w-16 text-right font-medium tabular-nums ${flood.points ? "text-rose-700" : "text-stone-500"}`}>
            {flood.points ? flood.points.toFixed(1) : "0"}
          </span>
        </div>
      )}
    </div>
  );
}
