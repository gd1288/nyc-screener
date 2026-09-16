"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import ListingTable from "@/components/ListingTable";
import NeighborhoodMap from "@/components/NeighborhoodMap";
import { Empty, ErrorNote, PageHeader, Stat, inputCls } from "@/components/ui";
import { useApi, type ListingRow, type NeighborhoodRow, type Summary } from "@/lib/api";
import { BOROUGHS, money } from "@/lib/format";

type Filters = {
  borough: string;
  neighborhood: string;
  min_price: string;
  max_price: string;
  min_beds: string;
  min_growth: string;
  min_cap_rate: string;
  max_days_on_market: string;
  price_cut: boolean;
  new_only: boolean;
};

const EMPTY: Filters = {
  borough: "", neighborhood: "", min_price: "", max_price: "", min_beds: "", min_growth: "",
  min_cap_rate: "", max_days_on_market: "", price_cut: false, new_only: false,
};

function toQuery(f: Filters) {
  const q = new URLSearchParams({ status: "active" });
  for (const [k, v] of Object.entries(f)) {
    if (v === "" || v === false) continue;
    q.set(k, k === "min_cap_rate" ? String(Number(v) / 100) : String(v));
  }
  return q.toString();
}

export default function ScreenerPage() {
  const router = useRouter();
  const [filters, setFilters] = useState<Filters>(EMPTY);
  const listings = useApi<ListingRow[]>(`/listings?${toQuery(filters)}`);
  const summary = useApi<Summary>("/summary");
  const hoods = useApi<NeighborhoodRow[]>("/neighborhoods");

  const set = <K extends keyof Filters>(k: K, v: Filters[K]) => setFilters((f) => ({ ...f, [k]: v }));
  const rows = useMemo(() => listings.data ?? [], [listings.data]);
  const points = useMemo(
    () =>
      rows
        .filter((r) => r.latitude != null && r.longitude != null)
        .map((r) => ({ id: r.id, latitude: r.latitude!, longitude: r.longitude!, label: `${r.address} · ${money(r.price, true)}` })),
    [rows],
  );
  const hoodOptions = (hoods.data ?? []).filter((h) => !filters.borough || h.borough === filters.borough).sort((a, b) => a.name.localeCompare(b.name));

  return (
    <>
      <PageHeader
        title="Condo screener"
        subtitle="Active NYC condo listings ranked by Opportunity Score: neighborhood growth potential, value vs comps and rental yield."
      />
      <ErrorNote error={listings.error} />

      {summary.data && (
        <div className="mb-5 grid grid-cols-2 gap-4 rounded-xl border border-stone-200 bg-white p-4 sm:grid-cols-5">
          <Stat label="Active listings" value={summary.data.active} />
          <Stat label="New (3 days)" value={summary.data.new} />
          <Stat label="With price cuts" value={summary.data.price_drops} />
          <Stat label="Sold / off market" value={summary.data.sold + summary.data.off_market} />
          <Stat label="Neighborhoods scored" value={summary.data.neighborhoods_scored} />
        </div>
      )}

      <div className="mb-4 grid grid-cols-2 gap-3 rounded-xl border border-stone-200 bg-white p-4 md:grid-cols-4 xl:grid-cols-8">
        <Field label="Borough">
          <select className={inputCls} value={filters.borough} onChange={(e) => setFilters((f) => ({ ...f, borough: e.target.value, neighborhood: "" }))}>
            <option value="">All</option>
            {BOROUGHS.map((b) => <option key={b}>{b}</option>)}
          </select>
        </Field>
        <Field label="Neighborhood">
          <select className={inputCls} value={filters.neighborhood} onChange={(e) => set("neighborhood", e.target.value)}>
            <option value="">All</option>
            {hoodOptions.map((h) => <option key={h.code} value={h.code}>{h.name}</option>)}
          </select>
        </Field>
        <Field label="Min price ($)"><input className={inputCls} inputMode="numeric" value={filters.min_price} onChange={(e) => set("min_price", e.target.value)} placeholder="500000" /></Field>
        <Field label="Max price ($)"><input className={inputCls} inputMode="numeric" value={filters.max_price} onChange={(e) => set("max_price", e.target.value)} placeholder="2000000" /></Field>
        <Field label="Min beds"><input className={inputCls} inputMode="numeric" value={filters.min_beds} onChange={(e) => set("min_beds", e.target.value)} placeholder="1" /></Field>
        <Field label="Min growth score"><input className={inputCls} inputMode="numeric" value={filters.min_growth} onChange={(e) => set("min_growth", e.target.value)} placeholder="50" /></Field>
        <Field label="Min cap rate (%)"><input className={inputCls} inputMode="decimal" value={filters.min_cap_rate} onChange={(e) => set("min_cap_rate", e.target.value)} placeholder="3" /></Field>
        <Field label="Max days on market"><input className={inputCls} inputMode="numeric" value={filters.max_days_on_market} onChange={(e) => set("max_days_on_market", e.target.value)} placeholder="90" /></Field>
        <label className="col-span-2 flex items-center gap-4 text-sm text-stone-700 md:col-span-4 xl:col-span-8">
          <span className="flex items-center gap-1.5"><input type="checkbox" checked={filters.new_only} onChange={(e) => set("new_only", e.target.checked)} /> New only</span>
          <span className="flex items-center gap-1.5"><input type="checkbox" checked={filters.price_cut} onChange={(e) => set("price_cut", e.target.checked)} /> Price cut</span>
          <button className="ml-auto text-xs text-stone-500 hover:text-stone-900" onClick={() => setFilters(EMPTY)}>Clear filters</button>
        </label>
      </div>

      <div className="grid gap-4 xl:grid-cols-[1fr_420px]">
        <div className="min-w-0">
          {listings.loading && !listings.data ? (
            <div className="rounded-xl border border-stone-200 bg-white p-8 text-center text-sm text-stone-500">Loading listings…</div>
          ) : rows.length ? (
            <ListingTable
              rows={rows}
              columns={["opportunity", "address", "price", "beds", "ppsf", "dom", "growth", "cap", "cashflow", "irr", "comps"]}
              initialSort={{ key: "opportunity", desc: true }}
            />
          ) : summary.data?.active ? (
            <Empty title="No listings match these filters" />
          ) : (
            <Empty title="No listings yet">
              <p>Listings come from two places:</p>
              <ul className="mt-2 space-y-1 text-left">
                <li>• <b>RentCast</b> (automatic, daily): add a free <code>RENTCAST_API_KEY</code> to <code>.env</code>, then click <b>Refresh now</b>.</li>
                <li>• <b>Your own finds</b>: paste a listing from StreetEasy or a broker on the <Link className="underline" href="/add">Add listings</Link> page.</li>
              </ul>
              <p className="mt-3">Meanwhile, the <Link className="underline" href="/neighborhoods">Neighborhoods</Link> rankings are ready to explore.</p>
            </Empty>
          )}
        </div>
        <div className="xl:sticky xl:top-16 xl:self-start">
          <NeighborhoodMap
            points={points}
            highlight={filters.neighborhood || null}
            height={520}
            onSelectPoint={(id) => router.push(`/listing/${id}`)}
            onSelectNeighborhood={(code) => router.push(`/neighborhoods/${code}`)}
          />
        </div>
      </div>
    </>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs text-stone-500">{label}</span>
      {children}
    </label>
  );
}
