# Directive: Deploy

## Purpose
Rebuild and restart the live container after a code change. This is the one genuinely repeatable operational workflow in this project — everything else here is feature/UX work, not process.

## When to run
Only when explicitly asked to deploy/redeploy — never automatically as part of Session Close, even after a commit+push. See `CLAUDE.md`'s Session Close section for why.

## Tool — Claude does not run this. The user does.

**Corrected 2026-09-02** (see `HANDOFF.md` correction #4): the code-server container Claude Code runs in has no `docker` binary and no `docker.sock` — confirmed absent, not a PATH issue. Claude cannot execute `execution/deploy.sh` (or any `docker`/`docker compose` command) itself, and per the user's standing instruction, wouldn't even if it technically could — docker commands are always run by the user, from wherever they actually have docker access.

Claude's job in a deploy:
1. Confirm the change is actually committed (`git status` clean, or explicitly told to deploy uncommitted work).
2. Hand the user this exact command in a copy-pasteable block:
   ```bash
   bash execution/deploy.sh
   ```
   (run from `/docker/youtube-withdrawal` — the actual compose/build directory, not necessarily wherever Claude's own checkout lives; see `context/infra.md`.)
3. Wait for the user to report back the result. If it exited non-zero, read its own printed diagnosis together — it already distinguishes "container didn't start" from "container's up but not responding" (most often a TubeArchivist connectivity problem, not this app's own code).

The script itself is still useful and still does the full pull/rebuild/restart/verify sequence with a hard pass/fail exit code — that part hasn't changed. What changed is who invokes it.

## Edge Cases
- If the script reports success but the deployed behavior still looks wrong, confirm the Docker build actually picked up the new code (check the image build timestamp) rather than assuming a passing health check means the right code shipped.
- This app has no separate staging environment — a deploy goes straight to the live, user-facing instance at `withdrawal.sudheim.eu`. There's no rollback mechanism beyond `git revert` + redeploy.

## Notes
Claude Code's own checkout (`/data/projects/youtube-withdrawal`) and the compose/deploy directory (`/docker/youtube-withdrawal`) are on the same VM101 host but are **separate git checkouts** — confirmed 2026-09-02, correcting the 2026-09-01 assumption that they were the same directory. `execution/deploy.sh` `cd`s to its own parent directory, so it must be run from a copy of the script that actually lives in `/docker/youtube-withdrawal` (the one `docker compose` builds from) — running a copy from Claude's own checkout would `cd` to the wrong place. Since the user is the one running the command anyway (see above), this mostly self-resolves: tell them to run it from `/docker/youtube-withdrawal`.
