# DrishtiLM Scanner — Android / Mobile Capture App (Expo SDK 57)

Industry-grade field capture for `POST /api/v1/scans` (1 shot) and
`POST /api/v1/scans/merge` (2–5 shots). Matches the `main` backend contract:
uploads return **202 Job** in production — the app polls `GET /jobs/{id}`
then `GET /scans/{id}`, exactly like the web dashboard.

## What it does

- JWT auth (SecureStore, 401 → auto sign-out) + configurable API address
- Guided capture: shot 1 = whole pack + card scale stencil, rest = macro
  declaration close-ups, gyroscope tilt-lock at 10°, flash toggle
- 2–5 shots, thumbnails with remove, optional product/brand/category
- Auto-compress to ≤10 MB (1600px longest side, JPEG) so uploads never 413
- Async job polling with stage (`uploading → queued → working → done`),
  elapsed timer, and Cancel
- Verdict card (verdict, confidence, failing rules + remedies, warnings,
  request-id on errors for backend log correlation)
- History (search + verdict filter + detail) and Settings (API URL + health
  check + sign out)
- Crash ErrorBoundary — a render bug never bricks an inspection camp

## Stack

Expo SDK 57 + TypeScript strict + `react-native-vision-camera` v5
(`dev-client` build — **Expo Go cannot run the camera**), `react-native-svg`
overlays, `expo-sensors` tilt, `expo-secure-store` tokens,
`@react-native-async-storage/async-storage` prefs,
`expo-image-manipulator` + `expo-file-system` upload pipeline.

## Run

```bash
cd mobile
npm install
npx expo prebuild          # generates android/ (needs Android Studio)
npx expo run:android       # dev-client on emulator / USB device
```

Backend address:

- Android emulator → `http://10.0.2.2:8000` (default in `app.json`)
- Physical phone on same Wi-Fi → Settings → API address →
  `http://<PC-LAN-IP>:8000` (e.g. `http://192.168.1.5:8000`), Save & test

Backend must be up: `uvicorn app.main:app --port 8000` (see root README).

## Verify without a device

```bash
npm run typecheck          # tsc --noEmit, strict
npx expo export --output-dir dist-check   # JS bundle resolves (delete after)
```

## EAS builds

```bash
npm i -g eas-cli
eas build --profile development --platform android   # dev-client APK
eas build --profile preview --platform android       # QA APK
eas build --profile production --platform android    # Play AAB
```

## Troubleshooting

| Symptom | Fix |
|---|---|
| Cannot reach API | Settings → Test; emulator uses `10.0.2.2`, phone uses LAN IP; backend `:8000` |
| Session expired | Sign in again (JWT lives 60 min) |
| Need 2–5 photos | Take wide + at least one macro before Analyze |
| File too large / 413 | Automatic — image is recompressed; if it persists, move slightly farther |
| Analysis slow / 408 | Poll window is 6 min; result lands in History when done |
| Camera black in Expo Go | Expected — use `npx expo run:android` dev-client build |
| Ref: xxxx on error | Copy it — backend logs (`X-Request-ID`) carry the same id |

Full verdict detail, officer review, and PDF stay in the web dashboard.
