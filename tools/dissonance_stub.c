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
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#define EXPORT __attribute__((visibility("default")))
typedef struct { int speech; int hang; float threshold; int vad_level; int muted; int frames; float peak; } Pre;

static float threshold_from_env(void) {
    const char* e = getenv("MP_VAD_DB"); double db = e ? atof(e) : -48.0;
    if (db > -10.0) db = -10.0;
    if (db < -90.0) db = -90.0;
    return (float)pow(10.0, db / 20.0);
}

// Diagnostics: ~/Library/Logs/metalport/dissonance-stub.log (or $MP_DISSONANCE_LOG): preprocessor creation, speech start/stop and a
// 5 s summary (frames, loudest frame in dBFS). Low volume on purpose; it answers "does the game get my voice and does the gate open".
static void note(const char* fmt, double a, double b, double c) {
    static char path[1024]; static int init;
    if (!init) {
        init = 1; const char* e = getenv("MP_DISSONANCE_LOG"); const char* home = getenv("HOME");
        if (e && *e) snprintf(path, sizeof path, "%s", e); else if (home) snprintf(path, sizeof path, "%s/Library/Logs/metalport/dissonance-stub.log", home);
    }
    if (!path[0]) return;
    FILE* f = fopen(path, "a"); if (!f) return;
    time_t t = time(NULL); struct tm tm; localtime_r(&t, &tm); char ts[16]; strftime(ts, sizeof ts, "%H:%M:%S", &tm);
    fprintf(f, "%s ", ts); fprintf(f, fmt, a, b, c); fputc('\n', f); fclose(f);
}

EXPORT void* Dissonance_CreatePreprocessor(int noise, int aec, int a, int b, int c, int routing, int d) {
    (void)noise; (void)aec; (void)a; (void)b; (void)c; (void)routing; (void)d;
    Pre* p = calloc(1, sizeof *p); if (p) p->threshold = threshold_from_env();
    if (p) note("preprocessor created, gate %.1f dBFS", 20.0 * log10(p->threshold), 0, 0);
    return p;
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
    float rms = (float)sqrt(sum / n); int was = p->speech;
    // The game reports "output muted" while it is NOT transmitting, so muted must not gate detection (it would never start).
    if (rms > p->threshold) { p->speech = 1; p->hang = 25; }                      // 250 ms hang-over
    else if (p->hang > 0) p->hang--; else p->speech = 0;
    if (rms > p->peak) p->peak = rms;
    if (p->speech != was) note(p->speech ? "speech start (frame %.1f dBFS)" : "speech stop (frame %.1f dBFS)", 20.0 * log10(rms + 1e-9), 0, 0);
    if (++p->frames % 500 == 0) { note("5 s: %.0f frames, loudest %.1f dBFS", 500, 20.0 * log10(p->peak + 1e-9), 0); p->peak = 0; }
    if (out != in) memcpy(out, in, (size_t)n * sizeof(float));
    return 0;
}

// RNNoise is optional in Dissonance; report "no speech" and no gains so it falls back to the plain path.
EXPORT void* Dissonance_CreateRnnoiseState(void) { return calloc(1, 8); }
EXPORT void Dissonance_DestroyRnnoiseState(void* h) { free(h); }
EXPORT int Dissonance_RnnoiseProcessFrame(void* h, int a, int b, float* in, float* out) { (void)h; (void)a; (void)b; (void)in; (void)out; return 0; }
EXPORT int Dissonance_RnnoiseGetGains(void* h, float* gains, int n) { (void)h; (void)gains; (void)n; return 0; }
