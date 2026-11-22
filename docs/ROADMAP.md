# Roadmap

## Verify first

1. Address remaining HDRP graphics and compute failures on representative scenes. Extend the existing [shader checks](SHADER-CHECKS.md) with focused regressions for depth resolve and incorrect resource bindings. Geometry, tessellation, and DXIL require their own feasibility checks.
2. Reproduce the reported Lethal Company tearing in vanilla with in-game VSync enabled. Compare ProMotion and fixed 60 Hz, then windowed and fullscreen at the same refresh rate. Record Metal HUD presentation mode and frame intervals and check the runtime `CAMetalLayer.displaySyncEnabled` value. Reuse `tools/bench_trace.py` for FPS and 1% lows. Check Retina sizing, cursor hit testing, and macOS Game Mode individually.
3. Reproduce the [tracked game issues](../games/README.md) one at a time. For Lethal Company, check ship lighting, mod asset shaders, terminal focus, Steam presence, and Windows joins on the exact build.

## Tooling to explore

- **Manifest-only eligibility.** `metalport check` already inspects local data. Explore eligibility hints from manifests the signed-in user can access before downloading game content. Report missing metadata as unknown. See the [Steam metadata limits](PORTING-A-NEW-GAME.md).
- **Depot fetching.** Consider optional authenticated download with explicit app, depot and manifest IDs. Keep ownership and authentication in Steam or a compatible downloader.
- **Native dependencies.** Record verified macOS plugin equivalents. Add targeted compatibility fixes for recurring cursor, registry and path calls when a game demonstrates the need. Required middleware needs compatible implementations.
- **Player matching and signing.** Keep exact Unity matching by default. Test near-version players in disposable copies with scene and save checks. Record entitlements when a reproduced signing failure requires them.

Windows IL2CPP translation is outside the managed Mono porting pipeline.
