# Mod profiles

Install BepInEx with `tools/mods "/path/to/Game.app" install` or build with `tools/metalport port … --mods`. The repository includes `tools/mp-mods`. For the shorter command, run `mkdir -p ~/.local/bin && install -m 755 tools/mp-mods ~/.local/bin/mp-mods` from the checkout and put `~/.local/bin` on your PATH.

Use `--game lc` or `--game repo` for the built-in app locations. For another location use `--app "/path/to/Game.app" --community lethal-company` or the corresponding Thunderstore community slug. Profiles are stored by app bundle identifier.

```sh
mp-mods --game lc profiles
mp-mods --game lc --profile friends-v81-updated list
mp-mods --game lc --profile friends-v81-updated disable DiFFoZ-LethalPerformance
mp-mods --game lc --profile friends-v81-updated enable DiFFoZ-LethalPerformance
mp-mods --game lc --profile friends-v81-updated play
```

Close the game before toggling. The toggle works on CLI-managed packages and preserves their files and settings. Run `check` after disabling a mod to find active dependants. Normal launches are vanilla. For the default mod profile use `mp-mods --game lc play` or `-mods` in Steam Launch Options.

| Command | Use |
|---|---|
| `games`, `profiles` | List game shortcuts or the selected app's profiles |
| `search QUERY [--packs]`, `info PACKAGE` | Browse or inspect Thunderstore packages |
| `add PACKAGE`, `update PACKAGE`, `repair PACKAGE` | Install with dependencies, update one mod, or reinstall its current version |
| `disable PACKAGE`, `enable PACKAGE` | Toggle a managed package |
| `list`, `outdated`, `check`, `folder` | List mods, find newer versions, inspect dependencies and loader errors, or open the plugin folder |
| `pack NAME PACKAGE`, `import NAME CODE_OR_R2Z` | Create a profile from a published pack, manager code or .r2z archive |
| `play [NAME]`, `share [NAME]` | Launch or export the selected profile |

Put global flags before the command. Use `mp-mods COMMAND --help` for arguments. Package references use `Author-Package[-version]` or a Thunderstore URL.

## Sharing and compatibility

`share` uploads enabled package names and pinned versions to Thunderstore. An unchanged export reuses the cached code. Windows friends can import the code in a Thunderstore-compatible manager and select the matching game build. Settings, local patches, native libraries and saves are outside the export. Verify a Mac-to-Windows join before calling the pack compatible.

Windows-native mods and shaders in Windows-built mod bundles can need separate work on Metal. After `check`, test the affected scene in-game. For performance comparisons, use the same scene and resolution and compare frame intervals in the Metal HUD.
