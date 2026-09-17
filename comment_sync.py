import html
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from urllib.parse import quote

from . import config
from .rally_client import RallyClient
from .zdr_client import ZDRClient

_STAMP_RE = re.compile(
    r"^(?:"
    r"\d{4}-\d{2}-\d{2}[ t]\d{2}:\d{2}(?::\d{2})?(?:\s*[+-]\d{2}:?\d{2})?"
    r"|"
    r"\d{1,2}/\d{1,2}/\d{4}\s*-\s*\d{2}:\d{2}(?::\d{2})?(?:\s*[+-]\d{2}:?\d{2})?\s*-?"
    r")"
)
_COMMENTS_PREFIX_RE = re.compile(r"^comments\s*:", re.IGNORECASE)
_TAG_PREFIXES = (
    "latest comments from rally posted at:",
    "latest comments from rally posted at",
    "latest comments from rally",
)
_RALLY_OBJECT_ID_RE = re.compile(r"/defect/(\d+)")


def _normalize(text):
    return " ".join((text or "").split()).casefold()


def _parse_rally_datetime(created):
    if not created:
        return None
    raw = str(created).strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone()


def _already_copied(rally_text, zdr_comments):
    needle = _normalize(rally_text)
    if not needle:
        return True
    for comment in zdr_comments:
        hay = _normalize(comment.get("text"))
        if not hay:
            continue
        if needle in hay:
            return True
        remainder = _body_after_tag(hay)
        if needle == remainder or needle in remainder:
            return True
    return False


def _body_after_tag(hay):
    for prefix in _TAG_PREFIXES:
        if hay.startswith(prefix):
            rest = hay[len(prefix) :].strip(" :-")
            rest = _STAMP_RE.sub("", rest, count=1).strip(" -")
            rest = _COMMENTS_PREFIX_RE.sub("", rest).strip()
            return rest
    return hay


def format_discussion_line(post):
    dt = _parse_rally_datetime(post.get("created")) or datetime.now().astimezone()
    date = f"{dt.month}/{dt.day}/{dt.year}"
    time_24 = dt.strftime("%H:%M:%S")
    hour12 = dt.hour % 12 or 12
    ampm = "AM" if dt.hour < 12 else "PM"
    author = (post.get("author") or "Unknown").strip()
    team = config.COMMENT_SYNC_OTHER_TEAM
    text = " ".join((post.get("text") or "").split())
    return f"{date} - {time_24} {hour12} {ampm} - {author}({team}) - {text}"


def _new_posts_since_last_copied(posts, zdr_comments):
    """Rally posts after the newest one already on ZDR. If none copied yet, the latest only."""
    nonempty = [p for p in posts if (p.get("text") or "").strip()]
    if not nonempty:
        return []
    last_copied_idx = -1
    for i, post in enumerate(nonempty):
        if _already_copied(post.get("text"), zdr_comments):
            last_copied_idx = i
    if last_copied_idx == -1:
        return [nonempty[-1]]
    return nonempty[last_copied_idx + 1 :]


def sync_rally_discussion_to_zdr(rally_id, zdr_key, rally_client=None, zdr_client=None):
    """Copy new Rally discussions into ZDR; skip anything already copied."""
    rally_client = rally_client or RallyClient()
    zdr_client = zdr_client or ZDRClient()
    posts = rally_client.list_comments(rally_id)
    if not posts:
        return {"status": "no_rally_comment", "rally_id": rally_id, "zdr_key": zdr_key, "count": 0}

    zdr_comments = zdr_client.list_comments(zdr_key)
    to_copy = _new_posts_since_last_copied(posts, zdr_comments)
    if not to_copy:
        return {"status": "skipped", "rally_id": rally_id, "zdr_key": zdr_key, "count": 0}

    lines = [format_discussion_line(post) for post in to_copy]
    body = "\n\n".join(lines)
    zdr_client.add_comment(zdr_key, body, heading=config.COMMENT_SYNC_TAG)
    return {"status": "posted", "rally_id": rally_id, "zdr_key": zdr_key, "count": len(to_copy)}


def pairs_from_matched(result):
    """One (Rally ID, ZDR key) pair per matched row — same ticket the dashboard shows."""
    pairs = []
    seen = set()
    for row in result.get("matched") or []:
        rally = row.get("rally") or {}
        zdr_list = row.get("zdr") or []
        rally_id = rally.get("id")
        zdr_key = zdr_list[0].get("key") if zdr_list else None
        if not rally_id or not zdr_key:
            continue
        key = (rally_id, zdr_key)
        if key in seen:
            continue
        seen.add(key)
        pairs.append({"rally_id": rally_id, "zdr_key": zdr_key, "rally_ref": rally.get("ref") or ""})
    return pairs


def _sync_one_pair(pair):
    rally_id = pair["rally_id"]
    zdr_key = pair["zdr_key"]
    try:
        result = sync_rally_discussion_to_zdr(rally_id, zdr_key)
    except Exception as e:
        result = {
            "status": "error",
            "rally_id": rally_id,
            "zdr_key": zdr_key,
            "count": 0,
            "error": str(e),
        }
    result["rally_ref"] = pair.get("rally_ref") or ""
    return result


def sync_matched_pairs(result):
    """Copy new Rally discussions into ZDR for every matched defect. Safe to call on Refresh."""
    pairs = pairs_from_matched(result)
    if not pairs:
        return []
    workers = min(8, len(pairs))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(_sync_one_pair, pairs))


def _rally_href(rally_id, rally_ref=""):
    match = _RALLY_OBJECT_ID_RE.search(rally_ref or "")
    base = config.RALLY_BASE_URL.rstrip("/")
    if match:
        return f"{base}/#/detail/defect/{match.group(1)}"
    return f"{base}/#/search?keywords={quote(str(rally_id))}"


def _zdr_href(zdr_key):
    return f"https://{config.ZDR_SITE}/browse/{quote(str(zdr_key), safe='-')}"


def _pair_link_html(result):
    rally_id = html.escape(str(result.get("rally_id") or ""))
    zdr_key = html.escape(str(result.get("zdr_key") or ""))
    rally_url = html.escape(_rally_href(result.get("rally_id"), result.get("rally_ref")), quote=True)
    zdr_url = html.escape(_zdr_href(result.get("zdr_key")), quote=True)
    return (
        f'<div class="notice-pair">'
        f'<a href="{rally_url}" target="_blank" rel="noopener">{rally_id}</a>'
        f"-&gt;"
        f'<a href="{zdr_url}" target="_blank" rel="noopener">{zdr_key}</a>'
        f"</div>"
    )


def notice_for_results(results):
    if not results:
        return None
    posted = [r for r in results if r["status"] == "posted"]
    skipped = [r for r in results if r["status"] == "skipped"]
    no_comment = [r for r in results if r["status"] == "no_rally_comment"]
    errors = [r for r in results if r["status"] not in ("posted", "skipped", "no_rally_comment")]
    blocks = ['<div class="notice-title">Sync up details :</div>']
    if posted:
        blocks.append(
            f'<div class="notice-block">Copied Rally Comments to ZDRs Tickets: {len(posted)}'
            + "".join(_pair_link_html(r) for r in posted)
            + "</div>"
        )
    if skipped:
        blocks.append(
            f'<div class="notice-block">Skipped {len(skipped)} Defects as already in Sync: {len(skipped)}</div>'
        )
    if no_comment:
        blocks.append(
            f'<div class="notice-block">{len(no_comment)} had no Rally discussion.</div>'
        )
    if errors:
        failed = "".join(
            _pair_link_html(r)
            + f'<div class="notice-error">{html.escape(r.get("error") or "unknown error")}</div>'
            for r in errors
        )
        blocks.append(f'<div class="notice-block">Failed ({len(errors)}):{failed}</div>')
    if len(blocks) == 1:
        return None
    kind = "error" if errors else "success"
    return (kind, "".join(blocks), "html")
