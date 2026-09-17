from . import config


def check_defect_status(rally_state, zdr_status):
    if not zdr_status:
        return {"status": "unsynced", "message": "ZDR ticket has no status."}
    if rally_state in config.SYNC_CHECK_RALLY_STATUSES:
        blocking = {s.lower() for s in config.SYNC_CHECK_ZDR_BLOCKING_STATUSES}
        if zdr_status.strip().lower() in blocking:
            return {
                "status": "unsynced",
                "message": (
                    f"Rally status is '{rally_state}' but ZDR status is '{zdr_status}' — "
                    f"ZDR shouldn't be in {', '.join(config.SYNC_CHECK_ZDR_BLOCKING_STATUSES)} "
                    f"while Rally is {rally_state}."
                ),
            }
        return {
            "status": "synced",
            "message": f"Rally status '{rally_state}' and ZDR status '{zdr_status}' are compatible.",
        }
    return {
        "status": "synced",
        "message": f"No status conflict rule applies when Rally status is '{rally_state}'.",
    }


def check_fix_eta(rally_target_date, zdr_qa_complete_date):
    rally_date = (rally_target_date or "")[:10]
    zdr_date = (zdr_qa_complete_date or "")[:10]
    if rally_date and zdr_date:
        if rally_date == zdr_date:
            return {"status": "synced", "message": f"Both Fix ETAs are {rally_date}."}
        return {
            "status": "unsynced",
            "message": f"Rally Fix ETA is {rally_date} but ZDR Fix ETA is {zdr_date}.",
        }
    if not rally_date and not zdr_date:
        return {"status": "synced", "message": "Neither system has a Fix ETA set."}
    if rally_date:
        return {"status": "unsynced", "message": f"Rally Fix ETA is {rally_date} but ZDR has no Fix ETA set."}
    return {"status": "unsynced", "message": f"ZDR Fix ETA is {zdr_date} but Rally has no Fix ETA set."}
