"""The hint is produced in the same call as the exercise and lives in extras."""


def attach_hint(item: dict, roh: dict) -> None:
    """Puts the hint from the model answer into item['extras']."""
    tipp = roh.get("tip")
    tipp = tipp.strip() if isinstance(tipp, str) else ""
    if not tipp:
        return
    extras = item.get("extras")
    if not isinstance(extras, dict):
        extras = {}
        item["extras"] = extras
    extras["tip"] = tipp
