# ZDR ↔ Rally Defect Sync

Compares open defects between Rally (external ALM) and ZDR (Zinnia's internal
"Defect Reporting" Jira project), then lets you create ZDR tickets for any
open Rally defect that doesn't have one yet.

Matching is done via ZDR's **"External Issue ID A"** field
(`customfield_13901`), which should hold the Rally `FormattedID` (e.g.
`DE1234`) for any ZDR ticket that originated from a Rally defect.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Fill in `.env`:
- `RALLY_ZSESSIONID` / `RALLY_JSESSIONID` — no Rally API key access on this
  account, so auth uses your live browser session cookies instead. Log in to
  Rally normally, open DevTools → Application/Storage → Cookies → your Rally
  domain, and copy the `ZSESSIONID` and `JSESSIONID` values. These expire
  (idle timeout/logout), so you'll need to refresh them when calls start
  failing with 401/403 — this is a session token, not a durable credential.
- `ZDR_JIRA_EMAIL` / `ZDR_JIRA_API_TOKEN` — your Zinnia Atlassian account email
  and an API token from https://id.atlassian.com/manage-profile/security/api-tokens

Fill in `config.yaml`:
- `rally.project` — which Rally project to pull defects from
- `rally.not_state` — a defect is "open" if `State != not_state` (default: `"Closed"`)
- `rally.owners` — limit to defects owned by this list (matches Rally's Owner
  display name exactly); leave empty to include every owner in the project
- `zdr.jql_filter` — appended to `project = ZDR AND ...` verbatim; currently
  scopes to the Farmers Product Launches 2025 OA7540 release, restricts to
  tickets already carrying a Rally-style (`DE*`) external ID, and excludes
  `Done`/`Cancelled`/`Pending Client Info`/`Pending Client Sign Off`/`Pending
  Approval to Close`. Edit this directly (in Jira's JQL syntax) to change scope.
- `zdr.jql_order_by` — sort clause, e.g. `cf[13508] ASC` (Defect Severity)

## Usage

Read-only comparison:

```bash
python -m src.cli compare
python -m src.cli compare --csv-out reports/comparison.csv
```

Compare, then interactively create ZDR tickets for defects that are open in
Rally but missing from ZDR:

```bash
python -m src.cli sync
```

`sync` never writes anything without an explicit confirmation — it shows you
the missing defects, lets you pick which ones (or `all`), confirms once more,
then creates them.

### Live dashboard (web UI)

```bash
python -m src.server
```

Serves the same comparison dashboard at http://127.0.0.1:5050 — every page
load (or the Refresh button) re-fetches live data from Rally and ZDR. This is
a Flask dev server for local/personal use, not meant to be exposed beyond
localhost.

## Notes / things to double check before relying on this

- ZDR's "Defect Reporting" project only has two issue types
  ("Ask a question" and "Submit a request or incident"). New defects are
  created as `Submit a request or incident` (id `11266`) — there's no
  dedicated "Bug"/"Defect" issue type.
- The project spans multiple clients (RNA, Nassau, Farmers, GILICO, JPMC,
  Arcus, Everly, SB, Wellabe, etc.) with client-specific custom fields. This
  script only sets `summary`, `description`, and the Rally cross-reference
  field on creation — add more fields in `src/zdr_client.py::create_defect`
  if your team needs severity/client/system populated automatically.
- "Orphaned in ZDR" (an open ZDR ticket referencing a Rally ID that Rally no
  longer reports as open) is reported by `compare` but not acted on — that
  usually means the Rally defect was closed/rejected and ZDR should be
  reviewed manually.
