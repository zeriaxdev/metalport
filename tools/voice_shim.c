// libopus_egpv: Photon Voice calls Opus through a renamed "opus_egpv" with non-variadic ctl helpers. Everything else is stock libopus (re-exported).
// ctl_set tuning calls (FEC, DTX, complexity...) never fail the codec: Photon throws on any non-OK status, and these are optional.
#include <opus.h>
#include <stdio.h>
#include <stdlib.h>
static void note(const char* tag, void* st, int req, int val, int r) {
    static const char* path; static int init; if (!init) { path = getenv("OPUS_SHIM_LOG"); init = 1; }
    if (!path) return; FILE* f = fopen(path, "a"); if (f) { fprintf(f, "%s st=%p req=%d val=%d -> %d\n", tag, st, req, val, r); fclose(f); }
}
static int optional(int req) { return req == 4012 || req == 4016 || req == 4010 || req == 4014 || req == 4024 || req == 4006 || req == 4020 || req == 4022; }
int opus_encoder_ctl_set(OpusEncoder* st, int request, int value) { int r = opus_encoder_ctl(st, request, value); note("enc_set", st, request, value, r); return (r != 0 && optional(request)) ? 0 : r; }
int opus_encoder_ctl_get(OpusEncoder* st, int request, int* value) { int r = opus_encoder_ctl(st, request, value); note("enc_get", st, request, value ? *value : -999, r); return r; }
int opus_decoder_ctl_set(OpusDecoder* st, int request, int value) { int r = opus_decoder_ctl(st, request, value); note("dec_set", st, request, value, r); return r; }
int opus_decoder_ctl_get(OpusDecoder* st, int request, int* value) { int r = opus_decoder_ctl(st, request, value); note("dec_get", st, request, value ? *value : -999, r); return r; }
