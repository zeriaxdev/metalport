# Changelog

## 0.5.0 (2026-11-21)
- R.E.P.O.: post-processing on (bloom, lens distortion, chromatic aberration, grain, vignette, AO, motion blur); corner square fixed.
  Color grading stays off for now (HDR LUT baker bakes a constant LUT on Metal; see docs/GAME-NOTES-REPO.md).
- `tools/cbfix.py`: float3-overwrite fix for Unity 2020.2+ data (parameter blobs), registers chosen per pass; used by `inject.py`.
  `REFIX=1 inject_inplace.py <Data>` applies it to shaders injected before.
- `ilfix nocompute <dll>` (SystemInfo.supportsComputeShaders -> false, so PostProcessing v2 uses fragment fallbacks) and
  `ilfix returnfalse <dll> <Type> <method>`.
- `tools/make_launcher.py`: apps start by double-click (Steam/overlay/HUD/tweaks set up inside), with "Steam not running" and
  "Steam couldn't confirm ownership" dialogs. R.E.P.O. build is now `R.E.P.O.app`.
- `tools/steam_entry.py` (generalised from the Buckshot Roulette port): Steam shows Play for the Mac app; records OS-less depots as
  installed so Steam doesn't want the Windows files.
- `tools/bench_trace.py`: FPS, 1 % lows, render size, GPU busy, CPU, memory from a Metal System Trace (native or CrossOver).
- UnityCompat.Diag: live commands `cam`, `camcomp`, `volmask`, `ppfx`, `pplist`, `ui`, `dump` (layer PNGs + LUT stats), `res`.

## 0.4.0 (2026-11-20)
- Legacy Unity path (2019.x data on the 2021.3 arm64 player), proven on Outer Wilds: `tools/legacy/` (`convert_data.py`, `make_json.py`,
  `validate_typetrees.py`), `tools/shader2021.py`, `tools/ilfix/` (Mono.Cecil IL rewriter + `UnityCompat` shims). docs/LEGACY-UNITY.md,
  docs/GAME-NOTES-OUTERWILDS.md.
- Injector: Unity 2019 serialized files (format 21, flat sub-programs, local keyword lists). Unity 6 / 2021+ paths unchanged.
- natives.py: shims for old Steamworks.NET builds (SteamAPI_Init, GetISteamX version remap), applied only when the game calls them.
- repo_tweaks: `REPO_NO_ACTIVATE` (run hidden, render while covered), `REPO_INVOKE` (call a static C# method every 10 s); both off by default.
- Converter refuses already-converted input (no more in-place un-stamping through symlinks).

## 0.3.0 (2026-11-19)
- Toolkit: `fetch_unity.py`, `port.py`, `assemble_app.py`, `natives.py`, `inspect_game.py`, `patch_buildsettings.py`, `fix_addressables.py`, `build_hlslcc.sh`, generic `launch.sh`.
- Whole pipeline re-run from scratch on the pristine depot in ~33 s (+ downloads) and verified to start (Metal device, Steam init, menu).
- Documentation: README, docs/PIPELINE.md, docs/PORTING-A-NEW-GAME.md, docs/GAME-NOTES-REPO.md.
- Fixes: bounded Steam-library search; paths with spaces.

## 0.2.0 (2026-11-19)
- Voice chat shims: Opus (libopus 1.6.1) + Photon WebRTC/AudioIn stand-ins, mic permission text.
- Steam overlay injected by run.sh (SteamAppId/SteamGameId + gameoverlayrenderer.dylib).
- First-run shader warm-up (Shader.WarmupAllShaders via Mono), mouse scale, App Nap off, Metal HUD on.
- Multi-chunk shader support in tools (Hidden/PostProcessing/Uber translates but renders wrong -> skipped via SKIP_SHADER).
- Non-development arm64 player, Discord no-op stub, Steam API shim for 5 newer flat-API calls.

## 0.1.0 (2026-11-19)
- First native Metal build: D3D11->Metal shader translation (HLSLcc), macOS Mono class libraries, Addressables path fixes, Steam init.
