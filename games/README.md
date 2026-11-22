# Game tracker

| Game | Steam app ID | Status | Verified scope and next gap |
|---|---:|---|---|
| [R.E.P.O.](repo.json) | 3241660 | Playable | Local play and Steam online hosting verified. Friend join and color grading need work. |
| [Outer Wilds](../docs/GAME-NOTES-OUTERWILDS.md) | 753640 | Playable with issues | Legacy Unity path. Giant's Deep surface renders black from a distance. |
| [ULTRAKILL](ultrakill.json) | 1229490 | Experimental port | Menu, tutorial and Level 0-1 tested. Full campaign and palette parity remain open. |
| [Lethal Company](lethal-company.json) | 1966720 | Experimental port | Local v81 launch and modded Gordion landing verified. Rendering parity and Windows multiplayer remain open. |

Follow the [eligibility guide](../docs/PORTING-A-NEW-GAME.md) for new games. A game absent from this table is unassessed here. Mark assessed games as candidate, blocked, experimental, or playable, and name the specific blocker or test.

Record the app ID, Windows depot and manifest, Unity version, scripting backend, render pipeline, native dependencies, and what was tested. List supported manifests only after verification. Keep account data and personal library lists out of the repository.

## Public candidates

Screened using public Steam depot metadata. Build and play tests are still open for these candidates in MetalPort.

| Game or branch | Status | First check |
|---|---|---|
| [Bopl Battle](https://steamdb.info/depot/1686941/) (1686940) | First candidate | Small Windows Mono depot with Steamworks. Test a local match, controllers, then Steam lobbies. |
| [Content Warning](https://steamdb.info/depot/2881651/) (2881650) | URP candidate | Mono and URP assemblies. Test recorded clips, audio, and Photon hosting in addition to rendering. |
| [PEAK](https://steamdb.info/depot/3527291/) (3527290) | URP candidate | Mono and URP assemblies. Check native plugins and test co-op with a Windows player. |
| [Schedule I](https://steamdb.info/app/3164500/depots/) (3164500) | Alternate branch only | The public default uses IL2CPP. Inspect the `alternate` Mono branch and check native Burst dependencies. |
| [Risk of Rain 2](https://steamdb.info/app/632360/depots/) (632360) | Game-specific work | Third-party Apple Silicon port exists. Use it as a reference for Wwise, graphics and Steam work. [Source project](https://github.com/wisnuub/ror2-silicon-macos) |

[Sledding Game](https://steamdb.info/app/3438850/depots/) uses IL2CPP in its current Windows build. [Escape Simulator](https://steamdb.info/app/1435790/depots/) already ships a macOS depot.
