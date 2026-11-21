# R.E.P.O. notes

* Steam app **3241660**, depot **3241661** (Windows only). Built against v0.5.2, manifest `4238581831212146714`.
  Get it: Steam console (`open steam://open/console`) → `download_depot 3241660 3241661 4238581831212146714` (~1 GB, lands in `.../steamapps/content/app_3241660/depot_3241661`).
* Unity **6000.3.28f1**, Mono, built-in/URP-style shaders (143 shader objects, ~5900 unique D3D11 programs), Photon PUN + Photon Voice, Addressables (localization), Steam via Facepunch.Steamworks, Discord Social SDK.
* Native plugins and what we did: `steam_api64` → borrowed arm64 lib + shim · `discord_partner_sdk` → no-op stub · `opus_egpv` → libopus · `webrtc-audio`, `AudioIn` → stubs · `libonigwrap` → not needed so far.
* Port command used: `tools/port.py …` (no shader skipped since v0.5) then `natives.py --tweaks --steam --discord --voice`, `ilfix nocompute <Managed>/Unity.Postprocessing.Runtime.dll`, `ilfix returnfalse <same dll> UnityEngine.Rendering.PostProcessing.ColorGrading IsEnabledAndSupported`, `make_launcher.py R.E.P.O.app --appid 3241660 --title R.E.P.O.`, sign. Optional Steam Play button: `steam_entry.py --appid 3241660 --name "R.E.P.O." add <app>` (Steam closed).

## Status (reviewed 2026-11-21)
| Area | State |
|---|---|
| Main menu, tutorial, levels | render, ~110-130 fps at 3024x1898 (M5), GPU ~5-6 ms |
| Steam init, overlay (Shift+Tab), rich presence | works |
| Invites / join friend | untested with a friend; the game must already be running |
| Voice chat | shims built, Opus verified in isolation; **not yet verified in a real room** |
| Post-processing (bloom, lens distortion, chromatic aberration, grain, vignette, AO, motion blur) | **on** since v0.5: the Uber shader was hit by the float3 overwrite (`_PostExposure`, `_ChromaticAberration_Amount`), fixed by `cbfix.py`; PPv2 told "no compute" so it uses fragment fallbacks |
| Color grading | **off** (`ColorGrading.IsEnabledAndSupported` patched to false): the HDR LUT baker (`Lut2DBaker`) bakes a constant LUT on Metal (`_Lut2D_Params` reads as 0 — it lives in the stage's m_CommonParameters, see below), which made the whole scene ~2 % bright |
| Corner square | **fixed**: it was in the HUD layer, drawn by the HUD camera's post-processing while Uber had no Metal version |
| Mods / BepInEx | loader + test-plugin/Harmony smoke test recorded on M5; individual mod combinations remain unverified (see below) |
| Shader hitches | ~68 s warm-up on first launch removes first-use compile stutter |

## Performance notes
The player renders at native Retina resolution and the display's 120 Hz; the laptop can run warm. Use the in-game graphics settings (frame cap/VSync, pixelation, quality) or play windowed at a smaller size.
The Metal HUD (off by default; Steam Launch Options `-hud`, or `HUD=1 tools/launch.sh …`) shows resolution, fps, GPU ms and presentation mode.

## Lethal Company (inspected, not ported)
Unity 2022.3, Mono, **HDRP**: 179 graphics shaders compiled for D3D11 in the inspected build. Selected compute conversion now exists, but HDRP-specific passes and full-pipeline gameplay have not been validated. Compute support alone does not establish a working port.

## Next ideas
1. Color grading: find why Lut2DBaker's common parameters (`m_CommonParameters`, e.g. `_Lut2D_Params` at offset 448) read as 0 on Metal; then drop the ColorGrading returnfalse patch. Layer dump: `UnityCompat.Diag` cmd `dump <dir>` logs LUT render-texture stats.
2. Translate remaining graphics StructuredBuffer variants (RDEF type `SIT_STRUCTURED` + struct member layout); the corner-square fix is already known and does not depend on this work.
3. Real voice test, then echo cancellation (WebRTC AEC3 builds for arm64 could replace the pass-through stub).
4. Finish ULTRAKILL's compute gameplay validation; its existing native port has additional game-specific repairs (see `games/ultrakill.json`).

## Steam Cloud
* Enabled 2026-11-21 with `tools/steam_entry.py --appid 3241660 --name "R.E.P.O." --cloud add <R.E.P.O.app>` (Steam closed). R.E.P.O.'s cloud
  rules cover `LocalLow/semiwork/Repo/**/*.es3` and the cosmetics preset icons; the override maps them to
  `~/Library/Application Support/local.repo.port` on macOS. Mac, CrossOver and Windows now share one cloud copy.
* First sync downloaded all 171 cloud files and replaced local `SettingsData.es3` and `CurrentKeyBindings.es3` with the cloud versions.

## Mods (BepInEx)
* `tools/mods ports/R.E.P.O.app install` (done 2026-11-21); put mods in `~/Library/Application Support/metalport/mods/local.repo.port/BepInEx/plugins`
  (`tools/mods ports/R.E.P.O.app open`). Most R.E.P.O. mods on Thunderstore are BepInEx 5 C# plugins: copy the mod's `.dll` (and any
  folder it ships under `BepInEx/plugins`) there. Mod managers (r2modman, Gale) aren't wired up.
* Verified: BepInEx 5.4.23.6 loads, a test plugin runs on Apple M5, Harmony patches game code. Multiplayer mods need the same mods on
  everyone's game, as on Windows. Steam Launch Options `-nomods` for a clean run.
* r2modmac (macOS mod manager) works: set its Steam directory to `~/Library/Application Support/Steam` and the game folder to
  `steamapps/common/R.E.P.O. Mac Port`, Add mods, Apply to Game, then start R.E.P.O. from Steam or by double-click (not r2modmac's
  play button, which targets CrossOver for Windows games; skip its Wine/winhttp guide). Verified 2026-11-21: MenuLib 2.6.0 + MoreHead
  1.4.6 load natively. MoreHead's own asset bundle has Windows-only shaders (`Desired shader compiler platform 14 is not available`):
  translating mod bundles is the next step.
