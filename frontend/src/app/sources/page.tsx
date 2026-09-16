"use client";

import { useEffect, useState } from "react";
import { Card, ErrorNote, PageHeader, Tag, ghostButtonCls } from "@/components/ui";
import { api, useApi, type SourceInfo } from "@/lib/api";
import { dateTime, num } from "@/lib/format";

const KIND_LABEL: Record<string, string> = {
  boundaries: "Geography",
  sales: "Closed sales",
  neighborhood: "Neighborhood signal",
  listings: "Listings",
  sold_check: "Sold detection",
};

export default function SourcesPage() {
  const { data, error, reload } = useApi<{ sources: SourceInfo[]; refreshing: boolean }>("/sources");
  const [busy, setBusy] = useState<string | null>(null);

  useEffect(() => {
    if (!data?.refreshing) return;
    const t = setInterval(reload, 3000);
    return () => clearInterval(t);
  }, [data?.refreshing, reload]);

  async function run(name: string) {
    setBusy(name);
    try {
      await api("/refresh", { method: "POST", body: JSON.stringify({ sources: [name] }) });
      setTimeout(reload, 800);
    } catch (e) {
      alert((e as Error).message);
    } finally {
      setBusy(null);
    }
  }

  const missing = [...new Set((data?.sources ?? []).flatMap((s) => s.missing_settings))];

  return (
    <>
      <PageHeader
        title="Data sources"
        subtitle="Every source is a plug-in listed in backend/sources.yaml. Sources run on their own schedule while the backend is running, or all at once with Refresh now."
      />
      <ErrorNote error={error} />
      {missing.length > 0 && (
        <div className="mb-4 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
          <b>Add these free keys to <code>.env</code></b> in the project folder, then restart the backend: {missing.join(", ")}.
          <ul className="mt-2 list-disc pl-5 text-xs">
            {missing.includes("CENSUS_API_KEY") && <li>CENSUS_API_KEY: api.census.gov/data/key_signup.html (turns on the demographics pillar)</li>}
            {missing.includes("RENTCAST_API_KEY") && <li>RENTCAST_API_KEY: app.rentcast.io (free tier: automatic new-listing discovery)</li>}
          </ul>
        </div>
      )}
      <Card title={`${data?.sources.length ?? 0} sources`} action={data?.refreshing && <span className="text-xs text-emerald-700">Refresh in progress…</span>}>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="text-xs text-stone-500">
              <tr>
                <th className="py-1.5 text-left font-normal">Source</th>
                <th className="py-1.5 text-left font-normal">Type</th>
                <th className="py-1.5 text-left font-normal">Schedule</th>
                <th className="py-1.5 text-left font-normal">Last run</th>
                <th className="py-1.5 text-right font-normal">Records</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {(data?.sources ?? []).map((s) => (
                <tr key={s.name} className="border-t border-stone-100 align-top">
                  <td className="py-2 pr-3">
                    <div className="font-medium text-stone-900">{s.name}</div>
                    <div className="max-w-md text-xs text-stone-500">{s.description}</div>
                    {s.last_run?.message && <div className={`mt-1 max-w-md text-xs ${s.last_run.status === "error" ? "text-rose-700" : "text-amber-700"}`}>{s.last_run.message}</div>}
                  </td>
                  <td className="py-2 pr-3 text-xs text-stone-600">{KIND_LABEL[s.kind] ?? s.kind}</td>
                  <td className="py-2 pr-3 font-mono text-xs text-stone-600">{s.enabled ? s.schedule ?? "manual" : "disabled"}</td>
                  <td className="py-2 pr-3 text-xs">
                    {s.last_run ? (
                      <>
                        <Tag tone={s.last_run.status === "ok" ? "new" : s.last_run.status === "error" ? "drop" : "warn"}>{s.last_run.status}</Tag>
                        <div className="mt-0.5 text-stone-500">{dateTime(s.last_run.finished_at ?? s.last_run.started_at)}</div>
                      </>
                    ) : <span className="text-stone-400">never</span>}
                  </td>
                  <td className="py-2 pr-3 text-right tabular-nums">{s.last_run ? num(s.last_run.records) : "—"}</td>
                  <td className="py-2 text-right">
                    <button className={ghostButtonCls} disabled={!!busy || data?.refreshing || s.missing_settings.length > 0} onClick={() => run(s.name)}>
                      Run
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
      <p className="mt-3 text-xs text-stone-500">
        Schedules are cron expressions in New York time (e.g. <code>0 8 * * *</code> = daily at 8am). Running a single source also recomputes neighborhood scores.
      </p>
    </>
  );
}
