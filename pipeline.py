from . import config
from .compare import compare_defects
from .rally_client import RallyClient
from .zdr_client import ZDRClient


def run_comparison(on_progress=None):
    config.require_credentials()

    def notify(msg):
        if on_progress:
            on_progress(msg)

    notify("Fetching open defects from Rally...")
    rally_defects = RallyClient().list_open_defects()
    notify(f"  {len(rally_defects)} open Rally defects")

    notify("Fetching open defects from ZDR...")
    zdr_client = ZDRClient()
    zdr_open = zdr_client.list_open_defects()
    notify(f"  {len(zdr_open)} open ZDR defects")

    # Matching uses every linked ZDR ticket regardless of status, not just the
    # open ones — otherwise a defect whose ZDR ticket is already "Pending
    # Approval to Close" would wrongly show up as missing a ZDR ticket. The
    # exception is genuinely terminal statuses (Done, Cancelled) — a defect
    # linked only to a dead ticket should still count as missing one.
    zdr_all_linked = [
        i for i in zdr_client.list_all_linked_defects() if i["status"] not in config.ZDR_MATCHING_EXCLUDED_STATUSES
    ]

    return rally_defects, zdr_open, compare_defects(rally_defects, zdr_all_linked)


def create_zdr_from_rally(defect, rally_client=None, zdr_client=None, on_progress=None):
    """Create a ZDR ticket for a Rally defect and copy over its attachments."""
    rally_client = rally_client or RallyClient()
    zdr_client = zdr_client or ZDRClient()

    def notify(msg):
        if on_progress:
            on_progress(msg)

    zdr_key = zdr_client.create_defect(
        defect["id"],
        defect["name"],
        defect.get("description", ""),
        severity=defect.get("severity"),
        created=defect.get("created"),
        environment=defect.get("environment"),
    )
    notify(f"Created {zdr_key} for Rally defect {defect['id']}")

    attached, attach_errors = 0, []
    if defect.get("ref"):
        for att in rally_client.get_attachments(defect["ref"]):
            try:
                content = rally_client.get_attachment_bytes(att["content_ref"])
                zdr_client.add_attachment(zdr_key, att["name"], content, att["content_type"])
                attached += 1
            except Exception as e:
                attach_errors.append(f"{att['name']}: {e}")
    notify(f"  copied {attached} attachment(s)" + (f", {len(attach_errors)} failed" if attach_errors else ""))

    settings = config.RALLY_ON_ZDR_CREATED
    try:
        template = settings.get("comment_template")
        if template:
            rally_client.add_comment(defect["id"], template.format(zdr_key=zdr_key))
        fields = {}
        if settings.get("state"):
            fields["State"] = settings["state"]
        if settings.get("schedule_state"):
            fields["ScheduleState"] = settings["schedule_state"]
        if fields and defect.get("ref"):
            rally_client.update_fields(defect["ref"], fields)
        notify("  updated Rally defect with comment and status")
    except Exception as e:
        attach_errors.append(f"Rally defect update: {e}")

    return zdr_key, attached, attach_errors
