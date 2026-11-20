# R.E.P.O. notes

* Steam app **3241660**, depot **3241661** (Windows only). Built against v0.5.2, manifest `4238581831212146714`.
  Get it: Steam console (`open steam://open/console`) → `download_depot 3241660 3241661 4238581831212146714` (~1 GB, lands in `.../steamapps/content/app_3241660/depot_3241661`).
* Unity **6000.3.28f1**, Mono, built-in/URP-style shaders (143 shader objects, ~5900 unique D3D11 programs), Photon PUN + Photon Voice, Addressables (localization), Steam via Facepunch.Steamworks, Discord Social SDK.
* Native plugins and what we did: `steam_api64` → borrowed arm64 lib + shim · `discord_partner_sdk` → no-op stub · `opus_egpv` → libopus · `webrtc-audio`, `AudioIn` → stubs · `libonigwrap` → not needed so far.
* Port command used: `tools/port.py …` (no shader skipped since v0.5) then `natives.py --tweaks --steam --discord --voice`, `ilfix nocompute <Managed>/Unity.Postprocessing.Runtime.dll`, `ilfix returnfalse <same dll> UnityEngine.Rendering.PostProcessing.ColorGrading IsEnabledAndSupported`, `make_launcher.py R.E.P.O.app --appid 3241660 --title R.E.P.O.`, sign. Optional Steam Play button: `steam_entry.py --appid 3241660 --name "R.E.P.O." add <app>` (Steam closed).

## Status (v0.3.0)
| Area | State |
|---|---|
| Main menu, tutorial, levels | render, ~110-130 fps at 3024x1898 (M5), GPU ~5-6 ms |
| Steam init, overlay (Shift+Tab), rich presence | works |
| Invites / join friend | untested with a friend; the game must already be running |
| Voice chat | shims built, Opus verified in isolation; **not yet verified in a real room** |
| Post-processing (bloom, lens distortion, chromatic aberration, grain, vignette, AO, motion blur) | **on** since v0.5: the Uber shader was hit by the float3 overwrite (`_PostExposure`, `_ChromaticAberration_Amount`), fixed by `cbfix.py`; PPv2 told "no compute" so it uses fragment fallbacks |
| Color grading | **off** (`ColorGrading.IsEnabledAndSupported` patched to false): the HDR LUT baker (`Lut2DBaker`) bakes a constant LUT on Metal (`_Lut2D_Params` reads as 0 — it lives in the stage's m_CommonParameters, see below), which made the whole scene ~2 % bright |
| Corner square | **fixed**: it was in the HUD layer, drawn by the HUD camera's post-processing while Uber had no Metal version |
| Mods / BepInEx | not supported (no arm64 loader) |
| Shader hitches | ~68 s warm-up on first launch removes first-use compile stutter |

## Performance notes
The player renders at native Retina resolution and the display's 120 Hz; the laptop can run warm. Use the in-game graphics settings (frame cap/VSync, pixelation, quality) or play windowed at a smaller size.
The Metal HUD (`MTL_HUD_ENABLED=1`, on by default in `launch.sh`) shows resolution, fps, GPU ms and presentation mode.

## Lethal Company (tried, not viable)
Unity 2022.3, Mono, **HDRP**: 179 shaders compiled for D3D11 only, and HDRP needs compute shaders. Out of scope until compute translation exists.

## Next ideas
1. Color grading: find why Lut2DBaker's common parameters (`m_CommonParameters`, e.g. `_Lut2D_Params` at offset 448) read as 0 on Metal; then drop the ColorGrading returnfalse patch. Layer dump: `UnityCompat.Diag` cmd `dump <dir>` logs LUT render-texture stats.
2. Translate StructuredBuffer variants (RDEF type `SIT_STRUCTURED` + struct member layout) — probably the corner square.
3. Real voice test, then echo cancellation (WebRTC AEC3 builds for arm64 could replace the pass-through stub).
4. ULTRAKILL (Unity, Mono, built-in pipeline) is the natural second target for this toolkit.
