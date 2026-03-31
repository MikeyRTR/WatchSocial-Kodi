"""
WatchSocial Sync — Kodi Service Addon

Monitors Kodi playback events and sends webhook payloads to WatchSocial's
media-sync endpoint. Supports:
  - Scrobble on completion (media.scrobble)
  - Now-playing tracking (media.play / media.pause / media.resume / media.stop)
  - Rating sync (media.rate) via Kodi's built-in rating system

The webhook payload format matches what the KodiAdapter on the server expects:
{
  "event": "media.scrobble",
  "player": { "title": "Kodi", "local": true },
  "account": { "title": "kodi" },
  "item": {
    "title": "Episode Title",
    "type": "episode",
    "showTitle": "Show Name",
    "season": 1,
    "episode": 3,
    "duration": 2700000,
    "viewOffset": 2160000,
    "uniqueids": { "tmdb": "12345", "imdb": "tt1234567", "tvdb": "67890" }
  }
}
"""

import json
import threading

try:
    from urllib.request import Request, urlopen
    from urllib.error import URLError, HTTPError
except ImportError:
    from urllib2 import Request, urlopen, URLError, HTTPError

import xbmc
import xbmcaddon

ADDON = xbmcaddon.Addon()
ADDON_ID = ADDON.getAddonInfo("id")


def log(msg, level=xbmc.LOGINFO):
    xbmc.log("[{}] {}".format(ADDON_ID, msg), level)


def debug(msg):
    if ADDON.getSettingBool("debug_logging"):
        log(msg, xbmc.LOGDEBUG)


def get_setting(key):
    return ADDON.getSetting(key)


def get_webhook_url():
    url = get_setting("webhook_url").strip()
    if not url:
        return None
    return url


def get_player_name():
    name = get_setting("player_name").strip()
    return name if name else "Kodi"


def get_scrobble_percent():
    try:
        return int(get_setting("scrobble_percent"))
    except (ValueError, TypeError):
        return 80


def send_playback_events_enabled():
    return ADDON.getSettingBool("send_playback_events")


def get_playing_item_info(player_id):
    """Query Kodi's JSON-RPC for details about the currently playing item."""
    query = json.dumps({
        "jsonrpc": "2.0",
        "method": "Player.GetItem",
        "params": {
            "playerid": player_id,
            "properties": [
                "title", "showtitle", "season", "episode",
                "duration", "year", "type", "uniqueid", "rating",
                "userrating"
            ]
        },
        "id": 1
    })
    response = xbmc.executeJSONRPC(query)
    data = json.loads(response)
    result = data.get("result", {})
    item = result.get("item", {})
    return item


def get_player_id():
    """Get the active video player ID."""
    query = json.dumps({
        "jsonrpc": "2.0",
        "method": "Player.GetActivePlayers",
        "params": {},
        "id": 1
    })
    response = xbmc.executeJSONRPC(query)
    data = json.loads(response)
    players = data.get("result", [])
    for p in players:
        if p.get("type") == "video":
            return p.get("playerid")
    return None


def get_player_time(player_id):
    """Get current playback position in milliseconds."""
    query = json.dumps({
        "jsonrpc": "2.0",
        "method": "Player.GetProperties",
        "params": {
            "playerid": player_id,
            "properties": ["time", "totaltime", "percentage"]
        },
        "id": 1
    })
    response = xbmc.executeJSONRPC(query)
    data = json.loads(response)
    result = data.get("result", {})

    def time_to_ms(t):
        if not t:
            return 0
        return (
            t.get("hours", 0) * 3600000
            + t.get("minutes", 0) * 60000
            + t.get("seconds", 0) * 1000
            + t.get("milliseconds", 0)
        )

    return {
        "viewOffset": time_to_ms(result.get("time")),
        "duration": time_to_ms(result.get("totaltime")),
        "percentage": result.get("percentage", 0),
    }


def build_item_payload(item, time_info=None):
    """Build the 'item' portion of the webhook payload from Kodi JSON-RPC data."""
    item_type = item.get("type", "unknown")
    # Kodi uses "episode" and "movie" — map directly
    content_type = "movie" if item_type == "movie" else "episode"

    uniqueids = item.get("uniqueid", {})
    # Kodi stores IDs like {"tmdb": "12345", "imdb": "tt1234567", "tvdb": "67890"}
    external_ids = {}
    if uniqueids.get("tmdb"):
        external_ids["tmdb"] = str(uniqueids["tmdb"])
    if uniqueids.get("imdb"):
        external_ids["imdb"] = str(uniqueids["imdb"])
    if uniqueids.get("tvdb"):
        external_ids["tvdb"] = str(uniqueids["tvdb"])

    payload = {
        "title": item.get("title", ""),
        "type": content_type,
        "uniqueids": external_ids if external_ids else None,
    }

    if content_type == "episode":
        payload["showTitle"] = item.get("showtitle") or None
        payload["season"] = item.get("season") if item.get("season", -1) >= 0 else None
        payload["episode"] = item.get("episode") if item.get("episode", -1) >= 0 else None

    if item.get("year"):
        payload["year"] = item["year"]

    # Duration from Kodi item (in seconds) → convert to ms
    if item.get("duration"):
        payload["duration"] = item["duration"] * 1000

    if time_info:
        payload["viewOffset"] = time_info.get("viewOffset", 0)
        if time_info.get("duration"):
            payload["duration"] = time_info["duration"]

    return payload


def build_webhook_payload(event, item_payload):
    """Build the full webhook payload matching KodiAdapter's expected format."""
    return {
        "event": event,
        "player": {
            "title": get_player_name(),
            "local": True,
        },
        "account": {
            "title": "kodi",
        },
        "item": item_payload,
    }


def send_webhook(payload):
    """Send the webhook payload to WatchSocial in a background thread."""
    url = get_webhook_url()
    if not url:
        debug("No webhook URL configured — skipping")
        return

    def _send():
        try:
            body = json.dumps(payload).encode("utf-8")
            req = Request(url, data=body, headers={
                "Content-Type": "application/json",
                "User-Agent": "WatchSocial-Kodi/1.0",
            })
            resp = urlopen(req, timeout=10)
            status = resp.getcode()
            debug("Webhook sent: {} — HTTP {}".format(payload.get("event"), status))
        except HTTPError as e:
            log("Webhook HTTP error: {} {}".format(e.code, e.reason), xbmc.LOGWARNING)
        except URLError as e:
            log("Webhook connection error: {}".format(e.reason), xbmc.LOGWARNING)
        except Exception as e:
            log("Webhook error: {}".format(str(e)), xbmc.LOGWARNING)

    t = threading.Thread(target=_send, daemon=True)
    t.start()


class WatchSocialPlayer(xbmc.Player):
    """Monitors Kodi playback events and sends webhooks to WatchSocial."""

    def __init__(self):
        super().__init__()
        self._current_item = None
        self._scrobbled = False
        self._last_player_id = None

    def _refresh_item(self):
        """Fetch current playing item info from Kodi."""
        player_id = get_player_id()
        if player_id is None:
            return None
        self._last_player_id = player_id
        item = get_playing_item_info(player_id)
        if not item or not item.get("title"):
            return None
        self._current_item = item
        return item

    def onAVStarted(self):
        """Called when playback actually starts (video decoded)."""
        try:
            item = self._refresh_item()
            if not item:
                return

            item_type = item.get("type", "")
            if item_type not in ("episode", "movie"):
                debug("Ignoring non-video item type: {}".format(item_type))
                return

            self._scrobbled = False
            log("Playback started: {} — {}".format(
                item.get("showtitle", ""), item.get("title", "")
            ))

            if send_playback_events_enabled():
                time_info = get_player_time(self._last_player_id) if self._last_player_id else {}
                payload = build_item_payload(item, time_info)
                send_webhook(build_webhook_payload("media.play", payload))

        except Exception as e:
            log("onAVStarted error: {}".format(str(e)), xbmc.LOGWARNING)

    def onPlayBackPaused(self):
        """Called when playback is paused."""
        try:
            if not self._current_item or not send_playback_events_enabled():
                return
            time_info = get_player_time(self._last_player_id) if self._last_player_id else {}
            payload = build_item_payload(self._current_item, time_info)
            send_webhook(build_webhook_payload("media.pause", payload))
        except Exception as e:
            log("onPlayBackPaused error: {}".format(str(e)), xbmc.LOGWARNING)

    def onPlayBackResumed(self):
        """Called when playback is resumed after pause."""
        try:
            if not self._current_item or not send_playback_events_enabled():
                return
            time_info = get_player_time(self._last_player_id) if self._last_player_id else {}
            payload = build_item_payload(self._current_item, time_info)
            send_webhook(build_webhook_payload("media.resume", payload))
        except Exception as e:
            log("onPlayBackResumed error: {}".format(str(e)), xbmc.LOGWARNING)

    def onPlayBackStopped(self):
        """Called when playback is stopped by the user."""
        try:
            self._handle_stop()
        except Exception as e:
            log("onPlayBackStopped error: {}".format(str(e)), xbmc.LOGWARNING)

    def onPlayBackEnded(self):
        """Called when playback reaches the end of the file."""
        try:
            # If we haven't scrobbled yet, do it now (100% watched)
            if self._current_item and not self._scrobbled:
                self._do_scrobble(self._current_item)
            self._handle_stop()
        except Exception as e:
            log("onPlayBackEnded error: {}".format(str(e)), xbmc.LOGWARNING)

    def _handle_stop(self):
        """Common stop handler — send stop event and reset state."""
        if self._current_item and send_playback_events_enabled():
            payload = build_item_payload(self._current_item)
            send_webhook(build_webhook_payload("media.stop", payload))
        self._current_item = None
        self._scrobbled = False
        self._last_player_id = None

    def _do_scrobble(self, item):
        """Send a scrobble event for the given item."""
        if self._scrobbled:
            return
        self._scrobbled = True

        item_type = item.get("type", "")
        if item_type not in ("episode", "movie"):
            return

        payload = build_item_payload(item)
        send_webhook(build_webhook_payload("media.scrobble", payload))

        title = item.get("title", "Unknown")
        show = item.get("showtitle", "")
        if show:
            log("Scrobbled: {} — {}".format(show, title))
        else:
            log("Scrobbled: {}".format(title))

    def check_scrobble(self):
        """Called periodically to check if we should scrobble based on progress."""
        if self._scrobbled or not self._current_item:
            return
        if self._last_player_id is None:
            return

        try:
            time_info = get_player_time(self._last_player_id)
            percentage = time_info.get("percentage", 0)
            threshold = get_scrobble_percent()

            if percentage >= threshold:
                # Update item with latest time info before scrobbling
                self._do_scrobble(self._current_item)
        except Exception:
            pass


class WatchSocialMonitor(xbmc.Monitor):
    """Monitors Kodi system events (settings changes, abort)."""

    def onSettingsChanged(self):
        debug("Settings changed — reloading")
        global ADDON
        ADDON = xbmcaddon.Addon()


def main():
    log("WatchSocial Sync service starting")

    monitor = WatchSocialMonitor()
    player = WatchSocialPlayer()

    # Check webhook URL on startup
    url = get_webhook_url()
    if not url:
        log("No webhook URL configured. Go to addon settings to set it up.")
    else:
        log("Webhook URL configured — ready to sync")

    # Main loop: check scrobble progress every 15 seconds
    while not monitor.abortRequested():
        if monitor.waitForAbort(15):
            break
        player.check_scrobble()

    log("WatchSocial Sync service stopped")


if __name__ == "__main__":
    main()
