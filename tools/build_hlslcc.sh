#!/bin/sh
# Builds tools/h2m: a tiny CLI around Unity's open-source HLSLcc (DXBC -> Metal source). Needs git, cmake, clang.
set -e; cd "$(dirname "$0")"; here=$(pwd); mkdir -p .build; cd .build
REV=3ea1fcd6bd0ac445bc078de0bf32f0950188577b   # pinned HLSLcc commit (MIT-style license + bstring BSD notice, see THIRD-PARTY-NOTICES.md)
[ -d HLSLcc ] || { git init -q HLSLcc && git -C HLSLcc fetch -q --depth 1 https://github.com/Unity-Technologies/HLSLcc.git $REV && git -C HLSLcc checkout -q FETCH_HEAD; }
(cd HLSLcc
 for file in hlslcc-structured-stride.patch hlslcc-msaa-array.patch hlslcc-metal-minprecision.patch; do
     if ! patch -R -p1 -F 0 -f -s --dry-run < "$here/$file" >/dev/null 2>&1; then
         patch -p1 -F 0 -f < "$here/$file"
     fi
 done)
mkdir -p HLSLcc/build && cd HLSLcc/build
cmake -DHLSLCC_LIBRARY_SHARED=OFF -DCMAKE_BUILD_TYPE=Release -DCMAKE_POLICY_VERSION_MINIMUM=3.5 -DCMAKE_CXX_FLAGS="-std=c++14 -w" .. >/dev/null
make -j8 >/dev/null; cd ../../..
clang++ -std=c++14 -w -I .build/HLSLcc/include h2m.cpp .build/HLSLcc/build/libhlslcc.a -o h2m && echo "built tools/h2m"
