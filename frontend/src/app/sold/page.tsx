"use client";

import { useState } from "react";
import ListingTable from "@/components/ListingTable";
import { Empty, ErrorNote, PageHeader, Stat } from "@/components/ui";
import { useApi, type ListingRow } from "@/lib/api";
import { num, pct } from "@/lib/format";

const TABS = [
  { key: "closed", label: "All" },
  { key: "sold", label: "Sold" },
  { key: "off_market", label: "Off market (pending?)" },
  { key: "withdrawn", label: "Withdrawn" },
];

export default function SoldPage() {
  const [tab, setTab] = useState("closed");
  const { data, error, loading } = useApi<ListingRow[]>(`/listings?status=${tab}`);
  const rows = data ?? [];
  const sold = rows.filter((r) => r.status === "sold" && r.sold_vs_list_pct != null);
  const median = (xs: number[]) => (xs.length ? [...xs].sort((a, b) => a - b)[Math.floor(xs.length / 2)] : null);

  return (
    <>
      <PageHeader
        title="Sold & off-market"
        subtitle="Listings that left the market. A sale is confirmed when its deed is recorded in ACRIS (usually 2–8 weeks after closing); until then it shows as off market."
      />
      <ErrorNote error={error} />
      <div className="mb-4 flex flex-wrap gap-1">
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`rounded-md px-3 py-1 text-sm ${tab === t.key ? "bg-stone-900 text-white" : "border border-stone-300 bg-white text-stone-700 hover:bg-stone-50"}`}
          >
            {t.label}
          </button>
        ))}
      </div>
      {sold.length > 0 && (
        <div className="mb-4 grid grid-cols-3 gap-4 rounded-xl border border-stone-200 bg-white p-4">
          <Stat label="Confirmed sales" value={sold.length} />
          <Stat label="Median sale vs last ask" value={pct(median(sold.map((r) => r.sold_vs_list_pct!)), 1, true)} />
          <Stat label="Median days on market" value={num(median(sold.map((r) => r.days_on_market)))} />
        </div>
      )}
      {loading && !data ? (
        <div className="p-8 text-center text-sm text-stone-500">Loading…</div>
      ) : rows.length ? (
        <ListingTable
          rows={rows}
          columns={["address", "status", "price", "soldPrice", "soldVsList", "soldDate", "dom", "growth", "listed"]}
          initialSort={{ key: "soldDate", desc: true }}
        />
      ) : (
        <Empty title="Nothing here yet">
          Listings move here automatically when they disappear from the listing feed, when a deed is recorded, or when you mark them sold.
        </Empty>
      )}
    </>
  );
}
