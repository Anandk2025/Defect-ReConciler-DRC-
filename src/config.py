import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent

load_dotenv(ROOT / ".env")

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


def require_credentials():
    missing = []
    if not RALLY_ZSESSIONID:
        missing.append("RALLY_ZSESSIONID")
    if not RALLY_JSESSIONID:
        missing.append("RALLY_JSESSIONID")
    if not ZDR_JIRA_EMAIL:
        missing.append("ZDR_JIRA_EMAIL")
    if not ZDR_JIRA_API_TOKEN:
        missing.append("ZDR_JIRA_API_TOKEN")
    if missing:
        raise SystemExit(
            f"Missing required .env values: {', '.join(missing)}. "
            f"Copy .env.example to .env and fill them in."
        )
