# metalport

*Native Apple Silicon ports of Windows Unity games.*

metalport runs a **Windows-only Unity game natively on Apple Silicon with Metal**, without Rosetta, Wine or CrossOver. It wraps the
game's own Windows data in Unity's Mac player and translates its shaders from Direct3D 11 to Metal, once, when building.

> **Notice.** This independent project is not affiliated with, endorsed by, or sponsored by Unity Technologies, Valve, Discord, or any game
> developer or publisher. It contains no game files and no Unity or Valve binaries: those come from your own downloads, on your own Mac.
> You must own each game you port and comply with its license terms; do not share the result. The MIT license covers only this toolkit
> (see [THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md)). Product names and trademarks belong to their respective owners.

## Status

| Game | State |
|---|---|
| R.E.P.O. | ✅ Playable: ~110–130 fps at 3024×1898 (M5), Steam overlay, online hosting, Steam Cloud, mods |
| Outer Wilds | ◐ Playable with one rendering issue |
| ULTRAKILL | ◐ In progress |
| Lethal Company | ❌ Not ported (HDRP; shader coverage measured) |

Full feature list, limits and verified versions: **[docs/FEATURES.md](docs/FEATURES.md)**.

## Does my game qualify?

- **Unity with Mono** (the game folder has `<Game>_Data/Managed/*.dll`). IL2CPP and Unreal games can't be ported this way.
- **Unity 2020.2 or newer.** Unity 2019–2020.1 needs the [legacy path](docs/LEGACY-UNITY.md).
- **Built-in or URP rendering.** HDRP isn't supported yet.

`tools/metalport` checks all of this first and stops with a plain reason.

## Quick start

Requirements: Apple Silicon Mac, Xcode command line tools, Python 3, CMake, Steam with the game in your library.

```sh
tools/metalport port <steam app id | game folder>
```

Writes `ports/<Game>/<Game>.app`, one status line per step. Useful options:

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
- **Mods** are off unless asked for: install them with [r2modmac](https://github.com/Zard-Studios/r2modmac) ("Apply to Game") or
  `tools/mods <app> add <Author-Mod>`, then add `-mods` to Steam's Launch Options.

## Documentation

| Doc | Contents |
|---|---|
| [FEATURES.md](docs/FEATURES.md) | what works, what doesn't, supported games and versions |
| [PIPELINE.md](docs/PIPELINE.md) | how a port works, step by step |
| [PORTING-A-NEW-GAME.md](docs/PORTING-A-NEW-GAME.md) | go/no-go checklist, debugging |
| [LEGACY-UNITY.md](docs/LEGACY-UNITY.md) | Unity 2019 games on the 2021 player |
| [COMPUTE-SHADERS.md](docs/COMPUTE-SHADERS.md), [SHADER-CHECKS.md](docs/SHADER-CHECKS.md) | shader translation and coverage checks |
| `GAME-NOTES-*.md`, [games/](games) | per-game notes and data |

Changes: [CHANGELOG.md](CHANGELOG.md). License: [MIT](LICENSE).
