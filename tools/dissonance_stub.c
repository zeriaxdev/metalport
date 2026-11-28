// libdissonance_stub: macOS stand-in for Dissonance Voice Chat's native "AudioPluginDissonance" (Windows-only in the game).
// Dissonance P/Invokes 16 functions from it for capture preprocessing. Without a library the preprocessor thread dies with
// DllNotFoundException and no microphone audio is ever sent.
// This stub keeps the managed pipeline alive: audio passes through unchanged (no noise suppression, no echo cancellation, no AGC)
// and speech detection is a plain loudness gate. Signatures come from DissonanceVoip.dll (decoded with Mono.Cecil), 4-byte BOOL as in
// Windows P/Invoke marshalling. The Opus helpers (dissonance_opus_*) already live in liboptional_compat.dylib.
//
// ponytail: loudness gate instead of WebRTC VAD; the threshold has a knob, MP_VAD_DB (dBFS, default -48). Raise it if the mic
// sends background noise, lower it if quiet speech is cut. Upgrade path: bind real WebRTC audio processing.
#include <math.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

#define EXPORT __attribute__((visibility("default")))
typedef struct { int speech; int hang; float threshold; int vad_level; int muted; } Pre;

static float threshold_from_env(void) {
    const char* e = getenv("MP_VAD_DB"); double db = e ? atof(e) : -48.0;
    if (db > -10.0) db = -10.0;
    if (db < -90.0) db = -90.0;
    return (float)pow(10.0, db / 20.0);
}

EXPORT void* Dissonance_CreatePreprocessor(int noise, int aec, int a, int b, int c, int routing, int d) {
    (void)noise; (void)aec; (void)a; (void)b; (void)c; (void)routing; (void)d;
    Pre* p = calloc(1, sizeof *p); if (p) p->threshold = threshold_from_env(); return p;
}
EXPORT void Dissonance_DestroyPreprocessor(void* h) { free(h); }
EXPORT void Dissonance_ConfigureNoiseSuppression(void* h, int level) { (void)h; (void)level; }
EXPORT void Dissonance_ConfigureVadSensitivity(void* h, int level) { if (h) ((Pre*)h)->vad_level = level; }
EXPORT void Dissonance_ConfigureAecSuppression(void* h, int level, int routing) { (void)h; (void)level; (void)routing; }
EXPORT int Dissonance_GetVadSpeechState(void* h) { return h ? ((Pre*)h)->speech : 0; }
EXPORT void Dissonance_SetAgcIsOutputMutedState(void* h, int muted) { if (h) ((Pre*)h)->muted = muted; }
EXPORT int Dissonance_PreprocessorExchangeInstance(void* a, void* b) { (void)a; (void)b; return 1; }
EXPORT int Dissonance_GetFilterState(void) { return 3; }                       // FilterOk
EXPORT void Dissonance_GetAecMetrics(void* h, int x) { (void)h; (void)x; }

// ProcessorErrors: 0 Ok, -5 NullPointer, -7 BadSampleRate. One call = one 10 ms frame (rate/100 samples); the game passes the same buffer as input and output.
EXPORT int Dissonance_PreprocessCaptureFrame(void* h, int rate, float* in, float* out, int delay_ms) {
    (void)delay_ms; Pre* p = h; if (!p || !in || !out) return -5;
    if (rate != 8000 && rate != 16000 && rate != 32000 && rate != 48000) return -7;
    int n = rate / 100; double sum = 0; for (int i = 0; i < n; i++) sum += (double)in[i] * in[i];
    float rms = (float)sqrt(sum / n);
    if (!p->muted && rms > p->threshold) { p->speech = 1; p->hang = 25; }       // 250 ms hang-over
    else if (p->hang > 0) p->hang--; else p->speech = 0;
    if (out != in) memcpy(out, in, (size_t)n * sizeof(float));
    return 0;
}

// RNNoise is optional in Dissonance; report "no speech" and no gains so it falls back to the plain path.
EXPORT void* Dissonance_CreateRnnoiseState(void) { return calloc(1, 8); }
EXPORT void Dissonance_DestroyRnnoiseState(void* h) { free(h); }
EXPORT int Dissonance_RnnoiseProcessFrame(void* h, int a, int b, float* in, float* out) { (void)h; (void)a; (void)b; (void)in; (void)out; return 0; }
EXPORT int Dissonance_RnnoiseGetGains(void* h, float* gains, int n) { (void)h; (void)gains; (void)n; return 0; }
