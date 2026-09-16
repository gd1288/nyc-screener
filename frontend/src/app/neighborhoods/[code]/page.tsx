"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import ListingTable from "@/components/ListingTable";
import NeighborhoodMap from "@/components/NeighborhoodMap";
import PillarBreakdown from "@/components/PillarBreakdown";
import { Card, ErrorNote, ScoreBadge, Stat, Tag, ghostButtonCls } from "@/components/ui";
import { useApi, type ListingRow, type NeighborhoodDetail } from "@/lib/api";
import { money, num, pct } from "@/lib/format";

export default function NeighborhoodPage() {
  const { code } = useParams<{ code: string }>();
  const router = useRouter();
  const { data, error } = useApi<NeighborhoodDetail>(`/neighborhoods/${code}`);
  const listings = useApi<ListingRow[]>(`/listings?status=active&neighborhood=${code}`);

  if (error) return <ErrorNote error={error} />;
  if (!data) return <div className="p-8 text-center text-sm text-stone-500">Loading…</div>;

  const m = (key: string) => {
    for (const p of Object.values(data.pillars)) if (p.metrics?.[key]) return p.metrics[key].value;
    return null;
  };
  const history = data.value_history;
  const tenYr = history.length > 10 ? (history[history.length - 1].value / history[history.length - 11].value) ** 0.1 - 1 : null;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <Link href="/neighborhoods" className="text-xs text-stone-500 hover:underline">← Neighborhoods</Link>
          <h1 className="mt-1 text-xl font-semibold">{data.name}</h1>
          <p className="text-sm text-stone-600">{data.borough} · {num(data.area_km2, 1)} km²</p>
        </div>
        <div className="flex items-center gap-3">
          <Link className={ghostButtonCls} href={`/compare?a=${data.code}`}>Compare…</Link>
          <div className="text-right text-xs text-stone-500">Growth score<br />{data.rank ? `#${data.rank} of ${data.total_ranked}` : ""}</div>
          <ScoreBadge score={data.score} size="lg" />
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4 rounded-xl border border-stone-200 bg-white p-4 sm:grid-cols-3 lg:grid-cols-6">
        <Stat label="Condo sales (2 yrs)" value={num(data.sales.sales_2y)} sub={`median ${money(data.sales.median_price_2y, true)}`} />
        <Stat label="Condo value growth/yr (10y)" value={pct(tenYr, 1)} />
        <Stat label="Gross rent yield" value={pct(m("gross_rent_yield"), 1)} />
        <Stat label="Discount to borough" value={pct(m("value_gap_borough"), 0)} tone={(m("value_gap_borough") ?? 0) > 0 ? "good" : undefined} />
        <Stat label="Active listings" value={data.active_listings} />
        <Stat label="Data coverage" value={pct(data.coverage, 0)} sub={data.coverage != null && data.coverage < 1 ? "missing pillars count as neutral" : undefined} />
      </div>

      <div className="grid gap-4 lg:grid-cols-[1.1fr_1fr]">
        <Card title="What drives the score" action={<span className="text-xs text-stone-500">Click a pillar for its metrics</span>}>
          <PillarBreakdown pillars={data.pillars} sources={data.metric_sources} />
        </Card>
        <div className="space-y-4">
          <NeighborhoodMap highlight={data.code} height={300} onSelectNeighborhood={(c) => router.push(`/neighborhoods/${c}`)} />
          <Card title="Growth catalysts nearby">
            {data.catalysts.length ? (
              <ul className="space-y-2 text-sm">
                {data.catalysts.map((c) => (
                  <li key={c.name}>
                    <div className="flex items-center gap-2 font-medium text-stone-800">{c.name} <Tag>{c.type}</Tag></div>
                    <div className="text-xs text-stone-500">{c.status} · weight {c.weight}</div>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-stone-500">No planned projects on the list near this neighborhood. Add projects in <code>backend/catalysts.yaml</code>.</p>
            )}
          </Card>
          {history.length > 1 && (
            <Card title="Typical condo value (Zillow ZHVI)">
              <ResponsiveContainer width="100%" height={200}>
                <LineChart data={history} margin={{ left: 8, right: 8, top: 8 }}>
                  <CartesianGrid stroke="#f5f5f4" />
                  <XAxis dataKey="year" tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }} tickFormatter={(v) => money(v, true)} width={64} domain={["auto", "auto"]} />
                  <Tooltip formatter={(v) => money(Number(v))} />
                  <Line type="monotone" dataKey="value" stroke="#059669" strokeWidth={2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </Card>
          )}
        </div>
      </div>

      {listings.data && listings.data.length > 0 && (
        <div>
          <h2 className="mb-2 text-sm font-semibold">Active listings here</h2>
          <ListingTable rows={listings.data} columns={["opportunity", "address", "price", "beds", "dom", "cap", "irr"]} />
        </div>
      )}
    </div>
  );
}
