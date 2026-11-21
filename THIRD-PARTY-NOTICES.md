# Third-party notices

This repository contains only original toolkit source under the MIT license (see `LICENSE`). It does not include or redistribute any of
the components below: each is downloaded or installed on your own machine when you build a port. This list says what is used and under
which terms; it is not a substitute for those terms.

## Build-time tools and libraries

| Component | Used by | License | Source |
|---|---|---|---|
| HLSLcc (pinned commit `3ea1fcd`) | `tools/build_hlslcc.sh`, `tools/h2m.cpp`: DX11 bytecode to Metal source | MIT-style (James Jones, Unity Technologies) and BSD-style for the bundled `bstring` (Paul Hsieh) | https://github.com/Unity-Technologies/HLSLcc |
| UnityPy | reading and writing Unity data files | MIT | https://github.com/K0lb3/UnityPy |
| TypeTreeGenerator | type trees for older Unity data (`tools/legacy/`) | MIT | https://github.com/K0lb3/TypeTreeGenerator |
| dnfile | reading .NET metadata | MIT | https://github.com/malwarefrank/dnfile |
| python-lz4 | Unity data compression | BSD-3-Clause | https://github.com/python-lz4/python-lz4 |
| ror2-silicon-macos (commit `9c40375`) | adapted into `tools/compute_shader/` (RDEF reconstruction, Metal layout helpers, compute payload construction, reflection driver, HLSLcc patch) and `tools/mslcheck.m` | MIT, copyright 2026 wisnuub; full text in `tools/shaderconv-LICENSE.txt` | https://github.com/wisnuub/ror2-silicon-macos |
| Mono.Cecil 0.11.6 | `tools/ilfix`: .NET IL rewriting | MIT | https://github.com/jbevain/cecil |

## Components copied into the app you build (never shipped by this repository)

| Component | How it gets there | Terms |
|---|---|---|
| Unity macOS player and Mono class libraries | downloaded by `tools/fetch_unity.py` from Unity's official release service | Unity's terms: https://unity.com/legal/terms-of-service |
| Steamworks API library (`libsteam_api.dylib`) | copied from a Steam game already installed on your Mac | Valve / Steamworks terms |
| libopus (voice games only) | your Homebrew installation | BSD-3-Clause, https://opus-codec.org/license/ |
| Your game's data | your own Steam download (APFS clone) | the game's license; do not redistribute |

Because the built app contains these components, **do not share it**.

## Trademarks

Unity is a trademark of Unity Technologies. Steam and Valve are trademarks of Valve Corporation. Discord is a trademark of Discord Inc.
Game names belong to their respective owners. This project is not affiliated with or endorsed by any of them.
