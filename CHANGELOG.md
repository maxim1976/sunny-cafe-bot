# Changelog

## 2026-04-08 — Security hardening

Security audit and fixes across the entire codebase.

### CRITICAL fixes

- **CSRF protection on admin panel** — Added `flask-wtf` with `CSRFProtect`.
  All admin POST forms now require a CSRF token (auto-injected via JS in
  `admin/templates/admin/base.html`). The LINE webhook and LIFF blueprint
  are exempt (they use their own auth mechanisms).

- **LIFF submit authentication** — `/liff/submit` no longer trusts the
  client-supplied `user_id`. The LIFF JS now sends `liff.getAccessToken()`,
  and the server verifies it via `api.line.me/oauth2/v2.1/verify` +
  `/v2/profile` before extracting the real user ID. Requires `LINE_CHANNEL_ID`
  env var to validate the token's `client_id`.

- **Admin credentials required** — `ADMIN_USER` and `ADMIN_PASSWORD` now use
  `os.environ[]` (hard crash if missing) instead of `os.getenv()` with
  fallback defaults like `"changeme"`.

### HIGH fixes

- **`FLASK_SECRET_KEY` required** — App crashes on startup if the env var is
  missing, instead of silently generating a random key per worker/restart.

- **Rate limiter memory leak fixed** — `_rate_store` now has periodic cleanup
  of stale user entries (every `RATE_WINDOW` seconds) and a hard cap of 10K
  tracked users to prevent OOM under sustained traffic.

- **Path traversal surface reduced** — `/images/<path:filename>` changed to
  `/images/<filename>` (no sub-path segments).

- **PII no longer logged** — User message content was logged at INFO level;
  now only logs `user_id` and message length.

### MEDIUM fixes

- **Phone number validation** — LIFF submit now validates phone against
  `^[\d\-\+\(\)\s]{7,20}$` regex. Fulfillment type is also whitelisted
  against the three valid values.

### New dependency

- `flask-wtf==1.2.1` (added to `requirements.txt`)

### New required env vars

- `FLASK_SECRET_KEY` — stable secret for Flask sessions and CSRF tokens
- `LINE_CHANNEL_ID` — was already documented but is now actively used for
  LIFF token verification

### Files changed

| File | What changed |
|------|-------------|
| `app.py` | CSRF init, secret key required, rate limiter cleanup, PII logging removed, image route narrowed, webhook CSRF-exempt |
| `admin/routes.py` | `os.environ[]` for credentials (no fallback) |
| `admin/templates/admin/base.html` | JS auto-injects CSRF token into all POST forms |
| `liff/routes.py` | `_verify_line_token()` added, submit uses access token, phone + fulfillment validation |
| `liff/templates/liff/checkout.html` | JS sends `liff.getAccessToken()` instead of hardcoded `user_id` |
| `requirements.txt` | Added `flask-wtf==1.2.1` |
| `CLAUDE.md` | Updated to reflect security measures |
