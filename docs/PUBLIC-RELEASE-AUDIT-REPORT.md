# Public release audit report

**HOLD**: release candidate `523c5f62733677f78f9b459121309db80bb608c0` (`main`, audited 2026-11-21).
The tracked toolkit contains no game data, no Unity/Valve binaries and no personal data in any commit, and no Steam ownership bypass was
found. It is held for three reasons: the README lacks the non-affiliation notice Unity's trademark guidelines require of projects that use
Unity marks; the project name starts with a Unity mark; and about 20 uncommitted/untracked files in the working tree have not been
audited and must not enter a release until they are. This is an evidence-based release recommendation, not legal certification.

## Release boundary

| Item | Value |
|---|---|
| Repository | `repo-metal`, remote `github.com/zeriaxdev/unity-mac-metal-port` (private) |
| Refs inspected | `main` (HEAD above), `origin/main` (`e5b994a`, last push), tag `v0.3.0`. No other branches, no submodules, no Git LFS (not installed; no `.gitattributes`). |
| History | 17 commits on all refs; 55 tracked files; the set of paths ever added equals the current tracked set (nothing deleted or renamed out). `git fsck --unreachable`: 0 objects. |
| Dirty state | 8 modified tracked files and 12 untracked paths from separate in-progress work (compute-shader conversion, shader checks, tests, `tools/shaderconv-LICENSE.txt`), plus `games/repo.json`. **Not part of this candidate; not audited.** |
| Release format | Source only (Git). No CI, no packaging scripts, no release assets, no binary distribution channel exists. |
| Ignored local outputs | `.gitignore` excludes `R.E.P.O.app/`, `Resources`, `*.dylib`, `*.a`, `tools/cache/`, `tools/h2m`, `games/library-candidates.local.md`. A `git archive` of HEAD contains only tracked files. |

## [CRITICAL - Must fix before push/release]

**C1. Missing non-affiliation notice.** Surface: `README.md` (whole file), repository description.
Evidence: README uses "Unity", "Steam", "Valve", "Discord" and game names; no notice of non-affiliation. Unity's *Guidelines for Using
Unity Trademarks* (v4.2, checked 2026-11-21, https://unity.com/legal/branding-trademarks) require a notice that a project using Unity
marks is not sponsored by or affiliated with Unity Technologies. Distinction: trademark guideline (contractual/brand policy), not copyright.
Confidence: high. Remediation: add the notice below to the README. Verify: README contains it.

## [WARNING - Recommended hardening]

**W1. Project name begins with a Unity mark.** Surface: repo name `unity-mac-metal-port`, README title. Unity's guidelines say not to use
its marks as (part of) a product or project name; descriptive use ("for Unity games", "compatible with Unity software") is allowed.
Confidence: medium (name vs. description is a judgment call). Remediation: rename, e.g. `mac-metal-port` with the tagline "for Windows
Unity games". Verify: no Unity mark in the project name or app identifiers.

**W2. Uncommitted and untracked work not audited.** Surface: working tree (`tools/compute_shader/`, `tools/compute_support.py`,
`tools/metal_check.py`, `tools/mslcheck.m`, `tools/shader_coverage.py`, `tools/shaderconv-LICENSE.txt`, `tests/`, `docs/COMPUTE-SHADERS.md`,
`docs/SHADER-CHECKS.md`, edits to 8 tracked files). The presence of `shaderconv-LICENSE.txt` and a pinned, patched HLSLcc backend
(per `docs/COMPUTE-SHADERS.md`) suggests third-party code or patches. Remediation: re-run this audit on the commit that adds them.

**W3. Possible derivation from an unlicensed upstream.** Surface: `games/ultrakill.json` (`upstream` field), `tools/patch_bundles.py:2`.
Evidence: the ULTRAKILL port was based on `github.com/Yash-Singh1/ultrakill-mac` at `0384137d`, which has **no license**
(default: all rights reserved). A line comparison (normalized lines ≥ 40 characters) of every tracked `tools/` source file against upstream
`converter/package.py`, `prepare_payload.py`, `verify_game.py`, `worker.py` and `tools/AssemblyPatcher/Program.cs` found **0** shared
lines. Limits: the other ~60 upstream files, its `patches/*.patch` and the untracked work (W2) were not compared; no shared lines does not
prove independent authorship. Remediation: keep upstream code out of this repo unless its author grants a license; record provenance of
`patch_bundles.py` (authored for this project during the ULTRAKILL work). Verify: comparison over the full upstream tree.

**W4. Steam ownership behavior only partly tested.** Surface: `tools/natives.py:50-80`, `tools/steamshim.c`, `steam_appid.txt`,
`tools/make_launcher.py` (sets `SteamAppId`). Technical behavior: the game links Valve's genuine `libsteam_api.dylib` and the running
Steam client; the shim only (a) adds flat-API accessors the library predates by asking `steamclient` for the real interface, (b) maps
`SteamAPI_Init` to the genuine `SteamAPI_InitSafe`, (c) returns success for `RequestCurrentStats` (newer SDKs load stats automatically).
No `BIsSubscribed*`, `BLoggedOn`, SteamID, auth-ticket or DLC result is forged; the game's own ownership check stays active.
Evidence of enforcement: with Steam not running, R.E.P.O. logged `SteamAPI_Init() failed … Steam not initialized. Quitting game.`
(2026-11-20); with Steam running, online play authenticated through Photon/Steam auth tickets (2026-11-21). **Not tested:** logged-out
Steam, and a signed-in account that does not own the game. `steam_appid.txt`/`SteamAppId` is Valve's documented development
mechanism and does not grant ownership. Remediation: run the non-owner test and record the result in `games/*.json`.

**W5. Third-party runtimes used locally under terms not reviewed.** Surface: `tools/fetch_unity.py:10-34`, `tools/natives.py:38-45`.
Unity: the end user's machine downloads the Mac player module and Mono class libraries from Unity's official release API
(`services.api.unity.com`) and copies them into a locally built app; nothing is redistributed by the project. A public official download
does not by itself establish permission for this use: the Unity Terms of Service and runtime terms need review. Steam: the Steamworks
redistributable is copied from another game the user installed, then wrapped locally; the Steamworks SDK access agreement governs
developers, not end users, so its application is unclear. Questions for counsel, not established violations. Remediation: state in the
README that these components come from the user's own downloads and are never redistributed (already true per `.gitignore`).

**W6. Interoperability-derived symbol list.** Surface: `tools/discord_syms.txt` (503 lines). Function names exported by the Discord
Social SDK, used to build a no-op stand-in so a game loads without Discord. Names only, no code. Low risk; note its purpose in the file
header.

**W7. Build dependency fetched unpinned.** Surface: `tools/build_hlslcc.sh:4` clones `Unity-Technologies/HLSLcc` at its default branch.
License verified (MIT-style, plus a BSD notice for the bundled `bstring` library). Remediation: pin to commit
`3ea1fcd6bd0ac445bc078de0bf32f0950188577b` and preserve both notices if the source or a binary is ever distributed.

**W8. No third-party notices inventory.** Remediation: add `THIRD-PARTY-NOTICES.md` from the dependency table below. It does not replace
per-license obligations for anything later distributed in binary form.

**W9. Generated apps contain third-party binaries.** Surface: locally built `.app` (Unity player, Mono, libsteam_api, Homebrew `libopus`
under BSD-3-Clause). Not distributed by the project, and the README forbids redistributing the result. If that ever changes, the generated
app needs its own license review.

**W10. Anti-circumvention analysis needs counsel.** Technical facts: the toolkit never executes, decrypts or modifies the game's Windows
executable (some ship Valve's DRM wrapper, e.g. Outer Wilds), using only the unencrypted `_Data` folder from the user's own download;
the game's own Steam checks run unchanged. Whether this implicates 17 U.S.C. § 1201 or national rules implementing EU Directive 2001/29/EC,
and whether Directive 2009/24/EC Articles 5–6 (interoperability) apply, are legal questions not settled here.

## [PASS - Verified clean]

- **P1. No proprietary binaries in any commit.** Scope: all 17 commits, every blob; checked by Mach-O/fat/PE/ELF/UnityFS magic bytes and
  by size (no blob > 200 KB). Limit: magic-byte scan, not content inspection of text files.
- **P2. No game data.** Scope: tracked files and history: no `.assets/.resource/.resS`, bundles, game assemblies, textures, audio, shader
  bytecode or generated shader source; no long base64/hex blobs. Game-specific knowledge is limited to type/shader names and numeric IDs.
- **P3. No personal data or secrets.** Scope: `git log -p --all` for the user's home path, email, Steam IDs, and password/key/token
  patterns: 0 hits. All commits use the GitHub noreply identity.
- **P4. License file present.** `LICENSE`: MIT, copyright zeriaxdev; all commits by that identity. Limit: much of the code was written
  with AI coding assistants at the author's direction; provenance is recorded in commit history only.

## Dependency and license table

| Component | Version / ref | Origin | License (upstream, checked 2026-11-21) | Use | Shipped by project |
|---|---|---|---|---|---|
| UnityPy | unpinned (pip) | PyPI / K0lb3/UnityPy | MIT | build-time library | no |
| TypeTreeGenerator(API) | unpinned (pip) | K0lb3/TypeTreeGenerator | MIT | build-time (legacy path) | no |
| dnfile | unpinned (pip) | malwarefrank/dnfile | MIT | build-time | no |
| lz4 (python-lz4) | unpinned (pip) | python-lz4 | BSD-3-Clause | build-time | no |
| Mono.Cecil | 0.11.6 (NuGet) | jbevain/cecil | MIT | build-time (`ilfix`) | no |
| HLSLcc | default branch (W7) | Unity-Technologies/HLSLcc | MIT-style + bstring BSD | linked into local `h2m` tool | no |
| libopus | Homebrew | xiph/opus | BSD-3-Clause | copied into local app | no |
| Unity Mac player + Mono libs | per game | Unity release API | Unity terms (W5) | copied into local app | no |
| libsteam_api | from user's installed games | Valve | Steamworks terms (W5) | wrapped into local app | no |

## Distribution and provenance table

| Material | Where it lives | Distributed? |
|---|---|---|
| Toolkit source (55 files) | Git | yes (private remote today) |
| Game data, Unity runtime, Valve library, built apps | user's machine, `.gitignore`d | no |
| `tools/cache/` (translated shader source from the user's game) | user's machine, `.gitignore`d | no |
| Untracked in-progress work (W2) | working tree | not yet; audit before committing |

## Proposed README notice

> This independent project is not affiliated with, endorsed by, or sponsored by Unity Technologies, Valve, Discord, or any game developer
> or publisher. It contains no game files and no Unity or Valve binaries: these come from your own downloads, on your own Mac. You must own
> each game you port and comply with its license terms; do not share the result. The toolkit's MIT license covers only this toolkit, not
> game content, engine runtimes or other third-party software. Product names and trademarks belong to their respective owners.

## Release checklist (ranked)

1. Add the notice above to the README (C1).
2. Decide the project name (W1).
3. Commit the in-progress work only after re-running this audit on it (W2).
4. Pin HLSLcc and add `THIRD-PARTY-NOTICES.md` (W7, W8).
5. Run the non-owner Steam test (W4).
6. Have counsel review W5 and W10 before any public release.

## Coverage log

- Commands: `git branch -a`, `git tag`, `git ls-remote`, `git rev-list --all`, `git fsck --unreachable`, blob magic-byte and size scan over
  `git rev-list --objects --all`, `git log -p --all` pattern scan, grep of tracked files for URLs, licenses, Steam APIs and embedded data.
- Upstream licenses read from GitHub (`gh api`) for HLSLcc, UnityPy, TypeTreeGenerator, dnfile, python-lz4, Mono.Cecil, Opus, ultrakill-mac.
- Legal sources: Unity trademark guidelines (read 2026-11-21). **Not re-fetched in this audit:** Unity Terms of Service
  (https://unity.com/legal/terms-of-service), Steam Subscriber Agreement (https://store.steampowered.com/subscriber_agreement/),
  17 U.S.C. § 1201 (https://www.law.cornell.edu/uscode/text/17/1201), Directive 2009/24/EC (https://eur-lex.europa.eu/eli/dir/2009/24/oj),
  Directive 2001/29/EC (https://eur-lex.europa.eu/eli/dir/2001/29/oj).
- Not covered: untracked/uncommitted work (W2); ~60 upstream ultrakill-mac files; Git LFS (tool absent, no LFS config found);
  non-owner and logged-out Steam tests (W4).

**Next action:** add the README notice (C1), then decide the name (W1).

## Remediation log

| Date | Finding | Change | Status |
|---|---|---|---|
| 2026-11-21 | C1 | README notice added (non-affiliation, no game/vendor binaries, own copy required, MIT scope, trademarks). | fixed |
| 2026-11-21 | W6 | `tools/discord_syms.txt` and `tools/discord_stub.c` removed: unused (`natives.py --discord` derives the names at build time from the user's own `Discord.Sdk.dll`). They remain in history at `e5b994a` and earlier. | fixed (history unchanged) |
| 2026-11-21 | W7 | `tools/build_hlslcc.sh` fetches HLSLcc at pinned commit `3ea1fcd6bd0ac445bc078de0bf32f0950188577b` (fetch verified). | fixed |
| 2026-11-21 | W8 | `THIRD-PARTY-NOTICES.md` added. | fixed |
| | W1, W2, W3, W4, W5, W9, W10 | Owner decision, a separate audit, a test with another account, or counsel. | open |

Verdict after these fixes: **HOLD** remains until W1 (name) is decided and W2 (in-progress work) is audited; then **READY WITH STATED
LIMITS** for a public source release, subject to the counsel items (W5, W10).
