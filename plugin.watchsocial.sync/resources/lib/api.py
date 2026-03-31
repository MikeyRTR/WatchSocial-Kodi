"""
WatchSocial API client for Kodi.

Handles authenticated requests to the WatchSocial API.
Auth is via Bearer token (Supabase JWT) stored in addon settings.
"""

import json

try:
    from urllib.request import Request, urlopen
    from urllib.error import URLError, HTTPError
    from urllib.parse import urlencode, quote
except ImportError:
    from urllib2 import Request, urlopen, URLError, HTTPError
    from urllib import urlencode, quote

import xbmc
import xbmcaddon

ADDON = xbmcaddon.Addon()
ADDON_ID = ADDON.getAddonInfo("id")
USER_AGENT = "WatchSocial-Kodi/1.0"
TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/w500"
TMDB_FANART_BASE = "https://image.tmdb.org/t/p/w1280"


def log(msg, level=xbmc.LOGINFO):
    xbmc.log("[{}] {}".format(ADDON_ID, msg), level)


def get_base_url():
    url = ADDON.getSetting("base_url").strip().rstrip("/")
    return url if url else ""


def get_auth_token():
    return ADDON.getSetting("auth_token").strip()


def api_request(path, method="GET", data=None, params=None):
    """Make an authenticated request to the WatchSocial API."""
    base = get_base_url()
    if not base:
        return None

    url = "{}/api/v1{}".format(base, path)
    if params:
        url += "?" + urlencode(params)

    body = None
    if data is not None:
        body = json.dumps(data).encode("utf-8")

    req = Request(url, data=body)
    req.add_header("User-Agent", USER_AGENT)
    req.add_header("Accept", "application/json")

    token = get_auth_token()
    if token:
        req.add_header("Authorization", "Bearer " + token)

    if body:
        req.add_header("Content-Type", "application/json")

    if method not in ("GET", "POST"):
        req.get_method = lambda: method

    try:
        resp = urlopen(req, timeout=15)
        content = resp.read().decode("utf-8")
        return json.loads(content) if content else {}
    except HTTPError as e:
        log("API error {}: {} {}".format(path, e.code, e.reason), xbmc.LOGWARNING)
        return None
    except URLError as e:
        log("API connection error {}: {}".format(path, e.reason), xbmc.LOGWARNING)
        return None
    except Exception as e:
        log("API error {}: {}".format(path, str(e)), xbmc.LOGWARNING)
        return None


# ── Catalog endpoints ──

def search(query, limit=20):
    return api_request("/search", params={"q": query, "limit": str(limit)})


def get_trending():
    return api_request("/trending")


def get_discover_batch(content_type="tv"):
    t = "movies" if content_type == "movie" else "tv"
    return api_request("/discover/batch", params={"type": t})


def get_show(show_id):
    return api_request("/shows/{}".format(quote(str(show_id), safe="")))


def get_episodes(show_id, season=None):
    params = {}
    if season is not None:
        params["season"] = str(season)
    return api_request(
        "/shows/{}/episodes".format(quote(str(show_id), safe="")),
        params=params if params else None,
    )


def get_calendar(start_date=None, end_date=None, upcoming=False):
    params = {}
    if upcoming:
        params["upcoming"] = "true"
    elif start_date and end_date:
        params["startDate"] = start_date
        params["endDate"] = end_date
    return api_request("/calendar", params=params)


# ── User-specific endpoints ──

def get_my_shows():
    """Fetch the current user's followed shows."""
    token = get_auth_token()
    if not token:
        return []
    return api_request("/shows/following")


def get_watched_episodes(show_id):
    """Get watched episode map for a show: { episodeId: { count, lastWatchedAt } }"""
    return api_request(
        "/episodes/shows/{}/episodes/watched".format(quote(str(show_id), safe=""))
    )


def get_lists(filter_type="my"):
    return api_request("/lists", params={"filter": filter_type})


def get_viewing_history():
    return api_request("/viewing-history")
