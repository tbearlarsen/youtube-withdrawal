# Deployment Infrastructure

Real, current state of where and how this app runs — confirmed 2026-09-01. Update this in place as the deployment changes; it's a snapshot of what's true now, not a history log. Primary source of record for this service is `home-server`'s `Services/vm101-youtube-withdrawal.md` and `Services/vm101-tubearchivist.md` (a sibling repo, kept in sync separately) — the facts below are copied here in full, not just linked, so a session working in this repo doesn't need to open another one to know where its own code runs.

## This app

- **Host:** VM101 (`10.0.0.101`), the home server's Docker host.
- **Public URL:** `https://withdrawal.sudheim.eu` (NPM reverse proxy, wildcard `*.sudheim.eu` SSL).
- **Port mapping:** host `8008` → container `8080`.
- **Compose:** `/docker/youtube-withdrawal/compose.yaml` on the server — its own stack, not merged into TubeArchivist's compose file (an earlier plan considered merging them; it ended up separate, joining TA's network instead — see `HANDOFF.md`).
- **Container name:** `youtube-withdrawal`.
- **Data volume:** `/docker/youtube-withdrawal/data/` (host) → `/app/data` (container) — the five JSON files described in `CLAUDE.md`'s Canonical Data section. No media stored here.
- **Docker network:** joins `tubearchivist_default` (external network) to reach TubeArchivist by container hostname, with no ports exposed between the two stacks.
- **Environment variables** (`/docker/youtube-withdrawal/.env` on the server): `TA_API_KEY` (secret), `TA_PUBLIC_URL=http://10.0.0.101:8001` (browser-facing link for the "Open TubeArchivist" button). `TA_URL=http://tubearchivist:8000` is set in the compose file itself (internal Docker network, server-to-server), not `.env`.

## Where Claude Code actually works

**Corrected 2026-09-02** — the 2026-09-01 note below was wrong in a way that matters; see `HANDOFF.md` correction #4.

Claude Code runs on VM101 via code-server, but in `/data/projects/youtube-withdrawal` — a **separate git checkout** from `/docker/youtube-withdrawal`, the one `docker compose` actually builds from. Confirmed by diffing the two directories: different `.git`, and `data/*.json` had already diverged (this checkout's copy is a stale snapshot from whenever it was cloned; `/docker/youtube-withdrawal/data/` is the live state). Same host, same filesystem (`/docker` is a locally-mounted disk, readable/writable directly from this checkout's shell), but not the same working directory.

More importantly: **this code-server container has no `docker` binary and no `docker.sock`** — confirmed via `which docker` (not found) and `ls /var/run/docker.sock` (does not exist), searched common paths, none found. Claude Code cannot run `docker`/`docker compose` from this environment at all, regardless of which checkout it's invoked from. The user runs all docker commands themselves, from wherever they actually have docker access; Claude's role is to edit compose/config files directly (it does have file write access to `/docker/*`) and hand over the exact commands to run, not to execute them.

~~As of 2026-09-01, going forward: directly on VM101 via code-server... Deploying is not a separate machine-to-machine step; it happens in place.~~ — superseded, see above.

## Deployment target: TubeArchivist (required dependency)

- **Host:** same VM101, port `8001`, LAN/WireGuard only — no public domain, no NPM proxy on TubeArchivist itself.
- **Compose:** `/docker/tubearchivist/compose.yaml`. Containers: `tubearchivist`, `archivist-es` (Elasticsearch), `archivist-redis`, `bgutil-provider` (added 2026-09-02, see below).
- **Media storage:** `/data/media/tubearchivist/` (CIFS-backed from CT100) — this app never touches media files directly, only TA's API.
- **ytdl-sub** (the tool this app replaced): fully retired as of 2026-09-01. TubeArchivist is the sole YouTube ingestion path now.
- **PO token provider (added 2026-09-02):** `bgutil-provider` (`brainicism/bgutil-ytdlp-pot-provider`), internal-only (`expose: 4416`, no host port). TA's `downloads.pot_provider_url` config points at `http://bgutil-provider:4416`. Required because YouTube now blocks unauthenticated yt-dlp requests with `403 Forbidden` without a valid PO token — this took down every priority download for a while before it was diagnosed (see `HANDOFF.md`). If downloads start failing with widespread 403s again, check this container is up (`docker ps --filter name=bgutil-provider`) before assuming anything else is wrong. TA's own docs note the provider image should be version-pinned to match TA's release rather than left on `latest` long-term — currently on `latest`, matching TA's own example compose; revisit if a future TA upgrade breaks compatibility.
- **SponsorBlock (enabled 2026-09-02):** `downloads.integrate_sponsorblock: true` in TA config. TA fetches segment timestamps from `sponsor.ajay.app` per video and stores them in Elasticsearch only (`sponsorblock` field on the video document) — never written to the media file itself, so this doesn't touch the archive and Jellyfin (which reads the raw file) has no visibility into it. Only usable by things that query TA's own API/DB, e.g. TA's own player, or a future tool in this app reading `sponsorblock.segments` off `/api/video/<id>/`. Videos downloaded before this was enabled show `sponsorblock: null` until reindexed.
- **Reindex interval tightened 2026-09-02:** `check_reindex` schedule's `config.days` changed from the TA default (90) to **1**, via `POST /api/task/schedule/check_reindex/`. Reason: `check_reindex` re-runs each video's full `build_json()` (including a fresh SponsorBlock fetch) for any video not refreshed in the last `days`, so at 90 it could take three months for a video downloaded right after publish to pick up SponsorBlock segments submitted later. The task itself only *runs* once daily (cron `0 12 *`, noon Europe/Copenhagen) regardless of `days`, so `1` is the practical maximum refresh frequency achievable here — there's no sub-day granularity available through this task. Tradeoff: this also re-touches other reindexed metadata (e.g. comments) daily instead of quarterly for the whole library, not just SponsorBlock — worth watching for unexpected load/API usage if the library grows large.

## Optional dependency: Jellyfin

If the TubeArchivist Metadata plugin is installed in Jellyfin, watch progress syncs Jellyfin → TubeArchivist → this app, shown as a progress bar on downloaded videos. Not required for the app's core functionality.

## Health checks

```bash
docker ps --filter name=youtube-withdrawal
curl -s http://10.0.0.101:8008/
```

## Update procedure

```bash
cd /docker/youtube-withdrawal
git pull
docker compose up -d --build
```
