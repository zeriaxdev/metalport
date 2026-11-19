// libopus_egpv: Photon Voice P/Invokes libopus' *variadic* opus_encoder_ctl / opus_decoder_ctl with a fixed (ptr, int, int-or-pointer) signature.
// On Apple arm64, variadic arguments travel on the stack, so a plain call from managed code hands libopus garbage (-> BadArguments / silent codec failure).
// These non-variadic exports take the third argument in a register and forward it to the real variadic functions. Everything else is stock libopus (re-exported).
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <dlfcn.h>
typedef int (*ctl_t)(void*, int, ...);
static ctl_t real_enc, real_dec;
__attribute__((constructor)) static void init(void) {
    real_enc = (ctl_t)dlsym(RTLD_NEXT, "opus_encoder_ctl"); real_dec = (ctl_t)dlsym(RTLD_NEXT, "opus_decoder_ctl");
    FILE* f = fopen("/tmp/opus_shim_alive.log", "a"); if (f) { fprintf(f, "shim loaded pid=%d enc=%p dec=%p\n", (int)getpid(), (void*)real_enc, (void*)real_dec); fclose(f); }
}
static void note(const char* tag, void* st, int req, long arg, int r) {
    static const char* path; static int inited; if (!inited) { path = getenv("OPUS_SHIM_LOG"); inited = 1; }
    if (!path) return; FILE* f = fopen(path, "a"); if (f) { fprintf(f, "%s st=%p req=%d arg=%ld -> %d\n", tag, st, req, arg, r); fclose(f); }
}
// OPUS_SET_* requests are even (4000, 4002...), OPUS_GET_* are odd: GET takes a pointer, SET takes an int.
static int call(ctl_t real, const char* tag, void* st, int req, long arg) {
    int r = (req & 1) ? real(st, req, (int32_t*)arg) : real(st, req, (int32_t)arg);
    note(tag, st, req, arg, r); return r;
}
int opus_encoder_ctl(void* st, int request, long arg) { return call(real_enc, "enc", st, request, arg); }
int opus_decoder_ctl(void* st, int request, long arg) { return call(real_dec, "dec", st, request, arg); }
