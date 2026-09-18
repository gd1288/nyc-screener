"use client";

/**
 * Workbench — local developer tooling: the roadmap board, the project's own checks, the data-health
 * report, and the record of unattended agent runs.
 *
 * Every endpoint behind this page is refused unless the backend was started with DEV_TOOLS=1 and
 * the request comes from this machine, so the page's normal state on a default install is "not
 * enabled" — which it explains rather than showing a broken board.
 */

import { useState } from "react";
import { Card, Empty, ErrorNote, PageHeader, Stat, Tag, buttonCls, ghostButtonCls, inputCls } from "@/components/ui";
import { api, useApi, type AgentRunRow, type CheckInfo, type CheckResult, type IssueBoard, type RunsResponse } from "@/lib/api";
import { money } from "@/lib/format";

const TABS = ["Roadmap", "Checks", "Debug", "Runs"] as const;
type Tab = (typeof TABS)[number];
const COLUMNS = ["Backlog", "Planned", "In progress", "In review", "Done"];

export default function WorkbenchPage() {
  const [tab, setTab] = useState<Tab>("Roadmap");
  const checks = useApi<CheckInfo[]>("/dev/checks");

  const disabled = checks.error && /403|not found|failed to fetch/i.test(checks.error);

  return (
    <>
      <PageHeader title="Workbench" subtitle="Plan, run checks, debug, and see what unattended runs cost." />

      {disabled ? (
        <Empty title="Workbench is not enabled">
          Start the API with <code className="rounded bg-stone-100 px-1">DEV_TOOLS=1</code> to enable it. The routes are
          only registered when that is set, and only accept requests from this machine.
        </Empty>
      ) : (
        <>
          <div className="mb-4 flex flex-wrap gap-1 border-b border-stone-200 pb-2">
            {TABS.map((t) => (
              <button
                key={t}
                onClick={() => setTab(t)}
                className={
                  t === tab
                    ? "rounded bg-stone-900 px-3 py-1.5 text-sm text-white"
                    : "rounded px-3 py-1.5 text-sm text-stone-600 hover:bg-stone-100"
                }
              >
                {t}
              </button>
            ))}
          </div>
          {tab === "Roadmap" && <RoadmapTab />}
          {tab === "Checks" && <ChecksTab checks={checks.data ?? []} />}
          {tab === "Debug" && <DebugTab />}
          {tab === "Runs" && <RunsTab />}
        </>
      )}
    </>
  );
}

function RoadmapTab() {
  const { data, error, loading } = useApi<IssueBoard>("/dev/issues?state=all&limit=100");
  if (loading) return <p className="text-sm text-stone-500">Loading issues…</p>;
  if (error) {
    return (
      <Card title="Roadmap">
        <ErrorNote error={error} />
        <p className="text-sm text-stone-600">
          This needs the <code className="rounded bg-stone-100 px-1">gh</code> CLI installed and authenticated, in a
          repo with a GitHub remote.
        </p>
      </Card>
    );
  }
  return (
    <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-5">
      {COLUMNS.map((column) => (
        <Card key={column} title={`${column} (${data?.board?.[column]?.length ?? 0})`}>
          <ul className="space-y-2">
            {(data?.board?.[column] ?? []).map((issue) => (
              <li key={issue.number} className="rounded border border-stone-200 p-2 text-sm">
                <a href={issue.url} target="_blank" rel="noreferrer" className="font-medium hover:underline">
                  #{issue.number} {issue.title}
                </a>
                <div className="mt-1 flex flex-wrap gap-1">
                  {(issue.labels ?? []).map((l) => (
                    <Tag key={l.name}>{l.name}</Tag>
                  ))}
                </div>
              </li>
            ))}
            {(data?.board?.[column] ?? []).length === 0 && <li className="text-sm text-stone-400">—</li>}
          </ul>
        </Card>
      ))}
    </div>
  );
}

function ChecksTab({ checks }: { checks: CheckInfo[] }) {
  const [results, setResults] = useState<Record<string, CheckResult | "running">>({});
  const [error, setError] = useState<string | null>(null);

  async function run(key: string) {
    setResults((prev) => ({ ...prev, [key]: "running" }));
    setError(null);
    try {
      const result = await api<CheckResult>(`/dev/checks/${key}`, { method: "POST" });
      setResults((prev) => ({ ...prev, [key]: result }));
    } catch (e) {
      setError((e as Error).message);
      setResults((prev) => {
        const next = { ...prev };
        delete next[key];
        return next;
      });
    }
  }

  return (
    <Card title="Checks">
      <ErrorNote error={error} />
      <ul className="space-y-3">
        {checks.map((check) => {
          const result = results[check.key];
          return (
            <li key={check.key} className="rounded border border-stone-200 p-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <div className="font-medium">{check.label}</div>
                  <code className="text-xs text-stone-500">{check.command.join(" ")}</code>
                  {check.description && <p className="mt-1 text-xs text-stone-500">{check.description}</p>}
                </div>
                <div className="flex items-center gap-2">
                  {result && result !== "running" && (
                    <Tag tone={result.ok ? "new" : "warn"}>
                      {result.ok ? "passed" : `exit ${result.exit_code ?? "?"}`} · {result.duration_seconds}s
                    </Tag>
                  )}
                  <button className={ghostButtonCls} disabled={result === "running"} onClick={() => run(check.key)}>
                    {result === "running" ? "Running…" : "Run"}
                  </button>
                </div>
              </div>
              {result && result !== "running" && (
                <pre className="mt-2 max-h-72 overflow-auto rounded bg-stone-900 p-2 text-xs text-stone-100">
                  {result.truncated ? `… (trimmed to the last lines)\n${result.output}` : result.output}
                </pre>
              )}
            </li>
          );
        })}
      </ul>
    </Card>
  );
}

function DebugTab() {
  const [report, setReport] = useState<CheckResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function load() {
    setBusy(true);
    setError(null);
    try {
      setReport(await api<CheckResult>("/dev/diagnose"));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card
      title="Data health"
      action={
        <div className="flex gap-2">
          <button className={ghostButtonCls} onClick={load} disabled={busy}>
            {busy ? "Running…" : "Run diagnose"}
          </button>
          {report && (
            <button className={ghostButtonCls} onClick={() => navigator.clipboard?.writeText(report.output)}>
              Copy report
            </button>
          )}
        </div>
      }
    >
      <ErrorNote error={error} />
      {report ? (
        <pre className="max-h-96 overflow-auto rounded bg-stone-900 p-2 text-xs text-stone-100">{report.output}</pre>
      ) : (
        <p className="text-sm text-stone-500">Run diagnose to see per-source status and the cached test result.</p>
      )}
    </Card>
  );
}

function RunsTab() {
  const { data, error, reload } = useApi<RunsResponse>("/dev/runs?limit=25");
  const [form, setForm] = useState({ kind: "plan", name: "", prompt: "", goal: "" });
  const [busy, setBusy] = useState(false);
  const [startError, setStartError] = useState<string | null>(null);
  const ceiling = data?.usage.max_budget_usd ?? 0.5;

  async function start() {
    setBusy(true);
    setStartError(null);
    try {
      await api("/dev/runs", { method: "POST", body: JSON.stringify({ ...form, plan_mode: form.kind === "plan" }) });
      setForm({ ...form, name: "", prompt: "", goal: "" });
      reload?.();
    } catch (e) {
      setStartError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-4">
      <Card title="Cost">
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          <Stat label="Runs" value={data?.usage.runs ?? 0} />
          <Stat label="Total spent" value={money(data?.usage.total_cost_usd ?? 0)} />
          <Stat label="Ceiling per run" value={money(ceiling)} sub="enforced by the API" />
          <Stat label="claude CLI" value={data?.claude_available ? "available" : "not on PATH"} />
        </div>
      </Card>

      <Card title="Start an unattended run">
        <ErrorNote error={startError} />
        <p className="mb-3 text-sm text-stone-600">
          Runs get their own git worktree and branch — your working tree is never touched — and stop at{" "}
          <b>{money(ceiling)}</b>. They never merge or push; the output is a branch to review.
        </p>
        <div className="grid grid-cols-1 gap-2 md:grid-cols-4">
          <select className={inputCls} value={form.kind} onChange={(e) => setForm({ ...form, kind: e.target.value })}>
            {["plan", "implement", "debug", "research"].map((k) => (
              <option key={k} value={k}>
                {k}
              </option>
            ))}
          </select>
          <input
            className={inputCls}
            placeholder="name, e.g. issue-12"
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
          />
          <input
            className={`${inputCls} md:col-span-2`}
            placeholder="/goal condition (optional)"
            value={form.goal}
            onChange={(e) => setForm({ ...form, goal: e.target.value })}
          />
        </div>
        <textarea
          className={`${inputCls} mt-2 h-24 w-full`}
          placeholder="What should the run do?"
          value={form.prompt}
          onChange={(e) => setForm({ ...form, prompt: e.target.value })}
        />
        <button className={`${buttonCls} mt-2`} disabled={busy || !form.name || !form.prompt} onClick={start}>
          {busy ? "Running…" : `Run (max ${money(ceiling)})`}
        </button>
      </Card>

      <Card title="Recent runs">
        <ErrorNote error={error} />
        {(data?.runs ?? []).length === 0 ? (
          <p className="text-sm text-stone-500">No runs yet.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-stone-200 text-left text-stone-500">
                  <th className="py-2 pr-3">Kind</th>
                  <th className="py-2 pr-3">Branch</th>
                  <th className="py-2 pr-3">Status</th>
                  <th className="py-2 pr-3">Cost</th>
                  <th className="py-2 pr-3">Turns</th>
                  <th className="py-2 pr-3">Duration</th>
                </tr>
              </thead>
              <tbody>
                {(data?.runs ?? []).map((run: AgentRunRow) => (
                  <tr key={run.id} className="border-b border-stone-100">
                    <td className="py-2 pr-3">{run.kind}</td>
                    <td className="py-2 pr-3 font-mono text-xs">{run.branch ?? "—"}</td>
                    <td className="py-2 pr-3">
                      <Tag tone={run.status === "ok" ? "new" : run.status === "running" ? "neutral" : "warn"}>
                        {run.status}
                      </Tag>
                    </td>
                    <td className="py-2 pr-3 tabular-nums">{run.cost_usd == null ? "—" : money(run.cost_usd)}</td>
                    <td className="py-2 pr-3 tabular-nums">{run.turns ?? "—"}</td>
                    <td className="py-2 pr-3 tabular-nums">{run.duration_seconds ?? "—"}s</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}
