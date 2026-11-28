# MetalPort upstream audit (research notes)

Date: 2026-11-28. The machine-readable findings file and the upstream clones live outside this repository.
The audit itself modified nothing in MetalPort; the follow-up changes are listed in section 12.

## 0. Scope and status (read this first)

| Batch | Status |
|---|---|
| 0. MetalPort baseline | Done |
| 1. Casualties: Unknown, PortMaster toolkit, own Buckshot repo | Done for the paths named below. Large parts of both trees were not read. |
| 2. Shader compilers and asset tooling | Partial. HLSLcc compared with the pin. DXMT license read. dxbc-spirv, UnityPy: cloned, source **not** audited. SPIRV-Cross, TypeTreeDumps: **not cloned**. |
| 3. Native ports, managed tools, mods | Partial. ultrakill-mac and dryport README level. ror2 head compared with the pin. cecil: cloned, **not** audited. |
| 4. Steam acquisition and diagnostics | Only DepotDownloader's license read. SteamKit **not cloned**. |
| 5. IL2CPP, 6. reference and other engines | **Not started.** |

Every finding is source inspected. Finding 001 was also checked read-only against an owned R.E.P.O. build (data inspected, game not run). Items marked HYPOTHESIS need the listed test before anyone trusts them.

## 1. MetalPort baseline (verified by reading the tree)

- Branch `main`, commit `14a21b309ba56f53848876d63e27a8dea00c4474` ("Add Steam port eligibility lookup and bump to 0.7.0", 2026-11-23), version 0.7.0.
- The audit ran on a working tree with uncommitted edits to `tools/` (including `tools/inject.py`); line numbers quoted for it come from that tree, not from the commit.
- Pipeline (docs/PIPELINE.md): exact-version Mac player, Mac Mono libraries, HLSLcc D3D11 to Metal, new Metal subprograms appended to Shader objects, `BuildSettings` patched to Metal, native stand-ins via dllmap, ad-hoc signing.
- Tests (`tests/`): `test_dxbc_rdef.py`, `test_compute.py`, `test_compute_integration.py`, `test_shader_pipeline.py`, `test_typed_texture.py`, `test_gameplay_capture.py`, `compute_dispatch.m`. No `.github/workflows`.
- Games (docs/FEATURES.md): R.E.P.O. playable (color grading off, friend join untested); Outer Wilds playable with issues; ULTRAKILL experimental; Lethal Company experimental HDRP.
- Local HLSLcc patches: `hlslcc-structured-stride.patch`, `hlslcc-msaa-array.patch`, `hlslcc-metal-minprecision.patch`.

## 2. Repository ledger (deduplicated)

| Repository | Commit | License at that commit | State |
|---|---|---|---|
| Andreansx/casualties-unknown-apple-silicon | 5757547 | MIT | cloned, partly audited |
| Producdevity/portmaster-unity-toolkit | 6a243dc | MIT | cloned, partly audited |
| zeriaxdev/buckshot-roulette-mac | b36e18d | MIT | cloned, partly audited |
| wisnuub/ror2-silicon-macos | 9c40375 | MIT | cloned; head equals MetalPort's pin; **lead confirmed** |
| Unity-Technologies/HLSLcc | 3ea1fcd | MIT-style | cloned; head equals MetalPort's pin |
| doitsujin/dxbc-spirv | 43d274a | MIT (Philip Rebohle, 2025) | cloned, **not audited** |
| 3Shain/dxmt | faa73e4 | LGPL-2.1+ at HEAD; MIT up to v0.80 per LICENSE.OLD | cloned, license only |
| K0lb3/UnityPy | 21a3b6e | MIT | cloned, **not audited** |
| jbevain/cecil | 30f197e | MIT | cloned, **not audited** |
| SteamRE/DepotDownloader | b62cf6a | GPL-2.0 | cloned, license only |
| Yash-Singh1/ultrakill-mac | 0384137 | **none** | **cloned; unconfirmed lead confirmed to exist**, README only |
| ninondev/dryport | 23c51c0 | GPL-3.0 | **cloned; lead confirmed to exist**, README only |

Full SHAs are kept in the audit ledger outside this repository. Every other repository in the brief is untouched (neither cloned nor ranked).

## 3. Ranked findings

Ranked by expected benefit, then strength of evidence, effort, and risk. IDs match the JSON.

1. **MP-AUDIT-001: R.E.P.O. color grading, `m_CommonParameters` (original hypothesis NOT supported).** MetalPort's notes say `_Lut2D_Params` lives in the stage's `m_CommonParameters` and reads 0 on Metal, and `tools/inject.py` does not handle that field, while PortMaster merges it into each entry (`dxbc.py` `with_common` L418, `metal.py` `_restore_common` L1370). Checked read-only on the local R.E.P.O. port with `tools/dump_common_params.py`: in `Hidden/PostProcessing/Lut2DBaker` the D3D11 and Metal parameter entries are **identical** (`$Globals`, size 736, 0 own members) and the shared members (`_Lut2D_Params@448` ... `_Gain@608`) are only in `m_CommonParameters` for both platforms. The Metal fragment program declares `float4 cb0_data[39]` and reads `_Lut2D_Params` as `cb0_data[28]` (28*16=448), which matches. So Metal entries lack nothing that D3D11 entries have. Still open: how the player merges common parameters for Metal. Next experiment: on a clone of the app, merge the members into the Metal entries and compare LUT render-texture stats. Confidence low, effort M.
2. **MP-AUDIT-002: Lethal Company frame pacing, VSync in quality levels (HYPOTHESIS, medium).** Casualties found `vSyncCount=0` in the booted quality level, which disabled `displaySyncEnabled`. MetalPort does not read per-level `vSyncCount` or the runtime value. Their symptom was power draw and repeated renders, not tearing, so the hypothesis may not match Lethal Company. First step: a read-only diagnostic. Also notes the single-byte typetree-diff technique for `macRetinaSupport`. Effort S, risk low.
3. **MP-AUDIT-005: tests and a game-file guard for `steam_entry.py` (high confidence).** `tools/steam_entry.py` edits Steam's binary appinfo cache and has no test. The owner's Buckshot repo (zeriaxdev/buckshot-roulette-mac) has six tests and a `check_no_game_files.py` guard. MetalPort has no CI. Effort S, risk low.
4. **MP-AUDIT-004: repeatable regression against Unity's own Metal output (medium).** MetalPort's 59/59 check exists only as a doc claim. dryport describes a per-Unity-version bench. GPL-3.0, so idea only. Effort M, risk low.
5. **MP-AUDIT-003: donor-built stock HDRP shaders for Lethal Company (HYPOTHESIS, low).** Needs a local Unity Editor and an exact package match. Effort L, risk medium.
6. **MP-AUDIT-011: ultrakill-mac bug classes (low).** Four named repairs to check. No license, so no code reuse.
7. **MP-AUDIT-012: DepotDownloader (low).** GPL-2.0, separate user-run tool at most. Legal review first.
8. Informational: **007** (HLSLcc upstream has nothing newer), **008** (ror2 matches the pin), **010** (DXMT licensing).

## 4. License matrix

| Source | License | Reuse mode |
|---|---|---|
| casualties-unknown-apple-silicon | MIT | adapt with notice, or reference |
| portmaster-unity-toolkit | MIT (vendored code under `setup-rs/vendor` has its own licenses) | adapt algorithms with notice |
| buckshot-roulette-mac | MIT, same owner | adapt |
| ror2-silicon-macos | MIT | already adapted, notice present |
| HLSLcc | MIT-style | dependency |
| dxbc-spirv, UnityPy, cecil | MIT | not yet evaluated for use |
| DXMT HEAD | LGPL-2.1+ | reference only |
| DXMT up to v0.80 | MIT per LICENSE.OLD (tag exists: peeled commit 589adb7) | **not verified**: tag not checked out |
| DepotDownloader | GPL-2.0 | separate process only, legal review |
| dryport | GPL-3.0 | reference only |
| ultrakill-mac | no license found | do not copy; ask the owner |

## 5. Overlap matrix

| Capability | MetalPort | Upstream | Overlap |
|---|---|---|---|
| Merge `m_CommonParameters` into entries | absent in graphics path | PortMaster | missing |
| VSync/Retina data diagnostics | absent | Casualties | missing |
| Donor shader transplant | absent | Casualties | missing |
| Real-name RDEF, `packed_float2` | flat `float4 cbN_data[]` | Casualties | not applicable |
| HLSLcc fixes | 3 local patches | upstream stagnant since 2020 | already present |
| Compute adaptation | adapted from ror2 | ror2 | already present |
| BepInEx on arm64 | works (official build) | Casualties `bepinex-applesilicon` | not compared |
| `steam_entry` tests, no-game-files guard | absent | Buckshot (own) | missing |

## 6. Per-game implications

- **R.E.P.O.:** 001 targets color grading. Friend join and real voice were not touched by this audit.
- **Lethal Company:** 002 (pacing) and 003 (HDRP) are hypotheses; nothing here fixes depth resolve or texture-array bindings directly.
- **ULTRAKILL:** 011 gives leads only.
- **Outer Wilds:** nothing found. Giant's Deep was not investigated.

## 7. Rejected approaches

- `packed_float2` and real-name RDEF (006): MetalPort's flat layout does not have the alignment problem.
- dryport's FMOD stub (009): returns success for every call, and is GPL-3.0.
- Copying anything from ultrakill-mac (no license) or DXMT HEAD (LGPL).
- PortMaster's GLES/Vulkan output: wrong ABI for Metal. Only its parameter-handling logic is relevant.
- A Rust rewrite: no bottleneck was found that justifies one.

## 8. Proof-of-concept proposals

1. **Common-parameter merge experiment (001).** Done read-only (`tools/dump_common_params.py`). Next: merge members into the Metal entries of a cloned app and compare LUT render-texture stats.
2. **Pacing probe (002).** `tools/quality_vsync.py` prints serialized levels (done); still needed: runtime log of `vSyncCount`, `displaySyncEnabled` and encoders per presented frame. Refuted if LC shows `vSyncCount=1` and sync on.
3. **Steam entry tests and guard (005).** Done, see section 12.

## 9. Prioritized backlog

1. ~~005 tests and guard~~ done.
2. ~~001 dump script~~ done; merge experiment next (M).
3. ~~002 serialized diagnostic~~ done; runtime half next (S).
4. 004 Unity-resources regression test (M).
5. 007: diff Casualties' and ror2's HLSLcc patches against MetalPort's three (S).
6. Finish Batch 2 on dxbc-spirv and SPIRV-Cross only if 001 and 002 fail to explain the open bugs.
7. 003 donor spike (L), only after confirming Lethal Company's HDRP package version.

## 11. Blockers and unknowns

- Lethal Company's HDRP package version and its stock-versus-custom shader split were not inspected.
- Whether the Unity player already merges `m_CommonParameters` for Metal subprograms is unknown. 001 depends on that.
- DXMT v0.80 LICENSE text and file provenance were not read.
- dryport `retarget_verify.py` and `fmodstub-gen.py` were not read, only their README descriptions.
- No game was run. No finding is verified beyond reading source.
- Lethal Company's data is not on this machine, so `tools/quality_vsync.py` has not been run on it. On R.E.P.O. the serialized current quality level (Ultra) has `vSyncCount=0`, the other five levels 1; whether the game's own VSync setting overrides it at runtime is unknown.

## 12. What was changed in MetalPort after this audit

- `tests/test_steam_entry.py` (7 tests, synthetic Steam cache). It found a real bug: `steam_entry.py remove` left an empty `rootoverrides` node in Steam's app cache after Steam Cloud was added. Fixed in `tools/steam_entry.py`.
- `tools/check_no_game_files.py` plus `tests/test_no_game_files.py`: fails on game, Unity or Valve files in tracked files or a release ZIP. Passes on the current repository (94 files).
- `.github/workflows/tests.yml`: runs the guard and the asset-free tests. **Not yet run on GitHub.**
- Read-only diagnostics: `tools/dump_common_params.py` and `tools/quality_vsync.py`.
