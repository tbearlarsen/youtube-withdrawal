# YouTube Withdrawal

A deliberate viewing layer on top of [TubeArchivist](https://github.com/tubearchivist/tubearchivist).

TubeArchivist passively downloads everything from every channel you follow. YouTube Withdrawal sits in front of it and adds a choice: you browse what's waiting in the queue, and decide what you actually want. Videos are only downloaded when you request them.

---

## How it works

TubeArchivist remains the engine. It handles subscriptions, downloading, storage, and indexing. YouTube Withdrawal is a control layer that talks to the TubeArchivist API:

```
Your browser
    │
    ▼
YouTube Withdrawal   ← browse, request, configure
    │  (TA API)
    ▼
TubeArchivist        ← downloads, stores, indexes
    │
    ▼
Your media library   (Jellyfin, Plex, etc.)
```

There is no separate database. No duplicate download logic. The five JSON files in `data/` store only what TA's API cannot — your favorites, requested videos, auto-download settings, stats, and one app preference.

---

## Features

- **Home feed** — pending videos from favorited channels, newest first, filtered to regular videos only (no shorts or streams)
- **Channel browser** — all TubeArchivist subscriptions with pending counts, sortable by name, pending count, or favorites-first
- **Channel detail** — tabs for pending, downloaded, and ignored videos; per-channel controls to request all, ignore all, restore ignored, subscribe/unsubscribe, favorite, and enable auto-download
- **Subscribe from the app** — search by channel URL, @handle, or YouTube channel ID; resolves the channel via yt-dlp without leaving the app
- **Video request** — click Request on any pending video to queue it for immediate download in TubeArchivist
- **Video detail** — full info page for any video, whether pending or already downloaded
- **Queue** — what you've requested that hasn't finished downloading yet
- **Downloads** — your full downloaded library with Jellyfin watch-progress bars
- **Auto-download** — per-channel toggle that automatically requests every new pending video from that channel
- **Settings** — directly controls TubeArchivist configuration via its API: subtitles, SponsorBlock, download format, comments, speed limits, subscription scan schedule, videos indexed per scan, and more
- **Backlog cleanup** — bulk-ignore videos older than a chosen age, or purge all pending shorts and streams
- **Light / dark / system theme** — stored in the browser; no server-side account needed

---

## Requirements

- [TubeArchivist](https://github.com/tubearchivist/tubearchivist) running and accessible via HTTP
- Docker and Docker Compose
- Optional: [Jellyfin](https://jellyfin.org/) with the [TubeArchivist Metadata plugin](https://github.com/tubearchivist/tubearchivist-jf) for watch-progress bars

---

## Deployment

### Option A — Same Docker host as TubeArchivist (recommended)

Join TubeArchivist's Docker network so the two containers communicate over the internal hostname `tubearchivist`, with no ports exposed between them.

Create a directory for the app and add a `compose.yaml`:

```yaml
services:
  youtube-withdrawal:
    image: ghcr.io/tbearlarsen/youtube-withdrawal:latest
    container_name: youtube-withdrawal
    restart: unless-stopped
    ports:
      - "8080:8080"
    environment:
      - TA_URL=http://tubearchivist:8000
      - TA_API_KEY=${TA_API_KEY}
    volumes:
      - ./data:/app/data
    networks:
      - tubearchivist_default

networks:
  tubearchivist_default:
    external: true
```

Create a `.env` file alongside it:

```
TA_API_KEY=your_api_key_here
```

Start it:

```bash
docker compose up -d
```

Access the app at `http://your-host:8080`.

> The network name `tubearchivist_default` assumes TubeArchivist was started with Docker Compose from a directory named `tubearchivist`. If it differs, run `docker network ls` to find the correct name and update the `networks` section accordingly.

---

### Option B — TubeArchivist on a different host or network

Set `TA_URL` to TubeArchivist's externally reachable address. The `networks` section is not needed.

```yaml
services:
  youtube-withdrawal:
    image: ghcr.io/tbearlarsen/youtube-withdrawal:latest
    container_name: youtube-withdrawal
    restart: unless-stopped
    ports:
      - "8080:8080"
    environment:
      - TA_URL=http://192.168.1.50:8001
      - TA_API_KEY=${TA_API_KEY}
    volumes:
      - ./data:/app/data
```

---

### Build from source

```bash
git clone https://github.com/tbearlarsen/youtube-withdrawal.git
cd youtube-withdrawal
cp .env.example .env
# Edit .env and set TA_API_KEY (and optionally TA_URL)
docker compose up -d --build
```

---

## Configuration

### Environment variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `TA_API_KEY` | Yes | — | TubeArchivist API key. Find it in TubeArchivist → Settings → User. |
| `TA_URL` | No | `http://tubearchivist:8000` | Base URL of your TubeArchivist instance. |

### In-app settings

Everything else is configured in the app's Settings page. All download and subscription settings are applied directly to TubeArchivist via its API — there is no duplicate configuration layer.

---

## First-time setup

1. Open the app and go to **Settings**.
2. Under **Maintenance → Scan subscriptions**, click **Scan now** to pull in your latest subscriptions and pending videos from TubeArchivist.
3. Go to **Library → Channels** and star the channels you want on your home feed.
4. Optionally set an auto-scan schedule so TubeArchivist picks up new videos on a regular cadence.
5. If you have a large backlog you'd rather ignore, use **Backlog Cleanup → Start Fresh** to bulk-ignore everything older than a chosen age.

---

## Features in depth

### Home feed

Shows pending videos (not yet downloaded) from your favorited channels, sorted by publish date. Capped at 200 videos. Only regular videos are shown — shorts and streams are filtered out so they don't pollute the feed.

Click **Request** on any video to queue it for download. TubeArchivist will pick it up on its next download cycle.

### Channel browser

Lists all channels you're subscribed to in TubeArchivist, with a badge showing how many pending videos each has. Sort options: favorites first, A→Z, Z→A, most pending, fewest pending.

**Subscribing to a new channel**: use the search box at the top of the Channels page. Enter a `@handle`, a full YouTube channel URL, or a raw `UCxxxxxxxx` channel ID. The app resolves the channel via yt-dlp and lets you subscribe without leaving YouTube Withdrawal. The channel appears in TubeArchivist after its next subscription scan.

### Channel detail

Click any channel to see three tabs:

- **Pending** — videos waiting to be downloaded. Request individually or request all at once.
- **Downloaded** — videos already in your library.
- **Ignored** — videos you've dismissed. Restore individually or restore all at once.

Per-channel actions in the header: toggle favorite (shows on home feed), toggle auto-download, ignore all pending, subscribe/unsubscribe.

### Auto-download

When enabled for a channel, YouTube Withdrawal automatically requests every pending video from that channel. This bypasses the manual selection step — useful for channels where you always want everything.

Auto-download is tracked locally in `data/auto_download.json` because TubeArchivist has no per-channel auto-start API. The actual downloading is still done by TubeArchivist; the app just sets each video's status to `priority` in TA's queue.

When you enable auto-download for a channel, all currently pending videos are requested immediately. Every 5 minutes, a background loop also checks for any newly added pending videos.

### Queue

Shows videos you've requested that are still pending or actively downloading. The queue is based on your local `requested.json`, not TubeArchivist's status, to avoid stale reads caused by Elasticsearch indexing lag after a status change.

Videos are removed from the queue automatically once TubeArchivist finishes downloading them (they'll move to **Downloads** instead). You can also remove a video from the queue manually, which restores it to pending status in TubeArchivist.

### Downloads

Your full downloaded library, pulled from TubeArchivist's video index. If you use Jellyfin with the TubeArchivist Metadata plugin, watch progress is synced back into TubeArchivist and displayed as a progress bar on each video card.

### Settings

The Settings page is a direct interface to TubeArchivist's configuration API. Changes here take effect in TubeArchivist immediately.

**Download settings** (applied to all channels):

| Setting | Notes |
|---|---|
| SponsorBlock | Fetches and stores segment data alongside each video |
| Auto-delete watched | Removes videos from disk N days after marking watched |
| Subtitles | Language codes (e.g. `en`, `en,de`), source type, and search indexing |
| Comments | Max count to archive and sort order |
| Return YouTube Dislike | Community dislike count via the RYD API |
| Embed metadata | Writes title, channel, date into the video file itself |
| Format string | yt-dlp `-f` value — leave blank for best available |
| Format sort | yt-dlp `--format-sort` value |
| Sleep interval | Seconds between downloads (default: 10) |
| Speed limit | Cap in KB/s |
| Throttle detection | yt-dlp restarts if speed drops below this KB/s |
| Extractor language | Preferred language for metadata extraction |

**Subscription scan** (under Maintenance):

- **Scan now** — triggers an immediate subscription scan in TubeArchivist.
- **Auto-scan schedule** — sets TubeArchivist's native Celery beat schedule for `update_subscribed`. Options from every hour to daily at 3 AM.
- **Videos indexed per scan** — controls how many videos TubeArchivist indexes per channel per scan, separately for videos, shorts, and live streams. Set shorts and streams to 0 to exclude them entirely.

**Backlog cleanup**:

- **Start Fresh** — bulk-ignores all pending videos older than a chosen age (30 days to 1 year). Useful after subscribing to many channels at once.
- **Purge shorts & streams** — ignores all pending shorts and live streams in the queue.

**Watch link**: optionally adds a **Watch** tab to the navigation bar pointing to any URL — useful for linking directly to your Jellyfin or Plex instance.

---

## Jellyfin integration

If you use Jellyfin with the [TubeArchivist Metadata plugin](https://github.com/tubearchivist/tubearchivist-jf), watch progress can be synced from Jellyfin back into TubeArchivist. YouTube Withdrawal reads this progress and displays it as a thin bar at the bottom of each video card in the Downloads view.

### Setup

1. Install the TubeArchivist Metadata plugin in Jellyfin (Repositories → TubeArchivist).
2. In Jellyfin → Plugins → TubeArchivist → Configure:
   - Set **TubeArchivist URL** and **API key**.
   - Set **JF Usernames To** to your Jellyfin username.
   - Enable **Sync progress from Jellyfin to TubeArchivist**.
   - Add an interval trigger (e.g. hourly) to the **JF → TubeArchivist Progress Sync** task.
3. Run the sync task once manually to import existing progress.

After that, watch progress updates in Jellyfin will propagate to TubeArchivist and appear in YouTube Withdrawal automatically.

---

## Persistent data

The `data/` volume holds five small JSON files. They require no migration — missing files are created with safe defaults on first write.

| File | Contents |
|---|---|
| `favorites.json` | Ordered list of channel IDs pinned to the home feed |
| `requested.json` | Set of video IDs you've queued for download |
| `auto_download.json` | List of channel IDs with auto-download enabled |
| `stats.json` | Weekly request counts (keyed by ISO week, e.g. `"2025-W24": 12`) |
| `settings.json` | App-level preferences (`watch_url`) |

All TubeArchivist configuration (download settings, subscription sizes, scan schedule) lives in TubeArchivist itself and is never duplicated here.

---

## Architecture notes

**Why a local requested tracker?** When YouTube Withdrawal sets a video's status to `priority` in TubeArchivist, the change goes into Elasticsearch with a short indexing delay. Immediately reading the video back via the API may still return `pending`. The local `requested.json` provides optimistic UI state — it's reconciled against TubeArchivist's actual pending queue on startup and during queue page loads.

**Why local auto-download tracking?** TubeArchivist has no per-channel auto-start API. The app tracks which channels have it enabled locally and uses TubeArchivist's priority download mechanism to fulfil it. The actual downloading is entirely TubeArchivist's responsibility.

**yt-dlp in the image**: The Docker image ships yt-dlp (downloaded at build time from the latest GitHub release). It is only used for channel resolution when subscribing — to convert a `@handle` or channel URL into a `UCxxxxxxxxx` channel ID. Downloads are always handled by TubeArchivist.

---

## Contributing

Issues and pull requests are welcome. The stack is intentionally minimal — FastAPI, Jinja2, HTMX, Tailwind via CDN. No build step. No JavaScript framework. Adding features that replicate what TubeArchivist already does natively (scheduling, download management, indexing) is out of scope by design.

To run locally:

```bash
git clone https://github.com/tbearlarsen/youtube-withdrawal.git
cd youtube-withdrawal
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env — set TA_API_KEY and TA_URL
uvicorn app.main:app --reload
```
