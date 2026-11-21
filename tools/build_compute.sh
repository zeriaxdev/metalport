#!/bin/sh
# Build the pinned Unity HLSLcc reflection backend; cached binaries stay outside source control.
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
out=$1
commit=3ea1fcd6bd0ac445bc078de0bf32f0950188577b
mkdir -p "$out/source"
if [ ! -f "$out/source/.patched" ]; then
    if [ ! -f "$out/hlslcc.tar.gz" ]; then
        curl -fL --retry 2 "https://codeload.github.com/Unity-Technologies/HLSLcc/tar.gz/$commit" -o "$out/hlslcc.tar.gz.tmp"
        mv "$out/hlslcc.tar.gz.tmp" "$out/hlslcc.tar.gz"
    fi
    tar -xzf "$out/hlslcc.tar.gz" --strip-components=1 -C "$out/source"
    (cd "$out/source" && patch -p1 < "$here/compute_shader/hlslcc-unity-player.patch")
    touch "$out/source/.patched"
fi
cmake -S "$out/source" -B "$out/build" -DHLSLCC_LIBRARY_SHARED=OFF -DCMAKE_BUILD_TYPE=Release -DCMAKE_POLICY_VERSION_MINIMUM=3.5
cmake --build "$out/build" -j 8
c++ -std=c++14 -O2 -I"$out/source/include" -I"$out/source/src/internal_includes" -I"$out/source/src/cbstring" -I"$out/source/src" "$here/compute_shader/dxbc2msl.cpp" "$out/build/libhlslcc.a" -o "$out/dxbc2msl.tmp"
mv "$out/dxbc2msl.tmp" "$out/dxbc2msl"
