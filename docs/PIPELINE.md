# How the port works

Idea: a Unity game's **data** (scenes, assets, scripts as IL, shaders) is mostly platform-independent. What is not: the player
executable, the .NET class libraries, the graphics-API-specific shader code, and native plugins. Replace those four things and the
Windows data runs on a macOS arm64 player with Metal.

```
Windows depot  ──clone──►  App.app/Contents/Resources/Data   (APFS clone: no extra disk until patched)
Unity Mac player (same version) ──►  App.app/Contents/{MacOS,Frameworks}
macOS Mono class libraries      ──►  Data/Managed/{mscorlib,System*,netstandard}.dll   (replace the Windows ones)
D3D11 shader bytecode ──HLSLcc──► Metal source ──►  appended to every Shader object (+ BuildSettings says "Metal")
native stand-ins ──► Contents/Plugins  (+ Mono dllmap)
```

## Step by step (what `tools/port.py` does)

### 1. Unity pieces — `fetch_unity.py`
The player must be the **exact** Unity version of the game (`6000.3.28f1`); serialized data is version-checked. Unity's release API
(`services.api.unity.com/unity/editor/release/v1/releases?version=...`) lists installers. We need:
* the **Mac Mono Support** module (~0.7 GB): `Variations/macos_arm64_player_{development,nondevelopment}_mono/UnityPlayer.app`, the
  `Info.plist`/`MainMenu.nib` templates, and `MonoBleedingEdge/etc`.
* the **macOS Mono class libraries** (`lib/mono/unityjit-macos`). They only exist inside the 5 GB Editor `.pkg` (a flat *xar* with a gzip'd cpio
  `Payload`). `fetch_unity.py` reads the xar table of contents with an HTTP range request and streams the payload through `gunzip | cpio`, keeping only
  `*lib/mono/unityjit*` (~100 MB) so nothing big touches the disk.

### 2. Assemble — `assemble_app.py`
* Player executable + frameworks from the nondevelopment variation (the development one adds a profiler and on-screen console; ~30% more CPU).
* `Info.plist` from Unity's template (executable/bundle id/name), `NSAppSleepDisabled`, `NSMicrophoneUsageDescription`.
* **Class libraries:** the Windows build's `mscorlib.dll`/`System*.dll` P/Invoke Win32 (`Interop+Kernel32`, `BCrypt`). Files that are byte-identical to Unity's
  `unityjit-win32` build are replaced by the `unityjit-macos` build (22 files for R.E.P.O.). Game/package assemblies are untouched.
* **`BuildSettings.m_GraphicsAPIs`** (in `globalgamemanagers`) lists the APIs the build was made for (`[D3D11, D3D12]`). The player refuses Metal with
  *"Forced GfxDevice 'Metal' was not built from editor"* and falls back to a Null device. `patch_buildsettings.py` flips the first entry to Metal (id 16) with a
  same-size **in-place byte patch**.
* **Addressables:** Windows catalogs store paths like `{RuntimePath}\StandaloneWindows64\x.bundle`. `fix_addressables.py` swaps `\Platform\` → `/Platform/`
  (same length in `catalog.bin`). Additionally one bundle path was resolved *relative to the directory containing the .app*, hence the `Resources` symlink next to the app.

### 3. Translate shaders — `xlate_all.py`, `dxbc_rdef.py`, `h2m.cpp`
Every Unity shader has per-platform *subprograms*. The Windows build only has Direct3D 11 (DXBC) ones. We feed each to **HLSLcc**, Unity's own open-source
HLSL-bytecode cross compiler, which is exactly what Unity uses to produce its Metal shaders. Two problems had to be solved:
* **Unity strips the `RDEF` chunk** (constant-buffer/texture reflection) from shipped DXBC, and HLSLcc crashes without it. `dxbc_rdef.py` rebuilds a minimal `RDEF` from the
  `dcl_constantbuffer / dcl_resource / dcl_sampler` declarations inside the shader bytecode (generic names `cbN`, `texN`, `sampler_sN`; each constant buffer is one `float4 cbN_data[size]`).
  Because constant-buffer data is uploaded by Unity using the D3D11 layout (offsets/names live in the shared *parameter blob*), a flat vec4 array is binary compatible.
  Binding indices therefore equal the D3D11 register numbers, which is also what Unity's own Metal output does (`buffer(0)` = `cb0`).
* **Sampler naming:** HLSLcc declares samplers as `sampler<name>` but references `<name>`; names must start with `sampler` or compilation fails (`use of undeclared identifier`).
* `h2m` flags: `0x1020081` = UBO | UBO_WITH_INSTANCE_NAME | TRANSLATE_MATRICES | INOUT_SEMANTIC_NAMES.
* Success rate on R.E.P.O.: 5826 / 5871 unique programs. The 45 failures are `StructuredBuffer` (DOTS/BRG instancing) variants and 1 geometry shader. Custom-data blocks (`dcl_immediateConstantBuffer`) must be skipped
  correctly when scanning declarations (length is in the next dword).

### 4. Inject Metal variants — `inject.py`, `inject_inplace.py`, `metalsub.py`
Binary layout of a `Shader` object (Unity 2021.2+, subprogram version `202012090`):
* `platforms[]` (ShaderCompilerPlatform ids: **4 = D3D11, 14 = Metal**, 15 OpenGLCore, 18 Vulkan), parallel arrays `offsets[][]`, `compressedLengths[][]`, `decompressedLengths[][]`,
  one **LZ4 block per chunk**, all concatenated in `compressedBlob`. `stageCounts[]` = number of distinct GPU program types of that platform (2 for Metal: VS+FS).
* Chunk 0 starts with a table: `u32 count`, then `count × (u32 offset, u32 length, u32 chunk)`. Small shaders keep their data in chunk 0; big ones (the post-processing *Uber* shader,
  4227 blobs) keep a table-only chunk 0 and data in chunks ≥1 (~8 MiB each).
* Blob types: parameter blobs (reflection: constant buffers, textures, samplers, bindings; **shared** between platforms, so Metal reuses the D3D11 ones — the only platform difference is
  a stereo constant-buffer size) and program blobs. A **program blob** = `[version][gpuProgramType][4× stats][keywords…][u32 dataLen][data][pad4][tail]`.
  For Metal `data` = a constant 48-byte prefix + `"xlatMtlMain\0"` + MSL source + `\0`; prefix int #9 is `37`, `+2` for instancing variants.
  The **tail** for vertex programs is `[channelMask][count] + count×(channel, slot)`; D3D11 stores `(channel, channel)`, Metal stores `(channel, 13 + k)`. Pixel programs: `(0,0)`.
* `m_ParsedForm…progVertex/progFragment.m_PlayerSubPrograms[group]` is a list of `{blobIndex, keywordIndices, shaderRequirements, gpuProgramType}`; D3D11 VS/PS = `15..16 / 17..18`,
  Metal VS/FS = `23 / 24`. For every D3D11 entry we append a Metal entry (same blob index/keywords) and extend `m_ParameterBlobIndices` in parallel.
* Verified by regenerating Unity's own Metal subprograms for its 6 internal shaders: header, keywords, prefix and tail matched 59/59 (the MSL text differs only because our RDEF names are generic).

**Writing the result — never re-serialize whole files.** UnityPy can rewrite a whole serialized file, but doing so on R.E.P.O. broke Photon and Animator controllers (unknown/raw objects). Instead
`inject_inplace.py` **appends** the new Shader bytes at the end of the file and edits only the 24-byte object-table entry (`i64 pathId, i64 offset, u32 size, i32 type`) plus the header's file size. Everything else stays byte-identical.
(`save_typetree()` *returns* the new bytes; `get_raw_data()` keeps returning the old ones — easy to trip on.)

### 5. Native stand-ins — `natives.py`
The game's `Plugins/x86_64/*.dll` cannot load. Managed code P/Invokes them by *name*; Mono's `dllmap` (in `MonoBleedingEdge/etc/mono/config`) redirects names to dylibs in `Contents/Plugins`.
* **Steam:** any installed Steam game ships a universal `libsteam_api.dylib`; the tool picks one that exports `SteamInternal_SteamAPI_Init` and adds a tiny shim for flat-API calls newer than that SDK
  (`SteamAPI_SteamUGC_v020`, … implemented via `SteamInternal_FindOrCreateUserInterface`). Borrowed dylibs must be **re-signed** after copying (`codesign --force -s -`) or `dlopen` fails with *code signature invalid*.
* **Discord Social SDK:** no macOS build available → no-op stand-in (stops a DllNotFoundException every frame, which cost real CPU).
* **Apple-arm64 variadic trap (found the hard way):** Photon declares the P/Invokes `opus_encoder_ctl_set/_get` with *entry point* `opus_encoder_ctl` — libopus' **variadic** function — and calls it with fixed arguments. On Apple arm64 variadic arguments are passed on the *stack*, so libopus read garbage (`InbandFec … BadArguments`, voice codec never created). `voice_shim.c` exports non-variadic `opus_encoder_ctl`/`opus_decoder_ctl` that forward to the real variadic ones (GET requests are odd numbers and take a pointer). Check the real entry names with the ImplMap table (`tools/natives.py` docs / dnfile), not the managed method names.
* **Photon Voice:** `opus_egpv` is stock Opus → Homebrew libopus + `voice_shim.c`; `webrtc-audio` (echo cancel/AGC/NS) → pass-through with an energy VAD; `AudioIn` → no native mics.
* **`repo_tweaks.dylib`** (injected via `DYLD_INSERT_LIBRARIES`): scales mouse deltas (macOS reports far smaller deltas than Windows raw input), disables App Nap (audio died when unfocused), and optionally calls `Shader.WarmupAllShaders()` through the Mono API.

### 6. Sign and launch — `launch.sh`
* Ad-hoc `codesign --force --deep -s -`; **re-sign after every change** inside the bundle (and never re-sign a running app).
* `MTL_HUD_ENABLED=1` shows Apple's Metal HUD (fps, GPU ms, resolution).
* **Steam overlay:** Steam injects `gameoverlayrenderer.dylib` only when *it* launches the game. We do it by hand: `SteamAppId`/`SteamGameId` + `DYLD_INSERT_LIBRARIES=…/gameoverlayrenderer.dylib`.
  The overlay then shows (Shift+Tab), the presentation mode switches from *Direct* to *Composited* (slightly more GPU time).
* **Warm-up:** the first launch compiles every Metal variant once (~68 s for R.E.P.O.; the window is unresponsive meanwhile). Metal caches the result per app; later runs don't hitch.

## Known open problems
* `Hidden/PostProcessing/Uber` (Unity Post-Processing v2) translates but renders wrong (dark scene, huge chromatic ghosting) → skipped via `SKIP_SHADER`; bloom/lens/grain are off.
  Suspects: texture-array/`Load` instructions, half-precision paths, or one of the effect shaders now being active. Untested.
* StructuredBuffer (instancing) variants and geometry/tessellation/compute shaders are not translated.
* A small corner square in R.E.P.O. renders with a missing-variant shader (not identified).

## AssetBundles
`tools/patch_bundles.py` applies the same Shader patch inside UnityFS bundles (re-packed with LZ4) and verifies that every other object is unchanged. Untested on a bundle that actually contains shaders in this repo; used by the ULTRAKILL port (55 patched files).
