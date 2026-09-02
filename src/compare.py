from . import config


def _strip_prefix(value):
    if not value:
        return None
    prefix = config.RALLY_ID_PREFIX
    if prefix and value.startswith(prefix):
        return value[len(prefix):]
    return value


def compare_defects(rally_defects, zdr_defects):
    zdr_by_rally_id = {}
    for issue in zdr_defects:
        rally_id = _strip_prefix(issue["rally_id"])
        if rally_id:
            zdr_by_rally_id.setdefault(rally_id, []).append(issue)

    matched = []
    missing_in_zdr = []
    for defect in rally_defects:
        hits = zdr_by_rally_id.get(defect["id"])
        if hits:
            matched.append({"rally": defect, "zdr": hits})
        else:
            missing_in_zdr.append(defect)

    rally_ids = {d["id"] for d in rally_defects}
    orphaned_in_zdr = [
        issue
        for issue in zdr_defects
        if issue["rally_id"] and _strip_prefix(issue["rally_id"]) not in rally_ids
    ]

    return {
        "matched": matched,
        "missing_in_zdr": missing_in_zdr,
        "orphaned_in_zdr": orphaned_in_zdr,
    }
