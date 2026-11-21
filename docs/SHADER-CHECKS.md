# Shader coverage and Metal compilation checks

Run the translation preflight before assembling a new app:

```sh
python3 tools/xlate_all.py /path/to/Game_Data --report /tmp/shader-source-coverage.json
```

The shared inventory scans loose `*.assets`, `levelN`, global managers and built-in shader files, plus nested `.bundle`, `.unity3d` and `.assetbundle` containers. `inspect_game.py` uses the same inventory and reports compute shaders as well as graphics shaders. Unusual container names/extensions need explicit inspection; this is not a scan of every possible proprietary archive.

Each JSON issue identifies its file, object ID, shader name, failure code and detail when available. Reports contain graphics/compute object counts and unique D3D program counts. Exit status is **2** when coverage or compilation is incomplete, or when a tool/device/asset cannot be read. A successful HLSLcc process alone is insufficient.

`tools/port.py` writes `shader-source-coverage.json` under `--out` before assembling the app. It invokes the existing byte-preserving patcher for both loose files and bundles in the cloned app, then writes `shader-output-coverage.json`. It refuses an existing app; use a fresh output folder. Source game assets are never patched by `port.py`.

## What gets checked

- DXBC translation failures, unsupported stages, missing source programs, missing Metal platforms and partial Metal program blobs are visible.
- `ComputeShader` objects use the versioned Unity 2021/2022 reader and reflected Metal converter. Unknown formats remain unsupported; existing Metal payloads and required kernel/keyword coverage are checked. See [COMPUTE-SHADERS.md](COMPUTE-SHADERS.md) for scope and tests.
- Every newly injected graphics shader needs all of its D3D vertex/fragment programs. One cached variant cannot cause a partially translated shader to be advertised as Metal.
- Generated source is compiled using the Metal runtime API, with the expected `xlatMtlMain` or `computeMain` entry point. The injector checks again after constant-buffer repairs. Device unavailability is an infrastructure error, not a shader syntax failure.
- Successful compilation checks are cached by MSL content, checker code and operating-system identity. Translation cache metadata includes the translator binary, RDEF reconstruction code and flags; failed/in-progress translations cannot reuse an older `.metal` artifact.

The compute reflection backend additionally needs CMake and its pinned HLSLcc source archive on first build. The checker builds automatically with `clang`, Foundation and Metal. Command Line Tools are required; the optional command-line Metal compiler download is not. The process needs access to a Metal device. A sandbox that hides the GPU must be rerun with appropriate device access.

## Explicit experiments

Known fallback experiments can pass `--allow-incomplete` to `port.py` or `xlate_all.py`, with `--skip-shader Name,OtherName` if necessary. This permits reported shader gaps while keeping `complete: false` in JSON and printing an incomplete result. Asset read errors, missing translators and unavailable validation infrastructure remain fatal. These flags do not verify the visual fallback.

In `port.py`, `--allow-incomplete` also preserves the available graphics variants of a partially translated shader, instead of rejecting its entire Metal version. Only those available variants get Metal program entries, and their final source must still pass compilation. The output audit retains a `partial_metal` issue for untranslated D3D programs left in that platform blob; the report stays incomplete. Compute conversion remains all-or-nothing per object. Direct injector use can opt in with `ALLOW_PARTIAL_SHADER=1`; it still exits nonzero when graphics coverage is partial.

Audit an already produced Data folder without changing game assets:

```sh
python3 tools/xlate_all.py /path/to/App.app/Contents/Resources/Data \
  --audit-only --report /tmp/shader-output-coverage.json
```

Audit checks serialized coverage; it does not recompile pre-existing Metal programs. Compilation success does not prove resource bindings, GPU dispatch results, rendered textures, audio or multiplayer. Those remain runtime checks.

## Tests

```sh
python3 -m unittest discover -s tests -v
RUN_METAL_TESTS=1 python3 -m unittest discover -s tests -v
```

The second command adds real Metal compiler tests on macOS. The checker is adapted from wisnuub's MIT-licensed RoR2 port; its notice is retained in `tools/shaderconv-LICENSE.txt`.
