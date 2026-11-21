# Outer Wilds notes

* Steam app **753640**, Windows depot **753641**, manifest `2759471679100125861` (game 1.1.16.1372). Unity **2019.4.39f1**, Mono,
  built-in deferred pipeline, PostProcessing v1. Ported with the legacy path (`LEGACY-UNITY.md`) onto the 2021.3.45f1 arm64 player.
* Status: title, menus, profiles, in-world play work; clicks and keyboard work; post-processing renders.
* **Open:** Giant's Deep looks black in the night sky at the start of a loop (clouds/atmosphere are drawn; the planetary fog
  effect darkens it). Not confirmed against the Windows build yet.
* **Performance** (M5, Very High AO + shadows, Wake Up prompt): 36–40 fps at 3024×1898, 48 fps at 1512×982; the Windows build
  under CrossOver/D3DMetal does 31 fps at 1512×982. GPU-bound; shadow-map vertex work (resolution-independent) is the largest
  cost, then AO. Shadows Medium + AO Off ≈ 63 fps at 3024×1898. Vsync off changes nothing.
* The game pauses when unfocused (`runInBackground` false); test hidden with `REPO_NO_ACTIVATE=1` + `DIAG_MODE=bg`.
* Saves: `~/Library/Application Support/local.port.outerwilds/` (same JSON format as Windows `LocalLow/Mobius Digital/Outer Wilds`).
* The Windows `OuterWilds.exe` has the Steam DRM wrapper: a CrossOver comparison needs it launched by a signed-in Windows Steam.

## Giant's Deep black: findings 2026-11-21
* The planet's visible surface from Timber Hearth is `GiantsDeep_Body/Clouds_GD/CloudsTopLayer_GD` (material `Clouds_GD_Top_mat`,
  shader `Outer Wilds/Environment/Giant's Deep/Cloud Layer Top`, kw `_EMISSION`, queue 1995), about 7.7 km away. At night only its
  atmosphere rim and emissive storms show; the sun-lit cloud surface is black (it should look like a full moon).
* All planet/cloud/atmosphere/fog shaders have full Metal coverage. Not the cause: float3 overwrites (audited), eye adaptation
  (off by default in every camera; turning it on blacks the screen because its compute shader is untranslated: harmless).
* Next suspects: (1) `PlanetaryFogImageEffect` fogging the whole disk with the night fog colour (test: `comp PlanetaryFogImageEffect 0`
  while the planet is in view); (2) shadow fade at 7.7 km (`_LightShadowData`, `unity_ShadowFadeCenterAndType`) leaving the
  surface fully shadowed.
* Test harness: `UnityCompat.Diag` commands `call PlayerCameraEffectController WakeUp`, `call PlayerCameraController SetDegreesY 75`,
  `find GiantsDeep`, `comp <Type> 0|1`, `dump <dir>`. Calling WakeUp from outside is unreliable (worked 3 of 5 runs); the planet is
  overhead roughly 4 minutes into a loop.
