// Stand-ins for Photon's WebRTC audio processor (pass-through + energy VAD, no AEC/NS/AGC) and AudioIn (no native mics; Unity's Microphone is used).
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
typedef struct { int hang; } Proc;
void* webrtc_audio_processor_create(int a, int b, int c, int d, int e) { return calloc(1, sizeof(Proc)); }
int webrtc_audio_processor_init(void* p) { return 0; }
int webrtc_audio_processor_set_param(void* p, int k, int v) { return 0; }
int webrtc_audio_processor_process(void* p, int16_t* buf, int n, unsigned char* vad) {
    Proc* s = (Proc*)p; double e = 0; for (int i = 0; i < n; i++) e += (double)buf[i] * buf[i];
    double rms = n ? __builtin_sqrt(e / n) : 0;
    if (rms > 250.0) s->hang = 15; else if (s->hang > 0) s->hang--;
    if (vad) *vad = s->hang > 0; return 0;
}
int webrtc_audio_processor_process_reverse(void* p, int16_t* buf, int n) { return 0; }
void webrtc_audio_processor_destroy(void* p) { free(p); }
void* Photon_Audio_In_CreateMicEnumerator(void) { return calloc(1, 8); }
void Photon_Audio_In_DestroyMicEnumerator(void* p) { free(p); }
int Photon_Audio_In_MicEnumerator_Count(void* p) { return 0; }
const char* Photon_Audio_In_MicEnumerator_NameAtIndex(void* p, int i) { return NULL; }
int Photon_Audio_In_MicEnumerator_IDAtIndex(void* p, int i) { return -1; }
void* Photon_Audio_In_Create(void) { return NULL; }
void Photon_Audio_In_Destroy(void* p) {}
