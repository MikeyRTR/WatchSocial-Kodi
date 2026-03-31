# WatchSocial Kodi Addon

Full WatchSocial integration for Kodi — browse, track, and sync your TV shows and movies.

## What it does

Full WatchSocial integration for Kodi. Two features in one addon:

1. **Content Browser** — browse trending shows, discover new content, see your up next episodes, search the catalog, and view your lists. All from within Kodi. Each item carries TMDB/IMDB IDs so resolver addons (Seren, Fen, etc.) can find streams.

2. **Scrobbler** — automatically marks episodes/movies as watched on your WatchSocial profile when you finish watching in Kodi. Sends real-time now-playing updates with progress percentage.

## Browsable Menus

- **My Shows** — your followed shows with watch progress
- **Up Next** — next unwatched episodes from shows you follow (next 14 days)
- **Trending** — top trending shows on WatchSocial
- **Discover TV / Movies** — trending, recently added, top rated, recommendations
- **Calendar** — upcoming episodes grouped by air date
- **Search** — search WatchSocial's catalog (local DB + TMDB fallback)
- **My Lists** — your custom lists

## Installation

### 1. Create a Kodi connection in WatchSocial
1. Go to Settings > Media Sync > Add Connection > Kodi
2. Copy the webhook URL from the connection card

### 2. Get your auth token
1. Go to Settings > Integrations on the WatchSocial website
2. Copy your API auth token

### 3. Install the addon
1. Copy `plugin.watchsocial.sync` to your Kodi addons directory:
   - **Windows**: `%APPDATA%\Kodi\addons\`
   - **Linux**: `~/.kodi/addons/`
   - **macOS**: `~/Library/Application Support/Kodi/addons/`
   - **LibreELEC/OSMC**: `/storage/.kodi/addons/`
2. Restart Kodi
3. Go to Add-ons > My add-ons > Video add-ons > WatchSocial > Configure
4. Set your WatchSocial URL, auth token, and webhook URL

## Settings

| Setting | Description |
|---------|-------------|
| WatchSocial URL | Your site URL (e.g. `https://watchsocial.tv`) |
| Auth Token | API token from your WatchSocial settings (for browsing) |
| Webhook URL | Webhook URL from Media Sync connection (for scrobbling) |
| Scrobble at % | When to mark content as watched (default 80%) |
| Send now-playing | Toggle play/pause/resume/stop events |
| Player name | Device name shown on your profile |

## How resolver addons work with this

Each show/movie/episode item in the listings includes:
- `uniqueid` with TMDB and IMDB IDs
- Full metadata (title, year, season, episode, plot, etc.)

Resolver addons like Seren, Fen, or a4kSubtitles read these IDs to find and play streams. WatchSocial provides the catalog and tracking, the resolver provides the playback source.

## Requirements

- Kodi 19 (Matrix) or newer
- A WatchSocial account
- A resolver addon for actual playback (optional — browsing works without one)
