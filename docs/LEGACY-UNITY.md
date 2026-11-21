# Older Unity games (2019.x – 2020.1): run them on a newer arm64 player

Unity only ships arm64 Mac players from 2020.2 on. A game built with 2019.x has no arm64 player of its own, and a newer player
rejects its data. This path makes a **2021.3** arm64 player read **2019** data. Proven on Outer Wilds (2019.4.39f1 → 2021.3.45f1,
see `GAME-NOTES-OUTERWILDS.md`). It is several times the work of the normal path; use it only when the game's Unity version has no
arm64 player (check: `strings <Data>/globalgamemanagers | head -1`).

Extra tools: `tools/legacy/` (data converter, JSON manifests, type-tree validator), `tools/shader2021.py` (Shader object
rewrite, called by the converter), `tools/ilfix/` (.NET IL rewriter, needs the .NET SDK: `brew install dotnet`, then
`export DOTNET_ROOT=/opt/homebrew/opt/dotnet/libexec`). Python needs `UnityPy`, `dnfile`, `TypeTreeGeneratorAPI`.

## Steps

`OLD` = the game's Unity version, `NEW` = 2021.3.45f1 (any 2021.3 with an arm64 player should do; only 2021.3.45f1 is tested).

1. **Fetch the newer Unity**: `tools/fetch_unity.py NEW unity-NEW`.
2. **Assemble + shaders, as usual**: `tools/port.py --data <depot>/<Game>_Data --unity unity-NEW --out port --name <App>`.
   The injector understands 2019 files (format 21, flat `m_SubPrograms`, local keyword lists) and appends Metal programs in the
   *old* layout. The class-library swap in this step matches nothing (it compares hashes against NEW's Windows libraries).
3. **Keep the injected old-layout files**: `cp -c -R port/<App>.app/Contents/Resources/Data staging` (APFS clone, no disk).
   Step 6 reads `staging`; never point it at the app's own Data (the converter refuses already-converted files).
4. **Swap the managed code to NEW** (in `port/<App>.app/Contents/Resources/Data/Managed`):
   * every `UnityEngine*.dll` ← `unity-NEW/module/**/Payload/Variations/mono/Managed/`
   * every class library that exists in `unity-NEW/monolibs/unityjit-macos/` (and its `Facades/`) ← that file, by name
5. **Manifests NEW reads from JSON** (2019 kept them inside globalgamemanagers):
   `tools/legacy/make_json.py <depot>/<Game>_Data/globalgamemanagers <app Data>/Managed <app Data>`
6. **Convert the data**: `tools/legacy/convert_data.py staging <depot>/<Game>_Data/Managed conv --from OLD --to NEW`,
   then move everything in `conv/` over the app's Data. It adds type trees to every file (MonoBehaviour trees are generated
   from the game's assemblies), stamps NEW, verifies every object's bytes are unchanged, and rewrites only PlayerSettings
   (`activeInputHandler`, else no mouse/keyboard) and Shader objects (`shader2021.py`).
7. **Built-in resources**: copy NEW's stock `unity default resources` (from the arm64 player variation's `Resources/`) over
   the app's `Data/Resources/unity default resources`. Do not convert the old one.
8. **Fix the IL** against NEW's engine API: `cd tools/ilfix/compat && dotnet build -c Release -p:UnityManaged=<app Data>/Managed`,
   then `cd .. && dotnet run -c Release -- fix <app Data>/Managed compat/bin/Release/netstandard2.0/UnityCompat.dll`.
   Check with `dotnet run -c Release -- report <app Data>/Managed` (should print nothing). Keeps `<dll>.orig`.
9. **Natives, sign, launch** as usual: `tools/natives.py --app port/<App>.app --steam --tweaks` (old Steamworks.NET builds get
   shims automatically), `codesign --force --deep -s - port/<App>.app`, `tools/launch.sh port <App> <appid>`.

Use the **non-development** player variation for play (step 2 without `--dev`): the development player crashes on quit in its
memory profiler and shows a watermark.

## What changed between 2019 and 2021 that this path handles

| Area | 2019 → 2021 change | Handled by |
|---|---|---|
| Serialized files | no type trees in release builds; NEW's class layouts differ | `convert_data.py` (type trees + version stamp) |
| MonoBehaviour type trees | generator puts the header align flag on `m_Script`; `string` without children; `string[]` typed as `string` | `convert_data.py` (fixed up) |
| PlayerSettings | two Input System bools → `activeInputHandler` int | `convert_data.py` |
| Shader objects | per-program params → `m_Parameters`; one keyword table; blob entry v202012090; Metal header v5 | `shader2021.py` |
| Metal float3 constants | NEW writes a float3 as 16 bytes, overwriting a scalar D3D packed into lane w (black post-FX) | `shader2021.repack()`: moves it to a free register, patches the MSL **and the blob's trailing binding table** (the player binds from that table, not `m_Parameters`) |
| Assembly list, RuntimeInitializeOnLoad | moved to JSON files | `legacy/make_json.py` |
| UIVertex.uv0–3 | Vector2 → Vector4; `CanvasRenderer.*UIVertexStream` take `List<Vector4>` | `ilfix` + `UnityCompat` shims |
| Types that moved namespace | e.g. Timeline `IAnimationWindowPreview` | `ilfix` |

## Debug kit (also useful for new-player ports)

* `tools/legacy/validate_typetrees.py <Data> [name,...]`: reads every object with its type tree; lists types that fail.
* `ilfix il <dll> <Type> [method]` prints IL; `ilfix calls <dll> <member>` lists callers (e.g. who sets `vSyncCount`).
* `metalport_tweaks` (injected by `launch.sh`):
  * `MP_NO_ACTIVATE=1`: start behind other windows and keep rendering while covered/unfocused (screenshots without
    taking focus; pair with `DIAG_MODE=bg`).
  * `MP_INVOKE="UnityCompat:UnityCompat.Diag:Run"`: calls `UnityCompat.Diag.Run()` in the game every 10 s.
* `UnityCompat.Diag` (`DIAG_MODE`, comma list): `bg` (runInBackground), `fps` (log FPS + pacing settings), `game`
  (Outer Wilds: skip the menu into the world), `sweep` (Outer Wilds: step AO/shadow settings 30 s each), `big`, `probe`,
  `uberinfo`, `cbtest`, `blittest`, `nofx`/`nopp`/`nofog`/`noeye`. `DIAG_PICK_FILE=<f>`: write `x y` (viewport 0–1) into
  `<f>` to log every renderer at that point with its shader. `DIAG_CMD_FILE=<f>`: lines `shadows 0|1`, `comp <Type> 0|1`,
  `res <w> <h>` are applied live. Output goes to the player log (`[diag]` lines).
* GPU cost: `xcrun xctrace record --template 'Metal System Trace' --attach <pid> --time-limit 5s`. The Metal HUD's "GPU" number
  counts one command buffer only; the trace's busy time is the real load.
