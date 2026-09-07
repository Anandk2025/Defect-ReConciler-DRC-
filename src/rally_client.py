import base64
import re
from html import unescape as html_unescape

import requests

from . import config

_TAG_RE = re.compile(r"<[^>]+>")
_IMG_RE = re.compile(r'(?i)<img[^>]*\ssrc="([^"]*)"[^>]*>')
_SECURITY_TOKEN_RE = re.compile(r'name="SecurityToken" content="([^"]+)"')


def _html_to_text(value):
    if not value:
        return ""
    # Inline images can't carry over as inline images in ZDR (Jira's plain
    # attachment API doesn't expose the media id ADF embedding needs) — leave
    # a marker with the filename so the reader knows to check the attachments.
    text = _IMG_RE.sub(lambda m: f"[Screenshot attached: {m.group(1).rsplit('/', 1)[-1]}]", value)
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</p>", "\n\n", text)
    text = _TAG_RE.sub("", text)
    text = html_unescape(text)
    return text.strip()


class RallyClient:
    def __init__(self):
        self.base_url = config.RALLY_BASE_URL.rstrip("/")
        self.session = requests.Session()
        self.session.cookies.set("ZSESSIONID", config.RALLY_ZSESSIONID)
        self.session.cookies.set("JSESSIONID", config.RALLY_JSESSIONID)
        self.session.headers.update({"Content-Type": "application/json"})
        self._project_ref = None
        self._security_token = None

    def _get(self, path, params=None):
        resp = self.session.get(f"{self.base_url}/slm/webservice/v2.0/{path}", params=params)
        resp.raise_for_status()
        return resp.json()

    def security_token(self):
        """Rally's write endpoints require a CSRF-style `key` query param that
        isn't returned by any WSAPI call — it's embedded as a meta tag in the
        main app page's HTML, so we fetch that page once and scrape it."""
        if self._security_token is None:
            resp = self.session.get(self.base_url)
            resp.raise_for_status()
            match = _SECURITY_TOKEN_RE.search(resp.text)
            if not match:
                raise RuntimeError("Could not find Rally's SecurityToken on the app page")
            self._security_token = match.group(1)
        return self._security_token

    def get_defect_ref(self, formatted_id):
        data = self._get("defect", params={"query": f'(FormattedID = "{formatted_id}")', "fetch": "ObjectID"})
        results = data["QueryResult"]["Results"]
        if not results:
            raise ValueError(f'Rally defect "{formatted_id}" not found')
        return results[0]["_ref"]

    def update_fields(self, defect_ref, fields):
        resp = self.session.post(defect_ref, params={"key": self.security_token()}, json={"Defect": fields})
        if not resp.ok:
            raise RuntimeError(f"Rally rejected update ({resp.status_code}): {resp.text}")
        errors = resp.json().get("OperationResult", {}).get("Errors") or []
        if errors:
            raise RuntimeError(f"Rally rejected update: {'; '.join(errors)}")

    def update_state(self, defect_ref, new_state):
        self.update_fields(defect_ref, {"State": new_state})

    def update_target_date(self, defect_ref, date_str):
        value = f"{date_str}T00:00:00.000Z" if date_str else None
        self.update_fields(defect_ref, {"TargetDate": value})

    def add_comment(self, formatted_id, text):
        defect_ref = self.get_defect_ref(formatted_id)
        resp = self.session.post(
            f"{self.base_url}/slm/webservice/v2.0/conversationpost/create",
            params={"key": self.security_token()},
            json={"ConversationPost": {"Artifact": defect_ref, "Text": text}},
        )
        if not resp.ok:
            raise RuntimeError(f"Rally rejected comment ({resp.status_code}): {resp.text}")
        errors = resp.json().get("CreateResult", {}).get("Errors") or []
        if errors:
            raise RuntimeError(f"Rally rejected comment: {'; '.join(errors)}")

    def project_ref(self):
        if self._project_ref is None:
            data = self._get(
                "project", params={"query": f'(Name = "{config.RALLY_PROJECT}")', "fetch": "ObjectID"}
            )
            results = data["QueryResult"]["Results"]
            if not results:
                raise ValueError(f'Rally project named "{config.RALLY_PROJECT}" not found')
            if len(results) > 1:
                raise ValueError(
                    f'Multiple Rally projects named "{config.RALLY_PROJECT}" found — '
                    "rename rally.project in config.yaml to a value that's unique in your Rally subscription."
                )
            self._project_ref = results[0]["_ref"]
        return self._project_ref

    @staticmethod
    def _or_query(clauses):
        query = clauses[0]
        for clause in clauses[1:]:
            query = f"({query} OR {clause})"
        return query

    @classmethod
    def _build_query(cls):
        query = f'(State != "{config.RALLY_NOT_STATE}")'
        if config.RALLY_OWNERS:
            owner_clauses = [f'(Owner.DisplayName = "{o}")' for o in config.RALLY_OWNERS]
            query = f"({query} AND {cls._or_query(owner_clauses)})"
        return query

    def list_open_defects(self):
        params = {
            "project": self.project_ref(),
            "projectScopeDown": "true",
            "query": self._build_query(),
            "fetch": "FormattedID,Name,Description,State,Severity,Environment,Owner,CreationDate,TargetDate",
            "pagesize": 200,
            "start": 1,
        }
        defects = []
        while True:
            data = self._get("defect", params=params)
            result = data["QueryResult"]
            for item in result["Results"]:
                defects.append(
                    {
                        "id": item["FormattedID"],
                        "ref": item["_ref"],
                        "name": item["Name"],
                        "description": _html_to_text(item.get("Description")),
                        "state": item["State"],
                        "severity": item.get("Severity"),
                        "environment": item.get("Environment"),
                        "owner": (item.get("Owner") or {}).get("_refObjectName"),
                        "created": item.get("CreationDate"),
                        "target_date": item.get("TargetDate"),
                    }
                )
            if result["StartIndex"] + result["PageSize"] > result["TotalResultCount"]:
                break
            params["start"] = result["StartIndex"] + result["PageSize"]
        return defects

    def get_attachments(self, defect_ref):
        data = self._get(
            "attachment",
            params={"query": f'(Artifact = "{defect_ref}")', "fetch": "Name,ContentType,Size,Content"},
        )
        attachments = []
        for item in data["QueryResult"]["Results"]:
            content = item.get("Content") or {}
            attachments.append(
                {
                    "name": item["Name"],
                    "content_type": item.get("ContentType") or "application/octet-stream",
                    "content_ref": content.get("_ref"),
                }
            )
        return attachments

    def get_attachment_bytes(self, content_ref):
        resp = self.session.get(content_ref, params={"fetch": "Content"})
        resp.raise_for_status()
        data = resp.json()
        b64 = data["AttachmentContent"]["Content"]
        return base64.b64decode(b64)

    def get_defect_summary(self, formatted_id):
        data = self._get("defect", params={"query": f'(FormattedID = "{formatted_id}")', "fetch": "State,TargetDate"})
        results = data["QueryResult"]["Results"]
        if not results:
            raise ValueError(f'Rally defect "{formatted_id}" not found')
        item = results[0]
        return {"state": item.get("State"), "target_date": item.get("TargetDate")}

    def get_latest_comment(self, formatted_id):
        data = self._get(
            "conversationpost",
            params={
                "query": f'(Artifact.FormattedID = "{formatted_id}")',
                "fetch": "Text,User,CreationDate",
                "order": "CreationDate DESC",
                "pagesize": 1,
            },
        )
        results = data["QueryResult"]["Results"]
        if not results:
            return None
        item = results[0]
        return {
            "text": _html_to_text(item.get("Text")),
            "author": (item.get("User") or {}).get("_refObjectName"),
            "created": item.get("CreationDate"),
        }

    def list_comments(self, formatted_id):
        """All Rally discussion posts for a defect, oldest first."""
        posts = []
        params = {
            "query": f'(Artifact.FormattedID = "{formatted_id}")',
            "fetch": "Text,User,CreationDate",
            "order": "CreationDate ASC",
            "pagesize": 200,
            "start": 1,
        }
        while True:
            data = self._get("conversationpost", params=params)
            result = data["QueryResult"]
            for item in result["Results"]:
                posts.append(
                    {
                        "text": _html_to_text(item.get("Text")),
                        "author": (item.get("User") or {}).get("_refObjectName"),
                        "created": item.get("CreationDate"),
                    }
                )
            if result["StartIndex"] + result["PageSize"] > result["TotalResultCount"]:
                break
            params["start"] = result["StartIndex"] + result["PageSize"]
        return posts
