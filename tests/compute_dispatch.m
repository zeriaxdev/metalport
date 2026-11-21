// Optional integration checks against user-supplied converted compute kernels.
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#include <math.h>
#include <stdint.h>
#include <string.h>

static void check(BOOL ok, NSString *message) {
    if (!ok) { fprintf(stderr, "%s\n", message.UTF8String); exit(2); }
}
static NSUInteger slot(NSDictionary *kv, NSString *group, NSString *name) {
    for (NSDictionary *binding in kv[group]) if ([binding[@"name"] isEqual:name]) return [binding[@"bindPoint"] unsignedIntegerValue];
    check(NO, [@"Missing binding: " stringByAppendingString:name]); return 0;
}
static id<MTLTexture> texture(id<MTLDevice> device, NSUInteger w, NSUInteger h, NSUInteger d) {
    MTLTextureDescriptor *desc = [MTLTextureDescriptor new];
    desc.textureType = d > 1 ? MTLTextureType3D : MTLTextureType2D;
    desc.width=w; desc.height=h; desc.depth=d; desc.pixelFormat=MTLPixelFormatRGBA32Float;
    desc.storageMode=MTLStorageModeShared; desc.usage=MTLTextureUsageShaderRead|MTLTextureUsageShaderWrite;
    id<MTLTexture> tex=[device newTextureWithDescriptor:desc]; check(tex!=nil,@"Cannot allocate test texture"); return tex;
}
static void put(id<MTLTexture> tex, float *data) {
    [tex replaceRegion:MTLRegionMake3D(0,0,0,tex.width,tex.height,tex.depth) mipmapLevel:0 slice:0 withBytes:data bytesPerRow:tex.width*16 bytesPerImage:tex.width*tex.height*16];
}
int main(int argc, const char **argv) {
    @autoreleasepool {
        check(argc==4,@"usage: compute_dispatch palette|mask|composite source.metal bindings.json");
        NSString *mode=@(argv[1]);
        NSDictionary *config=[NSJSONSerialization JSONObjectWithData:[NSData dataWithContentsOfFile:@(argv[3])] options:0 error:NULL];
        check(config!=nil,@"Cannot read binding metadata");
        NSDictionary *kv=config[@"kernel"];
        id<MTLDevice> device=MTLCreateSystemDefaultDevice(); check(device!=nil,@"Metal device unavailable");
        NSError *error=nil;
        NSString *source=[NSString stringWithContentsOfFile:@(argv[2]) encoding:NSUTF8StringEncoding error:&error];
        check(source!=nil,error.localizedDescription?:@"Cannot read source");
        id<MTLLibrary> library=[device newLibraryWithSource:source options:nil error:&error]; check(library!=nil,error.localizedDescription?:@"Compile failed");
        id<MTLFunction> fn=[library newFunctionWithName:@"computeMain"]; check(fn!=nil,@"Missing computeMain");
        id<MTLComputePipelineState> pipeline=[device newComputePipelineStateWithFunction:fn error:&error]; check(pipeline!=nil,error.localizedDescription?:@"Cannot build pipeline");
        BOOL palette=[mode isEqual:@"palette"], mask=[mode isEqual:@"mask"], composite=[mode isEqual:@"composite"];
        check(palette||mask||composite,@"Unknown test mode");
        NSUInteger w=8,h=8,d=palette?8:1, count=w*h*d;
        id<MTLTexture> input=texture(device,palette?32:8,palette?32:8,1);
        id<MTLTexture> output=texture(device,w,h,d);
        float in[32*32*4]={0};
        const float colors[4][4]={{0,0,0,1},{0.023f,0,0,1},{0,0.019f,0,1},{0,0,0.031f,1}};
        if (palette) {
            const int points[4]={0,3*32+9,31*32+31,31*32};
            for(int i=0;i<4;i++) memcpy(in+points[i]*4,colors[i],16);
        } else if(mask) {
            for(NSUInteger i=0;i<count;i++) { in[i*4]=(i%4==0)?0:(i%4==1)?0.2f:1.2f; in[i*4+1]=(i%4==3)?-0.3f:(i%4==1)?0.1f:0; }
        } else {
            for(NSUInteger i=0;i<count;i++) { float delta=(i%4==0)?0.25f:(i%4==1)?2.25f:(i%4==2)?1.25f:4000.f; in[i*4]=(delta+15.5f)/31.f; in[i*4+1]=0.5f; }
        }
        put(input,in);
        float initial[8*8*4];
        if(composite) {
            for(NSUInteger i=0;i<count;i++) { initial[i*4]=0.75f; initial[i*4+1]=0.4f; initial[i*4+2]=0.2f; initial[i*4+3]=0.5f; }
            put(output,initial);
        }
        id<MTLCommandQueue> queue=[device newCommandQueue];
        id<MTLCommandBuffer> command=[queue commandBuffer];
        id<MTLComputeCommandEncoder> encoder=[command computeCommandEncoder];
        [encoder setComputePipelineState:pipeline];
        [encoder setTexture:input atIndex:slot(kv,@"textures",palette?@"_PaletteTex":@"_PassIn")];
        [encoder setTexture:output atIndex:slot(kv,@"outBuffers",palette?@"Result":composite?@"_MainTex":@"_PassOut")];
        if(composite) {
            NSUInteger cbIndex=[kv[@"cbVariantIndices"][0] unsignedIntegerValue];
            NSDictionary *cb=config[@"constantBuffers"][cbIndex];
            NSMutableData *bytes=[NSMutableData dataWithLength:[cb[@"byteSize"] unsignedIntegerValue]];
            BOOL distance=NO, resolution=NO;
            for(NSDictionary *param in cb[@"params"]) {
                NSUInteger offset=[param[@"offset"] unsignedIntegerValue];
                if([param[@"name"] isEqual:@"_OutlineDistance"]) { check(offset+4<=bytes.length,@"CB offset out of bounds"); float value=1; memcpy((char*)bytes.mutableBytes+offset,&value,4); distance=YES; }
                if([param[@"name"] isEqual:@"_ResolutionDiff"]) { check(offset+8<=bytes.length,@"CB vector out of bounds"); float value[2]={1,1}; memcpy((char*)bytes.mutableBytes+offset,value,8); resolution=YES; }
            }
            check(distance&&resolution,@"Missing reflected CB parameters");
            [encoder setBytes:bytes.bytes length:bytes.length atIndex:slot(kv,@"cbs",@"Globals")];
        }
        NSArray *group=kv[@"threadGroupSize"];
        MTLSize threads=MTLSizeMake([group[0] unsignedIntegerValue],[group[1] unsignedIntegerValue],[group[2] unsignedIntegerValue]);
        check(threads.width*threads.height*threads.depth<=pipeline.maxTotalThreadsPerThreadgroup,@"Unsupported group size");
        [encoder dispatchThreads:MTLSizeMake(w,h,d) threadsPerThreadgroup:threads];
        [encoder endEncoding]; [command commit]; [command waitUntilCompleted];
        check(command.status==MTLCommandBufferStatusCompleted,command.error.localizedDescription?:@"GPU dispatch failed");
        float result[8*8*8*4];
        [output getBytes:result bytesPerRow:w*16 bytesPerImage:w*h*16 fromRegion:MTLRegionMake3D(0,0,0,w,h,d) mipmapLevel:0 slice:0];
        NSUInteger matched=0;
        for(NSUInteger i=0;i<count;i++) {
            BOOL ok=YES;
            if(palette) {
                float target[3]={(i%w)/255.f,((i/w)%h)/255.f,(i/(w*h))/255.f};
                float best=INFINITY, actual=0;
                for(int c=0;c<4;c++) { float distance=0; for(int k=0;k<3;k++) distance+=(colors[c][k]-target[k])*(colors[c][k]-target[k]); best=fminf(best,distance); }
                for(int k=0;k<3;k++) actual+=(result[i*4+k]-target[k])*(result[i*4+k]-target[k]);
                BOOL isColor=NO; for(int c=0;c<4;c++) if(!memcmp(result+i*4,colors[c],16)) isColor=YES;
                ok=isColor&&fabsf(actual-best)<1e-7f;
            } else if(mask) {
                uint32_t expected=fmaxf(ceilf(fminf(in[i*4],in[i*4+1])),floorf(in[i*4]))<1 ? 0x3f800000 : 0x3f042108;
                for(int k=0;k<4;k++) { uint32_t bits; memcpy(&bits,result+i*4+k,4); if(bits!=expected) ok=NO; }
            } else {
                for(int k=0;k<4;k++) { float expected=(i%4==2 && k<3)?0:initial[i*4+k]; if(fabsf(result[i*4+k]-expected)>1e-6f) ok=NO; }
            }
            if(ok) matched++;
            else if(i<4) fprintf(stderr,"Mismatch at %lu: %g,%g,%g,%g\n",(unsigned long)i,result[i*4],result[i*4+1],result[i*4+2],result[i*4+3]);
        }
        NSDictionary *summary=@{@"mode":mode,@"texels":@(count),@"matched":@(matched),@"device":device.name};
        NSData *json=[NSJSONSerialization dataWithJSONObject:summary options:0 error:NULL]; fwrite(json.bytes,1,json.length,stdout); putchar('\n');
        return matched==count?0:1;
    }
}
