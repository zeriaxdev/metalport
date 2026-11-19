# Changelog

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
