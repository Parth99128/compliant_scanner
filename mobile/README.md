# LMPC Scanner — Mobile Capture App (Expo, Phase 4)

Two-shot field capture feeding `POST /api/v1/scans/merge`: **Shot 1**
context (whole pack + card stencil for scale) and **Shot 2** macro
(declaration close-up in a focal window). The gyroscope locks the capture
button past 10° tilt. Both shots upload as one merged verdict.

## Stack

- Expo SDK 57 + TypeScript (strict) + `react-native-vision-camera` v5
- Overlays: `react-native-svg` · Tilt: `expo-sensors` · Token: `expo-secure-store`

## Run (needs a dev client — vision-camera has native code, Expo Go cannot run it)

```bash
cd mobile
npm install
npx expo prebuild        # generates android/ + ios/ (needs Android Studio / Xcode)
npx expo run:android      # or run:ios
```

Emulator backend address: `http://10.0.2.2:8001` (Android emulator loopback).
Physical device on the same Wi-Fi: set `extra.apiUrl` in `app.json` to the
PC's LAN IP, e.g. `http://192.168.1.5:8001`, then rebuild the dev client.

## Verify without a device

```bash
npx tsc --noEmit          # strict types
npx expo export --output-dir dist-check   # JS bundle resolves (rm after)
```

## Flow

auth (JWT, SecureStore) → capture 1 (card stencil) → preview → capture 2
(macro mask, tilt-locked) → preview → review → Analyze → merged verdict +
top rule findings. Full detail, human review and PDF stay in the web
dashboard (`/scans/[id]`).
