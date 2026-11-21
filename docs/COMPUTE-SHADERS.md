# Compute shader conversion

The normal `xlate_all.py` and `port.py` commands now handle separate `ComputeShader` objects as well as graphics shaders. No per-game source patch or game executable rewrite is required for the supported compute formats. This is one component of a port, not a guarantee that the whole game works.

## Supported data shapes

- Unity 2021-style `variantMap`: keyword-to-kernel records, including tuple/list map pairs.
- Unity 2022-style `uniqueVariants` plus `variantIndices`: unique kernel records with shared keyword/index maps. Keywords, lookup tables, requirements and thread group sizes are retained.
- D3D11 compute renderer **2** is the input. The converter appends Metal compute renderer **16**, preserving every existing renderer. These enums differ from regular Shader platform IDs (D3D11 4, Metal 14).
- All required kernels must translate and compile before the object is patched. Unknown layouts, invalid indices or inconsistent Metal metadata are reported. An existing Metal renderer missing required kernels/keyword mappings is not accepted as complete.

The format is selected by the actual serialized fields, not just the game's Unity version string. Other versions with similar fields still require testing. IL2CPP and Windows-native libraries are separate issues.

## Resource and layout handling

Unity's retained names, types and binding metadata rebuild the stripped DXBC reflection. A pinned, patched Unity HLSLcc backend emits Metal source and actual resource slots. Texture, UAV, buffer and constant-buffer bindings are rewritten from that reflection.

Each kernel receives a matching constant-buffer layout. Buffers with the same name can have different layouts; these are represented by distinct Metal table entries and the kernel's indices are updated. This avoids merging unrelated `Globals` layouts. The final minified MSL embedded in Unity's compute payload is checked with the runtime Metal compiler.

## Use

```sh
python3 tools/xlate_all.py /path/to/Game_Data --report /tmp/shader-coverage.json
python3 tools/port.py --data /path/to/Game_Data --unity /path/to/unity-runtime \
  --out /path/to/new-output --name Game
```

`xlate_all.py` writes cache/report files, not game assets. It now preflights compute objects too. `port.py` patches the cloned app using the existing loose-file/UnityFS preservation checks. Standalone `patch_bundles.py` and `inject_inplace.py` rewrite their input paths; use copies for experiments.

The compute translator builds automatically into `tools/cache/compute/`. First use needs CMake, a C++ compiler and access to the pinned Unity HLSLcc archive. It does not create a Git checkout. Compiler sources, patches, the driver and the OS identify the backend cache; binary content and rebuilt DXBC identify program cache entries. Game files are not fetched by this step.

`--skip-shader` applies to compute names too, and `--allow-incomplete` keeps known conversion gaps visible in JSON. It does not silently label an unsupported compute object Metal-capable, and missing build/Metal-check infrastructure remains fatal.

## Tests and evidence

```sh
python3 -m unittest discover -s tests -v
RUN_METAL_TESTS=1 UNITY_COMPUTE_TEST_BUNDLE=/path/to/ULTRAKILL/shaders.bundle \
  python3 -m unittest discover -s tests -v
```

The opt-in suite uses your local ULTRAKILL bundle. Game shader bytecode is not stored in this repository. It converts and compiles five real kernel variants across `PaletteCompute` and `OutlineCompute`, exercises preflight/injection/audit, checks format-21/22 and UnityFS preservation/idempotence, and dispatches three kernels on Metal with CPU-reference readback checks. The format-21 fixture is a projection of the same data, not a test of a complete older game.

Tested GPU operations: 512 palette-LUT texels, 64 mask texels and 64 composite texels. The composite check uploads constant-buffer values using the rebuilt metadata. JFA and Composite1PX compile successfully but have no readback reference in this suite.

### Verification status (ULTRAKILL, Unity 2022.3.29f1, Apple M5, 2026-11-21)

| Level | Palette `ComputeLUT` | Outline `CreateMask` | Outline `Composite` | Outline `JFA`, `Composite1PX` |
|---|---|---|---|---|
| Translates and compiles with Metal | ✅ | ✅ | ✅ | ✅ |
| Direct Metal dispatch, GPU readback vs CPU reference | ✅ 512/512 texels | ✅ 64/64 | ✅ 64/64 (±1e-6) | not tested |
| Through Unity's player (AssetBundle load, kernel bindings, constants, dispatch, readback) | ✅ 512/512 | ✅ 64/64 | ✅ 64/64 | kernels found, not dispatched |
| In gameplay | ◐ the game's palette code dispatches the converted kernel without engine errors; visual result **not verified** | not used by gameplay | not used by gameplay | not used by gameplay |

Notes: the Unity-player test ran in a disposable clone of the app with a copied profile; the installed app and saves were checked unchanged
by hash. ULTRAKILL's gameplay outlines use regular shader blits (`PostProcessV2_Handler.SetupOutlines`), not `OutlineCompute`. The
gameplay comparison is blocked: its automated test scene renders nearly black even with compute off, so the baseline is not yet
trustworthy.

Full gameplay through Unity's player, arbitrary HDRP/VFX pipelines, native audio, Steam networking and other games' compute kernels are not implied by these tests. The compute components adapt MIT-licensed code from wisnuub/ror2-silicon-macos; see `tools/shaderconv-LICENSE.txt`.
