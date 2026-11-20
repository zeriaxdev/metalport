# Changelog

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
