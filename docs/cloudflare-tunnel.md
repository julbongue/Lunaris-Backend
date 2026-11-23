# Cloudflare Tunnel for LUNARIS Backend

This guide exposes the local LUNARIS FastAPI backend to the internet through Cloudflare Tunnel so a Vercel-hosted frontend can call it over HTTPS.

## Scope and security

- Expose **only** the API service (`http://localhost:8000` by default).
- **Do not** expose PostgreSQL or Redis directly. (This backend does not use PostgreSQL/Redis; if you add them later, keep them bound to localhost/private network and never tunnel them publicly.)
- Configure CORS to allow only your production Vercel domain(s) and local development origins.
- Use HTTPS endpoints in the frontend (Cloudflare provides TLS termination for the tunnel hostname).
- Do not commit tunnel credentials, tokens, or `.cloudflared` JSON files.

## Prerequisites

- Backend running locally and healthy: `GET /api/v1/health`
- `cloudflared` installed: <https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/>
- For Named Tunnel: a Cloudflare account and a domain/zone you control in Cloudflare (action required by you)

## 1. Quick Tunnel (development/testing)

Quick Tunnel creates a temporary public `*.trycloudflare.com` URL. No Cloudflare account configuration is required, but the URL changes every run and is not suitable for stable production.

1. Start backend:
   ```bash
   ./scripts/start_backend.sh
   # or: python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```
2. Start tunnel:
   ```bash
   cloudflared tunnel --url http://localhost:8000
   # or: ./scripts/start_tunnel.sh quick
   ```
3. Copy the generated `https://<random>.trycloudflare.com` URL from cloudflared output.
4. Verify:
   ```bash
   curl https://<random>.trycloudflare.com/api/v1/health
   ```
5. Temporarily set frontend API base URL to that tunnel URL and ensure backend `CORS_ORIGINS` includes your Vercel domain.

**Limitations:** ephemeral URL, no stable hostname, dependent on local machine/network uptime, not recommended as permanent production ingress.

## 2. Named Tunnel (persistent)

Named Tunnel provides a stable hostname on your domain. You must authenticate with your Cloudflare account and manage DNS/routes.

> The commands below are exact; replace placeholders (`<TUNNEL_UUID>`, `api.example.com`, paths, account details) with your own values. This repository cannot perform Cloudflare account authentication or DNS changes for you.

1. Authenticate:
   ```bash
   cloudflared tunnel login
   ```
2. Create tunnel:
   ```bash
   cloudflared tunnel create lunaris-backend
   ```
   Note the tunnel UUID and credentials file path printed by cloudflared.
3. Route DNS (example):
   ```bash
   cloudflared tunnel route dns lunaris-backend api.example.com
   ```
4. Create local config from example (do not commit secrets):
   ```bash
   cp cloudflared/config.example.yml cloudflared/config.yml
   # edit cloudflared/config.yml: set tunnel UUID, credentials-file, hostname
   ```
5. Ensure backend CORS allows your frontend origin (e.g. `https://your-app.vercel.app`) in `.env`:
   ```env
   CORS_ORIGINS=https://your-app.vercel.app,http://localhost:3000
   ```
6. Start backend and tunnel:
   ```bash
   ./scripts/start_backend.sh
   ./scripts/start_tunnel.sh named
   # or: cloudflared tunnel --config cloudflared/config.yml run
   ```
7. Verify through public hostname:
   ```bash
   curl https://api.example.com/api/v1/health
   curl https://api.example.com/api/v1/capabilities
   # Swagger UI: https://api.example.com/docs
   ```

## 3. Frontend (Vercel) configuration

- Set Vercel environment variable for API base URL to your tunnel hostname, e.g. `https://api.example.com` (Named) or the current Quick Tunnel URL.
- Backend must include the exact Vercel origin in `CORS_ORIGINS` (no wildcard).
- Restart/redeploy backend after `.env` changes if needed; Vercel requires redeploy/env update for frontend changes.

## 4. Troubleshooting

- **502/connection refused:** backend not running or wrong port. Check `./scripts/check_health.sh` locally and cloudflared `service` URL.
- **CORS errors in browser:** add the exact frontend origin (`https://...`) to `CORS_ORIGINS`, avoid trailing slashes, restart backend.
- **401/403:** not issued by this backend unless added; check Cloudflare Access policies if you enabled them.
- **Timeouts on analysis:** JPL Horizons is an external dependency; check `HORIZONS_TIMEOUT_SECONDS` and upstream availability.
- **Quick Tunnel URL changed:** expected behavior; update frontend env or use Named Tunnel.
- **Rate limited (429):** adjust `RATE_LIMIT_*` carefully for trusted environments; keep protection enabled for public exposure.
- **Large request rejected (413):** increase `MAX_REQUEST_BODY_BYTES` only if necessary and safe.

## 5. Operational notes

- Keep `DEBUG=false` for public exposure.
- Monitor local machine availability; local tunnel depends on your Ubuntu host being online.
- Prefer a reverse proxy/WAF/Cloudflare Access for additional protection on sensitive deployments.
- Rotate/limit exposure if abuse is detected; rate limiting in-app is basic defense-in-depth only.
