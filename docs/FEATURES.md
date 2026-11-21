# Features and supported games

Last reviewed: 2026-11-21 (toolkit 0.6). Update this page in the same commit as any change it describes.

**Legend:** ✅ **Works**: used in a tested local port within the stated scope. ◐ **Partial**: works with limits (see notes). ❌ **Not yet**: planned or possible,
not done. ⛔ **Out of scope**: outside this toolkit's data/managed-IL approach. A status does not imply every game or feature combination is verified.

## Features

### Game support (what kind of game can be ported)

| Feature | Status | Notes / limits |
|---|---|---|
| Unity Mono games, Unity 2020.2 and newer | ✅ Works | Player must match the game's exact Unity version. Tested on 6000.3 (R.E.P.O.). |
| Unity Mono games, Unity 2019.x – 2020.1 | ✅ Works | Runs the data on a 2021.3 player ([LEGACY-UNITY.md](LEGACY-UNITY.md)). Tested on Outer Wilds (2019.4). Several times the work of a normal port. |
| Built-in render pipeline | ✅ Works | |
| URP | ◐ Partial | Vertex/pixel shaders translate; no URP game fully verified yet. |
| HDRP | ❌ Not yet | Selected compute formats now convert; HDRP-specific passes and full-pipeline gameplay remain unverified (Lethal Company is not ported). |
| Unity IL2CPP games | ⛔ Out of scope | Game code is compiled Windows native code; this toolkit does not translate it. |

### Graphics

| Feature | Status | Notes / limits |
|---|---|---|
| Vertex and pixel shaders, Direct3D 11 → Metal | ✅ Works | Unity's own HLSLcc; results cached per program. |
| Shaders inside AssetBundles / Addressables | ✅ Works | `patch_bundles.py`; non-shader objects verified byte-identical. |
| float3 constant overwrite fix | ✅ Works | Metal writes a float3 as 16 bytes; `cbfix.py` (2020.2+) and `shader2021.py` (2019 data) move the overwritten value. |
| Post-processing v1 (built-in) | ◐ Partial | Tested in Outer Wilds with eye adaptation disabled; its compute path is unverified. |
| Post-processing v2 | ◐ Partial | R.E.P.O.'s listed effects work via fragment fallbacks. Color grading remains off because its LUT bakes to a constant on Metal; other games/combinations need testing. |
| Compute shaders | ◐ Partial | Selected Unity 2021/2022 data converts; three ULTRAKILL kernels pass Unity-player GPU readback. Its palette also renders in a targeted Level 0-1 comparison (99.61% identical pixels vs fallback); full gameplay and exact parity remain unverified ([details](COMPUTE-SHADERS.md#targeted-gameplay-comparison)). |
| Geometry, hull and domain (tessellation) shaders | ❌ Not yet | Default preflight reports unsupported stages and stops. Incomplete opt-in does not establish a working fallback. |
| Vulkan-only (SPIR-V) shader variants | ❌ Not yet | Only D3D11 bytecode is translated. |

### Platform integration

| Feature | Status | Notes / limits |
|---|---|---|
| Native arm64 `.app` (player, .NET class libraries, data clone) | ✅ Works | Uses `cp -c` clones where supported; output still needs space for patched files, caches and metadata. |
| Steam init and overlay | ✅ Works | Uses the local Steam API/client with compatibility shims; coverage depends on the game's wrapper/API version. |
| Steam lobbies, invites and networking | ◐ Partial | Integration exists; R.E.P.O.'s notes do not record a verified friend invite/join test. |
| Voice chat (Photon Voice + Opus) | ◐ Partial | Opus tested in isolation; R.E.P.O. voice has not been verified in a real room. Echo cancellation is a pass-through. |
| Discord SDK | ◐ Partial | No-op stand-in: the game runs, Discord features are off. |
| Double-click launcher with Steam checks | ✅ Works | Dialogs for "Steam not running" and "Steam couldn't confirm ownership". |
| Steam library Play button for the Mac app | ✅ Works | `tools/steam-play <Game.app>` (quits and reopens Steam; Play button + Steam Cloud in one step); may need re-running after a game update. Undo: `tools/steam-play <Game.app> remove`. |
| Metal HUD on demand | ✅ Works | Steam Launch Options `-hud`, or `HUD=1`. |
| Steam Cloud for native saves | ✅ Works | Part of `tools/steam-play` (`steam_entry.py --cloud`): adds a macOS root override so Steam syncs `~/Library/Application Support/<bundle id>` with the Windows save folder. Back up saves first: the first sync replaces local files that differ from the cloud. |
| Mods (BepInEx 5) | ✅ Works | `tools/mods <Game.app> install` (official BepInEx 5.4.23.6 macOS universal build, pinned + checksum); mods go in `~/Library/Application Support/metalport/mods/<bundle id>/BepInEx/plugins`. Verified on R.E.P.O.: plugins load and Harmony patches game code on Apple Silicon. Mods that ship Windows-native DLLs won't work. Steam Launch Options `-nomods` starts without mods. |
| One-step installer from your own Steam copy | ❌ Not yet | Today: the commands in the README. |

### Tooling

| Feature | Status | Notes / limits |
|---|---|---|
| Go/no-go game inspector | ✅ Works | `inspect_game.py`: Unity version, scripting backend, pipeline, plugins. |
| Shader coverage report | ◐ Partial | Per-shader translation coverage and Metal compile checks. |
| In-game diagnostics | ✅ Works | Live commands (camera/effect toggles, layer dumps, object lookup), hidden test runs ([LEGACY-UNITY.md](LEGACY-UNITY.md#debug-kit-also-useful-for-new-player-ports)). |
| Benchmark from a Metal trace | ✅ Works | `bench_trace.py`: FPS, 1 % lows, render size, GPU and CPU load; works for CrossOver builds too. |

## Supported games

"Verified version" is the Steam depot manifest the port was built and tested on; other versions need a rebuild and re-test.
Details per game: [games/](../games).

| Game | Engine | Status | Verified version | Known issues |
|---|---|---|---|---|
| R.E.P.O. | Unity 6000.3, Mono | ✅ Playable | depot 3241661, manifest 4238581831212146714 (v0.5.2) | Color grading off. |
| Outer Wilds | Unity 2019.4 on the 2021.3 player | ◐ Playable with issues | depot 753641, manifest 2759471679100125861 | Giant's Deep surface renders black from afar. |
| ULTRAKILL | Unity 2022.3, Mono | ◐ In progress | depot 1229491, manifest 22957324 | Installed Level 0-1 renders normally (user-confirmed). Palette compute tested in an isolated scene comparison; installed build keeps its fallback. Full campaign and exact palette parity remain unverified. |
| Lethal Company | Unity 2022.3, HDRP | ❌ Blocked | | Needs HDRP support. |

## Roadmap (not started)

1. One-step installer: build, install, Play button and cleanup from your own Steam copy.
2. Post-processing v2 color grading on Metal.
3. HDRP (Lethal Company).
