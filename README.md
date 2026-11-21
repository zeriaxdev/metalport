# metalport

*Native Apple Silicon ports of Windows Unity games.*

Run a **Windows-only Unity game natively on Apple Silicon with Metal** — no Rosetta, no Wine/CrossOver — by wrapping the game's
existing Windows data in a macOS Unity player and translating its shaders from Direct3D 11 to Metal.

Ported so far: **R.E.P.O.** (playable, ~110-130 fps at 3024x1898 on an Apple M5, Steam overlay; see multiplayer/voice limits in the feature list) and **Outer Wilds**
(playable with one rendering issue). **What works, what doesn't, and which games are supported: [docs/FEATURES.md](docs/FEATURES.md).**

> **Notice.** This independent project is not affiliated with, endorsed by, or sponsored by Unity Technologies, Valve, Discord, or any game
> developer or publisher. It contains no game files and no Unity or Valve binaries: those come from your own downloads, on your own Mac
> (the Unity player from Unity's official download service, the game from your own Steam library). You must own each game you port and
> comply with its license terms; do not share the result. The toolkit's MIT license covers only this toolkit, not game content, engine
> runtimes or other third-party software (see [THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md)). Product names and trademarks belong to
> their respective owners.

## Does it work for my game?

| Requirement | Why |
|---|---|
| Unity **Mono** build with managed game-code DLLs | This toolkit handles data and managed IL; it does not translate IL2CPP's native Windows game code |
| Windows build on **Direct3D 11** shaders (typical) | Shaders are translated from DX11 bytecode |
| **Built-in / URP** style rendering | Vertex/pixel shaders and selected Unity 2021/2022 compute formats convert; full HDRP, geometry and tessellation remain unsupported. URP gameplay still needs validation |
| A compatible macOS Apple-Silicon player | Use the exact Unity version for the normal route. Unity 2019.x–2020.1 needs the separate [legacy migration](docs/LEGACY-UNITY.md) |

Details and the go/no-go checklist: [docs/PORTING-A-NEW-GAME.md](docs/PORTING-A-NEW-GAME.md).

## Quick start (macOS, Apple Silicon)

```sh
# 0. prerequisites: Xcode command line tools, cmake, python3, (brew install opus for voice games)
python3 -m venv .venv && .venv/bin/pip install UnityPy lz4 dnfile

# 1. get the Unity pieces for the game's exact Unity version (find it with: strings <Game>_Data/globalgamemanagers | head -1)
.venv/bin/python tools/fetch_unity.py 6000.3.28f1 work/unity          # ~0.7 GB download + ~5 GB streamed, ~100 MB kept

# 2. build + patch (game data stays untouched; the .app gets APFS-cloned copies)
.venv/bin/python tools/port.py --data "<path to Game_Data>" --unity work/unity --out work/out --name Game

# 3. native stand-ins for Windows-only plugins, then sign
# Select the flags your game needs; --discord and --voice are additional per-game integrations.
.venv/bin/python tools/natives.py --app work/out/Game.app --tweaks --steam
codesign --force --deep -s - work/out/Game.app

# 4. double-click launcher (Steam checks, overlay, first-run shader warm-up; Steam Launch Options -hud shows the Metal HUD)
.venv/bin/python tools/make_launcher.py work/out/Game.app --appid <steam app id> && codesign --force --deep -s - work/out/Game.app

# 5. optional: green Play button in Steam's own library entry + Steam Cloud for the saves (quits and reopens Steam)
tools/steam-play work/out/Game.app

# 6. optional: BepInEx mods (then: tools/mods work/out/Game.app open, and drop mod .dll files in)
tools/mods work/out/Game.app install
```

The example writes `work/out/Game.app`; `--out` controls the location. Local tested ports are kept under `ports/` (git-ignored), e.g. `ports/R.E.P.O.app`.
Default preflight stops on unsupported or failed shader variants. Explicit incomplete experiments remain unverified for rendering; see [SHADER-CHECKS.md](docs/SHADER-CHECKS.md).

## Layout

| Path | What |
|---|---|
| `tools/fetch_unity.py` | downloads Unity's Mac player module + streams the macOS Mono class libraries |
| `tools/port.py` | orchestrates assemble → translate → inject |
| `tools/assemble_app.py` | builds the `.app`: player, class-library swap, BuildSettings, Addressables fix |
| `tools/xlate_all.py`, `dxbc_rdef.py`, `h2m.cpp`, `build_hlslcc.sh` | DX11 bytecode → Metal source (Unity's own open-source HLSLcc) |
| `tools/inject.py`, `inject_inplace.py`, `metalsub.py` | writes the Metal variants into the game's `Shader` objects |
| `tools/natives.py` + `*.c`, `tweaks.m` | Steam / Discord / Photon-voice / mouse / warm-up stand-ins |
| `tools/launch.sh`, `tools/make_launcher.py`, `tools/steam_entry.py` | launchers: command line, double-click `.app`, Steam Play button and Steam Cloud |
| `docs/` | feature and game support list, how it works, porting guide, older-Unity path, per-game notes |
| `games/` | per-game data (Steam ids, depot manifests = supported versions, status, issues) for R.E.P.O., ULTRAKILL, Lethal Company |

## Status and versions
See [CHANGELOG.md](CHANGELOG.md). Current: see [VERSION](VERSION).
