# metalport

**Play Windows-only Unity games natively on Apple Silicon.** No Rosetta, no Wine, no CrossOver. Metal graphics, Steam overlay, invites and mods.

metalport takes the Windows copy of a game you own, wraps its data in Unity's own Mac player, and translates its shaders from Direct3D 11 to Metal. The translation happens once, on your Mac, when you build the app.

> [!IMPORTANT]
> **This repository contains no game files and no Unity or Valve binaries.** The game comes from your own Steam download and the player from Unity's servers, both on your own Mac. You must own each game you port and follow its license. Don't share the app you build: it contains the whole game. Share this page instead.

> This independent project is not affiliated with, endorsed by, or sponsored by Unity Technologies, Valve, Discord, or any game developer or publisher. Product names and trademarks belong to their respective owners.

## Games

| Game | Status | What was tested |
|---|---|---|
| [R.E.P.O.](games/repo.json) | Playable | Local play, Steam online hosting and mods. Color grading is off; joining a friend is untested. |
| [Lethal Company](games/lethal-company.json) | Experimental | v81 launches, hosts a LAN game and lands on Gordion with casino mods. HDRP rendering has gaps; Windows multiplayer is untested. |
| [ULTRAKILL](games/ultrakill.json) | Experimental | Menu, tutorial and Level 0-1. Full campaign and palette parity are open. |
| [Outer Wilds](docs/GAME-NOTES-OUTERWILDS.md) | Playable with issues | Runs through the [legacy path](docs/LEGACY-UNITY.md). Giant's Deep renders black from a distance. |

The [full tracker](games/README.md) has versions, blockers and candidate games. Start with a **Unity Mono** game on the Built-in or URP pipeline. HDRP is experimental, and IL2CPP builds are out of scope.

## What you need

- A Mac with Apple Silicon and the Xcode command line tools
- Python 3 and CMake
- Steam, signed in to the account that owns the game
- The game's Windows depot downloaded ([how](docs/PORTING-A-NEW-GAME.md))
- Several GB of free space

## Quick start

```sh
tools/metalport lookup "Bopl Battle"          # find the Steam app ID and depot
tools/metalport check  /path/to/Windows/game  # go/no-go report, builds nothing
tools/metalport port   /path/to/Windows/game  # builds ports/<Game>/<Game>.app
```

`lookup` takes a name or an app ID. `check` and `port` take a game folder, or an app ID whose Windows depot is already downloaded. Every run prints one status line per step and writes a full log and JSON summary to `~/Library/Logs/metalport/`.

| Option | Effect |
|---|---|
| `--steam-play` | Adds a Play button to the game's Steam library entry, plus Steam Cloud for saves. Quits and reopens Steam. |
| `--mods` | Installs BepInEx so the game can load mods |
| `--allow-incomplete` | Builds even if some shaders can't be translated |
| `--replace` | Moves an existing app to the Trash first |
| `-v` | Streams every tool's output |

The manual steps behind it: [PIPELINE.md](docs/PIPELINE.md) and [PORTING-A-NEW-GAME.md](docs/PORTING-A-NEW-GAME.md).

## Playing

- **Start** the app by double-click or from Steam's Play button. Steam must be running and signed in.
- **Metal HUD** (fps, GPU time): add `-hud` to the game's Steam Launch Options.
- **Mods** are opt-in. Build with `--mods`, or run `tools/mods "/path/to/Game.app" install`. Add `-mods` to the Launch Options to load mods applied by r2modmac. Named Thunderstore profiles: [MODS.md](docs/MODS.md).
- **Saves** sync through Steam Cloud when you built with `--steam-play`.

## How it works

```
Windows game data ─┐
                   ├─ Unity Mac player (exact version) ─┐
Unity Mono libs  ──┘                                    ├─ Game.app
D3D11 shaders ── HLSLcc ── Metal (injected into data) ──┤
Steam / voice / Discord stand-ins ──────────────────────┘
```

The player must match the game's exact Unity version. Shaders go through Unity's own [HLSLcc](https://github.com/Unity-Technologies/HLSLcc) with a few local patches, and the Metal programs are appended to the game's serialized shader objects. Native Windows plugins are replaced by Mac equivalents or stubs. Details: [PIPELINE.md](docs/PIPELINE.md).

## What works

| Area | Status |
|---|---|
| Vertex and pixel shaders, Direct3D 11 to Metal | Works |
| Compute shaders | Partial. Selected Unity 2021/2022 data converts. |
| Geometry, hull and domain shaders | Not yet |
| Steam init, overlay, rich presence, Cloud | Works |
| Steam lobbies and invites | Partial. Hosting works, joining a friend is untested. |
| Voice chat | Partial. Built, not yet verified in a real room. |
| Mods (BepInEx 5) | Works |
| Unity 2019 to 2020.1 games | Works with more manual effort |
| IL2CPP games | Out of scope |

Every row with its limits: [FEATURES.md](docs/FEATURES.md).

## Documentation

| Doc | Contents |
|---|---|
| [FEATURES.md](docs/FEATURES.md) | what works, what doesn't, supported versions |
| [PIPELINE.md](docs/PIPELINE.md) | how a port works, step by step |
| [PORTING-A-NEW-GAME.md](docs/PORTING-A-NEW-GAME.md) | go/no-go checklist, debugging |
| [LEGACY-UNITY.md](docs/LEGACY-UNITY.md) | Unity 2019 games on the 2021 player |
| [COMPUTE-SHADERS.md](docs/COMPUTE-SHADERS.md), [SHADER-CHECKS.md](docs/SHADER-CHECKS.md) | shader translation and coverage checks |
| [MODS.md](docs/MODS.md) | install, toggle, test and share mod profiles |
| [Roadmap](docs/ROADMAP.md), [game tracker](games/README.md) | known blockers and contribution priorities |
| [UPSTREAM-AUDIT.md](docs/UPSTREAM-AUDIT.md) | what other Unity-on-Mac projects do that may help, with licenses |

## Contributing and tests

```sh
pip install -r requirements.txt
python3 -m unittest discover tests     # needs no game, Unity player or Steam
python3 tools/check_no_game_files.py   # fails if game, Unity or Valve files are tracked
```

CI runs both. Metal and gameplay tests are opt-in. Read-only diagnostics: `tools/dump_common_params.py` (shared shader parameters) and `tools/quality_vsync.py` (vSync per quality level). Pick a task from the [roadmap](docs/ROADMAP.md) or test a [candidate game](games/README.md).

## Versioning and license

[VERSION](VERSION) is the toolkit version. During `0.x`, the minor version changes for new commands or CLI changes and the patch version for compatible fixes; `1.0.0` is reserved for a stable command-line interface. Game builds and depot versions are tracked independently. Changes: [CHANGELOG.md](CHANGELOG.md).

The toolkit is [MIT](LICENSE) licensed; third-party code is listed in [THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md).
