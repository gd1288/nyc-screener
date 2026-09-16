"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useMemo } from "react";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Card, PageHeader, ScoreBadge, inputCls } from "@/components/ui";
import { useApi, type NeighborhoodDetail, type NeighborhoodRow } from "@/lib/api";
import { PILLAR_ORDER, PILLAR_SHORT, metricValue } from "@/lib/format";

// Defaults to the example from the brief: Financial District vs Chelsea.
const DEFAULT_A = "MN0101";
const DEFAULT_B = "MN0401";

export default function ComparePage() {
  return (
    <Suspense>
      <Compare />
    </Suspense>
  );
}

function Compare() {
  const router = useRouter();
  const params = useSearchParams();
  const a = params.get("a") ?? DEFAULT_A;
  const b = params.get("b") ?? DEFAULT_B;
  const all = useApi<NeighborhoodRow[]>("/neighborhoods");
  const A = useApi<NeighborhoodDetail>(`/neighborhoods/${a}`);
  const B = useApi<NeighborhoodDetail>(`/neighborhoods/${b}`);

  const options = useMemo(() => [...(all.data ?? [])].sort((x, y) => x.name.localeCompare(y.name)), [all.data]);
  const set = (key: "a" | "b", code: string) => {
    const q = new URLSearchParams({ a, b, [key]: code });
    router.replace(`/compare?${q}`);
  };

  const ready = A.data && B.data;
  const chart = ready
    ? PILLAR_ORDER.map((p) => ({ pillar: PILLAR_SHORT[p], [A.data!.name]: A.data!.pillars[p]?.score ?? null, [B.data!.name]: B.data!.pillars[p]?.score ?? null }))
    : [];

  return (
    <>
      <PageHeader title="Compare neighborhoods" subtitle="See which growth drivers explain the gap between two neighborhoods." />
      <div className="mb-4 grid gap-3 sm:grid-cols-2">
        {(["a", "b"] as const).map((key) => (
          <select key={key} className={inputCls} value={key === "a" ? a : b} onChange={(e) => set(key, e.target.value)}>
            {options.map((o) => <option key={o.code} value={o.code}>{o.name} ({o.borough})</option>)}
          </select>
        ))}
      </div>
      {ready && (
        <div className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">
            {[A.data!, B.data!].map((d) => (
              <div key={d.code} className="flex items-center justify-between rounded-xl border border-stone-200 bg-white p-4">
                <div>
                  <div className="font-semibold">{d.name}</div>
                  <div className="text-xs text-stone-500">{d.borough} · rank #{d.rank} of {d.total_ranked}</div>
                </div>
                <ScoreBadge score={d.score} size="lg" />
              </div>
            ))}
          </div>
          <Card title="Pillar scores">
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={chart} margin={{ top: 8, right: 8 }}>
                <CartesianGrid stroke="#f5f5f4" vertical={false} />
                <XAxis dataKey="pillar" tick={{ fontSize: 11 }} interval={0} />
                <YAxis domain={[0, 100]} tick={{ fontSize: 11 }} width={32} />
                <Tooltip />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                <Bar dataKey={A.data!.name} fill="#1c1917" radius={[3, 3, 0, 0]} />
                <Bar dataKey={B.data!.name} fill="#a8a29e" radius={[3, 3, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </Card>
          <Card title="Why the scores differ">
            <Explanation a={A.data!} b={B.data!} />
          </Card>
          <Card title="Every metric side by side">
            <div className="overflow-x-auto">
              <table className="w-full text-sm tabular-nums">
                <thead className="text-xs text-stone-500">
                  <tr>
                    <th className="py-1 text-left font-normal">Metric</th>
                    <th className="py-1 text-right font-normal">{A.data!.name}</th>
                    <th className="py-1 text-right font-normal">{B.data!.name}</th>
                    <th className="py-1 text-right font-normal">Edge</th>
                  </tr>
                </thead>
                <tbody>
                  {PILLAR_ORDER.flatMap((p) =>
                    Object.entries(A.data!.pillars[p]?.metrics ?? {}).map(([mk, ma]) => {
                      const mb = B.data!.pillars[p]?.metrics?.[mk];
                      const pa = ma.percentile, pb = mb?.percentile;
                      const edge = pa == null || pb == null ? "—" : Math.abs(pa - pb) < 5 ? "even" : pa > pb ? A.data!.name.split("-")[0] : B.data!.name.split("-")[0];
                      return (
                        <tr key={`${p}-${mk}`} className="border-t border-stone-100">
                          <td className="py-1 pr-3"><span className="text-xs text-stone-400">{PILLAR_SHORT[p]} · </span>{ma.label}</td>
                          <td className="py-1 text-right">{metricValue(ma.value, ma.fmt)}</td>
                          <td className="py-1 text-right">{metricValue(mb?.value, ma.fmt)}</td>
                          <td className="py-1 text-right text-xs text-stone-600">{edge}</td>
                        </tr>
                      );
                    }),
                  )}
                  <tr className="border-t border-stone-200">
                    <td className="py-1">Flood risk penalty (points)</td>
                    <td className="py-1 text-right text-rose-700">{A.data!.pillars.flood_risk_penalty?.points?.toFixed(1)}</td>
                    <td className="py-1 text-right text-rose-700">{B.data!.pillars.flood_risk_penalty?.points?.toFixed(1)}</td>
                    <td />
                  </tr>
                </tbody>
              </table>
            </div>
          </Card>
        </div>
      )}
    </>
  );
}

function Explanation({ a, b }: { a: NeighborhoodDetail; b: NeighborhoodDetail }) {
  // Contribution of each pillar to the score gap = weight share x score difference.
  const totalWeight = PILLAR_ORDER.reduce((s, p) => s + (a.pillars[p]?.weight ?? 0), 0) || 1;
  const parts = PILLAR_ORDER.map((p) => {
    const sa = a.pillars[p]?.score ?? 50, sb = b.pillars[p]?.score ?? 50;
    return { p, label: a.pillars[p]?.label ?? p, points: ((a.pillars[p]?.weight ?? 0) / totalWeight) * (sa - sb) };
  });
  const flood = (a.pillars.flood_risk_penalty?.points ?? 0) - (b.pillars.flood_risk_penalty?.points ?? 0);
  parts.push({ p: "flood", label: "Flood risk penalty", points: flood });
  parts.sort((x, y) => Math.abs(y.points) - Math.abs(x.points));
  const gap = (a.score ?? 0) - (b.score ?? 0);
  const max = Math.max(...parts.map((x) => Math.abs(x.points)), 1);

  return (
    <div>
      <p className="mb-3 text-sm text-stone-700">
        <b>{a.name}</b> scores <b>{Math.abs(gap).toFixed(1)} points {gap >= 0 ? "higher" : "lower"}</b> than <b>{b.name}</b>. Contribution of each driver
        (positive favors {a.name.split("-")[0]}):
      </p>
      <div className="space-y-1.5">
        {parts.map((x) => (
          <div key={x.p} className="grid grid-cols-[180px_1fr_56px] items-center gap-2 text-sm">
            <span className="truncate text-stone-700">{x.label}</span>
            <div className="relative h-3 rounded bg-stone-100">
              <div className="absolute top-0 h-3 w-px bg-stone-400" style={{ left: "50%" }} />
              <div
                className={`absolute top-0 h-3 rounded ${x.points >= 0 ? "bg-stone-900" : "bg-stone-400"}`}
                style={{ left: x.points >= 0 ? "50%" : `${50 - (Math.abs(x.points) / max) * 50}%`, width: `${(Math.abs(x.points) / max) * 50}%` }}
              />
            </div>
            <span className="text-right tabular-nums">{x.points >= 0 ? "+" : ""}{x.points.toFixed(1)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
