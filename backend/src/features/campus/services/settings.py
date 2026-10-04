"""Admin settings of the campus assistant, all stored as strings in the settings table."""
import json
from dataclasses import asdict, dataclass

from src.features.admin.repository import settings as db
from src.limits import CAMPUS_CHAT_RETENTION_DAYS

KEY_SITEMAP_URL = "campus_sitemap_url"
KEY_URL_INCLUDE = "campus_url_include"
KEY_URL_EXCLUDE = "campus_url_exclude"
KEY_MAP_URL = "campus_map_url"
KEY_RETENTION_DAYS = "campus_chat_retention_days"
KEY_CRAWL_STATUS = "campus_crawl_status"

_RETENTION_MAX = 3650


@dataclass
class CampusSettings:
    sitemap_url: str = ""
    url_include: str = ""
    url_exclude: str = ""
    map_url: str = ""
    retention_days: int = CAMPUS_CHAT_RETENTION_DAYS

    def as_dict(self) -> dict:
        return asdict(self)


def clamp_retention(value) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        return CAMPUS_CHAT_RETENTION_DAYS
    return max(0, min(_RETENTION_MAX, n))


def read() -> CampusSettings:
    return CampusSettings(
        sitemap_url=db.get_setting(KEY_SITEMAP_URL, "").strip(),
        url_include=db.get_setting(KEY_URL_INCLUDE, ""),
        url_exclude=db.get_setting(KEY_URL_EXCLUDE, ""),
        map_url=db.get_setting(KEY_MAP_URL, "").strip(),
        retention_days=clamp_retention(db.get_setting(KEY_RETENTION_DAYS, str(CAMPUS_CHAT_RETENTION_DAYS))),
    )


def write(values: dict) -> CampusSettings:
    """Stores only the known fields, unknown ones are ignored."""
    text_keys = {
        "sitemap_url": KEY_SITEMAP_URL, "url_include": KEY_URL_INCLUDE, "url_exclude": KEY_URL_EXCLUDE,
        "map_url": KEY_MAP_URL,
    }
    for field, key in text_keys.items():
        if field in values and values[field] is not None:
            db.set_setting(key, str(values[field]).strip())
    if "retention_days" in values and values["retention_days"] is not None:
        db.set_setting(KEY_RETENTION_DAYS, str(clamp_retention(values["retention_days"])))
    return read()


def crawl_status() -> dict:
    raw = db.get_setting(KEY_CRAWL_STATUS, "")
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except ValueError:
        return {}


def set_crawl_status(status: dict) -> None:
    db.set_setting(KEY_CRAWL_STATUS, json.dumps(status))
