"use client";

import { useMemo, useState } from "react";
import { Card, Empty, ErrorNote, PageHeader, ScoreBadge, Tag, buttonCls, inputCls } from "@/components/ui";
import { api, useApi, type AreaRow, type RegionsResponse } from "@/lib/api";
import { pct } from "@/lib/format";

/**
 * Areas are the US-wide generalization of the NYC neighborhood pages: a census tract in Austin and
 * an NTA in Manhattan are both scored here, each ranked only against its own metro.
 *
 * The screen is built around one honesty constraint: every score is shown with its coverage. Most
 * pillars have no national source wired yet, so scores cluster near 50 with coverage around 0.1-0.3.
 * That is "we don't know yet", not "average", and a bare 50 would read as the latter.
 */

const LOW_COVERAGE = 0.5;

export default function AreasPage() {
  const regions = useApi<RegionsResponse>("/regions");
  const [set, setSet] = useState<string>("");
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  const sets = regions.data?.loaded ?? [];
  const activeSet = set || sets[0]?.comparison_set || "";
  const areas = useApi<AreaRow[]>(activeSet ? `/areas?comparison_set=${encodeURIComponent(activeSet)}&limit=500` : null);

  const rows = useMemo(() => {
    const list = areas.data ?? [];
    if (!query.trim()) return list;
    const needle = query.trim().toLowerCase();
    return list.filter((a) => a.name.toLowerCase().includes(needle) || a.code.includes(needle));
  }, [areas.data, query]);

  const scored = rows.filter((a) => (a.coverage ?? 0) > 0).length;

  async function loadRegion(key: string) {
    setLoading(key);
    setLoadError(null);
    try {
      await api<{ region: string }>("/regions", { method: "POST", body: JSON.stringify({ key }) });
      await regions.reload?.();
    } catch (e) {
      setLoadError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(null);
    }
  }

  return (
    <>
      <PageHeader
        title="Areas"
        subtitle="Any US neighborhood, scored against its own metro. Census tracts everywhere; NYC keeps its NTAs."
      />

      <ErrorNote error={regions.error ?? areas.error ?? loadError} />

      <Card title="Regions">
        <div className="flex flex-wrap gap-2">
          {regions.data?.available.map((r) => (
            <button
              key={r.key}
              type="button"
              disabled={r.loaded || loading !== null}
              onClick={() => loadRegion(r.key)}
              className={r.loaded ? "rounded border border-slate-200 px-3 py-1.5 text-sm text-slate-500" : buttonCls}
            >
              {r.loaded ? `${r.name} — loaded` : loading === r.key ? `Loading ${r.name}…` : `Load ${r.name}`}
            </button>
          ))}
        </div>
        {loading && <p className="mt-2 text-sm text-slate-500">Fetching tracts county by county — this takes a moment.</p>}
      </Card>

      <Card
        title="Comparison set"
        action={
          <input
            className={inputCls}
            placeholder="Filter by name or tract code"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        }
      >
        <div className="flex flex-wrap gap-2">
          {sets.map((s) => (
            <button
              key={s.comparison_set}
              type="button"
              onClick={() => setSet(s.comparison_set)}
              className={
                s.comparison_set === activeSet
                  ? "rounded bg-slate-900 px-3 py-1.5 text-sm text-white"
                  : "rounded border border-slate-300 px-3 py-1.5 text-sm hover:bg-slate-50"
              }
            >
              {s.name.split(",")[0]} <span className="opacity-60">({s.tracts} tracts)</span>
              {s.watched && <span className="ml-1 opacity-60">· watched</span>}
            </button>
          ))}
        </div>
        {activeSet && (
          <p className="mt-3 text-sm text-slate-600">
            Ranked within <code className="rounded bg-slate-100 px-1">{activeSet}</code> — {scored} of {rows.length}{" "}
            areas have any data behind their score. Percentiles never cross metros, so these ranks are not comparable
            with another region&apos;s.
          </p>
        )}
      </Card>

      {rows.length === 0 ? (
        <Empty title="No areas yet">Load a region above to fetch its census tracts.</Empty>
      ) : (
        <Card title={`${rows.length} areas`}>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-200 text-left text-slate-500">
                  <th className="py-2 pr-3">Rank</th>
                  <th className="py-2 pr-3">Area</th>
                  <th className="py-2 pr-3">Code</th>
                  <th className="py-2 pr-3">Score</th>
                  <th className="py-2 pr-3">Confidence</th>
                </tr>
              </thead>
              <tbody>
                {rows.slice(0, 200).map((area) => {
                  const coverage = area.coverage ?? 0;
                  return (
                    <tr key={area.id} className="border-b border-slate-100">
                      <td className="py-2 pr-3 tabular-nums text-slate-500">{area.rank ?? "—"}</td>
                      <td className="py-2 pr-3">{area.name}</td>
                      <td className="py-2 pr-3 font-mono text-xs text-slate-500">{area.code}</td>
                      <td className="py-2 pr-3">
                        <ScoreBadge score={area.score} />
                      </td>
                      <td className="py-2 pr-3">
                        {coverage <= 0 ? (
                          <Tag tone="warn">no data</Tag>
                        ) : coverage < LOW_COVERAGE ? (
                          <Tag tone="warn">{pct(coverage, 0)} of signals</Tag>
                        ) : (
                          <span className="text-slate-600">{pct(coverage, 0)} of signals</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          {rows.length > 200 && (
            <p className="mt-2 text-sm text-slate-500">Showing the top 200 of {rows.length}. Use the filter to narrow.</p>
          )}
        </Card>
      )}
    </>
  );
}
