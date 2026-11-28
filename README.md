# metalport

*Native Apple Silicon ports of Windows Unity games.*

metalport runs a **Windows-only Unity game natively on Apple Silicon with Metal**, without Rosetta, Wine or CrossOver. It wraps the
game's own Windows data in Unity's Mac player and translates its shaders from Direct3D 11 to Metal, once, when building.

> **Notice.** This independent project is not affiliated with, endorsed by, or sponsored by Unity Technologies, Valve, Discord, or any game
> developer or publisher. It contains no game files and no Unity or Valve binaries: those come from your own downloads, on your own Mac.
> You must own each game you port and comply with its license terms; do not share the result. The MIT license covers only this toolkit
> (see [THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md)). Product names and trademarks belong to their respective owners.

## Game compatibility

[Game status and verified versions](games/README.md) tracks playable ports, experiments, and pending checks. Start with a Unity Mono game that uses Built-in or URP rendering. Unity 2019–2020.1 uses the [legacy path](docs/LEGACY-UNITY.md). HDRP is experimental. Windows IL2CPP builds are outside this pipeline.

## Quick start

Requirements: Apple Silicon Mac, Xcode command line tools, Python 3, CMake, Steam with the game in your library.

```sh
tools/metalport lookup "Bopl Battle"
tools/metalport check "/path/to/Windows game folder"
tools/metalport port "/path/to/Windows game folder"
```

The lookup accepts a Steam app ID as well as a name. The check and port commands accept an app ID if its Windows depot is already downloaded. The port writes `ports/<Game>/<Game>.app`, one status line per step. Useful options:

| Option | Effect |
|---|---|
| `--steam-play` | green Play button in Steam's own library entry + Steam Cloud for saves |
| `--mods` | installs BepInEx for mods |
| `--allow-incomplete` | builds even if some shaders can't be translated |
| `-v` | shows every tool's output |

Each run leaves a full log and a JSON summary in `~/Library/Logs/metalport/`. The manual steps behind it are in
[docs/PIPELINE.md](docs/PIPELINE.md) and [docs/PORTING-A-NEW-GAME.md](docs/PORTING-A-NEW-GAME.md).

## Playing

- **Start** the app by double-click or Steam's Play button. Steam must be running and signed in to the account that owns the game.
- **Metal HUD** (fps, GPU time): add `-hud` to the game's Steam Launch Options.
- **Mods** are opt-in. Enable BepInEx with `--mods` at build time or `tools/mods "/path/to/Game.app" install`. Manage named Thunderstore profiles with [mp-mods](docs/MODS.md). For mods applied by r2modmac, use `-mods` in Steam Launch Options.

## Documentation

| Doc | Contents |
|---|---|
| [FEATURES.md](docs/FEATURES.md) | what works, what doesn't, supported games and versions |
| [PIPELINE.md](docs/PIPELINE.md) | how a port works, step by step |
| [PORTING-A-NEW-GAME.md](docs/PORTING-A-NEW-GAME.md) | go/no-go checklist, debugging |
| [LEGACY-UNITY.md](docs/LEGACY-UNITY.md) | Unity 2019 games on the 2021 player |
| [COMPUTE-SHADERS.md](docs/COMPUTE-SHADERS.md), [SHADER-CHECKS.md](docs/SHADER-CHECKS.md) | shader translation and coverage checks |
| [MODS.md](docs/MODS.md) | install, toggle, test and share mod profiles |
| [Game tracker](games/README.md), [roadmap](docs/ROADMAP.md) | per-game status, known blockers and contribution priorities |
| [UPSTREAM-AUDIT.md](docs/UPSTREAM-AUDIT.md) | what other Unity-on-Mac projects do that may help, with licenses and open hypotheses |

## Tests

`python3 -m unittest discover tests` needs no game, Unity player or Steam (`pip install -r requirements.txt` first); Metal and gameplay tests are opt-in. `python3 tools/check_no_game_files.py` fails if game, Unity or Valve files are tracked. CI runs both. Read-only diagnostics: `tools/dump_common_params.py` (shared shader parameters) and `tools/quality_vsync.py` (vSync per quality level).

## Versioning

[VERSION](VERSION) is the toolkit version. During `0.x`, bump the minor version for new commands or CLI changes, and the patch version for compatible fixes. Reserve `1.0.0` for a stable command-line interface. Game build and depot versions are tracked independently. [Semantic Versioning](https://semver.org/) · [Game tracker](games/README.md)

Changes: [CHANGELOG.md](CHANGELOG.md). License: [MIT](LICENSE).
