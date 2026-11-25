# CloudSentinel Android Companion App

Native Android threat notification & quick-response companion app built with **Kotlin** and **Jetpack Compose** to match the CloudSentinel Web War Room design system.

## Features
- **QR Code & 6-Digit Pairing**: Scan the QR code generated under **Web Dashboard -> Settings -> Mobile Alerts**.
- **Real-Time DEFCON Push Notifications (FCM HTTP v1)**: High-priority Android notification channel with inline **`[Block IP]`** action directly from the notification tray.
- **Local LAN Sync Fallback**: Automatically syncs live alerts every 5 seconds over Wi-Fi even before Firebase is configured.
- **Encrypted Credential Storage**: Stores the paired server URL and scoped device bearer token using Android `EncryptedSharedPreferences` (AES-256).

## Quick Setup (100% Free)
1. Open `mobile-android/` in **Android Studio**.
2. *(Optional for background push via Firebase)*:
   - Create a free Firebase Spark project at [console.firebase.google.com](https://console.firebase.google.com).
   - Register an Android app with package name `com.cloudsentinel.mobile`.
   - Download `google-services.json` and place it in `mobile-android/app/google-services.json`.
   - Set `CLOUDSENTINEL_FCM_PROJECT_ID` and `CLOUDSENTINEL_FCM_ACCESS_TOKEN` in your backend `.env`.
3. Connect your Android phone via USB Debugging (or start an Android Emulator) and click **Run**.
4. In the CloudSentinel Web Dashboard, go to **Settings -> Mobile Alerts**, click **Generate Pairing QR**, scan it with the app, and click **Send Test Alert**.
