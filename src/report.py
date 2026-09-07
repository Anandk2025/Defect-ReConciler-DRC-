import html
import json
import re
from datetime import datetime

from . import config

_ORANGE = "#F46C00"
_TEXT = "#171717"
_TEXT_DIM = "#6B6F73"
_BORDER = "#E7E3DC"

_SEVERITY_COLOR = {"Showstopper": "#C0392B", "High": "#C0392B", "Medium": "#B45309", "Low": "#0F766E"}
_STATUS_COLOR = {"In Triage": "#B45309", "Pending Approval to Close": "#2F855A"}
_STATE_DOT = {
    "Submitted": "#888780",
    "Open": _ORANGE,
    "In Progress": "#5B4FCF",
    "Fixed": "#0F766E",
    "Failed": "#C0392B",
    "Closed": "#2F855A",
}
_RALLY_OBJECT_ID_RE = re.compile(r"/defect/(\d+)")

_ICON_SVG = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2.3" '
    'stroke-linecap="round" stroke-linejoin="round" width="22" height="22">'
    '<path d="M3 12a9 9 0 0 1 15-6.7L21 8"/><path d="M21 3v5h-5"/>'
    '<path d="M21 12a9 9 0 0 1-15 6.7L3 16"/><path d="M3 21v-5h5"/>'
    "</svg>"
)
_FAVICON_DATA_URI = (
    "data:image/svg+xml,"
    "%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E"
    "%3Crect width='24' height='24' rx='6' fill='%23F46C00'/%3E"
    "%3Cpath d='M5 12a7 7 0 0 1 11.7-5.2L18.5 8.5' stroke='white' stroke-width='2' "
    "fill='none' stroke-linecap='round' stroke-linejoin='round'/%3E"
    "%3Cpath d='M18.5 5v3.5H15' stroke='white' stroke-width='2' fill='none' "
    "stroke-linecap='round' stroke-linejoin='round'/%3E"
    "%3Cpath d='M19 12a7 7 0 0 1-11.7 5.2L5.5 15.5' stroke='white' stroke-width='2' "
    "fill='none' stroke-linecap='round' stroke-linejoin='round'/%3E"
    "%3Cpath d='M5.5 19v-3.5H9' stroke='white' stroke-width='2' fill='none' "
    "stroke-linecap='round' stroke-linejoin='round'/%3E"
    "%3C/svg%3E"
)


def _esc(value, limit=None):
    text = str(value) if value is not None else "-"
    if limit and len(text) > limit:
        text = text[: limit].rstrip() + "..."
    return html.escape(text)


def _badge(text, color, classes="badge", data_attrs=""):
    return f'<span class="{classes}" style="background:{color}1a;color:{color};"{data_attrs}>{_esc(text)}</span>'


def _severity_badge(sev):
    sev = sev or "None"
    return _badge(sev, _SEVERITY_COLOR.get(sev, "#888780"))


def _state_badge(state):
    return _badge(state, _STATE_DOT.get(state, "#7f77dd"))


def _editable_state_badge(rally_id, state):
    return _badge(
        state,
        _STATE_DOT.get(state, "#7f77dd"),
        classes="badge rally-state-badge",
        data_attrs=f' data-rally-id="{_esc(rally_id)}" title="Click to change state"',
    )


def _status_badge(status):
    return _badge(status, _STATUS_COLOR.get(status, "#888780"))


def _editable_status_badge(zdr_key, status):
    return _badge(
        status,
        _STATUS_COLOR.get(status, "#888780"),
        classes="badge zdr-status-badge",
        data_attrs=f' data-zdr-key="{_esc(zdr_key)}" title="Click to change status"',
    )


def _date_display(value):
    return _esc((value or "")[:10] or "-")


def _editable_date_cell(kind, key, value):
    raw = (value or "")[:10]
    attr = "data-zdr-key" if kind == "zdr" else "data-rally-id"
    return (
        f'<span class="date-cell {kind}-date-cell" {attr}="{_esc(key)}" '
        f'data-value="{_esc(raw)}" title="Click to edit">{_date_display(value)}</span>'
    )


def _dot(color):
    return f'<span class="dot" style="background:{color};"></span>'


def _rally_link(rally):
    m = _RALLY_OBJECT_ID_RE.search(rally.get("ref") or "")
    rally_id = _esc(rally["id"])
    if not m:
        return rally_id
    url = f"{config.RALLY_BASE_URL}/#/detail/defect/{m.group(1)}"
    return f'<a href="{url}">{rally_id}</a>'


def _missing_row(d, enable_actions, created_map):
    action_cell = ""
    if enable_actions:
        created_key = created_map.get(d["id"]) if created_map else None
        if created_key:
            action_cell = f"""<td class="nowrap"><a href="https://{config.ZDR_SITE}/browse/{_esc(created_key)}" style="color:#2F855A;">Created {_esc(created_key)}</a></td>"""
        else:
            action_cell = f"""<td class="nowrap"><form method="post" action="/create-zdr/{_esc(d['id'])}" class="create-zdr-form" data-rally-id="{_esc(d['id'])}" style="margin:0;"><button type="submit" class="link-btn">Create ZDR</button></form></td>"""
    created = (d.get("created") or "")[:10]
    dot = _dot(_STATE_DOT.get(d["state"], "#7f77dd"))
    state_cell = _editable_state_badge(d["id"], d["state"]) if enable_actions else _state_badge(d["state"])
    return f"""<tr>
<td class="mono nowrap">{dot}{_rally_link(d)}</td>
<td>{state_cell}</td>
<td>{_severity_badge(d['severity'])}</td>
<td class="nowrap" title="{_esc(d['owner'])}">{_esc(d['owner'])}</td>
<td class="nowrap">{_esc(created)}</td>
<td class="dim ell" title="{_esc(d['name'])}">{_esc(d['name'], 100)}</td>
{action_cell}
</tr>"""


def _matched_row(m, enable_comments):
    rally, zdr = m["rally"], m["zdr"]
    keys = ", ".join(z["key"] for z in zdr)
    first_key = zdr[0]["key"] if zdr else ""
    status = zdr[0]["status"] if zdr else "-"
    comments_cell = ""
    update_comments_cell = ""
    sync_cell = ""
    if enable_comments:
        comments_cell = f"""<td class="nowrap">
<span class="comment-link" data-rally-id="{_esc(rally['id'])}" data-zdr-key="{_esc(first_key)}">Comments</span>
</td>"""
        update_comments_cell = f"""<td class="nowrap">
<span class="uc-link" data-direction="to-zdr" data-rally-id="{_esc(rally['id'])}" data-zdr-key="{_esc(first_key)}" title="Copy Rally's latest comment into ZDR">To ZDR</span>
<span class="uc-link" data-direction="to-rally" data-rally-id="{_esc(rally['id'])}" data-zdr-key="{_esc(first_key)}" title="Fetch External Client Version from ZDR's latest comment and post it to Rally">To Rally</span>
</td>"""
        sync_cell = f"""<td>
<button type="button" class="link-btn sync-check-btn" data-rally-id="{_esc(rally['id'])}" data-zdr-key="{_esc(first_key)}">Check sync</button>
</td>"""
    status_cell = _editable_status_badge(first_key, status) if enable_comments and zdr else _status_badge(status)
    state_cell = _editable_state_badge(rally["id"], rally["state"]) if enable_comments else _state_badge(rally["state"])
    qa_complete_date = zdr[0].get("qa_complete_date") if zdr else None
    if enable_comments and first_key:
        zdr_eta_cell = _editable_date_cell("zdr", first_key, qa_complete_date)
    else:
        zdr_eta_cell = _date_display(qa_complete_date)
    rally_eta_cell = (
        _editable_date_cell("rally", rally["id"], rally.get("target_date"))
        if enable_comments
        else _date_display(rally.get("target_date"))
    )
    row_class = "matched-row"
    row_title = ""
    if (rally.get("state") or "") == "Open":
        row_class += " row-rally-open"
        row_title = ' title="ZDR ticket exists, but Rally status is still Open"'
    return f"""<tr class="{row_class}"{row_title}>
<td class="mono nowrap">{_dot('#2F855A')}{_rally_link(rally)}</td>
<td class="mono nowrap"><a href="https://{config.ZDR_SITE}/browse/{_esc(first_key)}">{_esc(keys)}</a></td>
<td>{state_cell}</td>
<td>{status_cell}</td>
<td class="nowrap">{zdr_eta_cell}</td>
<td class="nowrap">{rally_eta_cell}</td>
<td class="nowrap" title="{_esc(rally['owner'])}">{_esc(rally['owner'])}</td>
<td class="dim ell" title="{_esc(rally['name'])}">{_esc(rally['name'], 100)}</td>
{comments_cell}
{update_comments_cell}
{sync_cell}
</tr>"""


def _all_row(rally, zdr_list, enable_actions, created_map):
    if zdr_list:
        first_key = zdr_list[0]["key"]
        keys = ", ".join(z["key"] for z in zdr_list)
        zdr_key_cell = f'<a href="https://{config.ZDR_SITE}/browse/{_esc(first_key)}">{_esc(keys)}</a>'
        zdr_status_cell = (
            _editable_status_badge(first_key, zdr_list[0]["status"])
            if enable_actions
            else _status_badge(zdr_list[0]["status"])
        )
        action_inner = '<span class="dim">-</span>'
        dot_color = "#2F855A"
    else:
        zdr_key_cell = '<span class="dim">-</span>'
        zdr_status_cell = '<span class="dim">-</span>'
        dot_color = _STATE_DOT.get(rally["state"], "#7f77dd")
        created_key = created_map.get(rally["id"]) if created_map else None
        if created_key:
            action_inner = f'<a href="https://{config.ZDR_SITE}/browse/{_esc(created_key)}" style="color:#2F855A;">Created {_esc(created_key)}</a>'
        else:
            action_inner = f"""<form method="post" action="/create-zdr/{_esc(rally['id'])}" class="create-zdr-form" data-rally-id="{_esc(rally['id'])}" style="margin:0;"><button type="submit" class="link-btn">Create ZDR</button></form>"""
    action_cell = f'<td class="nowrap">{action_inner}</td>' if enable_actions else ""
    state_cell = _editable_state_badge(rally["id"], rally["state"]) if enable_actions else _state_badge(rally["state"])
    return f"""<tr>
<td class="mono nowrap">{_dot(dot_color)}{_rally_link(rally)}</td>
<td>{state_cell}</td>
<td>{_severity_badge(rally['severity'])}</td>
<td class="nowrap" title="{_esc(rally['owner'])}">{_esc(rally['owner'])}</td>
<td class="mono nowrap">{zdr_key_cell}</td>
<td>{zdr_status_cell}</td>
<td class="dim ell" title="{_esc(rally['name'])}">{_esc(rally['name'], 100)}</td>
{action_cell}
</tr>"""


def build_login_html(error=None):
    error_html = (
        f'<p style="color:#C0392B;font-size:13px;font-weight:500;margin:0 0 16px;text-align:center;">{_esc(error)}</p>'
        if error
        else ""
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Defect ReConciler (DRC)</title>
<link rel="icon" type="image/svg+xml" href="{_FAVICON_DATA_URI}">
<style>
* {{ box-sizing:border-box; }}
body {{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#F7F5F2;color:{_TEXT};margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;padding:2rem;}}
.login-wrap {{width:100%;max-width:380px;text-align:center;}}
.app-icon {{width:48px;height:48px;border-radius:12px;background:linear-gradient(135deg,{_ORANGE},#FF9142);display:inline-flex;align-items:center;justify-content:center;box-shadow:0 2px 6px rgba(244,108,0,0.35);margin-bottom:14px;}}
h1 {{font-size:20px;font-weight:600;margin:0 0 4px;letter-spacing:-.01em;}}
.tagline {{font-size:13px;color:{_TEXT_DIM};margin:0 0 28px;}}
.card {{background:#fff;border:1px solid {_BORDER};border-radius:14px;padding:2rem 1.75rem;box-shadow:0 1px 2px rgba(23,23,23,0.04);text-align:left;}}
.card h2 {{font-size:17px;font-weight:600;margin:0 0 4px;text-align:center;}}
.card p.sub {{font-size:13px;color:{_TEXT_DIM};margin:0 0 22px;text-align:center;}}
label {{display:block;font-size:12px;font-weight:600;color:{_TEXT_DIM};margin-bottom:6px;}}
input[type=password] {{width:100%;padding:10px 12px;border:1px solid {_BORDER};border-radius:8px;font-size:14px;margin-bottom:16px;}}
input[type=password]:focus {{outline:none;border-color:{_ORANGE};}}
.remember {{display:flex;align-items:center;gap:8px;font-size:13px;color:{_TEXT_DIM};margin-bottom:20px;}}
button.submit {{width:100%;border:none;border-radius:999px;background:{_ORANGE};color:#fff;padding:11px 20px;font-size:14px;font-weight:600;cursor:pointer;}}
button.submit:hover {{background:#DE6300;}}
.footer {{font-size:11px;color:{_TEXT_DIM};margin-top:24px;}}
</style>
</head>
<body>
<div class="login-wrap">
  <div class="app-icon">{_ICON_SVG}</div>
  <h1>Defect ReConciler (DRC)</h1>
  <p class="tagline">Zinnia Defect Management (ZDR) &harr; External Defect Management (Rally)</p>
  <div class="card">
    <h2>Welcome back</h2>
    <p class="sub">Enter the shared team password to continue</p>
    {error_html}
    <form method="post" action="/login">
      <label for="password">Password</label>
      <input type="password" id="password" name="password" autofocus required>
      <label class="remember"><input type="checkbox" name="remember" value="1" style="width:auto;margin:0;"> Remember me</label>
      <button type="submit" class="submit">Log In</button>
    </form>
  </div>
  <p class="footer">Zinnia internal tool</p>
</div>
</body>
</html>"""


def build_html(
    result,
    rally_count,
    zdr_count,
    refresh_url=None,
    enable_actions=False,
    notice=None,
    created_map=None,
    show_logout=False,
):
    missing_rows = "".join(_missing_row(d, enable_actions, created_map) for d in result["missing_in_zdr"])
    matched_rows = "".join(_matched_row(m, enable_actions) for m in result["matched"])
    all_entries = [(m["rally"], m["zdr"]) for m in result["matched"]] + [
        (d, None) for d in result["missing_in_zdr"]
    ]
    all_rows = "".join(_all_row(r, z, enable_actions, created_map) for r, z in all_entries)
    matched_n = len(result["matched"])
    missing_n = len(result["missing_in_zdr"])
    all_n = matched_n + missing_n
    updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    refresh_button = (
        f'<button class="cta" onclick="location.href=\'{refresh_url}\'">Refresh</button>' if refresh_url else ""
    )
    logout_link = (
        '<a href="/logout" style="float:right;margin-right:16px;margin-top:9px;font-size:13px;font-weight:600;">'
        "Log out</a>"
        if show_logout
        else ""
    )
    pending_create_n = 0
    if enable_actions:
        pending_create_n = sum(
            1 for d in result["missing_in_zdr"] if not (created_map and created_map.get(d["id"]))
        )
    if enable_actions and pending_create_n:
        action_header = (
            "<th>Action<br>"
            '<form method="post" action="/create-all-zdrs" class="create-all-zdrs-form" '
            f'data-count="{pending_create_n}" style="margin:4px 0 0;display:block;">'
            '<button type="submit" class="link-btn" '
            'style="font-size:11px;text-transform:none;letter-spacing:0;font-weight:600;white-space:nowrap;">'
            "Create All ZDRs</button></form></th>"
        )
    elif enable_actions:
        action_header = "<th>Action</th>"
    else:
        action_header = ""
    action_col = '<col style="width:160px;">' if enable_actions else ""
    comments_header = "<th>Latest comments</th>" if enable_actions else ""
    comments_col = '<col style="width:150px;">' if enable_actions else ""
    update_comments_header = "<th>Update comments</th>" if enable_actions else ""
    update_comments_col = '<col style="width:110px;">' if enable_actions else ""
    sync_header = (
        '<th>Comments sync status '
        '<button type="button" id="check-all-sync-btn" class="link-btn" '
        'style="font-size:11px;text-transform:none;letter-spacing:0;font-weight:600;margin-left:4px;">'
        "Check all</button></th>"
        if enable_actions
        else ""
    )
    sync_col = '<col style="width:420px;">' if enable_actions else ""
    notice_html = ""
    if notice:
        kind, message = notice
        color = "#2F855A" if kind == "success" else "#C0392B"
        notice_html = f'<div class="notice" style="border-color:{color};color:{color};">{_esc(message)}</div>'
    rally_filter_link = (
        f'<a class="metric-filter-link" href="{config.RALLY_FILTER_URL}" target="_blank">Filter</a>'
        if config.RALLY_FILTER_URL
        else ""
    )
    zdr_filter_link = (
        f'<a class="metric-filter-link" href="{config.ZDR_FILTER_URL}" target="_blank">Filter</a>'
        if config.ZDR_FILTER_URL
        else ""
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Defect ReConciler (DRC)</title>
<link rel="icon" type="image/svg+xml" href="{_FAVICON_DATA_URI}">
<style>
* {{ box-sizing:border-box; }}
body {{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#F7F5F2;color:{_TEXT};margin:0;padding:2.5rem;}}
.header {{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:1.75rem;padding-bottom:1.5rem;border-bottom:1px solid {_BORDER};}}
.header-left {{display:flex;gap:14px;align-items:flex-start;}}
.app-icon {{width:42px;height:42px;border-radius:11px;background:linear-gradient(135deg,{_ORANGE},#FF9142);display:flex;align-items:center;justify-content:center;flex-shrink:0;box-shadow:0 2px 6px rgba(244,108,0,0.35);}}
.kicker {{font-size:12px;font-weight:600;letter-spacing:.02em;color:{_TEXT_DIM};margin:4px 0 0;}}
.kicker b {{color:{_ORANGE};font-weight:600;}}
h1 {{font-size:26px;font-weight:600;margin:0;color:{_TEXT};letter-spacing:-.01em;}}
h2 {{font-size:15px;font-weight:600;margin:0 0 4px;color:{_TEXT};}}
.section {{margin-bottom:1.75rem;}}
.metrics {{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:14px;max-width:960px;}}
.metric {{background:#fff;border-radius:12px;padding:1.1rem 1.25rem;border:1px solid {_BORDER};border-top:3px solid var(--accent, {_ORANGE});box-shadow:0 1px 2px rgba(23,23,23,0.04);}}
.metric p:first-child {{font-size:11px;font-weight:600;letter-spacing:.04em;text-transform:uppercase;color:{_TEXT_DIM};margin:0 0 6px;}}
.metric p:last-child {{font-size:26px;font-weight:600;margin:0;color:{_TEXT};}}
.tab-btn {{border:1px solid {_BORDER};border-radius:999px;background:#fff;padding:7px 16px;font-size:13px;font-weight:500;cursor:pointer;margin-right:8px;color:{_TEXT_DIM};}}
.tab-btn.active {{background:{_ORANGE};border-color:{_ORANGE};color:#fff;}}
.cta {{border:none;border-radius:999px;background:{_ORANGE};color:#fff;padding:9px 20px;font-size:13px;font-weight:600;cursor:pointer;float:right;}}
.cta:hover {{background:#DE6300;}}
table {{border-collapse:collapse;table-layout:fixed;background:#fff;width:max-content;min-width:100%;}}
th {{text-align:left;padding:10px 8px;font-size:11px;font-weight:600;letter-spacing:.03em;text-transform:uppercase;color:{_TEXT_DIM};border-bottom:1px solid {_BORDER};background:#fff;position:sticky;top:0;z-index:1;}}
td {{padding:10px 8px;font-size:13px;border-bottom:1px solid {_BORDER};}}
tr:hover td {{background:#FAF8F5;}}
tr.row-rally-open td {{background:#FDECEC;}}
tr.row-rally-open:hover td {{background:#F8D4D4;}}
.mono {{font-family:ui-monospace,monospace;font-size:12px;}}
.nowrap {{white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}}
.dim {{color:{_TEXT_DIM};}}
.ell {{max-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}}
.badge {{display:inline-block;padding:2px 9px;border-radius:999px;font-size:12px;font-weight:500;white-space:nowrap;}}
.dot {{display:inline-block;width:7px;height:7px;border-radius:50%;margin-right:7px;vertical-align:middle;}}
a {{color:{_ORANGE};text-decoration:none;}}
a:hover {{text-decoration:underline;}}
.panel {{width:100%;max-width:100%;overflow-x:scroll;overflow-y:auto;max-height:640px;background:#fff;border:1px solid {_BORDER};border-radius:12px;padding:4px 4px 8px;box-shadow:0 1px 2px rgba(23,23,23,0.04);scrollbar-gutter:stable;scrollbar-width:auto;}}
.panel::-webkit-scrollbar {{height:14px;width:12px;}}
.panel::-webkit-scrollbar-track {{background:#EFEBE4;border-radius:8px;}}
.panel::-webkit-scrollbar-thumb {{background:#C7C1B5;border-radius:8px;border:2px solid #EFEBE4;}}
.panel::-webkit-scrollbar-thumb:hover {{background:#A8A296;}}
.panel::-webkit-scrollbar-corner {{background:#EFEBE4;}}
.link-btn {{background:none;border:none;color:{_ORANGE};font-size:13px;font-weight:500;cursor:pointer;padding:0;}}
.link-btn:hover {{text-decoration:underline;}}
.link-btn:disabled {{color:{_TEXT_DIM};cursor:default;text-decoration:none;}}
.spinner {{display:inline-block;width:11px;height:11px;border:2px solid {_BORDER};border-top-color:{_ORANGE};border-radius:50%;animation:spin .6s linear infinite;vertical-align:middle;margin-right:5px;}}
.notice {{background:#fff;border:1px solid {_BORDER};border-left:4px solid;padding:12px 16px;border-radius:8px;margin-bottom:1.25rem;font-size:13px;font-weight:500;}}
.comment-link {{color:{_ORANGE};cursor:pointer;font-weight:500;}}
.comment-link:hover {{text-decoration:underline;}}
.uc-link {{color:{_ORANGE};cursor:pointer;font-weight:500;display:block;font-size:12px;}}
.uc-link:hover {{text-decoration:underline;}}
.uc-link + .uc-link {{margin-top:3px;}}
.comment-tooltip {{position:absolute;display:none;max-width:340px;background:{_TEXT};color:#fff;padding:0;border-radius:8px;font-size:12px;line-height:1.5;box-shadow:0 4px 12px rgba(23,23,23,0.18);z-index:50;overflow:hidden;}}
.comment-tooltip .ct-block {{padding:10px 12px;}}
.comment-tooltip .ct-block + .ct-block {{border-top:1px solid rgba(255,255,255,0.12);}}
.comment-tooltip .ct-label {{color:{_ORANGE};font-size:10px;font-weight:600;letter-spacing:.04em;text-transform:uppercase;margin-bottom:4px;}}
.comment-tooltip .ct-meta {{color:#B9BBBE;font-size:11px;margin-bottom:4px;}}
.metric-filter-link {{float:right;text-transform:none;letter-spacing:0;font-weight:500;}}
.sync-badge {{display:inline-block;padding:2px 9px;border-radius:999px;font-size:12px;font-weight:500;cursor:help;}}
.zdr-status-badge {{cursor:pointer;}}
.zdr-status-badge:hover {{box-shadow:0 0 0 1px currentColor inset;}}
.zdr-status-select, .zdr-field-select, .rally-state-select, .date-input {{font-size:12px;padding:2px 4px;height:auto;width:100%;max-width:100%;box-sizing:border-box;}}
.rally-state-badge {{cursor:pointer;}}
.rally-state-badge:hover {{box-shadow:0 0 0 1px currentColor inset;}}
.date-cell {{cursor:pointer;}}
.date-cell:hover {{text-decoration:underline;}}
@keyframes spin {{ to {{ transform:rotate(360deg); }} }}
</style>
</head>
<body>
<div class="header">
  <div class="header-left">
    <div class="app-icon">{_ICON_SVG}</div>
    <div>
      <h1>Defect ReConciler (DRC)</h1>
      <p class="kicker"><b>Zinnia Defect Management</b> (ZDR) &harr; <b>External Defect Management</b> (Rally)</p>
      <p class="dim" style="font-size:12px;margin:8px 0 0;">Last updated {updated_at}</p>
    </div>
  </div>
  {refresh_button}
  {logout_link}
</div>
{notice_html}

<div class="section">
  <h2>Defects counts summary</h2>
  <div class="metrics">
    <div class="metric" style="--accent:#0F766E;"><p>Rally open defects count{rally_filter_link}</p><p>{rally_count}</p></div>
    <div class="metric" style="--accent:#5B4FCF;"><p>ZDR open defects count{zdr_filter_link}</p><p>{zdr_count}</p></div>
  </div>
</div>

<div class="section">
  <h2>Defects counts match summary</h2>
  <p class="dim" style="font-size:13px;margin:0 0 10px;">Counts match and mismatch summary</p>
  <div class="metrics">
    <div class="metric" style="--accent:#2F855A;"><p>ZDR available for Rally defects</p><p style="color:#2F855A;">{matched_n}</p></div>
    <div class="metric" style="--accent:#C0392B;"><p>ZDR missing for Rally defects</p><p style="color:#C0392B;">{missing_n}</p></div>
  </div>
</div>
<div>
  <button class="tab-btn active" data-tab="all">All defects ({all_n})</button>
  <button class="tab-btn" data-tab="matched">ZDR available for Rally defects ({matched_n})</button>
  <button class="tab-btn" data-tab="missing">ZDR missing for Rally defects ({missing_n})</button>
</div>
<br>
<div class="panel" data-panel="all">
  <table>
    <colgroup><col style="width:90px;"><col style="width:130px;"><col style="width:80px;"><col style="width:130px;"><col style="width:100px;"><col style="width:130px;"><col>{action_col}</colgroup>
    <thead><tr><th>Rally id</th><th>Rally status</th><th>Severity</th><th>Owner</th><th>ZDR key</th><th>ZDR status</th><th>Summary</th>{action_header}</tr></thead>
    <tbody>{all_rows}</tbody>
  </table>
</div>
<div class="panel" data-panel="missing" style="display:none;">
  <table>
    <colgroup><col style="width:90px;"><col style="width:130px;"><col style="width:80px;"><col style="width:130px;"><col style="width:90px;"><col>{action_col}</colgroup>
    <thead><tr><th>Rally id</th><th>Rally status</th><th>Severity</th><th>Owner</th><th>Created</th><th>Summary</th>{action_header}</tr></thead>
    <tbody>{missing_rows}</tbody>
  </table>
</div>
<div class="panel" data-panel="matched" style="display:none;">
  <table style="min-width:1860px;">
    <colgroup><col style="width:90px;"><col style="width:100px;"><col style="width:130px;"><col style="width:150px;"><col style="width:110px;"><col style="width:110px;"><col style="width:140px;"><col style="width:180px;">{comments_col}{update_comments_col}{sync_col}</colgroup>
    <thead><tr><th>Rally id</th><th>ZDR key</th><th>Rally status</th><th>ZDR status</th><th>ZDR fix ETA</th><th>Rally fix ETA</th><th>Owner</th><th>Summary</th>{comments_header}{update_comments_header}{sync_header}</tr></thead>
    <tbody>{matched_rows}</tbody>
  </table>
</div>
<div class="comment-tooltip" id="comment-tooltip"></div>
<script>
document.querySelectorAll('.tab-btn').forEach(function(b) {{
  b.addEventListener('click', function() {{
    document.querySelectorAll('.panel').forEach(function(p) {{
      p.style.display = (p.getAttribute('data-panel') === b.getAttribute('data-tab')) ? '' : 'none';
    }});
    document.querySelectorAll('.tab-btn').forEach(function(x) {{ x.classList.remove('active'); }});
    b.classList.add('active');
  }});
}});
document.querySelectorAll('.panel').forEach(function(p) {{
  p.addEventListener('wheel', function(e) {{
    if (!e.shiftKey || p.scrollWidth <= p.clientWidth) {{ return; }}
    e.preventDefault();
    p.scrollLeft += e.deltaY;
  }}, {{passive: false}});
}});
document.querySelectorAll('.create-zdr-form').forEach(function(form) {{
  form.addEventListener('submit', function(e) {{
    if (!confirm('Create a ZDR ticket for ' + form.getAttribute('data-rally-id') + '?')) {{
      e.preventDefault();
      return;
    }}
    var btn = form.querySelector('button');
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span>Creating...';
  }});
}});
document.querySelectorAll('.create-all-zdrs-form').forEach(function(form) {{
  form.addEventListener('submit', function(e) {{
    var n = form.getAttribute('data-count');
    if (!confirm('Create ZDR tickets for all ' + n + ' missing Rally defects?')) {{
      e.preventDefault();
      return;
    }}
    document.querySelectorAll('.create-all-zdrs-form button, .create-zdr-form button').forEach(function(btn) {{
      btn.disabled = true;
    }});
    form.querySelector('button').innerHTML = '<span class="spinner"></span>Creating all...';
  }});
}});
(function() {{
  var tooltip = document.getElementById('comment-tooltip');
  var cache = {{}};
  function show(el, html) {{
    var rect = el.getBoundingClientRect();
    tooltip.innerHTML = html;
    tooltip.style.display = 'block';
    tooltip.style.left = (rect.left + window.scrollX) + 'px';
    tooltip.style.top = (rect.bottom + window.scrollY + 6) + 'px';
  }}
  function fetchOne(kind, id) {{
    return fetch('/api/comments/' + kind + '/' + encodeURIComponent(id))
      .then(function(r) {{ return r.json(); }})
      .catch(function(e) {{ return {{error: String(e)}}; }});
  }}
  function block(label, data) {{
    var body;
    if (data.error) {{
      body = 'Failed to load: ' + data.error;
    }} else {{
      var meta = data.author ? '<div class="ct-meta">' + data.author + (data.created ? ' · ' + data.created.slice(0, 10) : '') + '</div>' : '';
      body = meta + (data.text || 'No comments yet.').replace(/</g, '&lt;');
    }}
    return '<div class="ct-block"><div class="ct-label">' + label + '</div>' + body + '</div>';
  }}
  var openFor = null;
  function hide() {{
    tooltip.style.display = 'none';
    openFor = null;
  }}
  document.querySelectorAll('.comment-link').forEach(function(el) {{
    el.addEventListener('click', function(e) {{
      e.stopPropagation();
      if (openFor === el) {{ hide(); return; }}
      openFor = el;
      var rallyId = el.getAttribute('data-rally-id');
      var zdrKey = el.getAttribute('data-zdr-key');
      var key = rallyId + ':' + zdrKey;
      if (cache[key]) {{ show(el, cache[key]); return; }}
      show(el, '<div class="ct-block">Loading...</div>');
      Promise.all([fetchOne('rally', rallyId), fetchOne('zdr', zdrKey)]).then(function(results) {{
        var html = block('Rally', results[0]) + block('ZDR', results[1]);
        cache[key] = html;
        if (openFor === el) {{ show(el, html); }}
      }});
    }});
  }});
  tooltip.addEventListener('click', function(e) {{ e.stopPropagation(); }});
  document.addEventListener('click', function() {{ hide(); }});
}})();
var UC_DIRECTIONS = {{
  'to-zdr': {{
    url: '/api/zdr/copy-comment-to-zdr/',
    confirm: function(rallyId, zdrKey) {{ return 'Copy the latest Rally comment from ' + rallyId + ' into ' + zdrKey + '\\'s ZDR comments?'; }},
    notAvailable: function(rallyId, zdrKey) {{ return 'Rally comments are not available for ' + rallyId + '.'; }},
    posted: function(rallyId, zdrKey, value) {{ return 'Posted the latest Rally comment to ' + zdrKey + '.'; }},
  }},
  'to-rally': {{
    url: '/api/zdr/external-client-version/',
    confirm: function(rallyId, zdrKey) {{ return 'Look up External Client Version in ' + zdrKey + '\\'s latest comment and post it to ' + rallyId + '\\'s Rally discussion?'; }},
    notAvailable: function(rallyId, zdrKey) {{ return 'External Client Version data is not available for ' + zdrKey + '.'; }},
    posted: function(rallyId, zdrKey, value) {{ return 'Posted "' + value + '" to ' + rallyId + '\\'s Rally discussion.'; }},
  }},
}};
document.querySelectorAll('.uc-link').forEach(function(el) {{
  el.addEventListener('click', function(e) {{
    e.stopPropagation();
    var cfg = UC_DIRECTIONS[el.getAttribute('data-direction')];
    var rallyId = el.getAttribute('data-rally-id');
    var zdrKey = el.getAttribute('data-zdr-key');
    if (!confirm(cfg.confirm(rallyId, zdrKey))) {{
      return;
    }}
    var original = el.textContent;
    el.textContent = 'Working...';
    fetch(cfg.url + encodeURIComponent(rallyId) + '/' + encodeURIComponent(zdrKey), {{
      method: 'POST',
    }})
      .then(function(r) {{ return r.json(); }})
      .then(function(data) {{
        el.textContent = original;
        if (data.error) {{
          alert('Failed: ' + data.error);
        }} else if (data.status === 'not_available') {{
          alert(cfg.notAvailable(rallyId, zdrKey));
        }} else {{
          alert(cfg.posted(rallyId, zdrKey, data.value));
        }}
      }})
      .catch(function(e) {{
        el.textContent = original;
        alert('Failed: ' + e);
      }});
  }});
}});
function checkLine(title, result) {{
  var line = document.createElement('div');
  line.style.marginBottom = '5px';

  var label = document.createElement('span');
  label.textContent = title + ' - ';
  line.appendChild(label);

  var color, statusText;
  if (result.status === 'synced') {{ color = '#2F855A'; statusText = 'Sync'; }}
  else if (result.status === 'unsynced') {{ color = '#C0392B'; statusText = 'Unsynced'; }}
  else if (result.status === 'no_comments') {{ color = '#888780'; statusText = 'No comments'; }}
  else {{ color = '#C0392B'; statusText = 'Check failed'; }}

  var badge = document.createElement('span');
  badge.className = 'sync-badge';
  badge.style.background = color + '1a';
  badge.style.color = color;
  badge.textContent = statusText;
  line.appendChild(badge);

  if (result.message) {{
    var msg = document.createElement('span');
    msg.className = 'dim';
    msg.style.fontSize = '11px';
    msg.style.marginLeft = '4px';
    msg.textContent = '(' + result.message + ')';
    line.appendChild(msg);
  }}
  return line;
}}
function checkSync(btn) {{
  var rallyId = btn.getAttribute('data-rally-id');
  var zdrKey = btn.getAttribute('data-zdr-key');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span>Checking...';
  return fetch('/api/comments/sync-status/' + encodeURIComponent(rallyId) + '/' + encodeURIComponent(zdrKey))
    .then(function(r) {{ return r.json(); }})
    .then(function(data) {{
      var wrap = document.createElement('div');
      if (data.error) {{
        wrap.appendChild(checkLine('Defect Status Check', {{status: 'error', message: ''}}));
        wrap.appendChild(checkLine('Defect Fix ETA Check', {{status: 'error', message: ''}}));
        wrap.appendChild(checkLine('Defect Comments Sync Check', {{status: 'error', message: data.error}}));
      }} else {{
        wrap.appendChild(checkLine('Defect Status Check', data.status_check));
        wrap.appendChild(checkLine('Defect Fix ETA Check', data.fix_eta_check));
        wrap.appendChild(checkLine('Defect Comments Sync Check', data.comments_check));
      }}
      btn.replaceWith(wrap);
    }})
    .catch(function(e) {{
      btn.disabled = false;
      btn.innerHTML = 'Check sync';
      throw e;
    }});
}}
document.querySelectorAll('.sync-check-btn').forEach(function(btn) {{
  btn.addEventListener('click', function() {{
    checkSync(btn).catch(function(e) {{ alert('Failed to check sync status: ' + e); }});
  }});
}});
var checkAllBtn = document.getElementById('check-all-sync-btn');
if (checkAllBtn) {{
  checkAllBtn.addEventListener('click', function() {{
    var btns = Array.prototype.slice.call(document.querySelectorAll('.sync-check-btn'));
    if (!btns.length) {{ return; }}
    checkAllBtn.disabled = true;
    checkAllBtn.textContent = 'Checking all...';
    Promise.all(btns.map(function(b) {{ return checkSync(b).catch(function() {{ return null; }}); }}))
      .then(function() {{
        checkAllBtn.disabled = false;
        checkAllBtn.textContent = 'Check all';
      }});
  }});
}}
var STATUS_COLORS = {json.dumps(_STATUS_COLOR)};
function statusBadgeHtml(zdrKey, status) {{
  var color = STATUS_COLORS[status] || '#888780';
  var span = document.createElement('span');
  span.className = 'badge zdr-status-badge';
  span.style.background = color + '1a';
  span.style.color = color;
  span.setAttribute('data-zdr-key', zdrKey);
  span.title = 'Click to change status';
  span.textContent = status;
  return span;
}}
document.addEventListener('click', function(e) {{
  var el = e.target.closest('.zdr-status-badge');
  if (!el) {{ return; }}
  var zdrKey = el.getAttribute('data-zdr-key');
  var td = el.parentElement;
  td.innerHTML = '<span class="dim" style="font-size:12px;"><span class="spinner"></span>Loading...</span>';
  fetch('/api/zdr/transitions/' + encodeURIComponent(zdrKey))
    .then(function(r) {{ return r.json(); }})
    .then(function(data) {{
      if (data.error) {{
        td.innerHTML = '<span style="color:#C0392B;font-size:12px;">' + data.error + '</span>';
        return;
      }}
      if (!data.transitions.length) {{
        td.innerHTML = '<span class="dim" style="font-size:12px;">No transitions available</span>';
        return;
      }}
      var select = document.createElement('select');
      select.className = 'zdr-status-select';
      select.setAttribute('data-zdr-key', zdrKey);
      var placeholder = document.createElement('option');
      placeholder.textContent = 'Change status to...';
      placeholder.disabled = true;
      placeholder.selected = true;
      select.appendChild(placeholder);
      data.transitions.forEach(function(t) {{
        var opt = document.createElement('option');
        opt.value = t.id;
        opt.textContent = t.name;
        select.appendChild(opt);
      }});
      td.innerHTML = '';
      td.appendChild(select);
      select.focus();
    }})
    .catch(function(e) {{ td.innerHTML = '<span style="color:#C0392B;font-size:12px;">Failed to load: ' + e + '</span>'; }});
}});
function doTransition(zdrKey, td, transitionId, fields) {{
  td.innerHTML = '<span class="dim" style="font-size:12px;"><span class="spinner"></span>Updating...</span>';
  fetch('/api/zdr/transition/' + encodeURIComponent(zdrKey), {{
    method: 'POST',
    headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify({{transition_id: transitionId, fields: fields}}),
  }})
    .then(function(r) {{ return r.json(); }})
    .then(function(data) {{
      if (data.needs_field) {{
        var nf = data.needs_field;
        var wrap = document.createElement('div');
        var label = document.createElement('div');
        label.className = 'dim';
        label.style.fontSize = '11px';
        label.style.marginBottom = '4px';
        label.textContent = nf.name + ' is required for this transition:';
        var select = document.createElement('select');
        select.className = 'zdr-field-select';
        var placeholder = document.createElement('option');
        placeholder.textContent = 'Choose ' + nf.name + '...';
        placeholder.disabled = true;
        placeholder.selected = true;
        select.appendChild(placeholder);
        nf.options.forEach(function(o) {{
          var opt = document.createElement('option');
          opt.value = o.id;
          opt.textContent = o.name;
          select.appendChild(opt);
        }});
        select.addEventListener('change', function() {{
          var extraFields = {{}};
          extraFields[nf.id] = {{id: select.value}};
          doTransition(zdrKey, td, data.transition_id, extraFields);
        }});
        wrap.appendChild(label);
        wrap.appendChild(select);
        td.innerHTML = '';
        td.appendChild(wrap);
        select.focus();
        return;
      }}
      if (data.error) {{
        td.innerHTML = '<span style="color:#C0392B;font-size:12px;">' + data.error + '</span>';
        return;
      }}
      td.innerHTML = '';
      td.appendChild(statusBadgeHtml(zdrKey, data.status));
    }})
    .catch(function(e) {{ td.innerHTML = '<span style="color:#C0392B;font-size:12px;">Update failed: ' + e + '</span>'; }});
}}
document.addEventListener('change', function(e) {{
  var el = e.target.closest('.zdr-status-select');
  if (!el) {{ return; }}
  doTransition(el.getAttribute('data-zdr-key'), el.parentElement, el.value, null);
}});
var RALLY_STATE_OPTIONS = {json.dumps(config.RALLY_STATE_VALUES)};
var RALLY_STATE_COLORS = {json.dumps(_STATE_DOT)};
function rallyStateBadgeHtml(rallyId, state) {{
  var color = RALLY_STATE_COLORS[state] || '#7f77dd';
  var span = document.createElement('span');
  span.className = 'badge rally-state-badge';
  span.style.background = color + '1a';
  span.style.color = color;
  span.setAttribute('data-rally-id', rallyId);
  span.title = 'Click to change state';
  span.textContent = state;
  return span;
}}
document.addEventListener('click', function(e) {{
  var el = e.target.closest('.rally-state-badge');
  if (!el) {{ return; }}
  var rallyId = el.getAttribute('data-rally-id');
  var currentState = el.textContent;
  var td = el.parentElement;
  var select = document.createElement('select');
  select.className = 'rally-state-select';
  select.setAttribute('data-rally-id', rallyId);
  RALLY_STATE_OPTIONS.forEach(function(s) {{
    var opt = document.createElement('option');
    opt.value = s;
    opt.textContent = s;
    if (s === currentState) {{ opt.selected = true; }}
    select.appendChild(opt);
  }});
  td.innerHTML = '';
  td.appendChild(select);
  select.focus();
}});
document.addEventListener('change', function(e) {{
  var el = e.target.closest('.rally-state-select');
  if (!el) {{ return; }}
  var rallyId = el.getAttribute('data-rally-id');
  var newState = el.value;
  var td = el.parentElement;
  td.innerHTML = '<span class="dim" style="font-size:12px;"><span class="spinner"></span>Updating...</span>';
  fetch('/api/rally/update-state/' + encodeURIComponent(rallyId), {{
    method: 'POST',
    headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify({{state: newState}}),
  }})
    .then(function(r) {{ return r.json(); }})
    .then(function(data) {{
      if (data.error) {{
        td.innerHTML = '<span style="color:#C0392B;font-size:12px;">' + data.error + '</span>';
        return;
      }}
      td.innerHTML = '';
      td.appendChild(rallyStateBadgeHtml(rallyId, data.state));
      var tr = td.closest('tr');
      if (tr && tr.classList.contains('matched-row')) {{
        if (data.state === 'Open') {{
          tr.classList.add('row-rally-open');
          tr.title = 'ZDR ticket exists, but Rally status is still Open';
        }} else {{
          tr.classList.remove('row-rally-open');
          tr.removeAttribute('title');
        }}
      }}
    }})
    .catch(function(e) {{ td.innerHTML = '<span style="color:#C0392B;font-size:12px;">Update failed: ' + e + '</span>'; }});
}});
function dateCellHtml(kind, key, value) {{
  var span = document.createElement('span');
  span.className = 'date-cell ' + kind + '-date-cell';
  span.setAttribute(kind === 'zdr' ? 'data-zdr-key' : 'data-rally-id', key);
  span.setAttribute('data-value', value || '');
  span.title = 'Click to edit';
  span.textContent = value ? value.slice(0, 10) : '-';
  return span;
}}
document.addEventListener('click', function(e) {{
  var el = e.target.closest('.zdr-date-cell, .rally-date-cell');
  if (!el) {{ return; }}
  var isZdr = el.classList.contains('zdr-date-cell');
  var kind = isZdr ? 'zdr' : 'rally';
  var key = isZdr ? el.getAttribute('data-zdr-key') : el.getAttribute('data-rally-id');
  var current = el.getAttribute('data-value') || '';
  var td = el.parentElement;
  var input = document.createElement('input');
  input.type = 'date';
  input.className = 'date-input';
  input.value = current;
  td.innerHTML = '';
  td.appendChild(input);
  input.focus();
  var committed = false;
  input.addEventListener('change', function() {{
    committed = true;
    var newVal = input.value;
    if (newVal === current) {{
      td.innerHTML = '';
      td.appendChild(dateCellHtml(kind, key, current));
      return;
    }}
    td.innerHTML = '<span class="dim" style="font-size:12px;"><span class="spinner"></span>Updating...</span>';
    var url = isZdr
      ? '/api/zdr/update-date/' + encodeURIComponent(key)
      : '/api/rally/update-date/' + encodeURIComponent(key);
    fetch(url, {{
      method: 'POST',
      headers: {{'Content-Type': 'application/json'}},
      body: JSON.stringify({{date: newVal}}),
    }})
      .then(function(r) {{ return r.json(); }})
      .then(function(data) {{
        if (data.error) {{
          td.innerHTML = '<span style="color:#C0392B;font-size:12px;">' + data.error + '</span>';
          return;
        }}
        td.innerHTML = '';
        td.appendChild(dateCellHtml(kind, key, data.date));
      }})
      .catch(function(e) {{ td.innerHTML = '<span style="color:#C0392B;font-size:12px;">Update failed: ' + e + '</span>'; }});
  }});
  input.addEventListener('blur', function() {{
    if (!committed) {{
      td.innerHTML = '';
      td.appendChild(dateCellHtml(kind, key, current));
    }}
  }});
}});
</script>
</body>
</html>"""
