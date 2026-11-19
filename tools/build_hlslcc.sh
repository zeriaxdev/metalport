#!/bin/sh
# Builds tools/h2m: a tiny CLI around Unity's open-source HLSLcc (DXBC -> Metal source). Needs git, cmake, clang.
set -e; cd "$(dirname "$0")"; mkdir -p .build; cd .build
[ -d HLSLcc ] || git clone --depth 1 https://github.com/Unity-Technologies/HLSLcc.git
mkdir -p HLSLcc/build && cd HLSLcc/build
cmake -DHLSLCC_LIBRARY_SHARED=OFF -DCMAKE_BUILD_TYPE=Release -DCMAKE_POLICY_VERSION_MINIMUM=3.5 -DCMAKE_CXX_FLAGS="-std=c++14 -w" .. >/dev/null
make -j8 >/dev/null; cd ../../..
clang++ -std=c++14 -w -I .build/HLSLcc/include h2m.cpp .build/HLSLcc/build/libhlslcc.a -o h2m && echo "built tools/h2m"
