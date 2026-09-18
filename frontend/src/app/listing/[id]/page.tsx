"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import PillarBreakdown from "@/components/PillarBreakdown";
import { Card, ErrorNote, ScoreBadge, Stat, Tag, buttonCls, ghostButtonCls, inputCls } from "@/components/ui";
import { api, useApi, type Analysis, type Assumptions, type ListingDetail } from "@/lib/api";
import { date, money, num, pct } from "@/lib/format";

const COST_LABELS: Record<string, string> = {
  mansion_tax: "NYS mansion tax",
  mortgage_recording_tax: "Mortgage recording tax",
  title_insurance: "Title insurance",
  attorney_and_bank_fees: "Attorney & bank fees",
  nyc_transfer_tax: "NYC transfer tax (sponsor sale)",
  nys_transfer_tax: "NYS transfer tax (sponsor sale)",
};

export default function ListingPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { data, error, reload } = useApi<ListingDetail>(`/listings/${id}`);
  // User-edited model inputs; null means "use the defaults the API returned".
  const [custom, setCustom] = useState<{ assumptions: Assumptions; analysis: Analysis | null } | null>(null);

  if (error) return <ErrorNote error={error} />;
  if (!data) return <div className="p-8 text-center text-sm text-stone-500">Loading…</div>;

  const assumptions = custom?.assumptions ?? data.analysis.assumptions;
  const analysis = custom?.analysis ?? data.analysis;

  async function recalc(next: Assumptions) {
    setCustom((c) => ({ assumptions: next, analysis: c?.analysis ?? null }));
    const d = await api<ListingDetail>(`/listings/${id}/analyze`, { method: "POST", body: JSON.stringify(next) });
    setCustom({ assumptions: next, analysis: d.analysis });
  }

  function onListingChanged() {
    setCustom(null);
    reload();
  }

  const chart = data.history.filter((h) => h.price != null).map((h) => ({ date: h.date.slice(0, 10), price: h.price, event: h.event }));
  const base10 = analysis.projections.base["10"];

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <Link href="/" className="text-xs text-stone-500 hover:underline">← Screener</Link>
          <h1 className="mt-1 text-xl font-semibold">{data.address}{data.unit ? `, #${data.unit}` : ""}</h1>
          <div className="mt-1 flex flex-wrap items-center gap-2 text-sm text-stone-600">
            {data.neighborhood_code ? (
              <Link className="underline" href={`/neighborhoods/${data.neighborhood_code}`}>{data.neighborhood}</Link>
            ) : "Neighborhood unknown"}
            <span>· {data.borough}</span>
            <Tag tone={data.status === "sold" ? "sold" : data.status === "active" ? "neutral" : "warn"}>{data.status.replace("_", " ")}</Tag>
            {data.is_new && <Tag tone="new">New</Tag>}
            <span className="text-xs text-stone-400">source: {data.source}</span>
            {data.url && <a className="text-xs underline" href={data.url} target="_blank" rel="noreferrer">View listing ↗</a>}
          </div>
        </div>
        <div className="flex items-center gap-3">
          <Link href={`/valuation?import=${data.id}`} className={ghostButtonCls}>
            Analyze in Valuation
          </Link>
          <div className="text-right text-xs text-stone-500">Opportunity<br />score</div>
          <ScoreBadge score={data.opportunity_score} size="lg" />
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4 rounded-xl border border-stone-200 bg-white p-4 sm:grid-cols-4 lg:grid-cols-8">
        <Stat label="Price" value={money(data.price)} sub={data.price_change_pct ? `${pct(data.price_change_pct, 1, true)} from ${money(data.original_price, true)}` : "No price changes"} />
        <Stat label="Beds / baths" value={`${data.bedrooms ?? "—"} / ${data.bathrooms ?? "—"}`} sub={data.sqft ? `${num(data.sqft)} sqft` : "sqft unknown"} />
        <Stat label="$/sqft" value={money(data.price_per_sqft)} />
        <Stat label="Days on market" value={num(data.days_on_market)} sub={`Listed ${date(data.listed_date)}`} />
        <Stat label="Price cuts" value={data.price_cuts} sub={data.last_price_change ? `Last ${date(data.last_price_change)}` : undefined} tone={data.price_cuts ? "bad" : undefined} />
        <Stat label="Nbhd growth" value={<ScoreBadge score={data.growth_score} />} sub={data.neighborhood_score?.rank ? `#${data.neighborhood_score.rank} in NYC` : undefined} />
        <Stat label="Cap rate" value={pct(analysis.cap_rate, 2)} sub={`Gross yield ${pct(analysis.gross_yield, 1)}`} />
        <Stat label="10-yr IRR (base)" value={pct(base10.irr, 1)} tone={base10.irr != null ? (base10.irr >= 0.06 ? "good" : base10.irr < 0 ? "bad" : undefined) : undefined} />
      </div>

      {data.status === "sold" && (
        <div className="rounded-xl border border-violet-200 bg-violet-50 p-4 text-sm text-violet-900">
          Sold {date(data.sold_date)} for <b>{money(data.sold_price)}</b> ({pct(data.sold_vs_list_pct, 1, true)} vs last ask,{" "}
          {pct(data.sold_vs_original_pct, 1, true)} vs original ask) after {data.days_on_market} days.
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-[1.2fr_1fr]">
        <Card title="Investment model" action={analysis.estimated_fields.length > 0 && (
          <span className="text-xs text-amber-700">Estimated: {analysis.estimated_fields.join(", ").replaceAll("_", " ")}</span>
        )}>
          <AssumptionForm key={JSON.stringify(assumptions)} value={assumptions} onChange={recalc} />
          <div className="mt-4 grid gap-4 md:grid-cols-2">
            <div>
              <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-stone-500">Monthly</h3>
              <Rows rows={[
                ["Rent" + (analysis.rent_basis !== "listing" ? " (est.)" : ""), analysis.monthly.rent],
                ["Vacancy", -analysis.monthly.vacancy],
                ["Common charges", -analysis.monthly.common_charges],
                ["Property taxes", -analysis.monthly.property_taxes],
                ["Insurance", -analysis.monthly.insurance],
                ["Maintenance", -analysis.monthly.maintenance],
                ["Management", -analysis.monthly.management],
                ["Net operating income", analysis.monthly.noi, true],
                ["Mortgage", -analysis.monthly.mortgage],
                ["Cash flow", analysis.monthly.cash_flow, true],
              ]} />
            </div>
            <div>
              <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-stone-500">Cash to close</h3>
              <Rows rows={[
                ["Down payment", data.price * assumptions.down_payment_pct],
                ...Object.entries(analysis.purchase_costs).filter(([k]) => k !== "total").map(([k, v]) => [COST_LABELS[k] ?? k, v] as [string, number]),
                ["Total cash invested", analysis.cash_invested, true],
                ["Loan amount", analysis.loan_amount],
              ]} />
              <p className="mt-2 text-xs text-stone-500">Cash-on-cash return: <b>{pct(analysis.cash_on_cash, 1)}</b></p>
            </div>
          </div>
          <h3 className="mb-2 mt-5 text-xs font-semibold uppercase tracking-wide text-stone-500">Projected returns</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-sm tabular-nums">
              <thead className="text-xs text-stone-500">
                <tr>
                  <th className="py-1 text-left font-normal">Scenario</th>
                  <th className="py-1 text-right font-normal">Appreciation/yr</th>
                  <th className="py-1 text-right font-normal">Value in 10y</th>
                  <th className="py-1 text-right font-normal">IRR 10y</th>
                  <th className="py-1 text-right font-normal">Value in 20y</th>
                  <th className="py-1 text-right font-normal">IRR 20y</th>
                  <th className="py-1 text-right font-normal">Equity multiple 20y</th>
                </tr>
              </thead>
              <tbody>
                {(["bear", "base", "bull"] as const).map((s) => (
                  <tr key={s} className={`border-t border-stone-100 ${s === "base" ? "font-medium" : ""}`}>
                    <td className="py-1.5 capitalize">{s}</td>
                    <td className="py-1.5 text-right">{pct(analysis.appreciation[s], 1)}</td>
                    <td className="py-1.5 text-right">{money(analysis.projections[s]["10"].value, true)}</td>
                    <td className="py-1.5 text-right">{pct(analysis.projections[s]["10"].irr, 1)}</td>
                    <td className="py-1.5 text-right">{money(analysis.projections[s]["20"].value, true)}</td>
                    <td className="py-1.5 text-right">{pct(analysis.projections[s]["20"].irr, 1)}</td>
                    <td className="py-1.5 text-right">{analysis.projections[s]["20"].equity_multiple?.toFixed(2) ?? "—"}×</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="mt-2 text-xs text-stone-500">
            Base appreciation blends the citywide 10-year condo trend with this neighborhood&apos;s own trend, adjusted ±1 pt/yr by its growth score. Exit assumes selling costs of {pct(assumptions.exit_cost_pct, 0)}.
          </p>
        </Card>

        <div className="space-y-4">
          <Card title={<span className="flex items-center gap-2">Neighborhood growth score <ScoreBadge score={data.neighborhood_score?.score} /></span>}
            action={data.neighborhood_code && <Link className="text-xs underline" href={`/neighborhoods/${data.neighborhood_code}`}>Full profile</Link>}>
            {data.neighborhood_score ? <PillarBreakdown pillars={data.neighborhood_score.pillars} /> : <p className="text-sm text-stone-500">Not scored.</p>}
          </Card>

          <Card title="Price history">
            {chart.length > 1 ? (
              <ResponsiveContainer width="100%" height={180}>
                <LineChart data={chart} margin={{ left: 8, right: 8, top: 8 }}>
                  <CartesianGrid stroke="#f5f5f4" />
                  <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }} tickFormatter={(v) => money(v, true)} width={64} domain={["auto", "auto"]} />
                  <Tooltip formatter={(v) => money(Number(v))} />
                  <Line type="stepAfter" dataKey="price" stroke="#1c1917" strokeWidth={2} dot />
                </LineChart>
              </ResponsiveContainer>
            ) : null}
            <ul className="mt-2 divide-y divide-stone-100 text-sm">
              {[...data.history].reverse().map((h, i) => (
                <li key={i} className="flex justify-between py-1.5">
                  <span className="capitalize text-stone-700">{h.event.replace("_", " ")} <span className="text-xs text-stone-400">{date(h.date)}</span></span>
                  <span className="tabular-nums">{money(h.price)}</span>
                </li>
              ))}
            </ul>
          </Card>

          <Card title="Comparable sales">
            <p className="mb-2 text-sm text-stone-600">
              {data.neighborhood_sales ? <>Neighborhood: {data.neighborhood_sales.sales_2y} condo sales in 2 years, median {money(data.neighborhood_sales.median_price_2y)}.</> : null}
              {data.comps_ratio != null && <> This listing is <b>{pct(data.comps_ratio - 1, 0, true)}</b> vs {data.comps_basis}.</>}
            </p>
            {data.building_sales.length ? (
              <table className="w-full text-sm tabular-nums">
                <thead className="text-xs text-stone-500"><tr><th className="text-left font-normal">Same building</th><th className="text-left font-normal">Unit</th><th className="text-right font-normal">Price</th></tr></thead>
                <tbody>
                  {data.building_sales.map((s, i) => (
                    <tr key={i} className="border-t border-stone-100"><td className="py-1">{date(s.date)}</td><td>{s.unit ?? "—"}</td><td className="text-right">{money(s.price)}</td></tr>
                  ))}
                </tbody>
              </table>
            ) : <p className="text-xs text-stone-500">No recorded sales in this building in the last 3 years.</p>}
          </Card>

          <ManageListing listing={data} onChange={onListingChanged} onDeleted={() => router.push("/")} />
        </div>
      </div>
    </div>
  );
}

function Rows({ rows }: { rows: [string, number, boolean?][] }) {
  return (
    <table className="w-full text-sm tabular-nums">
      <tbody>
        {rows.map(([label, v, strong]) => (
          <tr key={label} className={strong ? "border-t border-stone-200 font-semibold" : ""}>
            <td className="py-0.5 text-stone-700">{label}</td>
            <td className={`py-0.5 text-right ${strong && v < 0 ? "text-rose-700" : ""}`}>{money(v)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

const FIELDS: { key: keyof Assumptions; label: string; pct?: boolean; step?: number }[] = [
  { key: "down_payment_pct", label: "Down payment %", pct: true },
  { key: "interest_rate", label: "Mortgage rate %", pct: true, step: 0.125 },
  { key: "vacancy_pct", label: "Vacancy %", pct: true },
  { key: "management_pct", label: "Management %", pct: true },
  { key: "rent_growth", label: "Rent growth %/yr", pct: true, step: 0.5 },
  { key: "expense_growth", label: "Expense growth %/yr", pct: true, step: 0.5 },
  { key: "exit_cost_pct", label: "Selling costs %", pct: true },
  { key: "insurance_monthly", label: "Insurance $/mo" },
  { key: "maintenance_monthly", label: "Maintenance $/mo" },
];

function AssumptionForm({ value, onChange }: { value: Assumptions; onChange: (a: Assumptions) => void }) {
  // Remounted (via `key`) whenever `value` changes, so the draft starts from the latest assumptions.
  const [draft, setDraft] = useState<Record<string, string>>(() => {
    const d: Record<string, string> = {};
    for (const f of FIELDS) d[f.key] = String(f.pct ? +((value[f.key] as number) * 100).toFixed(3) : value[f.key]);
    d.appreciation_override = value.appreciation_override == null ? "" : String(+(value.appreciation_override * 100).toFixed(2));
    return d;
  });

  function commit() {
    const next = { ...value } as Record<string, unknown>;
    for (const f of FIELDS) {
      const n = Number(draft[f.key]);
      if (!Number.isNaN(n)) next[f.key] = f.pct ? n / 100 : n;
    }
    next.appreciation_override = draft.appreciation_override === "" ? null : Number(draft.appreciation_override) / 100;
    onChange(next as Assumptions);
  }

  return (
    <form onSubmit={(e) => { e.preventDefault(); commit(); }} className="grid grid-cols-2 gap-2 sm:grid-cols-5">
      {FIELDS.map((f) => (
        <label key={f.key} className="block">
          <span className="mb-0.5 block text-[11px] text-stone-500">{f.label}</span>
          <input className={inputCls} value={draft[f.key] ?? ""} onChange={(e) => setDraft({ ...draft, [f.key]: e.target.value })} onBlur={commit} inputMode="decimal" />
        </label>
      ))}
      <label className="block">
        <span className="mb-0.5 block text-[11px] text-stone-500">Appreciation %/yr</span>
        <input className={inputCls} placeholder="auto" value={draft.appreciation_override ?? ""} onChange={(e) => setDraft({ ...draft, appreciation_override: e.target.value })} onBlur={commit} inputMode="decimal" />
      </label>
      <label className="col-span-2 flex items-center gap-2 text-xs text-stone-700 sm:col-span-5">
        <input type="checkbox" checked={value.new_development} onChange={(e) => onChange({ ...value, new_development: e.target.checked })} />
        New development (buyer pays sponsor&apos;s transfer taxes)
      </label>
    </form>
  );
}

function ManageListing({ listing, onChange, onDeleted }: { listing: ListingDetail; onChange: () => void; onDeleted: () => void }) {
  const [price, setPrice] = useState("");
  const [soldPrice, setSoldPrice] = useState("");
  const [busy, setBusy] = useState(false);

  async function patch(body: object) {
    setBusy(true);
    try {
      await api(`/listings/${listing.id}`, { method: "PATCH", body: JSON.stringify(body) });
      onChange();
    } catch (e) {
      alert((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card title="Update listing">
      <div className="space-y-3 text-sm">
        <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); if (price) patch({ price: Number(price) }).then(() => setPrice("")); }}>
          <input className={inputCls} placeholder="New asking price" value={price} onChange={(e) => setPrice(e.target.value)} inputMode="numeric" />
          <button className={ghostButtonCls} disabled={busy || !price}>Update price</button>
        </form>
        {listing.status !== "sold" && (
          <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); patch({ status: "sold", sold_price: soldPrice ? Number(soldPrice) : null }); }}>
            <input className={inputCls} placeholder="Sale price (optional)" value={soldPrice} onChange={(e) => setSoldPrice(e.target.value)} inputMode="numeric" />
            <button className={buttonCls} disabled={busy}>Mark sold</button>
          </form>
        )}
        <div className="flex flex-wrap gap-2">
          {listing.status !== "active" && <button className={ghostButtonCls} disabled={busy} onClick={() => patch({ status: "active" })}>Mark active</button>}
          {listing.status === "active" && <button className={ghostButtonCls} disabled={busy} onClick={() => patch({ status: "off_market" })}>Mark off market</button>}
          {listing.source === "manual" && (
            <button
              className="ml-auto text-xs text-rose-700 hover:underline"
              disabled={busy}
              onClick={async () => {
                if (!confirm("Delete this listing?")) return;
                await api(`/listings/${listing.id}`, { method: "DELETE" });
                onDeleted();
              }}
            >
              Delete listing
            </button>
          )}
        </div>
      </div>
    </Card>
  );
}
