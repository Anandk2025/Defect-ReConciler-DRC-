import os
import re
from contextvars import ContextVar
from pathlib import Path

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent

load_dotenv(ROOT / ".env")


def _clear_loopback_proxies():
    """Cursor injects HTTP(S)_PROXY=127.0.0.1 which breaks Rally/Jira from Flask."""
    keys = ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy")
    uses_loopback = False
    for key in keys:
        value = os.environ.get(key) or ""
        if "127.0.0.1" in value or "localhost" in value:
            uses_loopback = True
            break
    if uses_loopback:
        for key in keys:
            os.environ.pop(key, None)


_clear_loopback_proxies()

with open(ROOT / "config.yaml") as f:
    _cfg = yaml.safe_load(f)

RALLY_ZSESSIONID = os.environ.get("RALLY_ZSESSIONID", "")
RALLY_JSESSIONID = os.environ.get("RALLY_JSESSIONID", "")
RALLY_BASE_URL = _cfg["rally"]["base_url"]
RALLY_PROJECT = _cfg["rally"]["project"]
RALLY_NOT_STATE = _cfg["rally"]["not_state"]
RALLY_OWNERS = _cfg["rally"].get("owners") or []
RALLY_FILTER_URL = _cfg["rally"].get("filter_url") or ""
RALLY_STATE_VALUES = _cfg["rally"].get("state_values") or []
RALLY_ON_ZDR_CREATED = _cfg["rally"].get("on_zdr_created") or {}

ZDR_JIRA_EMAIL = os.environ.get("ZDR_JIRA_EMAIL", "")
ZDR_JIRA_API_TOKEN = os.environ.get("ZDR_JIRA_API_TOKEN", "")
ZDR_SITE = _cfg["zdr"]["site"]
ZDR_PROJECT_KEY = _cfg["zdr"]["project_key"]
ZDR_ISSUE_TYPE_ID = _cfg["zdr"]["issue_type_id"]
ZDR_EXTERNAL_ID_FIELD = _cfg["zdr"]["external_id_field"]
ZDR_QA_COMPLETE_DATE_FIELD = _cfg["zdr"]["qa_complete_date_field"]
ZDR_JQL_SCOPE = _cfg["zdr"]["jql_scope"]
ZDR_JQL_EXCLUDED_STATUSES = _cfg["zdr"].get("jql_excluded_statuses") or []
ZDR_JQL_ORDER_BY = _cfg["zdr"].get("jql_order_by") or ""
ZDR_MATCHING_EXCLUDED_STATUSES = _cfg["zdr"].get("matching_excluded_statuses") or []
ZDR_CREATE_DEFAULTS = _cfg["zdr"]["create_defaults"]
ZDR_FILTER_URL = _cfg["zdr"].get("filter_url") or ""

DRC_ACCESS_PASSWORD = os.environ.get("DRC_ACCESS_PASSWORD", "")
DRC_SECRET_KEY = os.environ.get("DRC_SECRET_KEY", "")

RALLY_ID_PREFIX = _cfg["matching"].get("rally_id_prefix") or ""

SYNC_CHECK_RALLY_STATUSES = _cfg.get("sync_check", {}).get("rally_statuses_requiring_zdr_progress") or []
SYNC_CHECK_ZDR_BLOCKING_STATUSES = _cfg.get("sync_check", {}).get("zdr_blocking_statuses") or []

AI_MODEL = _cfg.get("ai", {}).get("model") or "claude-haiku-4-5-20251001"

COMMENT_SYNC_TAG = (_cfg.get("comment_sync") or {}).get("tag_line") or "Latest Comments from Rally Posted at:"
COMMENT_SYNC_OTHER_TEAM = (_cfg.get("comment_sync") or {}).get("other_team") or "FNWL Team"

_CREDENTIAL_KEYS = ("RALLY_ZSESSIONID", "RALLY_JSESSIONID", "ZDR_JIRA_EMAIL", "ZDR_JIRA_API_TOKEN")
_request_credentials = ContextVar("drc_request_credentials", default=None)


class MissingCredentialsError(SystemExit):
    def __init__(self, missing):
        self.missing = list(missing)
        super().__init__(
            f"Missing required credentials: {', '.join(self.missing)}. "
            "Enter them on the session page, or set them in the environment."
        )


def bind_request_credentials(overrides):
    """Prefer per-browser session values over process environment for this request."""
    cleaned = {}
    if overrides:
        for key in _CREDENTIAL_KEYS:
            value = (overrides.get(key) or "").strip()
            if value:
                cleaned[key] = value
    _request_credentials.set(cleaned or None)


def current_credentials():
    bound = _request_credentials.get() or {}
    return {
        key: (bound.get(key) or os.environ.get(key) or globals().get(key) or "").strip()
        for key in _CREDENTIAL_KEYS
    }


def require_credentials():
    missing = [key for key, value in current_credentials().items() if not value]
    if missing:
        raise MissingCredentialsError(missing)


def _dotenv_assignment(key, value):
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'{key}="{escaped}"'


def _upsert_dotenv(updates):
    path = ROOT / ".env"
    text = path.read_text() if path.exists() else ""
    for key, value in updates.items():
        line = _dotenv_assignment(key, value)
        pattern = re.compile(rf"^{re.escape(key)}=.*$", re.MULTILINE)
        if pattern.search(text):
            text = pattern.sub(lambda _m, replacement=line: replacement, text, count=1)
        else:
            if text and not text.endswith("\n"):
                text += "\n"
            text += line + "\n"
    if text and not text.endswith("\n"):
        text += "\n"
    path.write_text(text)


def set_session_credentials(zsessionid, jsessionid, jira_email, jira_api_token):
    """Apply Rally + ZDR credentials to this process and, when possible, .env."""
    global RALLY_ZSESSIONID, RALLY_JSESSIONID, ZDR_JIRA_EMAIL, ZDR_JIRA_API_TOKEN
    zsessionid = (zsessionid or "").strip()
    jsessionid = (jsessionid or "").strip()
    jira_email = (jira_email or "").strip()
    jira_api_token = (jira_api_token or "").strip()
    if not zsessionid or not jsessionid:
        raise ValueError("Both Rally ZSESSIONID and JSESSIONID are required.")
    if not jira_email or not jira_api_token:
        raise ValueError("Both ZDR Jira email and API token are required.")
    if "@" not in jira_email:
        raise ValueError("ZDR Jira email looks invalid.")
    joined = "".join((zsessionid, jsessionid, jira_email, jira_api_token))
    if any(ch in joined for ch in ("\n", "\r", "\0")):
        raise ValueError("Credential values cannot contain line breaks.")
    updates = {
        "RALLY_ZSESSIONID": zsessionid,
        "RALLY_JSESSIONID": jsessionid,
        "ZDR_JIRA_EMAIL": jira_email,
        "ZDR_JIRA_API_TOKEN": jira_api_token,
    }
    env_file_updated = True
    try:
        _upsert_dotenv(updates)
    except OSError:
        env_file_updated = False
    RALLY_ZSESSIONID = zsessionid
    RALLY_JSESSIONID = jsessionid
    ZDR_JIRA_EMAIL = jira_email
    ZDR_JIRA_API_TOKEN = jira_api_token
    for key, value in updates.items():
        os.environ[key] = value
    bind_request_credentials(updates)
    return env_file_updated
