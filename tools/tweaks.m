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
    const char* p = getenv("MP_LOG"); if (!p || !*p || !strcmp(p, "/dev/null")) return;
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
    const char* mark = getenv("MP_WARMUP_MARK"); if (mark && !exc) { NSString* dir = [[NSString stringWithUTF8String:mark] stringByDeletingLastPathComponent];
        [[NSFileManager defaultManager] createDirectoryAtPath:dir withIntermediateDirectories:YES attributes:nil error:nil];
        [@"done" writeToFile:[NSString stringWithUTF8String:mark] atomically:YES encoding:NSUTF8StringEncoding error:nil]; }
}
// Debug hook: MP_INVOKE="Assembly:Namespace.Class:Method" calls that static, parameterless method on the main thread as soon as its assembly is loaded, then every 10 s.
static int invoke_env(void) {
    typedef void* (*mono_get_root_domain_t)(void); typedef void* (*mono_thread_attach_t)(void*); typedef void* (*mono_assembly_name_new_t)(const char*);
    typedef void* (*mono_assembly_loaded_t)(void*); typedef void* (*mono_assembly_get_image_t)(void*); typedef void* (*mono_class_from_name_t)(void*, const char*, const char*);
    typedef void* (*mono_class_get_method_from_name_t)(void*, const char*, int); typedef void* (*mono_runtime_invoke_t)(void*, void*, void**, void**);
    #undef SYM
    #define SYM(name) name##_t name = (name##_t)dlsym(RTLD_DEFAULT, #name); if (!name) return 0;
    SYM(mono_get_root_domain) SYM(mono_thread_attach) SYM(mono_assembly_name_new) SYM(mono_assembly_loaded) SYM(mono_assembly_get_image)
    SYM(mono_class_from_name) SYM(mono_class_get_method_from_name) SYM(mono_runtime_invoke)
    void* root = mono_get_root_domain(); if (!root) return 0;                        // mono not up yet
    char spec[512]; strlcpy(spec, getenv("MP_INVOKE"), sizeof spec);
    char* a = strtok(spec, ":"); char* cls = strtok(NULL, ":"); char* meth = strtok(NULL, ":"); if (!a || !cls || !meth) { warmlog("MP_INVOKE: want Assembly:Ns.Class:Method"); return 1; }
    char* dot = strrchr(cls, '.'); const char* ns = ""; if (dot) { *dot = 0; ns = cls; cls = dot + 1; }
    mono_thread_attach(root);
    void* asmb = mono_assembly_loaded(mono_assembly_name_new(a));
    if (!asmb) {                                       // not referenced yet: load it from Data/Managed once the engine assemblies are up
        typedef void* (*mono_domain_get_t)(void); typedef void* (*mono_domain_assembly_open_t)(void*, const char*);
        SYM(mono_domain_get) SYM(mono_domain_assembly_open)
        if (!mono_assembly_loaded(mono_assembly_name_new("UnityEngine.CoreModule"))) return 0;
        NSString* p = [NSString stringWithFormat:@"%@/Data/Managed/%s.dll", [[NSBundle mainBundle] resourcePath], a];
        asmb = mono_domain_assembly_open(mono_domain_get(), p.UTF8String); if (!asmb) return 0;
    }
    void* k = mono_class_from_name(mono_assembly_get_image(asmb), ns, cls); void* m = k ? mono_class_get_method_from_name(k, meth, 0) : NULL;
    if (!m) { warmlog("MP_INVOKE: method not found"); return 1; }
    void* exc = NULL; mono_runtime_invoke(m, NULL, NULL, &exc); if (exc) warmlog("MP_INVOKE: exception");
    static int once; if (!once++) warmlog("MP_INVOKE: first call done");
    return 1;
}
static void invoke_loop(void) { int ok = invoke_env(); dispatch_after(dispatch_time(DISPATCH_TIME_NOW, (ok ? 10 : 1) * NSEC_PER_SEC), dispatch_get_main_queue(), ^{ invoke_loop(); }); }
// MP_NO_ACTIVATE=1: for the first 20 s the game may not bring itself to the front (launch behind other windows); clicking it works as usual.
static BOOL gQuiet; static IMP origActivate, origActivate2, origKeyFront;
static void noActivate(id self, SEL _cmd, BOOL flag) { if (!gQuiet) ((void(*)(id, SEL, BOOL))origActivate)(self, _cmd, flag); }
static void noActivate2(id self, SEL _cmd) { if (!gQuiet) ((void(*)(id, SEL))origActivate2)(self, _cmd); }
static void keyFront(id self, SEL _cmd, id sender) { if (gQuiet) [self orderBack:sender]; else ((void(*)(id, SEL, id))origKeyFront)(self, _cmd, sender); }
__attribute__((constructor)) static void init(void) {
    if (getenv("MP_NO_ACTIVATE")) {
        gQuiet = YES;
        origActivate = method_setImplementation(class_getInstanceMethod([NSApplication class], @selector(activateIgnoringOtherApps:)), (IMP)noActivate);
        Method a2 = class_getInstanceMethod([NSApplication class], @selector(activate)); if (a2) origActivate2 = method_setImplementation(a2, (IMP)noActivate2);
        origKeyFront = method_setImplementation(class_getInstanceMethod([NSWindow class], @selector(makeKeyAndOrderFront:)), (IMP)keyFront);
        dispatch_after(dispatch_time(DISPATCH_TIME_NOW, (int64_t)(20 * NSEC_PER_SEC)), dispatch_get_main_queue(), ^{ gQuiet = NO; });
        method_setImplementation(class_getInstanceMethod([NSWindow class], @selector(occlusionState)), imp_implementationWithBlock(^NSWindowOcclusionState(id w) { return NSWindowOcclusionStateVisible; }));   // keep drawing while covered (screenshots)
        method_setImplementation(class_getInstanceMethod([NSApplication class], @selector(occlusionState)), imp_implementationWithBlock(^NSApplicationOcclusionState(id a) { return NSApplicationOcclusionStateVisible; }));
        method_setImplementation(class_getInstanceMethod([NSApplication class], @selector(isActive)), imp_implementationWithBlock(^BOOL(id a) { return YES; }));   // Unity pauses an inactive player
        dispatch_after(dispatch_time(DISPATCH_TIME_NOW, (int64_t)(2 * NSEC_PER_SEC)), dispatch_get_main_queue(), ^{
            [[NSNotificationCenter defaultCenter] postNotificationName:NSApplicationDidBecomeActiveNotification object:NSApp]; });
    }
    if (getenv("MP_INVOKE")) dispatch_after(dispatch_time(DISPATCH_TIME_NOW, (int64_t)(3 * NSEC_PER_SEC)), dispatch_get_main_queue(), ^{ invoke_loop(); });
    const char* s = getenv("MP_MOUSE_SCALE"); if (s) gScale = atof(s);
    Method mx = class_getInstanceMethod([NSEvent class], @selector(deltaX)), my = class_getInstanceMethod([NSEvent class], @selector(deltaY));
    origDX = method_setImplementation(mx, (IMP)dxHook); origDY = method_setImplementation(my, (IMP)dyHook);
    [[NSProcessInfo processInfo] beginActivityWithOptions:(NSActivityUserInitiatedAllowingIdleSystemSleep | NSActivityLatencyCritical) reason:@"R.E.P.O. game"];
    if (getenv("MP_WARMUP")) dispatch_after(dispatch_time(DISPATCH_TIME_NOW, (int64_t)(30 * NSEC_PER_SEC)), dispatch_get_main_queue(), ^{ warmup(); });
}
