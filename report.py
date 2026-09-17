import html
import json
import math
import re
from datetime import datetime
from urllib.parse import quote

from . import config
from .compare import _strip_prefix

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
_ZDR_OK_WHEN_RALLY_FIXED = {s.casefold() for s in (config.ZDR_JQL_EXCLUDED_STATUSES or (
    "Done",
    "Canceled",
    "Cancelled",
    "Pending Client Info",
    "Pending Client Sign Off",
    "PENDING APPROVAL TO CLOSE",
))}
_ZDR_OK_WHEN_RALLY_FIXED_LABEL = (
    "Done, Canceled, Cancelled, Pending Client Info, "
    "Pending Client Sign Off, or Pending Approval to Close"
)

_ICON_SVG = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2.35" '
    'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
    '<path d="M3 12a9 9 0 0 1 15-6.7L21 8"/><path d="M21 3v5h-5"/>'
    '<path d="M21 12a9 9 0 0 1-15 6.7L3 16"/><path d="M3 21v-5h5"/>'
    "</svg>"
)
_FAVICON_HREF = "/static/drc-mark.svg?v=1"


def _esc(value, limit=None):
    text = str(value) if value is not None else "-"
    if limit and len(text) > limit:
        text = text[: limit].rstrip() + "..."
    return html.escape(text)


_LOGO_IMG = '<img class="brand-logo" src="/static/zinnia-logo.png?v=2" alt="Zinnia">'
_REFRESH_ICON = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" '
    'stroke-linecap="round" stroke-linejoin="round" width="16" height="16" aria-hidden="true">'
    '<path d="M3 12a9 9 0 0 1 15-6.7L21 8"/><path d="M21 3v5h-5"/>'
    '<path d="M21 12a9 9 0 0 1-15 6.7L3 16"/><path d="M3 21v-5h5"/>'
    "</svg>"
)
_CHROME_CSS = """
.topbar{position:sticky;top:0;z-index:40;display:flex;justify-content:space-between;align-items:center;
  padding:14px 32px;background:#fff;border-bottom:1px solid #EFE7DC;box-shadow:0 1px 8px rgba(23,23,23,.04);}
.brand{display:flex;align-items:center;gap:16px;text-decoration:none;color:inherit;}
.brand-logo{height:42px;width:auto;display:block;}
.brand-rule{width:1px;height:28px;background:#E0D9D0;}
.brand-app{font-size:22px;font-weight:700;letter-spacing:.04em;color:#8A8680;}
.topbar-right{display:flex;align-items:center;gap:12px;}
.topbar-stamp{font-size:11px;color:#8A8680;text-align:right;line-height:1.35;margin:0;}
.icon-btn{width:36px;height:36px;border-radius:999px;border:1px solid #F3C7A4;background:#fff;color:#F46C00;
  display:inline-flex;align-items:center;justify-content:center;cursor:pointer;padding:0;}
.icon-btn:hover{background:#FFF4EB;}
.user-chip{display:inline-flex;align-items:center;gap:8px;border:1px solid #F3C7A4;border-radius:999px;
  padding:4px 8px 4px 12px;font-size:13px;font-weight:500;color:#171717;text-decoration:none;background:#fff;}
.user-chip:hover{background:#FFF4EB;text-decoration:none;}
.user-avatar{width:26px;height:26px;border-radius:50%;background:#FDE8D8;color:#F46C00;
  display:inline-flex;align-items:center;justify-content:center;font-size:10px;font-weight:700;}
.page{padding:28px 40px 40px;max-width:1440px;margin:0 auto;}
.site-footer{display:flex;justify-content:space-between;align-items:center;gap:16px;padding:14px 32px;
  background:#fff;border-top:1px solid #EFE7DC;font-size:16px;font-weight:500;color:#8A8680;margin-top:auto;}
.login-page{min-height:calc(100vh - 120px);display:flex;align-items:center;justify-content:center;padding:2rem;}
.app-lockup{display:flex;align-items:center;gap:16px;min-width:0;}
.app-mark{width:56px;height:56px;border-radius:16px;flex-shrink:0;
  background:linear-gradient(145deg,#FF8F3D,#F46C00);
  box-shadow:0 8px 22px rgba(244,108,0,.32);
  display:inline-flex;align-items:center;justify-content:center;}
.app-mark svg{width:28px;height:28px;display:block;}
.app-lockup-text{min-width:0;}
.app-lockup-title{font-size:28px;font-weight:800;letter-spacing:-.03em;color:#171717;margin:0;line-height:1.15;}
.app-lockup-sub{margin:6px 0 0;font-size:15px;font-weight:600;line-height:1.35;white-space:nowrap;}
.app-lockup-sub .accent{color:#F46C00;}
.app-lockup-sub .arrow{color:#F46C00;padding:0 6px;font-weight:700;}
.app-lockup-sub .dim{color:#8A8F93;font-weight:600;}
.busy-card{position:relative;}
.busy-overlay{display:none;position:absolute;inset:0;background:rgba(255,255,255,.88);border-radius:14px;
  flex-direction:column;align-items:center;justify-content:center;gap:12px;z-index:5;text-align:center;padding:24px;}
.busy-card.is-busy .busy-overlay{display:flex;}
.busy-card.is-busy .submit{opacity:.7;cursor:wait;}
.spinner{width:28px;height:28px;border:3px solid #F3C7A4;border-top-color:#F46C00;border-radius:50%;
  animation:drc-spin .7s linear infinite;}
@keyframes drc-spin{to{transform:rotate(360deg);}}
.busy-copy{margin:0;font-size:14px;font-weight:600;color:#171717;}
.busy-sub{margin:0;font-size:12px;color:#6B6F73;line-height:1.45;max-width:280px;}
"""


def _display_user_name():
    email = (config.current_credentials().get("ZDR_JIRA_EMAIL") or "").strip()
    local = email.split("@")[0] if email else ""
    if not local:
        return "DRC User"
    return " ".join(part.capitalize() for part in local.replace(".", " ").replace("_", " ").split())


def _user_initials(name):
    parts = [p for p in (name or "").split() if p]
    if len(parts) >= 2:
        return (parts[0][0] + parts[-1][0]).upper()
    return (name[:2] or "DR").upper()


def _brand_html():
    return f"""<a class="brand" href="/">
    {_LOGO_IMG}
    <span class="brand-rule"></span>
    <span class="brand-app">DRC</span>
  </a>"""


def _topbar_html(show_logout=False):
    user = ""
    if show_logout:
        name = _display_user_name()
        user = (
            f'<a class="user-chip" href="/logout" title="Log out">'
            f"{_esc(name)}<span class=\"user-avatar\">{_esc(_user_initials(name))}</span></a>"
        )
    return f"""<header class="topbar">
  {_brand_html()}
  <div class="topbar-right">{user}</div>
</header>"""


def _footer_html():
    return f"""<footer class="site-footer">
  {_brand_html()}
  <span>Zinnia internal · Defect ReConciler (DRC)</span>
</footer>"""


def _app_lockup_html():
    return f"""<div class="app-lockup">
  <div class="app-mark">{_ICON_SVG}</div>
  <div class="app-lockup-text">
    <h1 class="app-lockup-title">Defect ReConciler (DRC)</h1>
    <p class="app-lockup-sub"><span class="accent">Zinnia Defect Management (ZDR)</span><span class="arrow">&harr;</span><span class="accent">External Defect Management</span><span class="dim"> (Rally)</span></p>
  </div>
</div>"""


def _coverage_donut_html(matched_n, total):
    radius = 54
    circ = 2 * math.pi * radius
    ratio = (matched_n / total) if total else 0
    green_len = circ * ratio
    pct = f"{ratio * 100:.1f}%"
    track = "#E03131" if total else "#E7E3DC"
    return (
        f'<div class="donut-wrap">'
        f'<svg viewBox="0 0 160 160" aria-hidden="true">'
        f'<circle cx="80" cy="80" r="{radius}" fill="none" stroke="{track}" stroke-width="18"/>'
        f'<circle cx="80" cy="80" r="{radius}" fill="none" stroke="#2F9E44" stroke-width="18" '
        f'stroke-dasharray="{green_len:.2f} {circ:.2f}" transform="rotate(-90 80 80)"/>'
        f"</svg>"
        f'<div class="donut-center"><div class="donut-pct">{pct}</div>'
        f'<div class="donut-caption">Match coverage</div></div></div>'
    )


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


def _status_discrepancy(rally_state, zdr_status):
    """Return (css_class, title) when Rally/ZDR statuses disagree, else ('', '')."""
    state = (rally_state or "").strip()
    zdr = (zdr_status or "").strip()
    if state == "Open":
        return (
            "row-rally-open",
            "ZDR ticket exists, but Rally status is still Open",
        )
    if state == "Fixed" and zdr.casefold() not in _ZDR_OK_WHEN_RALLY_FIXED:
        return (
            "row-status-mismatch",
            "Discrepancy: Rally status is Fixed, but ZDR status is "
            f"{zdr or '-'}. ZDR should be {_ZDR_OK_WHEN_RALLY_FIXED_LABEL}.",
        )
    return "", ""


def _rally_link(rally):
    m = _RALLY_OBJECT_ID_RE.search(rally.get("ref") or "")
    rally_id = _esc(rally["id"])
    if not m:
        return rally_id
    url = f"{config.RALLY_BASE_URL}/#/detail/defect/{m.group(1)}"
    return f'<a href="{url}">{rally_id}</a>'


def _rally_href(rally_id, rally_ref=""):
    match = _RALLY_OBJECT_ID_RE.search(rally_ref or "")
    base = config.RALLY_BASE_URL.rstrip("/")
    if match:
        return f"{base}/#/detail/defect/{match.group(1)}"
    if rally_id:
        return f"{base}/#/search?keywords={quote(str(rally_id))}"
    return ""


def _zdr_href(zdr_key):
    if not zdr_key:
        return ""
    return f"https://{config.ZDR_SITE}/browse/{quote(str(zdr_key), safe='-')}"


def _blank_link(href, label):
    text = _esc(label)
    if not href or not label:
        return text or "—"
    return (
        f'<a href="{html.escape(href, quote=True)}" target="_blank" rel="noopener">{text}</a>'
    )


def created_ticket_notice(zdr_key, rally_id, attached="0", extra_error=""):
    zdr_link = _blank_link(_zdr_href(zdr_key), zdr_key)
    rally_link = _blank_link(_rally_href(rally_id), rally_id)
    message = (
        f"Created ZDR ticket {zdr_link} for Rally defect {rally_link} "
        f"({_esc(attached)} attachment(s) copied)."
    )
    if extra_error:
        message += " " + _esc(extra_error)
    return ("success", message, "html")


def created_all_notice(created_n, failed_n, ids="", extra_error=""):
    pairs = []
    for part in (ids or "").split(","):
        part = part.strip()
        if "→" not in part:
            if part:
                pairs.append(_esc(part))
            continue
        rally_id, zdr_key = [piece.strip() for piece in part.split("→", 1)]
        pairs.append(
            f"{_blank_link(_rally_href(rally_id), rally_id)}→{_blank_link(_zdr_href(zdr_key), zdr_key)}"
        )
    message = f"Created {_esc(created_n)} ZDR ticket(s)"
    if pairs:
        message += " (" + ", ".join(pairs) + ")"
    message += "."
    if extra_error:
        message += " " + _esc(extra_error)
    kind = "error" if str(failed_n) not in ("", "0") else "success"
    return (kind, message, "html")


def _open_count_discrepancies(rally_defects, zdr_open, result):
    """Rally-open vs ZDR-open count gaps (not the same as matched/missing)."""
    rally_defects = rally_defects or []
    zdr_open = zdr_open or []
    rally_ids = {d["id"] for d in rally_defects}
    open_zdr_by_rally = {}
    extras = []
    for issue in zdr_open:
        rid = _strip_prefix(issue.get("rally_id") or "")
        if rid and rid in rally_ids:
            open_zdr_by_rally.setdefault(rid, []).append(issue)
        else:
            extras.append(issue)

    matched_by_id = {m["rally"]["id"]: m for m in (result or {}).get("matched") or []}
    items = []
    for defect in rally_defects:
        if defect["id"] in open_zdr_by_rally:
            continue
        match = matched_by_id.get(defect["id"])
        items.append(
            {
                "kind": "matched_not_open" if match else "missing",
                "rally": defect,
                "zdr": (match["zdr"] if match else []),
            }
        )
    for issue in extras:
        items.append(
            {
                "kind": "extra_zdr",
                "rally": {
                    "id": _strip_prefix(issue.get("rally_id") or "") or "",
                    "ref": "",
                },
                "zdr": [issue],
            }
        )
    return items


def _discrepancy_item_html(item):
    rally = item.get("rally") or {}
    zdr_list = item.get("zdr") or []
    rally_link = _blank_link(_rally_href(rally.get("id"), rally.get("ref")), rally.get("id"))
    zdr_links = [
        _blank_link(_zdr_href(z.get("key")), z.get("key"))
        for z in zdr_list
        if z.get("key")
    ]
    zdr_joined = ", ".join(zdr_links) if zdr_links else "no ZDR ticket"
    state = rally.get("state") or "—"
    owner = rally.get("owner") or ""
    severity = rally.get("severity") or ""
    zdr_status_names = ", ".join(
        dict.fromkeys((z.get("status") or "—") for z in zdr_list)
    ) or "—"
    kind = item.get("kind")
    if kind == "missing":
        label = "Missing ZDR"
        meta_parts = [rally_link, _esc(state)]
        if severity:
            meta_parts.append(_esc(severity))
        if owner:
            meta_parts.append(_esc(owner))
        body = (
            "This Rally defect has no matching ZDR ticket, so it counts in Rally Open "
            "but not in ZDR Open."
        )
    elif kind == "matched_not_open":
        label = zdr_status_names
        meta_parts = [rally_link, zdr_joined]
        if owner:
            meta_parts.append(_esc(owner))
        body = (
            f"Rally is still {_esc(state)}. ZDR status is {_esc(zdr_status_names)}, "
            "which is excluded from the ZDR Open count."
        )
    else:
        label = "ZDR only"
        zdr_status = (zdr_list[0].get("status") if zdr_list else None) or "—"
        meta_parts = [zdr_joined]
        if rally.get("id"):
            meta_parts.append(rally_link)
        body = (
            f"ZDR is {_esc(zdr_status)}, so it counts in ZDR Open. "
            "The linked Rally defect is not in Rally Open (Closed, or owner outside "
            "the DRC owner filter)."
            if rally.get("id")
            else f"ZDR is {_esc(zdr_status)}, so it counts in ZDR Open. It is not linked "
            "to a Rally defect in the Rally Open list."
        )
    meta = " · ".join(p for p in meta_parts if p)
    return (
        f'<div class="ct-block">'
        f'<div class="ct-label">{_esc(label)}</div>'
        f'<div class="ct-meta">{meta}</div>'
        f'<div class="ct-body">{body}</div>'
        f"</div>"
    )


def _discrepancies_modal_html(rally_count, zdr_count, items):
    if rally_count == zdr_count and not items:
        return "", ""
    rows = "".join(_discrepancy_item_html(item) for item in items) or (
        '<div class="ct-block"><div class="ct-body">The Rally Open and ZDR Open counts '
        "differ, but no individual tickets could be listed.</div></div>"
    )
    link = (
        '<p class="dash-stat-hint">'
        '<a class="disc-open-link" href="#open-discrepancies">Discrepancies</a>'
        "</p>"
    )
    modal = f"""<div class="disc-pop disc-pop-right" id="open-discrepancies" hidden>
  <span class="disc-pop-caret" aria-hidden="true"></span>
  <div class="disc-pop-head">
    <div class="ct-label">Discrepancies</div>
    <div class="ct-meta">Rally Open {rally_count} · ZDR Open {zdr_count}</div>
  </div>
  <div class="disc-pop-scroll">{rows}</div>
</div>"""
    return link, modal


def _missing_row(d, enable_actions, created_map):
    action_cell = ""
    if enable_actions:
        created_key = created_map.get(d["id"]) if created_map else None
        if created_key:
            action_cell = f"""<td class="nowrap"><a href="https://{config.ZDR_SITE}/browse/{_esc(created_key)}" style="color:#2F855A;">Created {_esc(created_key)}</a></td>"""
        else:
            action_cell = f"""<td class="nowrap"><form method="post" action="/create-zdr/{_esc(d['id'])}" class="create-zdr-form" data-rally-id="{_esc(d['id'])}" style="margin:0;"><button type="submit" class="link-btn action-link">Create ZDR</button></form></td>"""
    created = (d.get("created") or "")[:10]
    dot = _dot(_STATE_DOT.get(d["state"], "#7f77dd"))
    state_cell = _editable_state_badge(d["id"], d["state"]) if enable_actions else _state_badge(d["state"])
    return f"""<tr>
{action_cell}
<td class="mono nowrap">{dot}{_rally_link(d)}</td>
<td>{state_cell}</td>
<td>{_severity_badge(d['severity'])}</td>
<td class="nowrap" title="{_esc(d['owner'])}">{_esc(d['owner'])}</td>
<td class="nowrap">{_esc(created)}</td>
<td class="dim ell" title="{_esc(d['name'])}">{_esc(d['name'], 100)}</td>
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
    extra, msg = _status_discrepancy(rally.get("state"), status)
    if extra:
        row_class += f" {extra}"
    row_title = f' title="{_esc(msg)}"' if msg else ""
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
            action_inner = f"""<form method="post" action="/create-zdr/{_esc(rally['id'])}" class="create-zdr-form" data-rally-id="{_esc(rally['id'])}" style="margin:0;"><button type="submit" class="link-btn action-link">Create ZDR</button></form>"""
    action_cell = f'<td class="nowrap">{action_inner}</td>' if enable_actions else ""
    state_cell = _editable_state_badge(rally["id"], rally["state"]) if enable_actions else _state_badge(rally["state"])
    extra, msg = ("", "")
    if zdr_list:
        extra, msg = _status_discrepancy(rally.get("state"), zdr_list[0].get("status"))
    row_class = " ".join(c for c in ("status-row", extra) if c)
    row_title = f' title="{_esc(msg)}"' if msg else ""
    class_attr = f' class="{row_class}"' if row_class else ""
    return f"""<tr{class_attr}{row_title}>
{action_cell}
<td class="mono nowrap">{_dot(dot_color)}{_rally_link(rally)}</td>
<td>{state_cell}</td>
<td>{_severity_badge(rally['severity'])}</td>
<td class="nowrap" title="{_esc(rally['owner'])}">{_esc(rally['owner'])}</td>
<td class="mono nowrap">{zdr_key_cell}</td>
<td>{zdr_status_cell}</td>
<td class="dim ell" title="{_esc(rally['name'])}">{_esc(rally['name'], 100)}</td>
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
<link rel="icon" type="image/svg+xml" href="{_FAVICON_HREF}">
<style>
* {{ box-sizing:border-box; }}
body {{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#FAFAFA;color:{_TEXT};margin:0;min-height:100vh;display:flex;flex-direction:column;}}
.login-wrap {{width:100%;max-width:720px;text-align:center;}}
.login-wrap .app-lockup {{justify-content:center;margin:0 auto 28px;text-align:left;}}
.card {{background:#fff;border:1px solid {_BORDER};border-radius:14px;padding:2rem 1.75rem;box-shadow:0 1px 2px rgba(23,23,23,0.04);text-align:left;max-width:380px;width:100%;margin:0 auto;}}
.card h2 {{font-size:17px;font-weight:600;margin:0 0 4px;text-align:center;}}
.card p.sub {{font-size:13px;color:{_TEXT_DIM};margin:0 0 22px;text-align:center;}}
label {{display:block;font-size:12px;font-weight:600;color:{_TEXT_DIM};margin-bottom:6px;}}
input[type=password] {{width:100%;padding:10px 12px;border:1px solid {_BORDER};border-radius:8px;font-size:14px;margin-bottom:16px;}}
input[type=password]:focus {{outline:none;border-color:{_ORANGE};}}
.remember {{display:flex;align-items:center;gap:8px;font-size:13px;color:{_TEXT_DIM};margin-bottom:20px;}}
button.submit {{width:100%;border:none;border-radius:999px;background:{_ORANGE};color:#fff;padding:11px 20px;font-size:14px;font-weight:600;cursor:pointer;display:inline-flex;align-items:center;justify-content:center;gap:8px;}}
button.submit:hover {{background:#DE6300;}}
button.submit:disabled {{background:#F46C00;cursor:wait;}}
{_CHROME_CSS}
</style>
</head>
<body>
{_topbar_html()}
<div class="login-page">
<div class="login-wrap">
  {_app_lockup_html()}
  <div class="card busy-card" id="login-card">
    <h2>Welcome back</h2>
    <p class="sub">Enter the shared team password to continue</p>
    {error_html}
    <form method="post" action="/login" id="login-form">
      <label for="password">Password</label>
      <input type="password" id="password" name="password" autofocus required>
      <label class="remember"><input type="checkbox" name="remember" value="1" style="width:auto;margin:0;"> Remember me</label>
      <button type="submit" class="submit" id="login-submit">Log In</button>
    </form>
    <div class="busy-overlay" id="login-busy" role="status" aria-live="polite" aria-hidden="true">
      <div class="spinner" aria-hidden="true"></div>
      <p class="busy-copy">Signing in…</p>
      <p class="busy-sub">Please wait while DRC opens the dashboard.</p>
    </div>
  </div>
</div>
</div>
{_footer_html()}
<script>
document.getElementById('login-form').addEventListener('submit', function() {{
  var card = document.getElementById('login-card');
  var overlay = document.getElementById('login-busy');
  var btn = document.getElementById('login-submit');
  card.classList.add('is-busy');
  overlay.setAttribute('aria-hidden', 'false');
  btn.disabled = true;
  btn.textContent = 'Signing in…';
}});
</script>
</body>
</html>"""


def build_connecting_html():
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Loading DRC…</title>
<link rel="icon" type="image/svg+xml" href="{_FAVICON_HREF}">
<meta http-equiv="refresh" content="0;url=/">
<style>
* {{ box-sizing:border-box; }}
body {{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#FAFAFA;color:{_TEXT};margin:0;min-height:100vh;display:flex;flex-direction:column;}}
.login-wrap {{width:100%;max-width:720px;text-align:center;}}
.login-wrap .app-lockup {{justify-content:center;margin:0 auto 28px;text-align:left;}}
.card {{background:#fff;border:1px solid {_BORDER};border-radius:14px;padding:2.25rem 1.75rem;box-shadow:0 1px 2px rgba(23,23,23,0.04);text-align:center;max-width:380px;width:100%;margin:0 auto;}}
{_CHROME_CSS}
</style>
</head>
<body>
{_topbar_html()}
<div class="login-page">
<div class="login-wrap">
  {_app_lockup_html()}
  <div class="card" role="status" aria-live="polite">
    <div class="spinner" aria-hidden="true" style="margin:0 auto 14px;"></div>
    <p class="busy-copy">Loading dashboard…</p>
    <p class="busy-sub" style="margin:8px auto 0;">Fetching open defects from Rally and ZDR. This can take a few seconds.</p>
  </div>
</div>
</div>
{_footer_html()}
<script>window.location.replace('/');</script>
</body>
</html>"""


def _secret_field_html(field_id, name, label, placeholder, required, autofocus=False):
    eye_open = (
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
        '<path d="M1 12s4-7 11-7 11 7 11 7-4 7-11 7S1 12 1 12z"/>'
        '<circle cx="12" cy="12" r="3"/></svg>'
    )
    eye_shut = (
        '<svg class="eye-off" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
        '<path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94"/>'
        '<path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19"/>'
        '<path d="M14.12 14.12a3 3 0 1 1-4.24-4.24"/>'
        '<line x1="1" y1="1" x2="23" y2="23"/></svg>'
    )
    req = " required" if required else ""
    focus = " autofocus" if autofocus else ""
    return f"""      <label for="{field_id}">{_esc(label)}</label>
      <div class="secret-field">
        <input type="password" id="{field_id}" name="{name}" spellcheck="false" autocapitalize="off" autocomplete="new-password" placeholder="{_esc(placeholder)}"{req}{focus}>
        <button type="button" class="secret-toggle" data-target="{field_id}" data-label="{_esc(label)}" aria-label="Show {_esc(label)}" aria-pressed="false">{eye_open}{eye_shut}</button>
      </div>"""


def build_rally_session_html(error=None, jira_email="", has_rally=False, has_jira_token=False):
    error_html = (
        f'<p style="color:#C0392B;font-size:13px;font-weight:500;margin:0 0 16px;text-align:center;">{_esc(error)}</p>'
        if error
        else ""
    )
    keep = "Leave blank to keep the current value"
    rally_placeholder = keep if has_rally else ""
    token_placeholder = keep if has_jira_token else ""
    email_value = _esc(jira_email)
    email_required = " required" if not jira_email else ""
    body = f"""<h2>Session credentials</h2>
    <p class="sub">Enter Rally session cookies and ZDR Jira credentials for your session. DRC updates environment variables and uses them for Rally and ZDR calls.</p>
    {error_html}
    <form method="post" action="/rally-session" autocomplete="off" id="session-form">
      <p class="section-label">Rally</p>
{_secret_field_html("zsessionid", "zsessionid", "ZSESSIONID", rally_placeholder, not has_rally, autofocus=True)}
{_secret_field_html("jsessionid", "jsessionid", "JSESSIONID", rally_placeholder, not has_rally)}
      <p class="hint">Chrome: DevTools → Application → Cookies → your Rally domain. Copy the cookie <strong>values</strong>, not the names.</p>
      <p class="section-label">ZDR Jira</p>
      <label for="jira_email">ZDR Jira email</label>
      <div class="plain-field">
        <input type="email" id="jira_email" name="jira_email" spellcheck="false" autocapitalize="off" autocomplete="off" value="{email_value}" placeholder="you@zinnia.com"{email_required}>
      </div>
{_secret_field_html("jira_api_token", "jira_api_token", "ZDR Jira API token", token_placeholder, not has_jira_token)}
      <p class="hint">Create an API token at <strong>id.atlassian.com</strong> → Security → API tokens. Use your Zinnia Atlassian email, not your password.</p>
      <button type="submit" class="submit" id="session-submit">Save session credentials</button>
    </form>
    <div class="busy-overlay" id="session-busy" role="status" aria-live="polite" aria-hidden="true">
      <div class="spinner" aria-hidden="true"></div>
      <p class="busy-copy">Signing in…</p>
      <p class="busy-sub">Saving credentials and opening the dashboard.</p>
    </div>
    <script>
    document.querySelectorAll('.secret-toggle').forEach(function(btn) {{
      btn.addEventListener('click', function() {{
        var input = document.getElementById(btn.getAttribute('data-target'));
        var show = input.type === 'password';
        var label = btn.getAttribute('data-label') || btn.getAttribute('data-target');
        input.type = show ? 'text' : 'password';
        btn.setAttribute('aria-pressed', show ? 'true' : 'false');
        btn.setAttribute('aria-label', (show ? 'Hide ' : 'Show ') + label);
        btn.classList.toggle('is-visible', show);
      }});
    }});
    document.getElementById('session-form').addEventListener('submit', function() {{
      var card = document.getElementById('session-card');
      var overlay = document.getElementById('session-busy');
      var btn = document.getElementById('session-submit');
      card.classList.add('is-busy');
      overlay.setAttribute('aria-hidden', 'false');
      btn.disabled = true;
      btn.textContent = 'Signing in…';
    }});
    </script>"""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Defect ReConciler (DRC)</title>
<link rel="icon" type="image/svg+xml" href="{_FAVICON_HREF}">
<style>
* {{ box-sizing:border-box; }}
body {{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#FAFAFA;color:{_TEXT};margin:0;min-height:100vh;display:flex;flex-direction:column;}}
.login-wrap {{width:100%;max-width:720px;text-align:center;}}
.login-wrap .app-lockup {{justify-content:center;margin:0 auto 28px;text-align:left;}}
.card {{background:#fff;border:1px solid {_BORDER};border-radius:14px;padding:2rem 1.75rem;box-shadow:0 1px 2px rgba(23,23,23,0.04);text-align:left;max-width:520px;width:100%;margin:0 auto;}}
.card h2 {{font-size:17px;font-weight:600;margin:0 0 4px;text-align:center;}}
.card p.sub {{font-size:13px;color:{_TEXT_DIM};margin:0 0 22px;text-align:center;line-height:1.45;}}
.card p.hint {{font-size:12px;color:{_TEXT_DIM};margin:0 0 18px;line-height:1.45;}}
.card p.section-label {{font-size:13px;font-weight:700;color:{_TEXT};margin:4px 0 10px;padding-top:8px;border-top:1px solid {_BORDER};}}
.card p.section-label:first-of-type {{border-top:none;padding-top:0;margin-top:0;}}
.card .mono {{font-family:ui-monospace,monospace;font-size:12px;}}
label {{display:block;font-size:12px;font-weight:600;color:{_TEXT_DIM};margin-bottom:6px;}}
.plain-field {{margin-bottom:14px;}}
.plain-field input {{width:100%;padding:10px 12px;border:1px solid {_BORDER};border-radius:8px;font-size:13px;}}
.plain-field input:focus {{outline:none;border-color:{_ORANGE};}}
.secret-field {{position:relative;margin-bottom:14px;}}
.secret-field input {{width:100%;padding:10px 42px 10px 12px;border:1px solid {_BORDER};border-radius:8px;font-size:13px;font-family:ui-monospace,monospace;}}
.secret-field input:focus {{outline:none;border-color:{_ORANGE};}}
.secret-toggle {{position:absolute;right:8px;top:50%;transform:translateY(-50%);border:none;background:transparent;color:{_TEXT_DIM};width:28px;height:28px;padding:4px;cursor:pointer;display:inline-flex;align-items:center;justify-content:center;}}
.secret-toggle:hover {{color:{_TEXT};}}
.secret-toggle svg {{width:18px;height:18px;display:block;}}
.secret-toggle .eye-off {{display:none;}}
.secret-toggle.is-visible .eye-off {{display:block;}}
.secret-toggle.is-visible svg:first-child {{display:none;}}
button.submit {{width:100%;border:none;border-radius:999px;background:{_ORANGE};color:#fff;padding:11px 20px;font-size:14px;font-weight:600;cursor:pointer;}}
button.submit:hover {{background:#DE6300;}}
button.submit:disabled {{background:#F46C00;cursor:wait;}}
{_CHROME_CSS}
</style>
</head>
<body>
{_topbar_html()}
<div class="login-page">
<div class="login-wrap">
  {_app_lockup_html()}
  <div class="card busy-card" id="session-card">
    {body}
  </div>
</div>
</div>
{_footer_html()}
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
    rally_defects=None,
    zdr_open=None,
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
    donut_html = _coverage_donut_html(matched_n, rally_count)
    missing_stat_class = "dash-stat dash-stat-alert" if missing_n else "dash-stat"
    now = datetime.now()
    updated_date = now.strftime("%Y-%m-%d")
    updated_time = now.strftime("%H:%M:%S")
    topbar = _topbar_html(show_logout=show_logout)
    refresh_block = ""
    if refresh_url:
        refresh_block = f"""<div class="page-refresh">
  <button class="cta" type="button" id="refresh-btn" data-url="{refresh_url}">
    <span class="cta-refresh-icon">{_REFRESH_ICON}</span>
    <span class="refresh-spinner" aria-hidden="true"></span>
    <span class="cta-refresh-label">Refresh</span>
  </button>
  <p class="refresh-stamp">Last updated {updated_date}<br>{updated_time}</p>
</div>"""
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
            '<button type="submit" class="link-btn action-link" '
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
    notice_html = '<p class="notify-empty">No refresh or sync notifications yet.</p>'
    if notice:
        kind, message = notice[0], notice[1]
        is_html = len(notice) > 2 and notice[2] == "html"
        color = "#2F855A" if kind == "success" else "#C0392B"
        body = message if is_html else _esc(message)
        notice_html = f'<div class="notice" style="border-color:{color};color:{color};">{body}</div>'
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
    disc_items = _open_count_discrepancies(rally_defects, zdr_open, result)
    disc_link, disc_modal = _discrepancies_modal_html(rally_count, zdr_count, disc_items)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Defect ReConciler (DRC)</title>
<link rel="icon" type="image/svg+xml" href="{_FAVICON_HREF}">
<style>
* {{ box-sizing:border-box; }}
body {{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#FAFAFA;color:{_TEXT};margin:0;min-height:100vh;display:flex;flex-direction:column;}}
{_CHROME_CSS}
.page-intro {{display:flex;justify-content:space-between;align-items:center;gap:24px;margin:0 0 1.5rem;}}
.page-refresh {{display:flex;flex-direction:column;align-items:center;flex-shrink:0;}}
.refresh-stamp {{font-size:12px;color:{_TEXT_DIM};margin:8px 0 0;text-align:center;line-height:1.4;}}
h2 {{font-size:15px;font-weight:600;margin:0 0 4px;color:{_TEXT};}}
.section {{margin-bottom:1.75rem;}}
.dashboard-box {{background:#FAF8F5;border:1px solid {_BORDER};border-radius:12px;padding:1.35rem 1.5rem 1.5rem;margin-bottom:0;box-shadow:0 1px 2px rgba(23,23,23,0.04);min-width:0;}}
.dashboard-title {{font-size:20px;font-weight:600;margin:0 0 1.15rem;padding-bottom:0.85rem;border-bottom:1px solid {_BORDER};letter-spacing:-.01em;}}
.dashboard-box .section {{margin-bottom:1.25rem;}}
.dashboard-box .section:last-child {{margin-bottom:0;}}
.overview-row {{display:grid;grid-template-columns:minmax(0,1.9fr) minmax(300px,.9fr);gap:16px;align-items:stretch;}}
.notify-box {{background:#FAF8F5;border:1px solid {_BORDER};border-radius:12px;padding:1.35rem 1.5rem 1.5rem;box-shadow:0 1px 2px rgba(23,23,23,0.04);display:flex;flex-direction:column;min-width:0;min-height:0;}}
.notify-body {{flex:1;background:#fff;border:1px solid {_BORDER};border-radius:16px;padding:1.15rem 1.25rem;overflow-y:auto;min-height:220px;}}
.notify-empty {{margin:0;font-size:13px;color:{_TEXT_DIM};font-weight:500;}}
.dash-grid {{display:grid;grid-template-columns:minmax(180px,0.9fr) minmax(0,1.35fr);gap:16px;align-items:stretch;}}
.donut-card,.dash-stat {{background:#fff;border:1px solid {_BORDER};border-radius:16px;box-shadow:0 1px 2px rgba(23,23,23,0.04);}}
.donut-card {{display:flex;align-items:center;justify-content:center;padding:1.25rem;min-height:260px;}}
.donut-wrap {{position:relative;width:210px;height:210px;}}
.donut-wrap svg {{width:100%;height:100%;display:block;}}
.donut-center {{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;pointer-events:none;}}
.donut-pct {{font-size:32px;font-weight:800;letter-spacing:-.03em;color:{_TEXT};line-height:1;}}
.donut-caption {{font-size:13px;color:{_TEXT_DIM};margin-top:6px;font-weight:500;}}
.dash-metrics {{display:grid;grid-template-columns:1fr 1fr;gap:16px;}}
.dash-stat {{padding:1.25rem 1.35rem;display:flex;flex-direction:column;justify-content:center;min-height:122px;}}
.dash-stat-label {{font-size:11px;font-weight:700;letter-spacing:.04em;text-transform:uppercase;color:{_TEXT_DIM};margin:0 0 10px;line-height:1.35;}}
.dash-stat-value {{font-size:36px;font-weight:700;margin:0;line-height:1;letter-spacing:-.03em;}}
.dash-stat-hint {{font-size:13px;color:{_TEXT_DIM};margin:8px 0 0;}}
.dash-stat-alert {{background:#FDECEC;border-color:#F3C4C4;}}
.dash-stat-label .metric-filter-link {{float:right;font-size:12px;letter-spacing:0;font-weight:500;text-transform:none;}}
.disc-open-link {{color:{_ORANGE};font-size:12px;font-weight:500;}}
.disc-pop {{position:absolute;z-index:80;width:460px;max-width:calc(100vw - 24px);display:block;background:#fff;color:{_TEXT};border:1px solid {_BORDER};border-radius:12px;box-shadow:0 8px 24px rgba(23,23,23,.14);overflow:visible;font-size:13px;line-height:1.5;}}
.disc-pop[hidden] {{display:none !important;}}
.disc-pop-caret {{position:absolute;width:0;height:0;border:7px solid transparent;}}
.disc-pop-right .disc-pop-caret {{left:-7px;top:var(--caret-top,18px);border-right-color:{_ORANGE};border-left-width:0;}}
.disc-pop-below .disc-pop-caret {{top:-7px;left:var(--caret-left,28px);border-bottom-color:{_ORANGE};border-top-width:0;}}
.disc-pop .ct-block {{padding:10px 14px;white-space:normal;overflow-wrap:break-word;word-break:normal;}}
.disc-pop .ct-block + .ct-block {{border-top:1px solid {_BORDER};}}
.disc-pop .ct-label {{color:{_ORANGE};font-size:13px;font-weight:600;letter-spacing:.04em;text-transform:uppercase;margin-bottom:4px;}}
.disc-pop .ct-meta {{color:{_TEXT_DIM};font-size:13px;margin-bottom:4px;}}
.disc-pop .ct-body {{color:{_TEXT};font-size:13px;white-space:normal;overflow-wrap:break-word;word-break:normal;}}
.disc-pop .ct-meta a {{white-space:nowrap;color:{_ORANGE};}}
.disc-pop-head {{background:{_ORANGE};color:#fff;padding:10px 14px;border-radius:11px 11px 0 0;}}
.disc-pop-head .ct-label {{color:#fff;font-size:13px;font-weight:700;letter-spacing:.04em;text-transform:uppercase;margin:0 0 3px;}}
.disc-pop-head .ct-meta {{color:rgba(255,255,255,.9);font-size:13px;margin:0;}}
.disc-pop-scroll {{max-height:260px;overflow-y:auto;overflow-x:hidden;background:#fff;border-radius:0 0 11px 11px;scrollbar-gutter:stable;scrollbar-width:thin;scrollbar-color:#C7C1B5 #EFEBE4;}}
.disc-pop-scroll::-webkit-scrollbar {{width:10px;}}
.disc-pop-scroll::-webkit-scrollbar-track {{background:#EFEBE4;}}
.disc-pop-scroll::-webkit-scrollbar-thumb {{background:#C7C1B5;border-radius:8px;border:2px solid #EFEBE4;}}
.disc-pop-scroll::-webkit-scrollbar-thumb:hover {{background:#A8A296;}}
@media (max-width: 1100px) {{
  .overview-row {{grid-template-columns:1fr;}}
}}
@media (max-width: 900px) {{
  .dash-grid {{grid-template-columns:1fr;}}
}}
.section-split {{border:0;border-top:1px solid {_BORDER};margin:1.75rem 0;}}
.filters-box {{background:#FAF8F5;border:1px solid {_BORDER};border-radius:12px;padding:1.35rem 1.5rem 1.5rem;margin-bottom:1.75rem;box-shadow:0 1px 2px rgba(23,23,23,0.04);}}
.filters-title {{font-size:20px;font-weight:600;margin:0 0 0.35rem;letter-spacing:-.01em;}}
.filters-sub {{font-size:13px;color:{_TEXT_DIM};margin:0 0 1.15rem;padding-bottom:0.85rem;border-bottom:1px solid {_BORDER};}}
.filter-tabs {{margin:0 0 1rem;}}
.metrics {{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:14px;}}
.metric {{background:#fff;border-radius:12px;padding:1.1rem 1.25rem;border:1px solid {_BORDER};border-top:3px solid var(--accent, {_ORANGE});box-shadow:0 1px 2px rgba(23,23,23,0.04);}}
.metric p:first-child {{font-size:11px;font-weight:600;letter-spacing:.04em;text-transform:uppercase;color:{_TEXT_DIM};margin:0 0 6px;}}
.metric p:last-child {{font-size:26px;font-weight:600;margin:0;color:{_TEXT};}}
.tab-btn {{border:1px solid {_BORDER};border-radius:999px;background:#fff;padding:7px 16px;font-size:13px;font-weight:500;cursor:pointer;margin-right:8px;color:{_TEXT_DIM};}}
.tab-btn.active {{background:{_ORANGE};border-color:{_ORANGE};color:#fff;}}
.cta {{border:none;border-radius:999px;background:{_ORANGE};color:#fff;padding:9px 20px;font-size:13px;font-weight:600;cursor:pointer;display:inline-flex;align-items:center;justify-content:center;gap:8px;}}
.cta:hover {{background:#DE6300;}}
.cta:disabled {{cursor:wait;opacity:.92;}}
.cta-refresh-icon {{display:inline-flex;}}
.cta-refresh-icon svg {{display:block;}}
.refresh-spinner {{width:16px;height:16px;border:2px solid rgba(255,255,255,.35);border-top-color:#fff;border-radius:50%;animation:drc-spin .7s linear infinite;display:none;flex-shrink:0;}}
.cta.is-refreshing .cta-refresh-icon {{display:none;}}
.cta.is-refreshing .refresh-spinner {{display:inline-block;}}
.page-busy {{position:fixed;inset:0;background:rgba(250,250,250,.78);z-index:80;display:flex;align-items:center;justify-content:center;padding:24px;}}
.page-busy[hidden] {{display:none !important;}}
.page-busy-card {{background:#fff;border:1px solid {_BORDER};border-radius:14px;padding:1.75rem 1.5rem;text-align:center;box-shadow:0 8px 28px rgba(23,23,23,.08);max-width:360px;width:100%;}}
.page-busy-spinner {{width:36px;height:36px;border:3px solid #F3C7A4;border-top-color:{_ORANGE};border-radius:50%;animation:drc-spin .7s linear infinite;margin:0 auto 12px;}}
.page-busy-copy {{margin:0;font-size:15px;font-weight:700;color:{_TEXT};}}
.page-busy-sub {{margin:8px 0 0;font-size:13px;color:{_TEXT_DIM};line-height:1.45;}}
table {{border-collapse:collapse;table-layout:fixed;background:#fff;width:100%;min-width:100%;}}
table.table-wide {{width:max-content;min-width:1860px;}}
th {{text-align:left;padding:10px 8px;font-size:11px;font-weight:600;letter-spacing:.03em;text-transform:uppercase;color:{_TEXT_DIM};border-bottom:1px solid {_BORDER};background:#fff;position:sticky;top:0;z-index:1;}}
td {{padding:10px 8px;font-size:13px;border-bottom:1px solid {_BORDER};}}
tr:hover td {{background:#FAF8F5;}}
tr.row-rally-open td, tr.row-status-mismatch td {{background:#FDECEC;}}
tr.row-rally-open:hover td, tr.row-status-mismatch:hover td {{background:#F8D4D4;}}
tr.row-rally-open, tr.row-status-mismatch {{cursor:help;}}
.mono {{font-family:ui-monospace,monospace;font-size:12px;}}
.nowrap {{white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}}
.dim {{color:{_TEXT_DIM};}}
.ell {{max-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}}
.badge {{display:inline-block;padding:2px 9px;border-radius:999px;font-size:12px;font-weight:500;white-space:nowrap;}}
.dot {{display:inline-block;width:7px;height:7px;border-radius:50%;margin-right:7px;vertical-align:middle;}}
a {{color:{_ORANGE};text-decoration:none;}}
a:hover {{text-decoration:underline;}}
.panel {{width:100%;max-width:100%;overflow-x:scroll;overflow-y:auto;height:640px;min-height:640px;background:#fff;border:1px solid {_BORDER};border-radius:12px;padding:4px 4px 8px;box-shadow:0 1px 2px rgba(23,23,23,0.04);scrollbar-gutter:stable;scrollbar-width:auto;}}
.panel::-webkit-scrollbar {{height:14px;width:12px;}}
.panel::-webkit-scrollbar-track {{background:#EFEBE4;border-radius:8px;}}
.panel::-webkit-scrollbar-thumb {{background:#C7C1B5;border-radius:8px;border:2px solid #EFEBE4;}}
.panel::-webkit-scrollbar-thumb:hover {{background:#A8A296;}}
.panel::-webkit-scrollbar-corner {{background:#EFEBE4;}}
.link-btn {{background:none;border:none;color:{_ORANGE};font-size:13px;font-weight:500;cursor:pointer;padding:0;}}
.link-btn:hover {{text-decoration:underline;}}
.link-btn.action-link {{text-decoration:underline;}}
.link-btn:disabled {{color:{_TEXT_DIM};cursor:default;text-decoration:none;}}
.spinner {{display:inline-block;width:11px;height:11px;border:2px solid {_BORDER};border-top-color:{_ORANGE};border-radius:50%;animation:spin .6s linear infinite;vertical-align:middle;margin-right:5px;}}
.notice {{background:transparent;border:none;border-left:4px solid;padding:0 0 0 12px;margin:0;font-size:13px;font-weight:500;}}
.notice a {{color:inherit;font-weight:700;text-decoration:underline;}}
.notice a:hover {{color:{_ORANGE};}}
.notice-title {{font-weight:700;font-size:14px;margin:0 0 8px;}}
.notice-block {{margin:0 0 10px;}}
.notice-block:last-child {{margin-bottom:0;}}
.notice-pair {{margin:4px 0 0;font-family:ui-monospace,monospace;font-size:12px;font-weight:500;}}
.notice-error {{margin:2px 0 0 12px;font-size:12px;font-weight:500;}}
.comment-link {{color:{_ORANGE};cursor:pointer;font-weight:500;}}
.comment-link:hover {{text-decoration:underline;}}
.uc-link {{color:{_ORANGE};cursor:pointer;font-weight:500;display:block;font-size:12px;}}
.uc-link:hover {{text-decoration:underline;}}
.uc-link + .uc-link {{margin-top:3px;}}
.comment-tooltip {{position:absolute;display:none;max-width:360px;max-height:320px;background:{_TEXT};color:#fff;padding:0;border-radius:8px;font-size:12px;line-height:1.5;box-shadow:0 4px 12px rgba(23,23,23,0.18);z-index:50;overflow-x:hidden;overflow-y:auto;scrollbar-gutter:stable;scrollbar-width:thin;scrollbar-color:#6A6A6A #2A2A2A;}}
.comment-tooltip::-webkit-scrollbar {{width:10px;}}
.comment-tooltip::-webkit-scrollbar-track {{background:#2A2A2A;}}
.comment-tooltip::-webkit-scrollbar-thumb {{background:#6A6A6A;border-radius:8px;border:2px solid #2A2A2A;}}
.comment-tooltip .ct-block {{padding:10px 12px;white-space:normal;overflow-wrap:break-word;word-break:normal;}}
.comment-tooltip .ct-block + .ct-block {{border-top:1px solid rgba(255,255,255,0.12);}}
.comment-tooltip .ct-label {{color:{_ORANGE};font-size:10px;font-weight:600;letter-spacing:.04em;text-transform:uppercase;margin-bottom:4px;}}
.comment-tooltip .ct-meta {{color:#B9BBBE;font-size:11px;margin-bottom:4px;}}
.comment-tooltip .ct-body {{color:#fff;}}
.comment-tooltip a {{white-space:nowrap;color:{_ORANGE};}}
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
<div id="refresh-busy" class="page-busy" hidden role="status" aria-live="polite">
  <div class="page-busy-card">
    <div class="page-busy-spinner" aria-hidden="true"></div>
    <p class="page-busy-copy">Refreshing…</p>
    <p class="page-busy-sub">Fetching Rally and ZDR and copying new comments. This can take a few seconds.</p>
  </div>
</div>
{topbar}
<div class="page">
<div class="page-intro">
  {_app_lockup_html()}
  {refresh_block}
</div>
<div class="overview-row">
<div class="dashboard-box">
  <h2 class="dashboard-title">Defects Dashboard</h2>
  <div class="dash-grid">
    <div class="donut-card">{donut_html}</div>
    <div class="dash-metrics">
      <div class="dash-stat">
        <p class="dash-stat-label">Rally Open Defects{rally_filter_link}</p>
        <p class="dash-stat-value" style="color:#4C6EF5;">{rally_count}</p>
      </div>
      <div class="dash-stat">
        <p class="dash-stat-label">ZDR Open Defects{zdr_filter_link}</p>
        <p class="dash-stat-value">{zdr_count}</p>
        {disc_link}
      </div>
      <div class="dash-stat">
        <p class="dash-stat-label">ZDR available for Rally defects</p>
        <p class="dash-stat-value" style="color:#2F9E44;">{matched_n}</p>
        <p class="dash-stat-hint">Available in ZDR</p>
      </div>
      <div class="{missing_stat_class}">
        <p class="dash-stat-label">ZDR missing for Rally Defects</p>
        <p class="dash-stat-value" style="color:#E03131;">{missing_n}</p>
        <p class="dash-stat-hint">Requires action</p>
      </div>
    </div>
  </div>
</div>
<div class="notify-box">
  <h2 class="dashboard-title">Refresh/Sync Up Notifications</h2>
  <div class="notify-body">{notice_html}</div>
</div>
</div>
<hr class="section-split">
<div class="filters-box">
  <h2 class="filters-title">Defects Filter</h2>
  <p class="filters-sub">Filter the defect list by All, ZDR available, or ZDR missing</p>
  <div class="filter-tabs">
    <button class="tab-btn active" data-tab="all">All defects ({all_n})</button>
    <button class="tab-btn" data-tab="matched">ZDR available for Rally defects ({matched_n})</button>
    <button class="tab-btn" data-tab="missing">ZDR missing for Rally defects ({missing_n})</button>
  </div>
  <div class="panel" data-panel="all">
  <table>
    <colgroup>{action_col}<col style="width:90px;"><col style="width:130px;"><col style="width:80px;"><col style="width:130px;"><col style="width:100px;"><col style="width:130px;"><col></colgroup>
    <thead><tr>{action_header}<th>Rally id</th><th>Rally status</th><th>Severity</th><th>Owner</th><th>ZDR key</th><th>ZDR status</th><th>Summary</th></tr></thead>
    <tbody>{all_rows}</tbody>
  </table>
</div>
<div class="panel" data-panel="missing" style="display:none;">
  <table>
    <colgroup>{action_col}<col style="width:90px;"><col style="width:130px;"><col style="width:80px;"><col style="width:130px;"><col style="width:90px;"><col></colgroup>
    <thead><tr>{action_header}<th>Rally id</th><th>Rally status</th><th>Severity</th><th>Owner</th><th>Created</th><th>Summary</th></tr></thead>
    <tbody>{missing_rows}</tbody>
  </table>
</div>
<div class="panel" data-panel="matched" style="display:none;">
  <table class="table-wide">
    <colgroup><col style="width:90px;"><col style="width:100px;"><col style="width:130px;"><col style="width:150px;"><col style="width:110px;"><col style="width:110px;"><col style="width:140px;"><col style="width:180px;">{comments_col}{update_comments_col}{sync_col}</colgroup>
    <thead><tr><th>Rally id</th><th>ZDR key</th><th>Rally status</th><th>ZDR status</th><th>ZDR fix ETA</th><th>Rally fix ETA</th><th>Owner</th><th>Summary</th>{comments_header}{update_comments_header}{sync_header}</tr></thead>
    <tbody>{matched_rows}</tbody>
  </table>
</div>
</div>
<div class="comment-tooltip" id="comment-tooltip"></div>
{disc_modal}
<script>
(function() {{
  var pop = document.getElementById('open-discrepancies');
  var openLink = document.querySelector('.disc-open-link');
  if (!pop || !openLink) {{ return; }}
  function place() {{
    var rect = openLink.getBoundingClientRect();
    pop.style.display = 'block';
    pop.hidden = false;
    var width = pop.offsetWidth || 460;
    var gap = 10;
    var left = rect.right + window.scrollX + gap;
    var top = rect.top + window.scrollY - 10;
    var maxLeft = window.scrollX + window.innerWidth - width - 12;
    pop.classList.remove('disc-pop-right', 'disc-pop-below');
    if (left > maxLeft) {{
      pop.classList.add('disc-pop-below');
      left = rect.left + window.scrollX;
      if (left + width > window.scrollX + window.innerWidth - 12) {{
        left = window.scrollX + window.innerWidth - width - 12;
      }}
      top = rect.bottom + window.scrollY + gap;
      pop.style.setProperty('--caret-left', Math.max(12, rect.left + window.scrollX - left + rect.width / 2 - 7) + 'px');
    }} else {{
      pop.classList.add('disc-pop-right');
      pop.style.setProperty('--caret-top', Math.max(10, rect.top + window.scrollY + rect.height / 2 - top - 7) + 'px');
    }}
    pop.style.left = left + 'px';
    pop.style.top = top + 'px';
  }}
  function openPop(e) {{
    if (e) {{ e.preventDefault(); e.stopPropagation(); }}
    if (!pop.hidden && pop.style.display === 'block') {{
      closePop();
      return;
    }}
    place();
  }}
  function closePop() {{
    pop.hidden = true;
    pop.style.display = 'none';
  }}
  openLink.addEventListener('click', openPop);
  pop.addEventListener('click', function(e) {{ e.stopPropagation(); }});
  document.addEventListener('click', function() {{ closePop(); }});
  document.addEventListener('keydown', function(e) {{
    if (e.key === 'Escape' && !pop.hidden) {{ closePop(); }}
  }});
}})();
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
  var btn = document.getElementById('refresh-btn');
  if (!btn) {{ return; }}
  btn.addEventListener('click', function() {{
    if (btn.disabled) {{ return; }}
    btn.disabled = true;
    btn.classList.add('is-refreshing');
    var label = btn.querySelector('.cta-refresh-label');
    if (label) {{ label.textContent = 'Refreshing…'; }}
    var overlay = document.getElementById('refresh-busy');
    if (overlay) {{ overlay.hidden = false; }}
    window.setTimeout(function() {{
      window.location.href = btn.getAttribute('data-url');
    }}, 80);
  }});
}})();
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
      applyStatusHighlight(td.closest('tr'));
    }})
    .catch(function(e) {{ td.innerHTML = '<span style="color:#C0392B;font-size:12px;">Update failed: ' + e + '</span>'; }});
}}
document.addEventListener('change', function(e) {{
  var el = e.target.closest('.zdr-status-select');
  if (!el) {{ return; }}
  doTransition(el.getAttribute('data-zdr-key'), el.parentElement, el.value, null);
}});
var ZDR_OK_WHEN_RALLY_FIXED = {json.dumps(sorted(_ZDR_OK_WHEN_RALLY_FIXED))};
function applyStatusHighlight(tr) {{
  if (!tr) {{ return; }}
  var rallyBadge = tr.querySelector('.rally-state-badge');
  var zdrBadge = tr.querySelector('.zdr-status-badge');
  tr.classList.remove('row-rally-open', 'row-status-mismatch');
  tr.removeAttribute('title');
  if (!rallyBadge || !zdrBadge) {{ return; }}
  var state = (rallyBadge.textContent || '').trim();
  var zdr = (zdrBadge.textContent || '').trim();
  if (state === 'Open') {{
    tr.classList.add('row-rally-open');
    tr.title = 'ZDR ticket exists, but Rally status is still Open';
  }} else if (state === 'Fixed' && ZDR_OK_WHEN_RALLY_FIXED.indexOf(zdr.toLowerCase()) === -1) {{
    tr.classList.add('row-status-mismatch');
    tr.title = 'Discrepancy: Rally status is Fixed, but ZDR status is ' + zdr
      + '. ZDR should be {_ZDR_OK_WHEN_RALLY_FIXED_LABEL}.';
  }}
}}
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
      applyStatusHighlight(td.closest('tr'));
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
</div>
{_footer_html()}
</body>
</html>"""
