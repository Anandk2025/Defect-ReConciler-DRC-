import hmac
import html
import os
import re
from datetime import timedelta
from urllib.parse import urlencode

from flask import Flask, jsonify, redirect, request, session

from . import config
from .ai_sync import check_comment_sync
from .comment_sync import notice_for_results, sync_matched_pairs
from .pipeline import create_zdr_from_rally, run_comparison
from .rally_client import RallyClient
from .report import (
    build_connecting_html,
    build_html,
    build_login_html,
    build_rally_session_html,
    created_all_notice,
    created_ticket_notice,
)
from .sync_checks import check_defect_status, check_fix_eta
from .zdr_client import ZDRClient, extract_external_client_version

app = Flask(__name__, static_folder=str(config.ROOT / "static"), static_url_path="/static")
app.secret_key = config.DRC_SECRET_KEY or "dev-only-key-set-DRC_SECRET_KEY-in-.env-before-sharing"
app.permanent_session_lifetime = timedelta(days=30)

_PUBLIC_PATHS = {"/login"}


@app.before_request
def _require_login():
    config.bind_request_credentials(session.get("drc_credentials"))
    if not config.DRC_ACCESS_PASSWORD or request.path in _PUBLIC_PATHS:
        return None
    if session.get("authenticated"):
        return None
    return redirect("/login")


@app.route("/login", methods=["GET", "POST"])
def login():
    if not config.DRC_ACCESS_PASSWORD:
        return redirect("/")
    if request.method == "POST":
        password = request.form.get("password", "")
        if hmac.compare_digest(password, config.DRC_ACCESS_PASSWORD):
            session["authenticated"] = True
            session.permanent = bool(request.form.get("remember"))
            return redirect("/connecting")
        return build_login_html(error="Incorrect password."), 401
    return build_login_html()


@app.route("/connecting")
def connecting():
    return build_connecting_html()


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

# Persists for the life of the server process so the "Created" state next to
# a row survives a plain page reload, not just the immediate redirect — Jira's
# search index can lag a few seconds behind a freshly created issue.
_recently_created = {}


def _reconcile_recently_created(result):
    """Jira's JQL search can take a few seconds to index a freshly created
    ticket, so a defect we just created a ZDR ticket for might still show up
    as "missing" on the very next comparison. Since we already know its key,
    move it into "matched" ourselves instead of waiting for the index."""
    if not _recently_created:
        return
    still_missing = []
    zdr = None
    for d in result["missing_in_zdr"]:
        zdr_key = _recently_created.get(d["id"])
        if not zdr_key:
            still_missing.append(d)
            continue
        zdr = zdr or ZDRClient()
        try:
            status = zdr.get_status(zdr_key)
        except Exception:
            status = "Unknown"
        if status in config.ZDR_MATCHING_EXCLUDED_STATUSES:
            # It exists but is dead (e.g. auto-cancelled) — treat as still
            # missing so the "Create ZDR" option comes back, and drop the
            # stale tracking entry so we stop pretending it's valid.
            still_missing.append(d)
            _recently_created.pop(d["id"], None)
            continue
        result["matched"].append(
            {"rally": d, "zdr": [{"key": zdr_key, "status": status, "summary": d["name"], "rally_id": d["id"]}]}
        )
    result["missing_in_zdr"] = still_missing


@app.route("/")
def index():
    notice = None
    if request.args.get("created"):
        notice = created_ticket_notice(
            request.args.get("created"),
            request.args.get("rally_id", ""),
            request.args.get("attached", "0"),
            request.args.get("error", ""),
        )
    elif request.args.get("created_all") is not None:
        notice = created_all_notice(
            request.args.get("created_all", "0"),
            request.args.get("failed", "0"),
            request.args.get("ids", ""),
            request.args.get("error", ""),
        )
    elif request.args.get("error"):
        notice = ("error", request.args["error"])

    try:
        rally_defects, zdr_defects, result = run_comparison()
    except SystemExit as e:
        if _is_session_credentials_error(e):
            return redirect("/rally-session")
        return f"<pre>{e}</pre>", 500
    except Exception as e:
        if _is_session_credentials_error(e):
            return redirect("/rally-session")
        return f"<pre>Failed to fetch comparison: {e}</pre>", 500
    _reconcile_recently_created(result)

    if request.args.get("refresh"):
        try:
            sync_notice = notice_for_results(sync_matched_pairs(result))
        except Exception as e:
            sync_notice = ("error", f"Failed to sync Rally discussions to ZDR: {e}")
        if sync_notice:
            if notice:
                left_html = notice[1] if len(notice) > 2 and notice[2] == "html" else html.escape(notice[1])
                right_html = (
                    sync_notice[1]
                    if len(sync_notice) > 2 and sync_notice[2] == "html"
                    else html.escape(sync_notice[1])
                )
                notice = (
                    "error" if notice[0] == "error" or sync_notice[0] == "error" else "success",
                    left_html + right_html,
                    "html",
                )
            else:
                notice = sync_notice

    return build_html(
        result,
        len(rally_defects),
        len(zdr_defects),
        refresh_url="/?refresh=1",
        enable_actions=True,
        notice=notice,
        created_map=_recently_created,
        show_logout=bool(config.DRC_ACCESS_PASSWORD),
        rally_defects=rally_defects,
        zdr_open=zdr_defects,
    )


@app.route("/create-zdr/<rally_id>", methods=["POST"])
def create_zdr(rally_id):
    try:
        _, _, result = run_comparison()
        defect = next((d for d in result["missing_in_zdr"] if d["id"] == rally_id), None)
        if defect is None:
            return redirect(
                f"/?error=Rally defect {rally_id} is no longer in the missing list — it may already have a ZDR ticket."
            )
        zdr_key, attached, attach_errors = create_zdr_from_rally(defect)
        _recently_created[rally_id] = zdr_key
    except Exception as e:
        return redirect(f"/?error=Failed to create ZDR ticket for {rally_id}: {e}")
    if attach_errors:
        return redirect(
            f"/?created={zdr_key}&rally_id={rally_id}&attached={attached}"
            f"&error=Some attachments failed to copy: {'; '.join(attach_errors)}"
        )
    return redirect(f"/?created={zdr_key}&rally_id={rally_id}&attached={attached}")


@app.route("/create-all-zdrs", methods=["POST"])
def create_all_zdrs():
    try:
        _, _, result = run_comparison()
        _reconcile_recently_created(result)
        missing = [d for d in result["missing_in_zdr"] if d["id"] not in _recently_created]
        if not missing:
            return redirect("/?error=There are no missing Rally defects to create ZDR tickets for.")
        rally_client = RallyClient()
        zdr_client = ZDRClient()
        created = []
        failures = []
        attach_notes = []
        for defect in missing:
            try:
                zdr_key, attached, attach_errors = create_zdr_from_rally(
                    defect, rally_client=rally_client, zdr_client=zdr_client
                )
                _recently_created[defect["id"]] = zdr_key
                created.append(f"{defect['id']}→{zdr_key}")
                if attach_errors:
                    attach_notes.append(f"{defect['id']}: {'; '.join(attach_errors)}")
            except Exception as e:
                failures.append(f"{defect['id']}: {e}")
    except Exception as e:
        return redirect(f"/?error=Failed to create ZDR tickets: {e}")

    params = {"created_all": str(len(created)), "failed": str(len(failures))}
    if created:
        params["ids"] = ", ".join(created)
    errors = []
    if attach_notes:
        errors.append("Some attachments failed to copy: " + "; ".join(attach_notes))
    if failures:
        errors.append("Failed: " + "; ".join(failures))
    if errors:
        params["error"] = " ".join(errors)
    return redirect("/?" + urlencode(params))


@app.route("/api/comments/rally/<rally_id>")
def rally_comment(rally_id):
    try:
        comment = RallyClient().get_latest_comment(rally_id)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    if not comment:
        return jsonify({"text": "No discussion posts yet."})
    return jsonify(comment)


@app.route("/api/comments/zdr/<zdr_key>")
def zdr_comment(zdr_key):
    try:
        comment = ZDRClient().get_latest_comment(zdr_key)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    if not comment:
        return jsonify({"text": "No comments yet."})
    return jsonify(comment)


@app.route("/api/comments/sync-status/<rally_id>/<zdr_key>")
def comments_sync_status(rally_id, zdr_key):
    try:
        rally_summary = RallyClient().get_defect_summary(rally_id)
        zdr_summary = ZDRClient().get_summary(zdr_key)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    status_check = check_defect_status(rally_summary["state"], zdr_summary["status"])
    fix_eta_check = check_fix_eta(rally_summary["target_date"], zdr_summary["qa_complete_date"])

    try:
        rally_comment = RallyClient().get_latest_comment(rally_id)
        zdr_comment = ZDRClient().get_latest_comment(zdr_key)
        if not rally_comment or not zdr_comment or not rally_comment.get("text") or not zdr_comment.get("text"):
            comments_check = {"status": "no_comments", "message": "One or both systems have no comments yet."}
        else:
            ai_result = check_comment_sync(rally_comment["text"], zdr_comment["text"])
            comments_check = {"status": ai_result["status"], "message": ai_result["reason"]}
    except Exception as e:
        comments_check = {"status": "error", "message": str(e)}

    return jsonify(
        {
            "status_check": status_check,
            "fix_eta_check": fix_eta_check,
            "comments_check": comments_check,
        }
    )


@app.route("/api/zdr/external-client-version/<rally_id>/<zdr_key>", methods=["POST"])
def zdr_external_client_version(rally_id, zdr_key):
    try:
        comment = ZDRClient().get_latest_comment(zdr_key)
        value = extract_external_client_version([comment] if comment else [])
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    if not value:
        return jsonify({"status": "not_available"})
    try:
        RallyClient().add_comment(rally_id, value)
    except Exception as e:
        return jsonify({"error": f"Found '{value}' but failed to post it to Rally: {e}"}), 500
    return jsonify({"status": "posted", "value": value})


@app.route("/api/zdr/copy-comment-to-zdr/<rally_id>/<zdr_key>", methods=["POST"])
def copy_comment_to_zdr(rally_id, zdr_key):
    try:
        comment = RallyClient().get_latest_comment(rally_id)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    if not comment or not comment.get("text"):
        return jsonify({"status": "not_available"})
    try:
        ZDRClient().add_comment(zdr_key, comment["text"])
    except Exception as e:
        return jsonify({"error": f"Found Rally comment but failed to post it to ZDR: {e}"}), 500
    return jsonify({"status": "posted", "value": comment["text"]})


@app.route("/api/zdr/transitions/<zdr_key>")
def zdr_transitions(zdr_key):
    try:
        transitions = ZDRClient().get_transitions(zdr_key)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    return jsonify({"transitions": transitions})


_MUST_BE_SET_RE = re.compile(r"([A-Za-z0-9 /]+?) must be set")


@app.route("/api/zdr/transition/<zdr_key>", methods=["POST"])
def zdr_transition(zdr_key):
    body = request.get_json(silent=True) or {}
    transition_id = body.get("transition_id")
    fields = body.get("fields")
    if not transition_id:
        return jsonify({"error": "transition_id is required"}), 400
    zdr = ZDRClient()
    try:
        zdr.transition_issue(zdr_key, transition_id, fields=fields)
        new_status = zdr.get_status(zdr_key)
    except Exception as e:
        # Some transitions enforce a required field via a workflow validator
        # that Jira only reports once you attempt the transition — look the
        # field up and hand its options back so the UI can prompt and retry.
        match = _MUST_BE_SET_RE.search(str(e))
        if match and not fields:
            try:
                field_info = zdr.get_editmeta_field(zdr_key, match.group(1).strip())
            except Exception:
                field_info = None
            if field_info:
                return jsonify({"needs_field": field_info, "transition_id": transition_id})
        return jsonify({"error": str(e)}), 500
    return jsonify({"status": new_status})


@app.route("/api/rally/state-options")
def rally_state_options():
    return jsonify({"states": config.RALLY_STATE_VALUES})


@app.route("/api/rally/update-state/<rally_id>", methods=["POST"])
def rally_update_state(rally_id):
    new_state = (request.get_json(silent=True) or {}).get("state")
    if not new_state:
        return jsonify({"error": "state is required"}), 400
    rally = RallyClient()
    try:
        ref = rally.get_defect_ref(rally_id)
        rally.update_state(ref, new_state)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    return jsonify({"state": new_state})


@app.route("/api/rally/update-date/<rally_id>", methods=["POST"])
def rally_update_date(rally_id):
    date_str = (request.get_json(silent=True) or {}).get("date") or ""
    rally = RallyClient()
    try:
        ref = rally.get_defect_ref(rally_id)
        rally.update_target_date(ref, date_str)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    return jsonify({"date": date_str})


@app.route("/api/zdr/update-date/<zdr_key>", methods=["POST"])
def zdr_update_date(zdr_key):
    date_str = (request.get_json(silent=True) or {}).get("date") or ""
    try:
        ZDRClient().set_qa_complete_date(zdr_key, date_str)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    return jsonify({"date": date_str})


def _is_session_credentials_error(exc):
    if isinstance(exc, config.MissingCredentialsError):
        return True
    message = str(exc)
    if any(
        key in message
        for key in ("RALLY_ZSESSIONID", "RALLY_JSESSIONID", "ZDR_JIRA_EMAIL", "ZDR_JIRA_API_TOKEN")
    ):
        return True
    if "401" not in message:
        return False
    lower = message.lower()
    return "rallydev.com" in lower or "atlassian.net" in lower


def _session_form(error=None, status=None):
    creds = config.current_credentials()
    html_page = build_rally_session_html(
        error=error,
        jira_email=creds.get("ZDR_JIRA_EMAIL") or "",
        has_rally=bool(creds.get("RALLY_ZSESSIONID") and creds.get("RALLY_JSESSIONID")),
        has_jira_token=bool(creds.get("ZDR_JIRA_API_TOKEN")),
    )
    if status is None:
        return html_page
    return html_page, status


@app.route("/rally-session", methods=["GET", "POST"])
def rally_session():
    creds = config.current_credentials()
    if request.method == "GET":
        return _session_form()
    merged = {
        "RALLY_ZSESSIONID": (request.form.get("zsessionid") or "").strip() or creds.get("RALLY_ZSESSIONID") or "",
        "RALLY_JSESSIONID": (request.form.get("jsessionid") or "").strip() or creds.get("RALLY_JSESSIONID") or "",
        "ZDR_JIRA_EMAIL": (request.form.get("jira_email") or "").strip() or creds.get("ZDR_JIRA_EMAIL") or "",
        "ZDR_JIRA_API_TOKEN": (request.form.get("jira_api_token") or "").strip()
        or creds.get("ZDR_JIRA_API_TOKEN")
        or "",
    }
    try:
        config.set_session_credentials(
            merged["RALLY_ZSESSIONID"],
            merged["RALLY_JSESSIONID"],
            merged["ZDR_JIRA_EMAIL"],
            merged["ZDR_JIRA_API_TOKEN"],
        )
    except ValueError as e:
        return _session_form(error=str(e), status=400)
    session["drc_credentials"] = merged
    session.permanent = True
    session.modified = True
    return redirect("/connecting")


def main():
    port = int(os.environ.get("PORT", "5050"))
    app.run(host="0.0.0.0", port=port, debug=False)


if __name__ == "__main__":
    main()
