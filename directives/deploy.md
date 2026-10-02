# Directive: Deploy

## Purpose
Rebuild and restart the live container after a code change. This is the one genuinely repeatable operational workflow in this project — everything else here is feature/UX work, not process.

## When to run
Only when explicitly asked to deploy/redeploy — never automatically as part of Session Close, even after a commit+push. See `CLAUDE.md`'s Session Close section for why.

## Who runs it — Claude, not the user

**Corrected 2026-10-01** (see `HANDOFF.md` correction #10): the user does not run deploys by hand and doesn't want to — *"No you deploy it, I dont want to have to do anything."* Deploys are done by a Claude session with the access below. The earlier rule (2026-09-02: "the user always runs docker commands themselves, Claude hands over commands") is superseded.

A deploy needs:
1. File access to `/docker/youtube-withdrawal` on VM101 (any code-server session on VM101 has this), for the `git pull`.
2. SSH to VM101 as a docker-group user — `claude@10.0.0.101` — for `docker compose`.

**This project's own session has (1) but not (2)** — confirmed 2026-10-01: `ssh claude@10.0.0.101` is refused (`Permission denied (publickey,password)`), and the code-server container has no `docker` binary or socket. The **home-server session does have both** (confirmed by it deploying `c11165b` 2026-10-01). So from here: commit and push, then ask the home-server session to deploy (`ListAgents` → `SendMessage` to it), including the commit hash and anything the deploy needs to know. If no session with that access is running, say so to the user rather than handing them commands.

**Approval: resolved 2026-10-01.** The home-server session's auto-mode classifier blocked `deploy.sh` ("Production Deploy") on each run until the user approved it. The user has since added a permanent project allow rule there for exactly `bash /projects/youtube-withdrawal/execution/deploy.sh`, so deploys run without prompting. Other commands in that session are still classified normally, so invoke the script by exactly that path.

## Tool
```bash
bash /projects/youtube-withdrawal/execution/deploy.sh
```
Prefer this dev-checkout copy: the script uses an absolute `DEPLOY_DIR`, so it works from anywhere, and the copy in `/docker/youtube-withdrawal/execution/` is whatever the *last* deploy pulled — as of 2026-10-01 (deploy checkout at `943cc24`) that copy still has the restore bug fixed in `c4b5add`.

It does, with a hard pass/fail exit code:
1. Backs up `/docker/youtube-withdrawal/data/` to `/docker/youtube-withdrawal-data-backup/` (overwritten each deploy).
2. `git pull --ff-only` **locally** — not over SSH: as VM101's `claude` user, git refuses the checkout with "dubious ownership" (it's owned by a different user).
3. Restores live data files the pull removed or changed (`cmp -s` per file) — also on failure, via a trap. It deliberately doesn't blanket-copy: the container runs as root, so untouched data files are `root:root 0644` and unwritable by the deploying shell.
4. Over SSH: `docker compose up -d --build`, then checks the container is running and `http://10.0.0.101:8008/` responds.

Override the SSH target with `DEPLOY_SSH=user@host` and the key with `DEPLOY_SSH_KEY=/path` (default `/docker/.claude-secrets/vm101_ssh_key`, the VM101 key the home-server session uses — not in a default ssh location, so it must be passed explicitly). The script checks the key is readable before touching anything, so a missing key can't leave the checkout pulled with the old container still running.

## Edge Cases
- **Live data and git.** `data/*.json` is runtime state written by the running app in the deploy checkout. `favorites.json` and `requested.json` were tracked in git until 2026-10-01 despite `.gitignore` (added before the ignore rule), so the app's in-place edits made `git pull` either fail or risk overwriting them. The commit that untracked them *deletes* them from the deploy checkout's working tree when pulled — step 3's restore is what saves them. Never pull the deploy checkout by hand without the same backup/restore.
- **Checking data after a deploy:** `requested.json` and `stats.json` can legitimately differ from the pre-deploy backup on a live, in-use app — a request made around deploy time changes both, and the app's startup reconcile drops `requested.json` entries whose videos finished downloading. Compare against `/docker/youtube-withdrawal-data-backup/` and file mtimes rather than treating any mismatch as a failed restore. `categories.json`, `favorites.json`, `settings.json`, etc. should match unless the user changed them mid-deploy.
- If the script reports success but the deployed behavior still looks wrong, confirm the Docker build actually picked up the new code (check the image build timestamp) rather than assuming a passing health check means the right code shipped.
- This app has no separate staging environment — a deploy goes straight to the live, user-facing instance at `withdrawal.sudheim.eu`. There's no rollback mechanism beyond `git revert` + redeploy.

## Notes
Claude Code's own checkout (`/projects/youtube-withdrawal`) and the deploy directory (`/docker/youtube-withdrawal`) are on the same VM101 host but are **separate git checkouts**. Only the deploy checkout's `data/` is live state.
