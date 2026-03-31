"""
WatchSocial Kodi Plugin — Content Browser

Provides browsable directory listings inside Kodi:
  - My Shows (followed shows with watch progress)
  - Up Next (next unwatched episodes from followed shows)
  - Trending
  - Discover (TV / Movies)
  - Calendar (upcoming episodes)
  - Search
  - My Lists

Each item carries TMDB/IMDB IDs so resolver addons can find streams.
"""

import sys
import json

try:
    from urllib.parse import parse_qs, urlencode, quote
except ImportError:
    from urlparse import parse_qs
    from urllib import urlencode, quote

import xbmc
import xbmcgui
import xbmcplugin
import xbmcaddon

# Add resources/lib to path
ADDON = xbmcaddon.Addon()
ADDON_PATH = ADDON.getAddonInfo("path")
sys.path.insert(0, ADDON_PATH + "/resources/lib")

from api import (
    search, get_trending, get_discover_batch, get_show,
    get_episodes, get_calendar, get_watched_episodes,
    get_lists, get_base_url, get_auth_token,
    TMDB_IMAGE_BASE, TMDB_FANART_BASE,
)

HANDLE = int(sys.argv[1])
BASE_URL = sys.argv[0]


def build_url(action, **kwargs):
    params = {"action": action}
    params.update(kwargs)
    return "{}?{}".format(BASE_URL, urlencode(params))


def get_params():
    qs = sys.argv[2].lstrip("?")
    return {k: v[0] for k, v in parse_qs(qs).items()}


def add_directory(title, action, icon=None, fanart=None, **kwargs):
    """Add a folder item to the listing."""
    url = build_url(action, **kwargs)
    li = xbmcgui.ListItem(title)
    art = {}
    if icon:
        art["icon"] = icon
        art["thumb"] = icon
        art["poster"] = icon
    if fanart:
        art["fanart"] = fanart
    if art:
        li.setArt(art)
    xbmcplugin.addDirectoryItem(HANDLE, url, li, isFolder=True)


def add_show_item(show, is_folder=True):
    """Add a show/movie item with full metadata for resolver addons."""
    title = show.get("title") or show.get("showTitle") or "Unknown"
    show_id = show.get("id") or show.get("showId") or ""
    slug = show.get("slug") or show.get("showSlug") or str(show_id)
    poster = show.get("posterUrl") or show.get("showPosterUrl") or ""
    content_type = show.get("contentType", "tv")
    year = show.get("year")
    genres = show.get("genres", [])
    rating = show.get("rating") or show.get("communityRating")
    tmdb_id = show.get("tmdbId")
    network = show.get("network", "")

    if is_folder:
        url = build_url("show_detail", show_id=slug)
    else:
        url = build_url("play_movie", show_id=slug, title=title)

    li = xbmcgui.ListItem(title)

    # Art
    art = {}
    if poster:
        art["poster"] = poster
        art["thumb"] = poster
        art["icon"] = poster
    banner = show.get("bannerUrl", "")
    if banner:
        art["fanart"] = banner
    if art:
        li.setArt(art)

    # Info labels — these are what resolver addons read
    info = {"title": title, "mediatype": "tvshow" if content_type == "tv" else "movie"}
    if year:
        info["year"] = int(year)
    if genres and isinstance(genres, list):
        info["genre"] = genres
    if rating:
        info["rating"] = float(rating)
    if network:
        info["studio"] = network
    plot = show.get("description", "")
    if plot:
        info["plot"] = plot

    li.setInfo("video", info)

    # Unique IDs — critical for resolver addons (Seren, Fen, etc.)
    unique_ids = {}
    if tmdb_id:
        unique_ids["tmdb"] = str(tmdb_id)
    imdb_id = show.get("imdbId")
    if imdb_id:
        unique_ids["imdb"] = str(imdb_id)
    if unique_ids:
        li.setUniqueIDs(unique_ids, "tmdb" if tmdb_id else "imdb")

    xbmcplugin.addDirectoryItem(HANDLE, url, li, isFolder=is_folder)


def add_episode_item(ep, show_info=None, watched=False):
    """Add an episode item with metadata for resolver addons."""
    show_title = ep.get("showTitle") or (show_info or {}).get("title") or ""
    ep_title = ep.get("title") or ""
    season = ep.get("seasonNumber", 0)
    episode = ep.get("episodeNumber", 0)
    label = "{}x{:02d} - {}".format(season, episode, ep_title) if ep_title else "{}x{:02d}".format(season, episode)
    if show_title and not show_info:
        label = "{} — {}".format(show_title, label)

    show_id = ep.get("showId") or ep.get("showSlug") or ""
    ep_id = ep.get("id") or ""

    url = build_url(
        "play_episode",
        show_id=show_id,
        season=str(season),
        episode=str(episode),
        title=show_title,
    )

    li = xbmcgui.ListItem(label)

    # Art
    art = {}
    poster = ep.get("showPosterUrl") or (show_info or {}).get("posterUrl") or ""
    thumb = ep.get("thumbnailUrl") or ep.get("stillPath") or ""
    if poster:
        art["poster"] = poster
        art["icon"] = poster
    if thumb:
        if thumb.startswith("/"):
            thumb = "https://image.tmdb.org/t/p/w300" + thumb
        art["thumb"] = thumb
    banner = (show_info or {}).get("bannerUrl", "")
    if banner:
        art["fanart"] = banner
    if art:
        li.setArt(art)

    # Info
    info = {
        "title": ep_title,
        "tvshowtitle": show_title,
        "season": season,
        "episode": episode,
        "mediatype": "episode",
    }
    air_date = ep.get("airDate", "")
    if air_date:
        info["aired"] = air_date[:10]
    desc = ep.get("description", "")
    if desc:
        info["plot"] = desc
    runtime = ep.get("runtime")
    if runtime:
        info["duration"] = int(runtime) * 60 if int(runtime) < 1000 else int(runtime)
    if watched:
        info["playcount"] = 1

    li.setInfo("video", info)

    # Unique IDs for resolvers
    unique_ids = {}
    tmdb_id = (show_info or {}).get("tmdbId") or ep.get("tmdbId")
    if tmdb_id:
        unique_ids["tmdb"] = str(tmdb_id)
    imdb_id = (show_info or {}).get("imdbId")
    if imdb_id:
        unique_ids["imdb"] = str(imdb_id)
    if unique_ids:
        li.setUniqueIDs(unique_ids, "tmdb" if tmdb_id else "imdb")

    li.setProperty("IsPlayable", "true")
    xbmcplugin.addDirectoryItem(HANDLE, url, li, isFolder=False)
