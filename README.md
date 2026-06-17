# YouTube Withdrawal

A deliberate viewing layer on top of [TubeArchivist](https://github.com/tubearchivist/tubearchivist).

Instead of passively downloading everything from every channel you follow, YouTube Withdrawal lets you browse what's waiting in your TubeArchivist queue and consciously choose what to watch. Videos only get downloaded when you request them.

## What it does

- **Home feed** — pending videos from channels you've marked as favorites, newest first
- **Browse channels** — all your TubeArchivist subscriptions with pending counts, sortable
- **Request videos** — click to queue a video for download in TubeArchivist
- **Queue** — what you've requested that's still downloading
- **Downloads** — your fully downloaded library with watch progress from Jellyfin
- **Settings** — controls TubeArchivist settings (subscription sizes, SponsorBlock, download options, scan schedule) directly via the TA API

## Requirements

- [TubeArchivist](https://github.com/tubearchivist/tubearchivist) running and accessible
- Docker + Docker Compose

## Setup

### 1. Get your TubeArchivist API key

In TubeArchivist → Settings → User → API key.

### 2. Run with Docker Compose

```yaml
services:
  youtube-withdrawal:
    image: ghcr.io/tbearlarsen/youtube-withdrawal:latest
    container_name: youtube-withdrawal
    restart: unless-stopped
    ports:
      - "8080:8080"
    environment:
      - TA_URL=http://tubearchivist:8000   # internal URL if on same Docker network
      - TA_API_KEY=your_api_key_here
    volumes:
      - ./data:/app/data
    networks:
      - tubearchivist_default              # join TA's network if running alongside it

networks:
  tubearchivist_default:
    external: true
```

If TubeArchivist is on a different host, set `TA_URL` to its external address (e.g. `http://192.168.1.10:8001`).

### 3. Build from source

```bash
git clone https://github.com/tbearlarsen/youtube-withdrawal.git
cd youtube-withdrawal
cp .env.example .env
# Edit .env and set TA_API_KEY
docker compose up -d --build
```

Access the app at `http://localhost:8080`.

## Environment variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `TA_API_KEY` | Yes | — | TubeArchivist API key |
| `TA_URL` | No | `http://tubearchivist:8000` | URL of your TubeArchivist instance |

## Persistent data

The `data/` volume holds five small JSON files:

| File | Purpose |
|---|---|
| `favorites.json` | Channels pinned to your home feed |
| `requested.json` | Videos you've queued for download |
| `auto_download.json` | Channels set to auto-request all new videos |
| `stats.json` | Weekly request counts |
| `settings.json` | App preferences (watch link, etc.) |

## Jellyfin integration

If you use [Jellyfin](https://jellyfin.org/) with TubeArchivist's Jellyfin plugin, watch progress syncs automatically and appears as progress bars on downloaded video cards.

## Philosophy

TubeArchivist is the engine — it handles downloading, storage, and indexing. YouTube Withdrawal is a control layer that sits in front of it, adding intentionality to what gets downloaded and surfacing it in a way that encourages deliberate choices over passive consumption.
