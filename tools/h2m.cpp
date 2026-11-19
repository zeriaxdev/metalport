// dxbc file -> Metal source via Unity's HLSLcc. usage: h2m in.dxbc flagsHex
#include <cstdio>
#include <cstdlib>
#include <vector>
#include <string>
#include "hlslcc.h"
struct Refl : HLSLccReflection {
    void OnDiagnostics(const std::string& e, int l, bool err) override { fprintf(stderr, "diag(%d): %s\n", err, e.c_str()); }
    void OnConstantBufferBinding(const std::string& n, int i) override { fprintf(stderr, "CB %s -> %d\n", n.c_str(), i); }
    void OnTextureBinding(const std::string& n, int i, int s, bool ms, HLSLCC_TEX_DIMENSION d, bool uav) override { fprintf(stderr, "TEX %s -> %d (sampler %d)\n", n.c_str(), i, s); }
    void OnBufferBinding(const std::string& n, int i, bool uav) override { fprintf(stderr, "BUF %s -> %d\n", n.c_str(), i); }
};
int main(int argc, char** argv) {
    FILE* f = fopen(argv[1], "rb"); std::vector<char> d(1 << 20); size_t n = fread(d.data(), 1, d.size(), f); d.resize(n); fclose(f);
    unsigned flags = (unsigned)strtoul(argv[2], 0, 16);
    GLSLCrossDependencyData dep; HLSLccSamplerPrecisionInfo sp; Refl r; GLSLShader out; GlExtensions ext = {};
    int ok = TranslateHLSLFromMem(d.data(), flags, LANG_METAL, &ext, &dep, sp, r, &out);
    fprintf(stderr, "ok=%d\n", ok);
    fputs(out.sourceCode.c_str(), stdout);
    return ok ? 0 : 1;
}
