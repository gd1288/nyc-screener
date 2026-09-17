@AGENTS.md

## UI conventions
- Reuse `src/lib/api.ts` (`useApi` hook, `api()` fetch wrapper) and `src/lib/format.ts` (money/pct/date
  formatting) — don't add a second fetch helper or reimplement formatting per page.
- Reuse `src/components/ui.tsx` (`Card`, `ScoreBadge`, `Stat`, `Tag`, `Empty`, `ErrorNote`,
  `PageHeader`, `inputCls`/`buttonCls`) for a new page instead of writing new equivalents.
- Charts: follow the `dataviz` skill's palette and accessibility guidance (Recharts is already a
  dependency) — read it before adding a new chart type.
- Verify a new or changed page at **1280px and 400px** (mobile) before calling it done — the app has
  users on both. Use `/verify` or a manual screenshot at both widths.
