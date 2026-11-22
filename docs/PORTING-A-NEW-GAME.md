# Porting another Unity game

## Find candidates before downloading

Start with `tools/metalport lookup "Bopl Battle"` or pass a Steam app ID. It searches the Steam Store's English-language US catalog and reads public depot IDs and manifests already cached by the local Steam client. When Windows game data is present, it runs the normal eligibility check. A store result alone leaves the backend and shader inputs unknown. The lookup does not fetch game files or use SteamDB.

1. Open [SteamDB Instant Search](https://steamdb.info/instantsearch/). Select **Technologies → Unity** and **Platforms → Windows**. Check the list of [detected Mono titles](https://steamdb.info/tech/SDK/Mono/) for more leads. Technology detection can mix platforms and branches.
2. Open the app's **Depots** page. Check for an official macOS build first. On the intended Windows branch, open the depot's file list if available. Look for both `Managed/Assembly-CSharp.dll` and the Mono runtime. If the title also has IL2CPP, check the exact branch you plan to use. Schedule I, for example, has a separate Mono branch.
3. Compare likely work. A small game with local play and few native plugins makes a good first test. For a co-op game, budget time for a real host/join test, voice chat and saves. Required Windows-only plugins, native Burst jobs, recording/encoding, middleware and unsupported shader features can each hold up a Mono port. The [game tracker](../games/README.md#public-candidates) shows examples.

## 1. Check the Windows build

1. Find the Steam app ID and open its depots page, for example [Lethal Company on SteamDB](https://steamdb.info/app/1966720/depots/). Look for a Windows depot. A technology tag or listed macOS depot is a clue. Both the backend and the pipeline can change across builds. Valve's publisher depot-version API requires a publisher key. [Steamworks API documentation](https://partner.steamgames.com/doc/webapi/ISteamApps#GetAppDepotVersions)
2. In the Steam console (`steam://open/console`), run `app_info_print <app ID>` to confirm the Windows depot and manifest. For a game you own, run `download_depot <app ID> <depot ID> <manifest ID>`. Use the path Steam prints. Depot IDs are assigned independently of app IDs.
3. Inspect that depot locally.

```sh
tools/metalport check "/path/to/Windows depot"
```

Typical Mono builds have `<Game>_Data/Managed/Assembly-CSharp.dll`. `GameAssembly.dll` with `il2cpp_data/Metadata/global-metadata.dat` indicates IL2CPP. URP and HDRP assemblies are useful hints about the render pipeline. This step reports the local build. Shader compile results and a gameplay test establish compatibility.

| Report line | Meaning |
|---|---|
| Scripting backend: **IL2CPP** | stop — game logic is native Windows code (needs a different approach) |
| Render pipeline: **HDRP** | full-pipeline compatibility is unverified; selected compute formats now convert, which alone is insufficient |
| Shaders: only `D3D11` + 6 internal ones | expected; the toolkit adds Metal |
| Shaders: `OpenGLCore` variants present | An Intel-compatible player/OpenGL experiment is a separate route; it does not establish native arm64 Metal compatibility |
| Shaders: only `Vulkan` / SPIR-V input | This toolkit has no SPIR-V input backend; Vulkan variants are not OpenGLCore programs |
| Native plugins | each is a work item (see §3) |
| Addressables | path fix is automatic; bundles may contain more shaders (see §4) |

Quick check of required Unity version: `strings <Data>/globalgamemanagers | head -1`. **2019.x – 2020.1** has no arm64 player: follow
[LEGACY-UNITY.md](LEGACY-UNITY.md) instead (runs the data on a 2021.3 player; several times the work).

## 2. Run the pipeline
Build from the checked folder.

```sh
tools/metalport port "/path/to/Windows depot" --appid 1966720
```

Replace the example app ID with the game's ID. Use a fresh output folder. Start by launching vanilla and checking the title screen, a gameplay scene, input, audio and saves. Test Steam services separately before enabling mods. If you use `--allow-incomplete`, record missing shaders in the [game tracker](../games/README.md). Shader translation and Metal compilation must pass before assembly; loose and bundled shaders are patched in the copied app. See [SHADER-CHECKS.md](SHADER-CHECKS.md) for JSON reports, failure statuses and explicit incomplete experiments.

## 3. Native plugins
List: `ls <Data>/Plugins/x86_64`. For each, find the P/Invoke library *name* the managed code uses (`strings <Data>/Managed/*.dll | grep -i <name>`), then decide:
* Steamworks → `natives.py --steam`.
* A library with an open-source macOS build (Opus, SQLite, FMOD wrappers…) → map it with a `dllmap` entry to a macOS build.
* Optional integrations the game tolerates without the service can use an explicit disabled/no-op implementation (see `discord` in `natives.py`). Required native dependencies, including required anti-cheat, remain blockers; do not assume they can be stubbed safely.
* To get exact signatures of P/Invoke functions (needed to write shims), parse the managed assembly metadata with `dnfile` (ImplMap table); the decoder used for Photon is described in PIPELINE.md.

## 4. Debug loop
Always launch with a log: `MP_LOG=/tmp/game.log tools/launch.sh <dir> <App> <appid>`.
| Symptom in the log | Cause / fix |
|---|---|
| `Forced GfxDevice 'Metal' was not built from editor` | `patch_buildsettings.py` didn't run / m_GraphicsAPIs not last field |
| `Desired shader compiler platform 14 is not available in shader blob` | a shader wasn't patched (multi-chunk, geometry stage, or in an AssetBundle) |
| `use of undeclared identifier 'sampN'` (MSL compile errors) | sampler naming — `dxbc_rdef.py` must name samplers `sampler_s<N>` |
| `Interop+Kernel32` / `BCrypt` DllNotFound/EntryPointNotFound | Windows class libraries still present (BCL swap) |
| `Invalid path in AssetBundleProvider` | Addressables backslashes / the `Resources` symlink beside the `.app` |
| `TypeInitializationException … PhotonNetwork` and `Animator Controller ... not valid` | a serialized file was re-serialized with UnityPy — restore the original and use `inject_inplace.py` |
| game quits: `Steam not initialized` | `natives.py --steam`, Steam running + signed in, `SteamAppId` set |
| `EntryPointNotFoundException: SteamAPI_Steam…_v0NN` | the borrowed libsteam_api is too old for that flat-API symbol → shim it |
| `dlopen … code signature invalid` | re-sign copied dylibs |
| a native call returns `BadArguments`/garbage though the library is the real one | **variadic C functions called with fixed arguments** (Apple arm64 passes variadic args on the stack): look at the P/Invoke *EntryPoint* (ImplMap) and wrap it with a non-variadic export (see `voice_shim.c`) |
| pink / black objects, no log line | a shader variant wasn't translated (`untranslated_variants` in the injector stats) |
| the whole scene black, UI visible | first verify the real camera pose/target and normal startup; then isolate post-processing in a separate copy. A shader exclusion is an incomplete experiment, not a verified fix |

Testing without taking over the screen, live toggles, FPS logging, GPU tracing: see the debug kit in [LEGACY-UNITY.md](LEGACY-UNITY.md#debug-kit-also-useful-for-new-player-ports).

## 5. Things you will probably still hit
* **AssetBundles with shaders** (Addressables / `StreamingAssets`): `port.py` now invokes the existing `tools/patch_bundles.py` helper automatically. For manual work, pass copies of the bundle files to the helper; it rewrites them in place, preserves non-shader object bytes and verifies the repacked entries. It also accepts loose serialized files.
* **Input:** mouse deltas are small → `MP_MOUSE_SCALE`; keyboard layout switching can spam the log.
* **Window titles / Win32 calls** (`user32.dll FindWindow`) throw once per call; harmless unless the game depends on them.
* **Performance:** the player runs at the display's native resolution and refresh (ProMotion 120 Hz) → cap frame rate or lower resolution in-game if the laptop runs hot.

## 6. Legal
Personal use only: you need to own the game; do not share the patched build or Unity's player; this repo has no game or Unity files.
