"use client";

import Link from "next/link";
import { useMemo, useState, type ReactNode } from "react";
import type { ListingRow } from "@/lib/api";
import { date, money, num, pct } from "@/lib/format";
import { ScoreBadge, Tag } from "./ui";

export type Column = {
  key: string;
  label: string;
  value: (r: ListingRow) => number | string | null;
  render: (r: ListingRow) => ReactNode;
  align?: "right";
  title?: string;
};

export const COLUMNS: Record<string, Column> = {
  opportunity: {
    key: "opportunity", label: "Opportunity", title: "50% neighborhood growth score, 25% value vs comps, 25% rental yield",
    value: (r) => r.opportunity_score, render: (r) => <ScoreBadge score={r.opportunity_score} />,
  },
  address: {
    key: "address", label: "Property", value: (r) => r.address,
    render: (r) => (
      <div className="min-w-52">
        <Link href={`/listing/${r.id}`} className="font-medium text-stone-900 hover:underline">
          {r.address}{r.unit ? `, #${r.unit}` : ""}
        </Link>
        <div className="mt-0.5 flex flex-wrap items-center gap-1 text-xs text-stone-500">
          <span>{r.neighborhood ?? "Unmapped"}</span>
          {r.is_new && <Tag tone="new">New</Tag>}
          {r.price_cuts > 0 && <Tag tone="drop">Price cut ×{r.price_cuts}</Tag>}
          {r.times_relisted > 0 && <Tag tone="warn">Relisted</Tag>}
        </div>
      </div>
    ),
  },
  price: {
    key: "price", label: "Price", align: "right", value: (r) => r.price,
    render: (r) => (
      <div>
        <div className="font-medium">{money(r.price)}</div>
        {r.price_change_pct !== 0 && (
          <div className={`text-xs ${r.price_change_pct < 0 ? "text-rose-700" : "text-emerald-700"}`}>{pct(r.price_change_pct, 1, true)} vs original</div>
        )}
      </div>
    ),
  },
  beds: {
    key: "beds", label: "Bd / Ba", align: "right", value: (r) => r.bedrooms,
    render: (r) => `${r.bedrooms == null ? "—" : r.bedrooms === 0 ? "Studio" : num(r.bedrooms, 1)} / ${num(r.bathrooms, 1)}`,
  },
  ppsf: { key: "ppsf", label: "$/sqft", align: "right", value: (r) => r.price_per_sqft, render: (r) => money(r.price_per_sqft) },
  dom: { key: "dom", label: "Days on mkt", align: "right", value: (r) => r.days_on_market, render: (r) => num(r.days_on_market) },
  growth: {
    key: "growth", label: "Nbhd growth", title: "Neighborhood Growth Score (0-100)", align: "right",
    value: (r) => r.growth_score, render: (r) => <ScoreBadge score={r.growth_score} />,
  },
  cap: { key: "cap", label: "Cap rate", align: "right", value: (r) => r.cap_rate, render: (r) => pct(r.cap_rate, 2) },
  cashflow: {
    key: "cashflow", label: "Cash flow/mo", align: "right", value: (r) => r.monthly_cash_flow,
    render: (r) => <span className={r.monthly_cash_flow < 0 ? "text-rose-700" : "text-emerald-700"}>{money(r.monthly_cash_flow)}</span>,
  },
  irr: {
    key: "irr", label: "10-yr IRR", title: "Base case, 25% down", align: "right", value: (r) => r.irr_10y_base,
    render: (r) => pct(r.irr_10y_base, 1),
  },
  comps: {
    key: "comps", label: "vs comps", title: "Price relative to comparable pricing (negative = cheaper)", align: "right",
    value: (r) => r.comps_ratio,
    render: (r) => (r.comps_ratio == null ? "—" : <span title={r.comps_basis ?? ""}>{pct(r.comps_ratio - 1, 0, true)}</span>),
  },
  listed: { key: "listed", label: "Listed", align: "right", value: (r) => r.listed_date, render: (r) => date(r.listed_date) },
  soldPrice: { key: "soldPrice", label: "Sold for", align: "right", value: (r) => r.sold_price, render: (r) => money(r.sold_price) },
  soldVsList: {
    key: "soldVsList", label: "vs last ask", align: "right", value: (r) => r.sold_vs_list_pct,
    render: (r) => pct(r.sold_vs_list_pct, 1, true),
  },
  soldDate: { key: "soldDate", label: "Closed", align: "right", value: (r) => r.sold_date ?? r.off_market_date, render: (r) => date(r.sold_date ?? r.off_market_date) },
  status: {
    key: "status", label: "Status", value: (r) => r.status,
    render: (r) => <Tag tone={r.status === "sold" ? "sold" : r.status === "off_market" ? "warn" : "neutral"}>{r.status.replace("_", " ")}</Tag>,
  },
};

export default function ListingTable({ rows, columns, initialSort }: { rows: ListingRow[]; columns: string[]; initialSort?: { key: string; desc: boolean } }) {
  const [sort, setSort] = useState(initialSort ?? { key: columns[0], desc: true });
  const sorted = useMemo(() => {
    const col = COLUMNS[sort.key];
    if (!col) return rows;
    return [...rows].sort((a, b) => {
      const va = col.value(a);
      const vb = col.value(b);
      if (va == null && vb == null) return 0;
      if (va == null) return 1;
      if (vb == null) return -1;
      const cmp = va < vb ? -1 : va > vb ? 1 : 0;
      return sort.desc ? -cmp : cmp;
    });
  }, [rows, sort]);

  return (
    <div className="overflow-x-auto rounded-xl border border-stone-200 bg-white">
      <table className="w-full text-sm">
        <thead className="border-b border-stone-200 bg-stone-50 text-xs text-stone-600">
          <tr>
            {columns.map((k) => {
              const c = COLUMNS[k];
              const activeSort = sort.key === k;
              return (
                <th key={k} title={c.title} className={`whitespace-nowrap px-3 py-2 font-medium ${c.align === "right" ? "text-right" : "text-left"}`}>
                  <button
                    className={`inline-flex items-center gap-1 hover:text-stone-900 ${activeSort ? "text-stone-900" : ""}`}
                    onClick={() => setSort({ key: k, desc: activeSort ? !sort.desc : true })}
                  >
                    {c.label}
                    <span className="text-[10px]">{activeSort ? (sort.desc ? "▼" : "▲") : ""}</span>
                  </button>
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody className="divide-y divide-stone-100">
          {sorted.map((r) => (
            <tr key={r.id} className="hover:bg-stone-50">
              {columns.map((k) => (
                <td key={k} className={`px-3 py-2 align-top tabular-nums ${COLUMNS[k].align === "right" ? "text-right" : ""}`}>
                  {COLUMNS[k].render(r)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
