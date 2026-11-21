// Adapted from wisnuub/ror2-silicon-macos, MIT, copyright (c) 2026 wisnuub.
// The full license is in shaderconv-LICENSE.txt.
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>

static void emit(NSDictionary *result) {
    NSData *json = [NSJSONSerialization dataWithJSONObject:result options:0 error:NULL];
    fwrite(json.bytes, 1, json.length, stdout);
    putchar('\n');
}

int main(int argc, const char **argv) {
    @autoreleasepool {
        id<MTLDevice> device = MTLCreateSystemDefaultDevice();
        if (!device) {
            emit(@{@"error": @"Metal device unavailable"});
            return 3;
        }
        MTLCompileOptions *options = [MTLCompileOptions new];
        options.fastMathEnabled = YES;
        int failures = 0;
        for (int i = 1; i < argc; ++i) {
            @autoreleasepool {
                NSError *error = nil;
                NSString *source = [NSString stringWithContentsOfFile:@(argv[i]) encoding:NSUTF8StringEncoding error:&error];
                id<MTLLibrary> library = source ? [device newLibraryWithSource:source options:options error:&error] : nil;
                BOOL ok = library && ([library newFunctionWithName:@"xlatMtlMain"] || [library newFunctionWithName:@"computeMain"]);
                emit(@{@"path": @(argv[i]), @"ok": @(ok), @"error": ok ? @"" : (error.localizedDescription ?: @"No xlatMtlMain or computeMain entry point")});
                if (!ok) ++failures;
            }
        }
        return failures ? 1 : 0;
    }
}
