# CloudSentinel Android Companion

Last reviewed: 2026-11-26.

This document covers the native Android companion app, the sensor-side mobile API, pairing, push notifications, security boundaries, and debugging. For the system-wide design, read `docs/ARCHITECTURE.md` first.

## 1. Purpose

The Android app is a mobile SOC companion for the same CloudSentinel sensor. It does not replace the web dashboard. It is for quick triage and emergency controls when the operator is away from a browser:

- View war-room KPIs and sensor reachability.
- Review the latest threat alerts and block a source IP.
- Inspect attacker sessions and captured commands.
- Ask the sensor-side AI copilot for triage help.
- Toggle honeypot ingress exposure from the phone.
- Receive Firebase Cloud Messaging (FCM) alerts with a `[Block IP]` action.

The app talks to the **sensor admin API**, not directly to ClickHouse, Redis, Event Grid, or the NSG.

## 2. System context

```text
Web dashboard (Vercel)
  -> /api/cloudsentinel/mobile (server-side admin token)
       -> sensor admin API /mobile/pairing-token
            -> 5-minute pairing code + pairing token + QR payload

Android app
  -> QR scan or manual pairing
  -> POST /mobile/pair (code + pairing token + FCM token)
       <- device token (cs_mob_*)
  -> Bearer device token on every later call
       -> /mobile/dashboard
       -> /mobile/alerts
       -> /mobile/sessions
       -> /mobile/block-ip
       -> /mobile/exposure
       -> /mobile/ai-copilot
       -> /mobile/fcm-token

Sensor admin API
  -> Redis / ClickHouse / SOAR / pipeline
  -> FCM HTTP v1 (if CLOUDSENTINEL_FCM_PROJECT_ID and CLOUDSENTINEL_FCM_ACCESS_TOKEN are set)
       -> Android FirebaseMessagingService
```

The web dashboard is the normal admin plane. The mobile API is a scoped device plane; a paired device token is not an admin token and must not be accepted by `/admin/*` routes.

## 3. Screens and navigation

The app uses Jetpack Compose and four bottom-navigation destinations:

| Screen | File | Main behavior |
|---|---|---|
| War Room | `ui/warroom/WarRoomScreen.kt` | KPI cards, top threat origin, active attackers, sensor status, ingress exposure toggle |
| Alerts | `ui/alerts/AlertFeedScreen.kt` | Recent alerts, risk filtering, block action, open session inspector |
| Copilot | `ui/copilot/AiCopilotScreen.kt` | Chat UI backed by `/mobile/ai-copilot` |
| Settings | `ui/settings/MobileSettingsScreen.kt` | Server/device status, alert policy, runtime controls, unpair |
| Pairing | `ui/pairing/PairingScreen.kt` | Manual pairing, QR scanner, debug-only dev preview |
| Session inspector | `ui/forensics/SessionInspectorSheet.kt` | Attacker IP, country, risk, MITRE tags, captured commands, timed block actions |

The activity is `MainActivity.kt`. The repository/state holder is `AlertRepository.kt`; it polls alerts, dashboard stats, and sessions every 5 seconds while paired.

## 4. Pairing flow

### 4.1 From the web dashboard

1. Open **Settings -> Mobile Alerts**.
2. Set **Sensor API URL**. In production this is the sensor origin, normally `https://<sensor-fqdn>` behind Caddy, not the Vercel dashboard URL.
3. Click **Generate Pairing**.
4. The sensor returns a 6-digit code, a pairing token, a server URL, and a QR payload. The challenge expires after **300 seconds**.
5. Show the QR, copy the one-click link, or manually enter the code and token in the app.

### 4.2 QR payload

The dashboard encodes a JSON payload:

```json
{
  "v": 1,
  "serverUrl": "https://sensor.example.com",
  "pairingCode": "123456",
  "pairingToken": "short-lived-pairing-token"
}
```

The Android `QrCodeScanner.kt` reads the QR and `PairingScreen.kt` decodes it with `QrPairingPayload`. The pairing token is required by the sensor; a bare 6-digit code is not enough.

### 4.3 Deep link

The dashboard can copy this link:

```text
cloudsentinel://pair?server=<urlencoded-sensor-url>&code=<code>&token=<pairing-token>
```

`MainActivity` handles the `cloudsentinel://pair` intent filter when the app has no paired session. Treat the link as a short-lived credential because it contains both the code and the pairing token.

### 4.4 Pairing limits

- Pairing challenge lifetime: 300 seconds.
- Pairing attempts: 10 per client IP per 60 seconds.
- Maximum paired devices: 20.
- The device gets a scoped `cs_mob_*` bearer token. Only a SHA-256 hash is stored on the sensor; the raw token is returned once and stored in Android `EncryptedSharedPreferences`.
- Revoke a device from the dashboard with `DELETE /mobile/devices/{deviceId}`.

## 5. Mobile API

All paths below are relative to the sensor admin API. `/mobile/pair` is public but requires the short-lived pairing token. Device routes require the device bearer token; admin-only routes require the admin token or JWT.

| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | `/mobile/pair` | pairing code + pairing token | Exchange a pairing challenge for a device token |
| GET | `/mobile/alerts?limit=50` | device | Recent alerts |
| POST | `/mobile/fcm-token` | device | Update the device FCM registration token |
| POST | `/mobile/block-ip` | device | Request a source-IP block through the normal block handler |
| POST | `/mobile/policy` | device | Update the mobile alert policy |
| POST | `/mobile/runtime-controls` | device | Change deception level, SOAR dry-run, or HASSH action in memory |
| GET | `/mobile/dashboard` | device | KPI, ingress, sensor, and policy snapshot |
| POST | `/mobile/exposure` | device | Persist an ingress exposure toggle |
| GET | `/mobile/sessions` | device | Recent attacker sessions and commands |
| POST | `/mobile/ai-copilot` | device | Sensor-side AI chat |
| GET | `/mobile/config` | admin | Mobile alert policy and paired devices |
| POST | `/mobile/config` | admin | Update mobile alert policy |
| POST | `/mobile/pairing-token` | admin | Create a pairing challenge |
| DELETE | `/mobile/devices/{deviceId}` | admin | Revoke a device |
| POST | `/mobile/test-alert` | admin | Send a test alert |

### 5.1 Block semantics

`POST /mobile/block-ip` validates the IP in the admin API and calls the same block handler used by the dashboard. It does not write an NSG rule directly. The normal SOAR/Event Grid/host-agent path still applies, including allowlist and public-IP checks.

`POST /mobile/runtime-controls` changes `settings.deception.level`, `settings.soar.firewall_dry_run`, or `settings.deception.hassh_action` in the running process. It does not write the runtime-config JSON, so the change is lost on restart and does not replace the web Settings/runtime-config path. Because a paired device can change defense posture, device tokens are high-privilege credentials even though they are scoped away from `/admin/*`.

### 5.2 Exposure semantics

`POST /mobile/exposure` now calls the same `apply_exposure_toggle` path as the web dashboard's `/admin/exposure`. It checks the cooldown, executes iptables `-C`/`-I`/`-D` rules for the configured honeypot port, and persists the resulting state. It does **not** create an Azure NSG rule directly; on Azure this is the sensor VM's host firewall path, not the NSG automation path. A firewall failure returns `ok: false` with the failed action; a broken control path returns `503`. The Android repository checks `ok` and shows a failure toast instead of assuming the requested state applied.

## 6. Security model

- Release manifest sets `android:usesCleartextTraffic="false"`; use HTTPS for the sensor API in release builds.
- The debug manifest allows cleartext for emulator/local development only.
- Device tokens are stored with `EncryptedSharedPreferences` (AES-256-GCM values, AES-256-SIV keys).
- Device tokens are high privilege: `/mobile/block-ip` can block, `/mobile/exposure` can pause ingress, and `/mobile/runtime-controls` can change deception/SOAR/HASSH posture. Revoke lost devices immediately.
- `android:allowBackup="false"` prevents cloud backup of the session store.
- Android permissions: `INTERNET`, `CAMERA`, `POST_NOTIFICATIONS`, `VIBRATE`.
- Notifications contain attacker IP, country, risk score, event type, and summary. Treat the lock screen as a data exposure surface.
- The FCM payload is data-only and is converted into a local notification by `CloudSentinelMessagingService`.
- `Continue in Dev Preview` is compiled only in debug builds (`BuildConfig.DEBUG`). It creates a fake local session with `cs_mob_dev_bypass` and cannot access the real API; release builds do not show it.
- The pairing QR/deep link is a bearer credential for 5 minutes. Do not post it in chat or logs.

## 7. Firebase Cloud Messaging

The app uses Firebase Cloud Messaging HTTP v1.

Required pieces:

1. `mobile-android/app/google-services.json` (not committed; copy from `google-services.json.example` and fill from the Firebase console).
2. Sensor environment:
   - `CLOUDSENTINEL_FCM_PROJECT_ID`
   - `CLOUDSENTINEL_FCM_ACCESS_TOKEN`
3. The app obtains its FCM registration token in `MainActivity` and sends it to `/mobile/fcm-token`.

Current limitation: the sensor sends with the bearer token from `CLOUDSENTINEL_FCM_ACCESS_TOKEN`. It does not mint or refresh Google OAuth tokens. When that access token expires, push delivery stops until the operator updates it. If either variable is missing, `dispatch_alert` records the alert locally in `var/mobile_devices.json` but does not send a push.

## 8. Build and run

Prerequisites: Android Studio, JDK 17, Android SDK 35, and a reachable sensor admin API.

```powershell
cd mobile-android
.\gradlew.bat assembleDebug
```

The debug APK is written under `app/build/outputs/apk/debug/`. A prebuilt `CloudSentinel-SOC-Mobile.apk` exists in the repository, but it may not match the current source. Rebuild before using it for a demo.

For a phone, pair from the dashboard QR. The scanner path avoids typing the server URL. For an emulator, use a reachable host alias and the debug build; `127.0.0.1` inside the emulator is the emulator itself, not the sensor.

Release builds must use HTTPS. `local.properties`, signing keys, and `google-services.json` must not be committed.

## 9. Backend requirements

- Sensor admin API enabled and reachable from the phone (direct TLS or Caddy on 443).
- `ADMIN_TOKEN`/JWT configured; the dashboard proxies mobile admin calls server-side.
- Dashboard environment:
  - `CLOUDSENTINEL_ADMIN_API_URL`
  - `CLOUDSENTINEL_ADMIN_TOKEN`
- For live data, the normal Redis/ClickHouse pipeline must be healthy; mobile endpoints fall back to recent alerts when ClickHouse is unavailable.
- For push, FCM project and access token must be set on the sensor.

## 10. Debugging

| Symptom | Check |
|---|---|
| Pairing says invalid or expired | Challenge is older than 5 minutes, code/token mismatch, or more than 10 attempts from the same public IP. Generate a new QR. |
| Pairing works but every call returns 401 | Device was revoked or its token is missing/corrupt. Unpair and pair again. |
| `127.0.0.1:8080` fails on a phone | That address is the phone itself. Use the sensor LAN/FQDN URL or the QR payload. Release builds reject cleartext. |
| Dashboard shows devices but phone is offline | Sensor API URL is wrong, Caddy is not proxying `/mobile/*`, or the phone cannot reach the sensor. |
| No FCM push | `google-services.json` missing, FCM sensor variables missing/expired, notifications permission denied, or the device has no FCM token. Test with Settings -> Mobile Alerts -> Test Alert. |
| Alerts list empty | No recent alerts in the mobile state, ClickHouse fallback empty, or alert policy filters everything. |
| Copilot says unavailable | Sensor has no LLM key/provider, budget exhausted, or `litellm` is not installed. Use the web dashboard or configure the LLM path. |
| Killswitch returns 503 or fails | The sensor could not execute the iptables rule: check the API process user, `iptables` path, and permissions. This path does not change the Azure NSG. |
| Android build fails without Firebase | Remove/ignore FCM for a local build or provide `google-services.json`; the Gradle plugin is applied only when that file exists. |

## 11. Known limitations

1. Mobile exposure uses the sensor host firewall (iptables), not the Azure NSG. Use the Azure block path for NSG enforcement.
2. FCM access token is supplied manually and is not refreshed.
3. No Android instrumentation tests are committed; the Python suite covers the API side. Debug and unsigned release builds were rebuilt successfully on 2026-11-26; release signing and a physical-device pass remain unverified.
4. The checked-in `CloudSentinel-SOC-Mobile.apk` is a build artifact; verify its timestamp or rebuild before a demo.
5. `Continue in Dev Preview` is debug-only; it is hidden in release builds.
6. The app has no certificate pinning or offline secure cache beyond the session token.
7. Mobile API behavior depends on sensor reachability; there is no separate mobile backend.
8. Runtime-control changes are in-memory only and revert on sensor restart.

When these change, update this file and `docs/ARCHITECTURE.md` together.
