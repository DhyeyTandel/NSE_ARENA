# Decisions

Append-only log of architectural decisions for this project.
Entries are added via the `/log` command. Do not rewrite or
tidy earlier entries.

## [2026-08-21] Frontend served same-origin behind Caddy, not via a hardcoded backend URL

**Problem** — `docs/RESUME_AUDIT.md` §4 flagged that `docker-compose.yml`
had no frontend service at all: only `caddy`, `backend`, `postgres`,
`redis`, with `Caddyfile` reverse-proxying everything to `backend:8000`.
The README's "Docker (Full Stack)" section claimed to run the whole app
but only ever started the API. Adding a frontend service meant deciding
how the built React app would find the backend once both live behind the
same Caddy host — the existing `frontend/src/config.js` defaults
`API_URL`/`WS_URL` to `http://localhost:8000`, which is only correct for
the native (non-Docker) dev setup where Vite's dev server and uvicorn run
on different ports on the same machine.

**Options considered**
1. Bake an absolute URL into the frontend build from `DOMAIN`
   (`https://${DOMAIN}` as a Docker build arg) — rejected. `DOMAIN`
   controls whether Caddy serves HTTP or automatic HTTPS (plain HTTP for
   `localhost`/unset, HTTPS otherwise per the existing Caddyfile
   comment), so a hardcoded `https://` prefix would break the local
   `docker-compose up` path, and a hardcoded `http://` would break real
   deploys. Getting this right would mean templating protocol *and* host
   into the image, coupling the frontend build to `DOMAIN` and forcing a
   rebuild on every domain change.
2. Serve the frontend's static build directly out of the `caddy`
   container via a shared volume, no separate frontend container —
   rejected even though it avoids an extra hop. It would mean the
   frontend's build step (npm ci / vite build) has to happen in an init
   container or on the host before `caddy` starts, which is more moving
   parts than a standard multi-stage Dockerfile, and it's not what was
   asked for (a frontend service + Dockerfile in the stack).
3. Same-origin relative URLs: build the frontend with `VITE_API_URL=""`
   /`VITE_WS_URL=""` (Docker build args, baked in at `vite build` time),
   so `fetch()`/`WebSocket()` calls go out as relative paths
   (`/auth/login`, `/ws/prices`) that resolve against whatever origin
   served the page. Caddy then path-routes: an explicit allowlist of
   backend path prefixes (`/auth`, `/trades`, `/portfolio`,
   `/leaderboard`, `/seasons`, `/ai`, `/api`, `/price`, `/score`, `/ws`,
   `/health`, `/docs`, `/redoc`, `/openapi.json` — enumerated from
   `main.py` and every `api/routes/*.py` router prefix, since the
   backend has no single common `/api` prefix) to `backend:8000`, and
   everything else (the SPA) to a new `frontend:80` nginx container —
   chosen. One frontend image now works unmodified behind `localhost` or
   any real `DOMAIN`, with no rebuild-per-environment and no
   protocol/host coupling.

**Decision** — Option 3. Added `frontend/Dockerfile` (multi-stage:
`node:20-alpine` build → `nginx:1.27-alpine` serve, with SPA fallback via
`try_files $uri /index.html` in `frontend/nginx.conf`), a `frontend`
service in `docker-compose.yml` with `VITE_API_URL`/`VITE_WS_URL` build
args pinned to `""`, and rewrote `Caddyfile` with a named `@backend`
path matcher followed by a catch-all `reverse_proxy frontend:80`. This
required one small change outside the strict "deploy config" boundary:
`frontend/src/config.js` used `import.meta.env.VITE_API_URL ||
'http://localhost:8000'` — `||` treats an explicitly-empty string the
same as unset and falls through to the localhost default, which would
have silently defeated the whole same-origin approach. Changed that one
line's operator to `??` (nullish coalescing) so an explicit empty string
is honored while the unset-in-native-dev case still gets the
`localhost:8000` default unchanged. Judged in-scope because this file's
entire purpose (per its own header comment, added when it was extracted
in commit `c5f21b9`) is deploy-time backend-URL configuration — not
application logic — and the alternative was leaving the Docker "full
stack" claim false in a different way (frontend built, but silently
unable to reach the API in any Docker deployment).

**Tradeoff accepted** — The Caddy path allowlist is a manually-maintained
list that has to be kept in sync with backend route prefixes; if a future
route is added under a new top-level prefix and `Caddyfile` isn't
updated, it will silently 404 through the frontend's SPA fallback instead
of reaching the backend. A `/api/*`-prefix convention on every backend
router would make this self-maintaining, but reprefixing existing routes
is a backend/`main.py` change outside this track's file ownership
(backend/*.py is owned by the parallel backend-track agent on this repo)
— left as a follow-up rather than done here.

**What went wrong** — nothing required a redo; the main risk (getting
`||` vs `??` wrong in `config.js`, or Caddy's same-directive-name
ordering for the two `reverse_proxy` lines) was caught by reasoning
through both before writing them, not by trial and error, since Docker
wasn't available in this sandbox to run the stack directly. `docker
compose config`/build could not be executed here (no `docker` binary) —
`docker-compose.yml` was instead validated by parsing it with a real YAML
parser (`js-yaml` under `node`) and reading the resulting structure back;
`.github/workflows/ci.yml` was validated the same way. Whoever next has a
Docker daemon available should do a real `docker compose up --build` pass
before this is called done.

**Scale/limits** — N/A for this change (docs/DevOps only).
