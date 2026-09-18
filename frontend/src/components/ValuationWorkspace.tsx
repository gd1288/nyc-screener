"use client";

/**
 * The valuation workspace: sliders, results, cash flow, scenarios, tornado, heatmap, Monte Carlo.
 *
 * Lives here rather than in a route file because two routes render it — the `/valuation` list page
 * (inline, next to the property picker) and `/valuation/[id]` (a deep-linkable page for one
 * property). Keeping one copy is the point: this is where the assumption sliders and the engine
 * contract meet, and a forked second copy would drift from the backend's `Assumptions` defaults.
 */

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  api,
  type DataTableResult,
  type MonteCarloResult,
  type ScenarioResult,
  type SensitivityRow,
  type ValuationProperty,
  type ValuationRun,
} from "@/lib/api";
import { Card, ErrorNote, Tag, ghostButtonCls } from "@/components/ui";
import { money, num, pct } from "@/lib/format";

type Horizon = "10" | "20";

// ---------------------------------------------------------------- field metadata (shared by Quick Mode + Advanced)

type FieldMeta = { label: string; min: number; max: number; step: number; fmt: (v: number) => string; group: string; def: number };

// `def` mirrors backend `Assumptions()` defaults so sliders open on the value the engine would
// actually use, rather than snapping to `min` until the first /run resolves (or forever, if it fails).
const FIELD_META: Record<string, FieldMeta> = {
  interest_rate: { label: "Mortgage rate", min: 0.02, max: 0.1, step: 0.001, fmt: (v) => pct(v, 2), group: "Financing", def: 0.065 },
  down_payment_pct: { label: "Down payment", min: 0.05, max: 0.5, step: 0.01, fmt: (v) => pct(v, 0), group: "Financing", def: 0.25 },
  loan_years: { label: "Loan term", min: 10, max: 30, step: 5, fmt: (v) => `${v} yrs`, group: "Financing", def: 30 },
  appreciation_override: { label: "Appreciation (annual)", min: -0.02, max: 0.08, step: 0.001, fmt: (v) => pct(v, 2), group: "Market", def: 0.02 },
  rent_growth: { label: "Rent growth", min: 0, max: 0.06, step: 0.001, fmt: (v) => pct(v, 2), group: "Income", def: 0.03 },
  vacancy_pct: { label: "Vacancy rate", min: 0, max: 0.15, step: 0.005, fmt: (v) => pct(v, 1), group: "Income", def: 0.05 },
  management_pct: { label: "Management fee", min: 0, max: 0.12, step: 0.005, fmt: (v) => pct(v, 1), group: "Income", def: 0.05 },
  maintenance_monthly: { label: "Maintenance", min: 0, max: 500, step: 10, fmt: (v) => money(v), group: "Expenses", def: 100 },
  insurance_monthly: { label: "Insurance", min: 0, max: 300, step: 10, fmt: (v) => money(v), group: "Expenses", def: 60 },
  expense_growth: { label: "Expense growth", min: 0, max: 0.06, step: 0.001, fmt: (v) => pct(v, 2), group: "Expenses", def: 0.03 },
  exit_cost_pct: { label: "Exit costs", min: 0, max: 0.15, step: 0.005, fmt: (v) => pct(v, 1), group: "Exit", def: 0.08 },
  scenario_spread: { label: "Bear/Bull spread", min: 0, max: 0.05, step: 0.0025, fmt: (v) => pct(v, 2), group: "Exit", def: 0.02 },
};
const DEFAULT_ASSUMPTIONS: Record<string, number> = Object.fromEntries(
  Object.entries(FIELD_META).map(([k, m]) => [k, m.def]),
);

/** Keys whose value the user has actually moved away from the opening default. */
function changedFrom(current: Record<string, number>, defaults: Record<string, number>): Record<string, number> {
  return Object.fromEntries(Object.entries(current).filter(([k, v]) => v !== defaults[k]));
}
const ADVANCED_GROUPS = ["Financing", "Income", "Expenses", "Exit"];
const QUICK_FIELDS = ["interest_rate", "appreciation_override"];


// ---------------------------------------------------------------- workspace: shared state + tabs

const TABS = [
  { id: "quick", label: "Quick Mode" },
  { id: "advanced", label: "Advanced" },
  { id: "cashflow", label: "Cash Flow Detail" },
  { id: "scenarios", label: "Scenarios" },
] as const;
type TabId = (typeof TABS)[number]["id"];

function factorBadge(key: string, run: ValuationRun | null) {
  if (!run || !(key in run.factors)) return null;
  const est = run.factors[key];
  if (est) return <Tag tone="neutral">market: {est.source}</Tag>;
  return <Tag tone="warn">no live source — estimated default</Tag>;
}

export default function PropertyWorkspace({ property, onDelete }: { property: ValuationProperty; onDelete: () => void }) {
  const [tab, setTab] = useState<TabId>("quick");
  const [price, setPrice] = useState(property.price);
  const [rent, setRent] = useState(property.rent_estimate ?? 0);
  const [assumptionOverrides, setAssumptionOverrides] = useState<Record<string, number>>(DEFAULT_ASSUMPTIONS);
  const [horizon, setHorizon] = useState<Horizon>("10");
  const [run, setRun] = useState<ValuationRun | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const seeded = useRef(false);

  const propertyOverrides = useMemo(() => ({ price, rent_estimate: rent }), [price, rent]);

  useEffect(() => {
    const timer = setTimeout(async () => {
      setPending(true);
      setErr(null);
      try {
        const result = await api<ValuationRun>(`/valuation/properties/${property.id}/run`, {
          method: "POST",
          body: JSON.stringify({ overrides: assumptionOverrides, property_overrides: propertyOverrides }),
        });
        setRun(result);
        if (!seeded.current) {
          seeded.current = true;
          const seed: Record<string, number> = { appreciation_override: result.appreciation.base };
          for (const [k, v] of Object.entries(result.assumptions)) {
            if (k !== "appreciation_override" && typeof v === "number") seed[k] = v;
          }
          // Merge, don't replace: a slider the user moved during the debounce + request window
          // would otherwise be silently reverted to the server's value.
          setAssumptionOverrides((prev) => ({ ...seed, ...changedFrom(prev, DEFAULT_ASSUMPTIONS) }));
        }
      } catch (e) {
        setErr((e as Error).message);
      } finally {
        setPending(false);
      }
    }, 250);
    return () => clearTimeout(timer);
  }, [property.id, propertyOverrides, assumptionOverrides]);

  function setField(key: string, value: number) {
    setAssumptionOverrides((prev) => ({ ...prev, [key]: value }));
  }

  const exportHref = useMemo(() => {
    const params = new URLSearchParams({
      overrides: JSON.stringify(assumptionOverrides),
      property_overrides: JSON.stringify(propertyOverrides),
    });
    return `/api/valuation/properties/${property.id}/export.xlsx?${params}`;
  }, [property.id, assumptionOverrides, propertyOverrides]);

  return (
    <div className="space-y-4">
      <Card
        title={property.label}
        action={
          <div className="flex gap-2">
            {/* A plain link, not a fetch: the browser handles the download and the
                Content-Disposition filename, and the workbook never passes through JS memory.
                The scenario travels in the URL - the same overrides the /run above posts - so the
                workbook matches the sliders on screen rather than the property's saved defaults. */}
            <a className={ghostButtonCls} href={exportHref} download>
              Download Excel
            </a>
            <button className={ghostButtonCls} onClick={onDelete}>
              Delete
            </button>
          </div>
        }
      >
        {property.address && <p className="mb-1 text-sm text-stone-600">{property.address}</p>}
        {property.listing && <LinkedListingNote property={property} />}
        <div className="flex flex-wrap gap-1 border-b border-stone-100 pb-3">
          {TABS.map((t) => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={`rounded-md px-3 py-1.5 text-sm font-medium ${tab === t.id ? "bg-stone-900 text-white" : "text-stone-600 hover:bg-stone-100"}`}
            >
              {t.label}
            </button>
          ))}
        </div>

        {tab === "quick" && (
          <QuickModePanel price={price} setPrice={setPrice} rent={rent} setRent={setRent} assumptionOverrides={assumptionOverrides} setField={setField} run={run} />
        )}
        {tab === "advanced" && <AdvancedPanel assumptionOverrides={assumptionOverrides} setField={setField} run={run} />}

        {(tab === "quick" || tab === "advanced" || tab === "cashflow") && (
          <div className="mt-4 flex items-center gap-2 text-sm">
            <span className="text-stone-600">Hold period:</span>
            {(["10", "20"] as const).map((h) => (
              <button
                key={h}
                onClick={() => setHorizon(h)}
                className={`rounded-md px-2.5 py-1 ${horizon === h ? "bg-stone-900 text-white" : "border border-stone-300 text-stone-700 hover:bg-stone-50"}`}
              >
                {h} years
              </button>
            ))}
            {pending && <span className="text-xs text-stone-400">updating…</span>}
          </div>
        )}
      </Card>
      <ErrorNote error={err} />

      {tab !== "scenarios" && run && run.projections.base[horizon] && <ResultsPanel run={run} projection={run.projections.base[horizon]} />}
      {tab === "cashflow" && run && run.projections.base[horizon] && <CashFlowDetailPanel projection={run.projections.base[horizon]} horizon={horizon} />}
      {tab === "scenarios" && <ScenariosPanel propertyId={property.id} propertyOverrides={propertyOverrides} assumptionOverrides={assumptionOverrides} />}
    </div>
  );
}

// ---------------------------------------------------------------- Quick Mode

function LinkedListingNote({ property }: { property: ValuationProperty }) {
  const listing = property.listing!;
  const drift = listing.price_drift_pct ?? 0;
  const moved = Math.abs(drift) > 0.0001;
  const [resyncing, setResyncing] = useState(false);

  async function resync() {
    setResyncing(true);
    try {
      await api(`/valuation/properties/${property.id}/resync-from-listing`, { method: "POST" });
      window.location.reload();
    } finally {
      setResyncing(false);
    }
  }

  return (
    <p className="mb-3 flex flex-wrap items-center gap-2 text-xs text-stone-500">
      <Link href={`/listing/${listing.id}`} className="underline hover:text-stone-800">
        From screener listing #{listing.id}
      </Link>
      {listing.status !== "active" && <Tag tone="sold">{listing.status.replace("_", " ")}</Tag>}
      {moved && (
        <>
          <span className={drift < 0 ? "text-emerald-700" : "text-rose-700"}>
            Ask has moved {pct(drift, 1, true)} since import ({money(listing.price, true)} now vs {money(property.price, true)} analysed)
          </span>
          <button className="underline hover:text-stone-800" onClick={resync} disabled={resyncing}>
            {resyncing ? "Updating…" : "Update to current"}
          </button>
        </>
      )}
    </p>
  );
}

function QuickModePanel({
  price, setPrice, rent, setRent, assumptionOverrides, setField, run,
}: {
  price: number; setPrice: (v: number) => void; rent: number; setRent: (v: number) => void;
  assumptionOverrides: Record<string, number>; setField: (k: string, v: number) => void; run: ValuationRun | null;
}) {
  return (
    <div className="mt-4 grid grid-cols-1 gap-5 sm:grid-cols-2">
      <SliderField label="Price" value={price} min={price * 0.5} max={price * 1.5} step={5000} format={(v) => money(v, true)} onChange={setPrice} />
      <div>
        <SliderField label="Monthly rent" value={rent} min={0} max={Math.max(rent * 2, 5000)} step={50} format={(v) => money(v)} onChange={setRent} />
        {/* At $0 the engine treats rent as unknown and substitutes a neighborhood estimate, so the
            slider would otherwise read $0 next to results computed from a very different number. */}
        {rent === 0 && run && run.monthly.rent > 0 && (
          <p className="mt-1 text-xs text-amber-700">
            Using {money(run.monthly.rent)}/mo — {run.rent_basis}. Set a rent above $0 to override it.
          </p>
        )}
      </div>
      {QUICK_FIELDS.map((key) => {
        const meta = FIELD_META[key];
        const value = assumptionOverrides[key] ?? meta.def;
        return (
          <div key={key}>
            <SliderField label={meta.label} value={value} min={meta.min} max={meta.max} step={meta.step} format={meta.fmt} onChange={(v) => setField(key, v)} />
            {factorBadge(key, run)}
          </div>
        );
      })}
    </div>
  );
}

// ---------------------------------------------------------------- Advanced

function AdvancedPanel({
  assumptionOverrides, setField, run,
}: {
  assumptionOverrides: Record<string, number>; setField: (k: string, v: number) => void; run: ValuationRun | null;
}) {
  return (
    <div className="mt-4 space-y-5">
      {ADVANCED_GROUPS.map((group) => (
        <div key={group}>
          <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-stone-500">{group}</h3>
          <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {Object.entries(FIELD_META)
              .filter(([, meta]) => meta.group === group)
              .map(([key, meta]) => {
                const value = assumptionOverrides[key] ?? meta.def;
                return (
                  <div key={key}>
                    <SliderField label={meta.label} value={value} min={meta.min} max={meta.max} step={meta.step} format={meta.fmt} onChange={(v) => setField(key, v)} />
                    {factorBadge(key, run)}
                  </div>
                );
              })}
          </div>
        </div>
      ))}
    </div>
  );
}

function SliderField({
  label, value, min, max, step, format, onChange,
}: {
  label: string; value: number; min: number; max: number; step: number; format: (v: number) => string; onChange: (v: number) => void;
}) {
  return (
    <label className="block text-xs text-stone-600">
      <div className="mb-1 flex items-baseline justify-between">
        <span>{label}</span>
        <span className="font-semibold tabular-nums text-stone-900">{format(value)}</span>
      </div>
      <input type="range" className="w-full accent-stone-900" min={min} max={max} step={step} value={value} onChange={(e) => onChange(Number(e.target.value))} />
    </label>
  );
}

// ---------------------------------------------------------------- shared results strip

function ResultsPanel({ run, projection }: { run: ValuationRun; projection: ValuationRun["projections"]["base"]["10"] }) {
  const cards = useMemo(
    () => [
      { label: "Cap rate", value: pct(run.cap_rate, 2) },
      { label: "Cash on cash", value: pct(run.cash_on_cash, 2) },
      { label: "Monthly cash flow", value: money(run.monthly.cash_flow) },
      { label: "IRR", value: pct(projection.irr, 1) },
      { label: "Equity multiple", value: projection.equity_multiple ? `${projection.equity_multiple}×` : "—" },
      { label: "Projected value", value: money(projection.value, true) },
    ],
    [run, projection],
  );
  return (
    <Card title="Results">
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
        {cards.map((c) => (
          <div key={c.label}>
            <div className="text-xs text-stone-500">{c.label}</div>
            <div className="text-lg font-semibold tabular-nums text-stone-900">{c.value}</div>
          </div>
        ))}
      </div>
      {run.estimated_factors.length > 0 && (
        <p className="mt-4 text-xs text-stone-500">
          Using fixed defaults (no live data source) for: {run.estimated_factors.join(", ")}. These are candidates for{" "}
          <code className="rounded bg-stone-100 px-1">/research-sources</code>.
        </p>
      )}
      <p className="mt-2 text-xs text-stone-500">
        Estimated inputs: {run.estimated_fields.join(", ") || "none"}. Rent basis: {run.rent_basis}.
      </p>
      <p className="mt-1 text-xs text-stone-400">
        {num(run.purchase_costs.total)} in estimated purchase costs · {money(run.cash_invested)} cash invested.
      </p>
    </Card>
  );
}

// ---------------------------------------------------------------- Cash Flow Detail

function CashFlowDetailPanel({ projection, horizon }: { projection: ValuationRun["projections"]["base"]["10"]; horizon: Horizon }) {
  const rows = projection.path;
  return (
    <Card title={`Cash flow detail — ${horizon} years`}>
      <div className="mb-3 flex flex-wrap gap-4 text-sm">
        <span>
          Cash flow turns positive:{" "}
          <b>{projection.cash_flow_positive_year ? `year ${projection.cash_flow_positive_year}` : "not within this hold period"}</b>
        </span>
        <span>
          Investment paid back: <b>{projection.payback_year ? `year ${projection.payback_year}` : "not within this hold period"}</b>
        </span>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[900px] text-right text-sm tabular-nums">
          <thead className="text-xs text-stone-500">
            <tr className="border-b border-stone-200">
              <th className="py-1.5 text-left font-normal">Year</th>
              <th className="font-normal">NOI</th>
              <th className="font-normal">Mortgage</th>
              <th className="font-normal">Cash flow</th>
              <th className="font-normal">Cumulative CF</th>
              <th className="font-normal">DSCR</th>
              <th className="font-normal">Property value</th>
              <th className="font-normal">Loan balance</th>
              <th className="font-normal">Equity</th>
              <th className="font-normal">Sale proceeds if exit now</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.year} className="border-b border-stone-100 last:border-0">
                <td className="py-1 text-left text-stone-500">{r.year}</td>
                <td>{money(r.noi)}</td>
                <td>{money(r.mortgage)}</td>
                <td className={r.cash_flow < 0 ? "text-rose-700" : ""}>{money(r.cash_flow)}</td>
                <td className={r.cumulative_cash_flow < 0 ? "text-rose-700" : ""}>{money(r.cumulative_cash_flow)}</td>
                <td>{r.dscr == null ? "—" : r.dscr.toFixed(2)}</td>
                <td>{money(r.property_value, true)}</td>
                <td>{money(r.loan_balance, true)}</td>
                <td>{money(r.equity, true)}</td>
                <td>{money(r.sale_proceeds_if_exit_now, true)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="mt-3 text-xs text-stone-500">
        DSCR = NOI ÷ annual mortgage payment. Below 1.0 means the property&apos;s income doesn&apos;t cover debt service that year — most lenders want 1.2+.
      </p>
    </Card>
  );
}

// ---------------------------------------------------------------- Scenarios

function ScenariosPanel({
  propertyId, propertyOverrides, assumptionOverrides,
}: {
  propertyId: number; propertyOverrides: { price: number; rent_estimate: number }; assumptionOverrides: Record<string, number>;
}) {
  const [scenarios, setScenarios] = useState<ScenarioResult[] | null>(null);
  const [sensitivity, setSensitivity] = useState<SensitivityRow[] | null>(null);
  const [dataTable, setDataTable] = useState<DataTableResult | null>(null);
  const [monteCarlo, setMonteCarlo] = useState<MonteCarloResult | null>(null);
  const [mcLoading, setMcLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    const timer = setTimeout(async () => {
      setErr(null);
      try {
        const body = JSON.stringify({ overrides: assumptionOverrides, property_overrides: propertyOverrides });
        const [cmp, sens, dt] = await Promise.all([
          api<ScenarioResult[]>(`/valuation/properties/${propertyId}/scenarios/compare`, { method: "POST", body }),
          api<SensitivityRow[]>(`/valuation/properties/${propertyId}/sensitivity`, { method: "POST", body }),
          api<DataTableResult>(`/valuation/properties/${propertyId}/data-table`, { method: "POST", body }),
        ]);
        setScenarios(cmp);
        setSensitivity(sens);
        setDataTable(dt);
      } catch (e) {
        setErr((e as Error).message);
      }
    }, 300);
    return () => clearTimeout(timer);
  }, [propertyId, propertyOverrides, assumptionOverrides]);

  async function runMonteCarlo() {
    setMcLoading(true);
    setErr(null);
    try {
      const body = JSON.stringify({ overrides: assumptionOverrides, property_overrides: propertyOverrides, n: 500, seed: 42 });
      setMonteCarlo(await api<MonteCarloResult>(`/valuation/properties/${propertyId}/monte-carlo`, { method: "POST", body }));
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setMcLoading(false);
    }
  }

  return (
    <div className="space-y-4">
      <ErrorNote error={err} />
      {scenarios && <ScenarioComparisonTable scenarios={scenarios} />}
      {sensitivity && <TornadoChart rows={sensitivity} />}
      {dataTable && <DataTableHeatmap table={dataTable} />}
      <MonteCarloCard result={monteCarlo} loading={mcLoading} onRun={runMonteCarlo} />
    </div>
  );
}

function ScenarioComparisonTable({ scenarios }: { scenarios: ScenarioResult[] }) {
  const base = scenarios.find((s) => s.name === "Base");
  return (
    <Card title="Scenario comparison">
      <div className="overflow-x-auto">
        <table className="w-full min-w-[700px] text-right text-sm tabular-nums">
          <thead className="text-xs text-stone-500">
            <tr className="border-b border-stone-200">
              <th className="py-1.5 text-left font-normal">Scenario</th>
              <th className="font-normal">Cap rate</th>
              <th className="font-normal">Cash on cash</th>
              <th className="font-normal">Monthly CF</th>
              <th className="font-normal">IRR (10y)</th>
              <th className="font-normal">IRR (20y)</th>
              <th className="font-normal">Equity multiple (10y)</th>
            </tr>
          </thead>
          <tbody>
            {scenarios.map((s) => {
              // Only a real difference between two real IRRs - `?? 0` here would render a
              // confident green "+0.0pt" next to a "—" when either side has no solvable IRR.
              const diff =
                base && s.name !== "Base" && s.irr_10 != null && base.irr_10 != null ? s.irr_10 - base.irr_10 : null;
              return (
                <tr key={s.name} className={`border-b border-stone-100 last:border-0 ${s.name === "Base" ? "font-semibold" : ""}`}>
                  <td className="py-1 text-left text-stone-700">{s.name}</td>
                  <td>{pct(s.cap_rate, 2)}</td>
                  <td>{pct(s.cash_on_cash, 2)}</td>
                  <td className={s.monthly_cash_flow < 0 ? "text-rose-700" : ""}>{money(s.monthly_cash_flow)}</td>
                  <td>
                    {pct(s.irr_10, 1)}
                    {diff != null && (
                      <span className={`ml-1 text-xs ${diff >= 0 ? "text-emerald-600" : "text-rose-600"}`}>
                        ({diff >= 0 ? "+" : ""}
                        {(diff * 100).toFixed(1)}pt)
                      </span>
                    )}
                  </td>
                  <td>{pct(s.irr_20, 1)}</td>
                  <td>{s.equity_multiple_10 ? `${s.equity_multiple_10}×` : "—"}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="mt-3 text-xs text-stone-500">Differences from Base shown in parentheses. Presets are built in; custom named scenarios aren&apos;t saved yet.</p>
    </Card>
  );
}

function TornadoChart({ rows }: { rows: SensitivityRow[] }) {
  if (rows.length === 0) return null;
  const solvable = rows.filter((r) => !r.undefined && r.low_irr != null && r.high_irr != null);
  const maxAbs = Math.max(...solvable.map((r) => Math.max(Math.abs(r.low_irr!), Math.abs(r.high_irr!))), 0.01);
  const toPct = (v: number) => 50 + (v / maxAbs) * 50; // 0% axis sits at the 50% mark of the track
  return (
    <Card title="Sensitivity (tornado)">
      <p className="mb-3 text-xs text-stone-500">
        How far the 10-year IRR swings when one factor moves across its likely range, holding everything else at Base. Ranked by impact.
      </p>
      <div className="space-y-3">
        {rows.map((r) => {
          const unsolvable = r.undefined || r.low_irr == null || r.high_irr == null;
          const lo = unsolvable ? 0 : toPct(Math.min(r.low_irr!, r.high_irr!));
          const hi = unsolvable ? 0 : toPct(Math.max(r.low_irr!, r.high_irr!));
          return (
            <div key={r.factor}>
              <div className="mb-1 flex items-center justify-between text-xs text-stone-600">
                <span>
                  {r.label}
                  {!r.backed_by_source && <span className="ml-1 text-stone-400">(no live source — swung ±assumed range)</span>}
                </span>
                <span className="tabular-nums text-stone-500">
                  {unsolvable ? "no solvable IRR across this range" : `${pct(r.low_irr, 1)} → ${pct(r.high_irr, 1)}`}
                </span>
              </div>
              <div className="relative h-4 rounded bg-stone-100">
                <div className="absolute inset-y-0 w-px bg-stone-400" style={{ left: "50%" }} />
                {!unsolvable && (
                  <div
                    className={`absolute inset-y-0 rounded ${r.high_irr! >= r.low_irr! ? "bg-emerald-400" : "bg-rose-400"}`}
                    style={{ left: `${Math.min(lo, hi)}%`, width: `${Math.max(Math.abs(hi - lo), 0.5)}%` }}
                  />
                )}
              </div>
            </div>
          );
        })}
      </div>
    </Card>
  );
}

function irrColor(v: number | null, maxAbs: number): string {
  if (v == null) return "transparent";
  const t = Math.min(Math.abs(v) / maxAbs, 1);
  if (v >= 0) {
    const l = 92 - t * 42; // toward emerald
    return `hsl(152 55% ${l}%)`;
  }
  const l = 92 - t * 42; // toward rose
  return `hsl(2 65% ${l}%)`;
}

function DataTableHeatmap({ table }: { table: DataTableResult }) {
  const xMeta = FIELD_META[table.x_factor];
  const yMeta = FIELD_META[table.y_factor];
  const flat = table.irr_grid.flat().filter((v): v is number => v != null);
  const maxAbs = Math.max(...flat.map((v) => Math.abs(v)), 0.01);
  return (
    <Card title="Two-factor sensitivity">
      <p className="mb-3 text-xs text-stone-500">
        10-year IRR for every combination of {xMeta?.label ?? table.x_factor} (columns) and {yMeta?.label ?? table.y_factor} (rows).
      </p>
      <div className="overflow-x-auto">
        <table className="text-center text-xs tabular-nums">
          <thead>
            <tr>
              <th />
              {table.x_values.map((x) => (
                <th key={x} className="px-2 pb-1 font-normal text-stone-500">
                  {xMeta ? xMeta.fmt(x) : x}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {table.y_values.map((y, ri) => (
              <tr key={y}>
                <th className="pr-2 text-right font-normal text-stone-500">{yMeta ? yMeta.fmt(y) : y}</th>
                {table.irr_grid[ri].map((v, ci) => (
                  <td key={ci} className="border border-white px-3 py-2 font-medium text-stone-900" style={{ backgroundColor: irrColor(v, maxAbs) }}>
                    {pct(v, 1)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

function MonteCarloCard({ result, loading, onRun }: { result: MonteCarloResult | null; loading: boolean; onRun: () => void }) {
  const maxCount = result ? Math.max(...result.histogram.map((b) => b.count), 1) : 1;
  return (
    <Card
      title="Monte Carlo"
      action={
        <button className={ghostButtonCls} onClick={onRun} disabled={loading}>
          {loading ? "Running…" : result ? "Re-run" : "Run 500 simulations"}
        </button>
      }
    >
      {!result && !loading && (
        <p className="text-sm text-stone-500">
          Randomly samples every factor backed by a real data source within its P10–P90 range (others stay at their default) and shows the resulting spread of 10-year IRR.
        </p>
      )}
      {result && (
        <>
          <div className="mb-3 grid grid-cols-2 gap-4 sm:grid-cols-4">
            <div>
              <div className="text-xs text-stone-500">P10</div>
              <div className="text-lg font-semibold tabular-nums">{pct(result.p10, 1)}</div>
            </div>
            <div>
              <div className="text-xs text-stone-500">P50 (median)</div>
              <div className="text-lg font-semibold tabular-nums">{pct(result.p50, 1)}</div>
            </div>
            <div>
              <div className="text-xs text-stone-500">P90</div>
              <div className="text-lg font-semibold tabular-nums">{pct(result.p90, 1)}</div>
            </div>
            <div>
              <div className="text-xs text-stone-500">Probability of loss</div>
              <div className="text-lg font-semibold tabular-nums text-rose-700">{pct(result.prob_loss, 0)}</div>
            </div>
          </div>
          <div className="flex h-24 items-end gap-px">
            {result.histogram.map((b, i) => (
              <div key={i} className="min-w-[3px] flex-1 rounded-t bg-stone-700" style={{ height: `${Math.max((b.count / maxCount) * 100, 2)}%` }} title={`${pct(b.bin_start, 1)} to ${pct(b.bin_end, 1)}: ${b.count}`} />
            ))}
          </div>
          <p className="mt-2 text-xs text-stone-500">
            {result.randomized_factors.length} of {result.randomized_factors.length + result.held_at_default.length} factors randomized (real data backs
            them); the rest held at their default. Distribution of 10-year IRR across {result.valid_n} runs.
          </p>
        </>
      )}
    </Card>
  );
}
