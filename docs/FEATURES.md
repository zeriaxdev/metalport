# Features and supported games

Last reviewed: 2026-11-21 (toolkit 0.5). Update this page in the same commit as any change it describes.

**Legend:** ✅ **Works**: used in a shipped port. ◐ **Partial**: works with limits (see notes). ❌ **Not yet**: planned or possible,
not done. ⛔ **Out of scope**: not possible with this approach.

## Features

### Game support (what kind of game can be ported)

| Feature | Status | Notes / limits |
|---|---|---|
| Unity Mono games, Unity 2020.2 and newer | ✅ Works | Player must match the game's exact Unity version. Tested on 6000.3 (R.E.P.O.). |
| Unity Mono games, Unity 2019.x – 2020.1 | ✅ Works | Runs the data on a 2021.3 player ([LEGACY-UNITY.md](LEGACY-UNITY.md)). Tested on Outer Wilds (2019.4). Several times the work of a normal port. |
| Built-in render pipeline | ✅ Works | |
| URP | ◐ Partial | Vertex/pixel shaders translate; no URP game fully verified yet. |
| HDRP | ❌ Not yet | Needs compute shaders and HDRP-specific passes (blocks Lethal Company). |
| Unity IL2CPP games | ⛔ Out of scope | Game code is compiled Windows x86 code; this toolkit rewrites data, not machine code. |

### Graphics

| Feature | Status | Notes / limits |
|---|---|---|
| Vertex and pixel shaders, Direct3D 11 → Metal | ✅ Works | Unity's own HLSLcc; results cached per program. |
| Shaders inside AssetBundles / Addressables | ✅ Works | `patch_bundles.py`; non-shader objects verified byte-identical. |
| float3 constant overwrite fix | ✅ Works | Metal writes a float3 as 16 bytes; `cbfix.py` (2020.2+) and `shader2021.py` (2019 data) move the overwritten value. |
| Post-processing v1 (built-in) | ✅ Works | Eye adaptation uses a compute shader; games ship it disabled. |
| Post-processing v2 | ◐ Partial | Everything except color grading, which is switched off (its LUT bakes to a constant on Metal). |
| Compute shaders | ◐ Partial | Converter for Unity 2021/2022 compute data exists with unit tests; not yet verified in a running game. |
| Geometry, hull and domain (tessellation) shaders | ❌ Not yet | Shaders that need them are skipped and fall back. |
| Vulkan-only (SPIR-V) shader variants | ❌ Not yet | Only D3D11 bytecode is translated. |

### Platform integration

| Feature | Status | Notes / limits |
|---|---|---|
| Native arm64 `.app` (player, .NET class libraries, data clone) | ✅ Works | Game data is an APFS clone of your Steam download: no extra disk until files differ. |
| Steam (init, ownership, overlay, lobbies, networking) | ✅ Works | Newer and older Steamworks.NET builds; missing flat-API calls are shimmed. |
| Voice chat (Photon Voice + Opus) | ✅ Works | Echo cancellation is a pass-through. |
| Discord SDK | ◐ Partial | No-op stand-in: the game runs, Discord features are off. |
| Double-click launcher with Steam checks | ✅ Works | Dialogs for "Steam not running" and "Steam couldn't confirm ownership". |
| Steam library Play button for the Mac app | ✅ Works | `steam_entry.py`; Steam must be closed while it runs; may need re-running after a game update. |
| Metal HUD on demand | ✅ Works | Steam Launch Options `-hud`, or `HUD=1`. |
| Steam Cloud for native saves | ✅ Works | `steam_entry.py --cloud`: adds a macOS root override so Steam syncs `~/Library/Application Support/<bundle id>` with the Windows save folder. Back up saves first: the first sync replaces local files that differ from the cloud. |
| Mods (BepInEx) | ❌ Not yet | Needs the macOS Doorstop loader. |
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
| ULTRAKILL | Unity 2022.3, Mono | ◐ In progress | depot 1229491, manifest 22957324 | Menu and tutorial work; campaign not verified; compute effects off. |
| Lethal Company | Unity 2022.3, HDRP | ❌ Blocked | | Needs HDRP support. |
| Five Nights at Freddy's 1–4, Sister Location, Pizzeria Simulator | Clickteam Fusion 2.5 | ◐ Separate path | | Packaged around a user-built KlikCore2 runtime (`make_fusion_app.py`); FNAF 1 verified. |

## Roadmap (not started)

1. One-step installer: build, install, Play button and cleanup from your own Steam copy.
2. Post-processing v2 color grading on Metal.
3. Mods via BepInEx.
4. HDRP (Lethal Company).
