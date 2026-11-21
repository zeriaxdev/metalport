# Compute conversion components

Adapted from wisnuub/ror2-silicon-macos at commit `9c403754aa786c34465fba389719b703bc492070`: typed RDEF reconstruction, Metal layout/minification helpers, compute payload/binding construction, the reflection driver and HLSLcc patch. These components are MIT licensed, copyright 2026 wisnuub. The full notice is retained in `../shaderconv-LICENSE.txt`.

The per-kernel constant-buffer table handling and serialized-schema adapters live in `../compute_support.py`. The unused upstream name-keyed constant-buffer helper was removed; buffers with identical names must not be merged across different layouts.

HLSLcc itself is fetched at Unity commit `3ea1fcd6bd0ac445bc078de0bf32f0950188577b` by `../build_compute.sh` into the ignored cache, with its own license retained in the downloaded source. No game data is included here.
