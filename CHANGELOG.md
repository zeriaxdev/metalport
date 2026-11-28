# Changelog

## Unreleased
- Add `tools/patch_mod_bundles.py <plugins dir>`: finds BepInEx mod asset bundles whose shaders have no Metal variant (they render magenta on a native Mac port), translates them, appends the Metal variants and replaces the bundle, with backups. On a Lethal Company profile it patched 6 bundles (Piggy's Variety Mod, RadioFurniture, LethalLib, GeneralImprovements, LethalCasino, WhoVoted); in-game verification is still pending. It sets a new `ALLOW_METAL_FAILURES=1` opt-in so a few variants Metal rejects are left out of a shader; `ALLOW_PARTIAL_SHADER` alone still never bypasses a Metal compiler failure.
- `metal_check.py` validates its batches four at a time instead of one (about 4x faster on a ~5,800-program game such as R.E.P.O.). The checker's cache key includes its own code, so the first run after this change re-validates once.
- Add `natives.py --dissonance`: a macOS stand-in for Dissonance Voice Chat's Windows-only `AudioPluginDissonance` (Lethal Company), so its capture-preprocessing thread no longer dies with `DllNotFoundException`. Audio passes through unchanged (no noise suppression or echo cancellation); speech detection is a loudness gate with a knob, `MP_VAD_DB` (default -48 dBFS). Unit-tested with `tests/test_dissonance_stub.py`; verified in a real Lethal Company lobby, where a friend heard the host over voice. The stub logs speech start/stop and a 5 s frame summary to `~/Library/Logs/metalport/dissonance-stub.log`.
- Add asset-free tests for `steam_entry.py` (synthetic Steam cache) and `tools/check_no_game_files.py`, which fails if game, Unity or Valve files are tracked or in a release ZIP; add a GitHub Actions workflow that runs both with the existing tests (not yet run on GitHub).
- Fix `steam_entry.py remove`: it left an empty `rootoverrides` node in Steam's app cache after Steam Cloud had been added.
- Add read-only diagnostics `tools/dump_common_params.py` and `tools/quality_vsync.py`, and `docs/UPSTREAM-AUDIT.md` (findings from other Unity-on-Mac projects, with licenses).

## 0.7.0 (2026-11-23)
- Add `metalport lookup` for Steam title and app ID searches, cached Steam depots, and local eligibility checks. Add `metalport check` for downloaded Windows game data.
- Add `mp-mods` for named Thunderstore profiles, reversible mod toggles, dependency checks, and share-code reuse for unchanged exports. Named profiles can launch through Steam on configured ports.
- Fix integer texture handling, resource binding alignment, and multisampled texture array reads during shader translation.
- Expand the porting tutorial and compatibility tracker, including the local Lethal Company v81 smoke test and its open rendering and multiplayer issues.

## 0.6.0 (2026-11-21)
- Opt-in ULTRAKILL scene comparison (`tests/gameplay`): isolated app/profile copies, natural camera capture, dark/solid-frame rejection,
  palette compute OFF/ON dispatch checks and measured pixel differences. The targeted M5/Metal run completes with 99.61% identical
  palette pixels; full campaign and exact parity remain unverified. Installed app/saves are untouched.
- Project renamed **metalport**. Generic names everywhere: launcher/tweaks settings `REPO_*` are now `MP_*` (`MP_LOG`, `MP_INVOKE`,
  `MP_NO_ACTIVATE`, `MP_MOUSE_SCALE`, `MP_WARMUP`), the tweaks library is `metalport_tweaks.dylib` (`tools/tweaks.m`), logs and support
  files live in `~/Library/Logs/metalport` and `~/Library/Application Support/metalport`. Rebuild existing apps with
  `natives.py --tweaks` and `make_launcher.py`.
- Built apps go in `ports/` (git-ignored). Removed R.E.P.O.-only `run.sh` and `steam_appid.txt`.
- Clickteam Fusion (FNAF) packaging moved out: this toolkit is for Unity games only.
- Steam Cloud for native saves (`steam_entry.py --cloud`), Metal HUD opt-in (`-hud`), docs/FEATURES.md, third-party notices.

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
