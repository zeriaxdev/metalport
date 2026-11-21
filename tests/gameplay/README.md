# Optional ULTRAKILL gameplay comparison

This is an opt-in test using an existing working native ULTRAKILL app and the user's local game assemblies. No game binaries, assets, saves or shaders are included here. The probe and IL transformations are original test code.

Requires macOS with Metal access, the toolkit Python environment (UnityPy/Pillow), .NET SDK 8 or newer, and Mono.Cecil 0.11.6 (restored by the patch project if not already cached).

```sh
.venv/bin/python tests/gameplay/compare.py \
  --app /path/to/ULTRAKILL.app --out /path/to/new-comparison
```

The input must have `Contents/Resources/converter-profile.json` and its corresponding local profile. The script refuses an existing output directory, clones the app, copies Saves/Preferences/Palettes/Cybergrind, converts the cloned compute bundle, and modifies only that clone's bootstrap to attach the probe. A dispatch counter is inserted into the copied game's palette method. The patcher rejects other output paths. Symlinked profile content is rejected.

It then runs muted compute-OFF and compute-ON tests through Main Menu → Level 0-1, each with its own copied profile and private home. A sandbox denies writes to the source app, original game input, live Application Support and live Preferences. It only terminates its own test process on timeout. Do not use this to alter the installed app or live saves.

The probe uses the game's actual post-processing singleton and natural camera pose. Batch-mode rendering needs an explicit render of that camera; forcing an old spawn coordinate previously produced an almost-black room. The final virtual-camera output and raw scene target are captured separately. Solid white and nearly black normal frames are rejected. A synthetic palette is applied through the game's own API, then removed with color precision restored.

`comparison.json` records camera pose, engine errors, dispatch counts, lighting-buffer presence, original-file hash checks, baseline image checks and per-pixel differences. A completed comparison is not a claim of pixel-exact parity or a full campaign/performance test. Read the captures as well as the JSON. If the user plays or changes settings in the original game concurrently, its hashes can legitimately change; the sandbox restriction is still required.

Output app bundles, assemblies, profiles, caches and captures stay outside the repository or under an ignored local build directory. Commit only this source, never the test outputs. Full-campaign play, other palettes, other input versions, and the unused bundled outline kernels remain separate checks.
