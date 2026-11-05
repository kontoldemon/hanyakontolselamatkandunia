# CloudSentinel Dashboard

Next.js dashboard for the CloudSentinel SSH honeypot. It shows the war room, threat map, sessions, command replay, and the AI analysis panel.

The dashboard reads data through its own API routes. Those routes call the admin API on the sensor. The browser never talks to the sensor directly.

## Local development

```bash
npm install
npm run dev
```

Open `http://localhost:3000`.

## Build and lint

```bash
npm run lint
npm run build
```

## Environment

Create `.env.local` with the values below. Do not commit it.

| Variable | Purpose |
|---|---|
| `CLOUDSENTINEL_ADMIN_API_URL` | Admin API base URL |
| `CLOUDSENTINEL_ADMIN_TOKEN` | Bearer token for the admin API |
| `NEXT_PUBLIC_CLOUDSENTINEL_SOCKET_URL` | Socket.io stream URL |
| `DASHBOARD_USERNAME` | Dashboard login user |
| `DASHBOARD_PASSWORD` | Dashboard login password |
| `DASHBOARD_AUTH_SECRET` | HMAC secret for the session cookie |
| `NEXT_PUBLIC_TURNSTILE_SITE_KEY` | Cloudflare Turnstile site key |
| `TURNSTILE_SECRET_KEY` | Cloudflare Turnstile secret key |
| `RESEND_API_KEY` | Email provider key for OTP delivery |
| `ADMIN_EMAIL` | Destination for the OTP email |
| `OTP_SECRET` | HMAC secret for the OTP hash |
| `CLOUDSENTINEL_EXPOSURE_PROVIDER` | Exposure provider, for example `digitalocean` |
| `DIGITALOCEAN_TOKEN` | DigitalOcean API token for the exposure toggle |

The admin token and the DigitalOcean token are privileged. Keep them in the Vercel environment, never in the repository.

## Deploy

```bash
vercel deploy --prod --yes
```

Set the same variables in the Vercel project settings.

## Auth flow

1. The user submits username, password, and a Turnstile token.
2. The server checks the credentials and sends a six-digit OTP to `ADMIN_EMAIL`.
3. The OTP hash is stored in an HttpOnly cookie.
4. The user submits the OTP, and the server sets an HMAC-signed session cookie.

See `../docs/ARCHITECTURE.md` for the known auth gaps.
