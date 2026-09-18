---
name: propose-criteria
description: Ask the criteria-proposer agent for new valuation criteria (data factors, metrics, methods) and optional staging-UI suggestions, added to research/criteria.yaml as `proposed`. Use for "what else should the valuation consider", "propose new criteria", or a periodic ledger review. Proposes only; approval and implementation are separate steps.
context: fork
agent: criteria-proposer
background: false
---

# /propose-criteria

Hand the request to the `criteria-proposer` agent as given; its procedure is in
`.claude/agents/criteria-proposer.md`. If the user named a focus (rent growth, risk, a neighborhood
factor), pass it along; otherwise let it review the whole ledger.

After it returns:
1. Run `cd backend && uv run python -m app.cli criteria` and report any problems.
2. Summarise the new `proposed` rows and any staging UI suggestions in a few lines.
3. Ask the user to approve, reject or defer each. Only the user changes a status to `approved`,
   `rejected` or `live`, and only then does data sourcing (`research-sources`) or implementation
   (`add-data-source`, or a staging artifact change) begin.
