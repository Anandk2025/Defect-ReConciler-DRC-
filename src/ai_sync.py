import re
import subprocess

from . import config

_PROMPT = """You are comparing the latest status comment on a Rally defect against the latest status comment on the corresponding ZDR (Jira) ticket for the same underlying issue.

Judge whether the two comments still reflect the same current context — same status, same next step, same blocker/owner — or whether they have diverged (one is stale, contradicts the other, or describes a different state of the issue).

Rally comment:
\"\"\"
{rally_text}
\"\"\"

ZDR comment:
\"\"\"
{zdr_text}
\"\"\"

Respond in exactly this format, nothing else:
STATUS: SYNCED or UNSYNCED
REASON: <one concise sentence explaining why>"""

_STATUS_RE = re.compile(r"STATUS:\s*(SYNCED|UNSYNCED)", re.IGNORECASE)
_REASON_RE = re.compile(r"REASON:\s*(.+)", re.IGNORECASE | re.DOTALL)


def check_comment_sync(rally_text, zdr_text):
    """Shells out to the locally installed, already-logged-in `claude` CLI
    (Claude Code) instead of calling the Anthropic API directly — this
    reuses your Claude.ai account login instead of needing a separate API
    key, Bedrock, or Vertex access."""
    prompt = _PROMPT.format(rally_text=rally_text, zdr_text=zdr_text)
    try:
        result = subprocess.run(
            ["claude", "-p", prompt, "--model", config.AI_MODEL],
            capture_output=True,
            text=True,
            timeout=60,
        )
    except FileNotFoundError:
        raise RuntimeError("`claude` CLI not found on PATH")
    except subprocess.TimeoutExpired:
        raise RuntimeError("claude CLI timed out")

    if result.returncode != 0:
        raise RuntimeError(f"claude CLI failed: {result.stderr.strip() or result.stdout.strip()}")

    text = result.stdout.strip()
    status_match = _STATUS_RE.search(text)
    reason_match = _REASON_RE.search(text)
    if not status_match:
        raise RuntimeError(f"Unexpected response from model: {text[:200]}")

    return {
        "status": "synced" if status_match.group(1).upper() == "SYNCED" else "unsynced",
        "reason": reason_match.group(1).strip() if reason_match else "",
    }
