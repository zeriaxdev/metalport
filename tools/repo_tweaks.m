// Injected into the R.E.P.O. player (DYLD_INSERT_LIBRARIES): mouse delta scale, App Nap off, optional first-run shader warm-up.
#import <Cocoa/Cocoa.h>
#import <objc/runtime.h>
#include <stdlib.h>
#include <dlfcn.h>
#include <ApplicationServices/ApplicationServices.h>
static double gScale = 2.0;
static IMP origDX, origDY;
static CGFloat dxHook(id self, SEL _cmd) { return ((CGFloat(*)(id, SEL))origDX)(self, _cmd) * gScale; }
static CGFloat dyHook(id self, SEL _cmd) { return ((CGFloat(*)(id, SEL))origDY)(self, _cmd) * gScale; }
#define DYLD_INTERPOSE(_r,_o) __attribute__((used)) static struct{const void*r;const void*o;} _i_##_o __attribute__((section("__DATA,__interpose"))) = {(const void*)(unsigned long)&_r,(const void*)(unsigned long)&_o};
void my_CGGetLastMouseDelta(int32_t* dx, int32_t* dy) { CGGetLastMouseDelta(dx, dy); if (dx) *dx = (int32_t)(*dx * gScale); if (dy) *dy = (int32_t)(*dy * gScale); }
DYLD_INTERPOSE(my_CGGetLastMouseDelta, CGGetLastMouseDelta)

static void warmlog(const char* msg) {
    const char* p = getenv("REPO_LOG"); if (!p || !*p || !strcmp(p, "/dev/null")) return;
    char path[1024]; snprintf(path, sizeof path, "%s.warmup", p); FILE* f = fopen(path, "a"); if (f) { fprintf(f, "%s\n", msg); fclose(f); }
}
// Shader.WarmupAllShaders() compiles every shader variant once so Metal caches it; blocks the main thread (a few minutes, first run only).
static void warmup(void) {
    #define SYM(name) name##_t name = (name##_t)dlsym(RTLD_DEFAULT, #name); if (!name) { warmlog("mono symbol missing: " #name); return; }
    typedef void* (*mono_get_root_domain_t)(void); typedef void* (*mono_thread_attach_t)(void*); typedef void* (*mono_assembly_name_new_t)(const char*);
    typedef void* (*mono_assembly_loaded_t)(void*); typedef void* (*mono_assembly_get_image_t)(void*); typedef void* (*mono_class_from_name_t)(void*, const char*, const char*);
    typedef void* (*mono_class_get_method_from_name_t)(void*, const char*, int); typedef void* (*mono_runtime_invoke_t)(void*, void*, void**, void**);
    SYM(mono_get_root_domain) SYM(mono_thread_attach) SYM(mono_assembly_name_new) SYM(mono_assembly_loaded) SYM(mono_assembly_get_image)
    SYM(mono_class_from_name) SYM(mono_class_get_method_from_name) SYM(mono_runtime_invoke)
    mono_thread_attach(mono_get_root_domain());
    void* asmb = mono_assembly_loaded(mono_assembly_name_new("UnityEngine.CoreModule")); if (!asmb) { warmlog("UnityEngine.CoreModule not loaded"); return; }
    void* klass = mono_class_from_name(mono_assembly_get_image(asmb), "UnityEngine", "Shader"); if (!klass) { warmlog("Shader class missing"); return; }
    void* m = mono_class_get_method_from_name(klass, "WarmupAllShaders", 0); if (!m) { warmlog("WarmupAllShaders missing"); return; }
    NSDate* t0 = [NSDate date]; warmlog("warmup: start"); void* exc = NULL; mono_runtime_invoke(m, NULL, NULL, &exc);
    char buf[128]; snprintf(buf, sizeof buf, "warmup: done in %.1f s%s", -[t0 timeIntervalSinceNow], exc ? " (exception)" : ""); warmlog(buf);
    const char* mark = getenv("REPO_WARMUP_MARK"); if (mark && !exc) { NSString* dir = [[NSString stringWithUTF8String:mark] stringByDeletingLastPathComponent];
        [[NSFileManager defaultManager] createDirectoryAtPath:dir withIntermediateDirectories:YES attributes:nil error:nil];
        [@"done" writeToFile:[NSString stringWithUTF8String:mark] atomically:YES encoding:NSUTF8StringEncoding error:nil]; }
}
__attribute__((constructor)) static void init(void) {
    const char* s = getenv("REPO_MOUSE_SCALE"); if (s) gScale = atof(s);
    Method mx = class_getInstanceMethod([NSEvent class], @selector(deltaX)), my = class_getInstanceMethod([NSEvent class], @selector(deltaY));
    origDX = method_setImplementation(mx, (IMP)dxHook); origDY = method_setImplementation(my, (IMP)dyHook);
    [[NSProcessInfo processInfo] beginActivityWithOptions:(NSActivityUserInitiatedAllowingIdleSystemSleep | NSActivityLatencyCritical) reason:@"R.E.P.O. game"];
    if (getenv("REPO_WARMUP")) dispatch_after(dispatch_time(DISPATCH_TIME_NOW, (int64_t)(30 * NSEC_PER_SEC)), dispatch_get_main_queue(), ^{ warmup(); });
}
