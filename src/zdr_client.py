import re

import requests
from requests.auth import HTTPBasicAuth

from . import config

_EXTERNAL_CLIENT_VERSION_RE = re.compile(
    r"external\s+client\s+version\s*(?:is)?\s*[:\-]?\s*(.+)", re.IGNORECASE
)


def extract_external_client_version(comments):
    """Comments aren't structured fields — "External Client Version" is a
    label someone typed into a ZDR comment by convention, so this scans
    comment text (newest first) for that label and pulls the rest of the
    line as its value."""
    for c in comments:
        match = _EXTERNAL_CLIENT_VERSION_RE.search(c.get("text") or "")
        if match:
            value = match.group(1).strip()
            if value:
                return value
    return None


def _text_to_adf(text):
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()] or [text]
    return [
        {"type": "paragraph", "content": [{"type": "text", "text": p}]}
        for p in paragraphs
    ]


def _adf_to_text(node):
    if not isinstance(node, dict):
        return ""
    if node.get("type") == "text":
        return node.get("text", "")
    parts = [_adf_to_text(child) for child in node.get("content", [])]
    joined = "".join(parts)
    return joined + ("\n" if node.get("type") == "paragraph" else "")


class ZDRClient:
    def __init__(self):
        self.base_url = f"https://{config.ZDR_SITE}/rest/api/3"
        self.auth = HTTPBasicAuth(config.ZDR_JIRA_EMAIL, config.ZDR_JIRA_API_TOKEN)
        self.headers = {"Content-Type": "application/json"}

    def _build_jql(self, exclude_statuses=False):
        jql = f"project = {config.ZDR_PROJECT_KEY} AND {config.ZDR_JQL_SCOPE}"
        if exclude_statuses and config.ZDR_JQL_EXCLUDED_STATUSES:
            statuses = ", ".join(f'"{s}"' for s in config.ZDR_JQL_EXCLUDED_STATUSES)
            jql += f" AND status not in ({statuses})"
        if config.ZDR_JQL_ORDER_BY:
            jql += f" ORDER BY {config.ZDR_JQL_ORDER_BY}"
        return jql

    def _search(self, jql):
        fields = ["summary", "status", config.ZDR_EXTERNAL_ID_FIELD, config.ZDR_QA_COMPLETE_DATE_FIELD]
        issues = []
        next_page_token = None
        while True:
            body = {"jql": jql, "fields": fields, "maxResults": 100}
            if next_page_token:
                body["nextPageToken"] = next_page_token
            resp = requests.post(
                f"{self.base_url}/search/jql", json=body, auth=self.auth, headers=self.headers
            )
            resp.raise_for_status()
            data = resp.json()
            for issue in data.get("issues", []):
                fields_data = issue["fields"]
                issues.append(
                    {
                        "key": issue["key"],
                        "summary": fields_data.get("summary"),
                        "status": (fields_data.get("status") or {}).get("name"),
                        "rally_id": fields_data.get(config.ZDR_EXTERNAL_ID_FIELD),
                        "qa_complete_date": fields_data.get(config.ZDR_QA_COMPLETE_DATE_FIELD),
                    }
                )
            if data.get("isLast", True):
                break
            next_page_token = data.get("nextPageToken")
        return issues

    def list_open_defects(self):
        return self._search(self._build_jql(exclude_statuses=True))

    def list_all_linked_defects(self):
        """Every ZDR ticket linked to a Rally defect, regardless of status —
        used for matching so an already-linked ticket in a closed-ish status
        (Pending Approval to Close, etc.) is never mistaken for "missing"."""
        return self._search(self._build_jql(exclude_statuses=False))

    def create_defect(self, rally_id, summary, description="", severity=None, created=None, environment=None):
        rally_id_value = f"{config.RALLY_ID_PREFIX}{rally_id}"
        description = description or f"Created from Rally defect {rally_id} via Defect ReConciler (DRC)."
        captured = []
        if severity:
            captured.append(f"Rally severity: {severity}")
        if created:
            captured.append(f"Rally creation date: {created}")
        if captured:
            description = "\n\n".join(captured) + "\n\n" + description

        defaults = config.ZDR_CREATE_DEFAULTS
        payload = {
            "fields": {
                "project": {"key": config.ZDR_PROJECT_KEY},
                "issuetype": {"id": config.ZDR_ISSUE_TYPE_ID},
                "summary": f"[{rally_id}] {summary}",
                "description": {
                    "type": "doc",
                    "version": 1,
                    "content": _text_to_adf(description),
                },
                config.ZDR_EXTERNAL_ID_FIELD: rally_id_value,
                defaults["client_field"]: [{"id": defaults["client_option_id"]}],
                defaults["organization_field"]: [defaults["organization_id"]],
                defaults["farmers_project_field"]: {"id": defaults["farmers_project_option_id"]},
                defaults["classification_field"]: {"id": defaults["classification_option_id"]},
            }
        }
        severity_option_id = (defaults.get("severity_options") or {}).get(severity)
        if severity_option_id:
            payload["fields"][defaults["severity_field"]] = {"id": severity_option_id}
        environment_option_id = (defaults.get("environment_options") or {}).get(environment)
        if environment_option_id:
            payload["fields"][defaults["environment_field"]] = {"id": environment_option_id}
        resp = requests.post(
            f"{self.base_url}/issue", json=payload, auth=self.auth, headers=self.headers
        )
        if not resp.ok:
            raise RuntimeError(f"Jira rejected issue create ({resp.status_code}): {resp.text}")
        key = resp.json()["key"]

        # Request Type can't be set on create (Jira rejects it there) — it has
        # to be set as a follow-up edit, and only accepts a bare string id.
        resp = requests.put(
            f"{self.base_url}/issue/{key}",
            json={"fields": {defaults["request_type_field"]: defaults["request_type_id"]}},
            auth=self.auth,
            headers=self.headers,
        )
        if not resp.ok:
            raise RuntimeError(f"Created {key} but failed to set Request Type ({resp.status_code}): {resp.text}")
        return key

    def add_attachment(self, issue_key, filename, content_bytes, content_type=None):
        resp = requests.post(
            f"{self.base_url}/issue/{issue_key}/attachments",
            auth=self.auth,
            headers={"X-Atlassian-Token": "no-check"},
            files={"file": (filename, content_bytes, content_type or "application/octet-stream")},
        )
        resp.raise_for_status()
        return resp.json()[0]["id"]

    def get_transitions(self, issue_key):
        resp = requests.get(f"{self.base_url}/issue/{issue_key}/transitions", auth=self.auth)
        resp.raise_for_status()
        return [{"id": t["id"], "name": t["to"]["name"]} for t in resp.json().get("transitions", [])]

    def transition_issue(self, issue_key, transition_id, fields=None):
        payload = {"transition": {"id": transition_id}}
        if fields:
            payload["fields"] = fields
        resp = requests.post(
            f"{self.base_url}/issue/{issue_key}/transitions",
            json=payload,
            auth=self.auth,
            headers=self.headers,
        )
        if not resp.ok:
            raise RuntimeError(f"Jira rejected transition ({resp.status_code}): {resp.text}")

    def get_editmeta_field(self, issue_key, field_name):
        """Some transitions enforce required fields via a workflow validator
        that isn't listed in the transitions API — it only surfaces once you
        attempt the transition. This looks the field up by name afterwards
        so the UI can prompt for a value and retry."""
        resp = requests.get(f"{self.base_url}/issue/{issue_key}/editmeta", auth=self.auth)
        resp.raise_for_status()
        for field_id, field in resp.json().get("fields", {}).items():
            if field.get("name") == field_name:
                options = [{"id": o["id"], "name": o["value"]} for o in field.get("allowedValues", [])]
                return {"id": field_id, "name": field_name, "options": options}
        return None

    def set_qa_complete_date(self, issue_key, date_str):
        resp = requests.put(
            f"{self.base_url}/issue/{issue_key}",
            json={"fields": {config.ZDR_QA_COMPLETE_DATE_FIELD: date_str or None}},
            auth=self.auth,
            headers=self.headers,
        )
        if not resp.ok:
            raise RuntimeError(f"Jira rejected QA Complete Date update ({resp.status_code}): {resp.text}")

    def get_status(self, issue_key):
        resp = requests.get(f"{self.base_url}/issue/{issue_key}", auth=self.auth, params={"fields": "status"})
        resp.raise_for_status()
        return resp.json()["fields"]["status"]["name"]

    def get_summary(self, issue_key):
        resp = requests.get(
            f"{self.base_url}/issue/{issue_key}",
            auth=self.auth,
            params={"fields": f"status,{config.ZDR_QA_COMPLETE_DATE_FIELD}"},
        )
        resp.raise_for_status()
        fields = resp.json()["fields"]
        return {
            "status": (fields.get("status") or {}).get("name"),
            "qa_complete_date": fields.get(config.ZDR_QA_COMPLETE_DATE_FIELD),
        }

    def get_latest_comment(self, issue_key):
        resp = requests.get(
            f"{self.base_url}/issue/{issue_key}/comment",
            auth=self.auth,
            params={"maxResults": 1, "orderBy": "-created"},
        )
        resp.raise_for_status()
        comments = resp.json().get("comments") or []
        if not comments:
            return None
        c = comments[0]
        return {
            "text": _adf_to_text(c.get("body")).strip(),
            "author": (c.get("author") or {}).get("displayName"),
            "created": c.get("created"),
        }

    def add_comment(self, issue_key, text):
        resp = requests.post(
            f"{self.base_url}/issue/{issue_key}/comment",
            json={"body": {"type": "doc", "version": 1, "content": _text_to_adf(text)}},
            auth=self.auth,
            headers=self.headers,
        )
        if not resp.ok:
            raise RuntimeError(f"Jira rejected comment ({resp.status_code}): {resp.text}")
