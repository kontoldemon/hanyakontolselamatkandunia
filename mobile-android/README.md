# CloudSentinel Android Companion

Native Android SOC companion built with Kotlin, Jetpack Compose (Material 3), Retrofit/OkHttp, kotlinx.serialization, CameraX/ML Kit, and Firebase Cloud Messaging.

Full contract: [../docs/MOBILE.md](../docs/MOBILE.md). System architecture: [../docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md).

## What it does

- Mini war room: connections, MTTB, MITRE count, blocked IPs, top origin, sensor reachability.
- Threat alert feed with a block action.
- Session/forensics inspector with captured commands.
- Settings for alert policy and sensor defense (deception level, SOAR dry-run, HASSH action).
- Sensor-side AI copilot.
- Ingress exposure toggle (see the limitation below).
- FCM push with a `[Block IP]` notification action.
- QR, one-click deep link, or manual pairing.

Package: `com.cloudsentinel.mobile`. Min SDK 26, target/compile SDK 35, JDK 17.

## Backend

The app talks to the sensor admin API, not directly to ClickHouse, Redis, or Azure.

Required on the sensor:

- Reachable admin API, normally `https://<sensor-fqdn>` behind Caddy.
- `ADMIN_TOKEN` or JWT auth configured.
- Mobile pairing challenge generated from the web dashboard.

For FCM:

- `mobile-android/app/google-services.json` from Firebase. It is not committed.
- Sensor env: `CLOUDSENTINEL_FCM_PROJECT_ID`, `CLOUDSENTINEL_FCM_ACCESS_TOKEN`.

## Pairing

1. In the web dashboard, open **Settings -> Mobile Alerts**.
2. Set **Sensor API URL** to the sensor origin, not the Vercel URL.
3. Click **Generate Pairing**.
4. Scan the QR, open the `cloudsentinel://pair?...` link, or enter the 6-digit code and pairing token manually.

The challenge lasts 5 minutes. Pairing is rate-limited to 10 attempts per minute per IP. The device receives a scoped `cs_mob_*` token stored with `EncryptedSharedPreferences`; revoke it from the dashboard when lost.

## Build

```powershell
cd mobile-android
.\gradlew.bat assembleDebug
```

The debug APK is under `app/build/outputs/apk/debug/`. `assembleDebug` and `assembleRelease` (unsigned) were verified on 2026-11-26. The checked-in `CloudSentinel-SOC-Mobile.apk` is an artifact and may be stale; rebuild before a demo. Release signing and physical-device testing remain unverified.

Release builds reject cleartext traffic (`android:usesCleartextTraffic="false"`). Only the debug manifest permits HTTP. Use HTTPS for any real deployment. `local.properties`, signing keys, and `google-services.json` stay untracked.

## Limitations

- **Exposure uses the host firewall.** `POST /mobile/exposure` now executes the same iptables toggle as the web dashboard. It does not create an Azure NSG rule. A failed command returns `ok: false`; a broken control path returns `503`. The app surfaces the failure instead of assuming the requested state applied.
- **Device tokens are high privilege.** They can block IPs, pause ingress, and change in-memory deception/SOAR/HASSH controls. Runtime-control changes revert on sensor restart. Revoke lost devices immediately.
- **FCM token is not refreshed.** The sensor uses the bearer token in `CLOUDSENTINEL_FCM_ACCESS_TOKEN`; update it when it expires.
- **Dev Preview** is debug-only (`BuildConfig.DEBUG`), creates a fake local session (`cs_mob_dev_bypass`), and cannot read the real API.
- No Android instrumentation tests are committed; the Python suite covers the API side.
- Copilot depends on the sensor LLM configuration and can return `AI assistant unavailable on sensor`.

## Pairing payload

```json
{"v":1,"serverUrl":"https://sensor.example.com","pairingCode":"123456","pairingToken":"short-lived-token"}
```

The server URL must be reachable from the phone. On an emulator, `127.0.0.1` is the emulator itself, not the sensor.
