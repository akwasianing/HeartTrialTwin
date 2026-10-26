// Offline Apple Vision OCR; stdout must be captured privately by the scanner.
#import <Foundation/Foundation.h>
#import <Vision/Vision.h>
int main(void) {
    @autoreleasepool {
        char *line = NULL;
        size_t capacity = 0;
        while (getline(&line, &capacity, stdin) > 0) {
            @autoreleasepool {
                NSString *path = [[NSString stringWithUTF8String:line]
                    stringByTrimmingCharactersInSet:[NSCharacterSet newlineCharacterSet]];
                VNRecognizeTextRequest *request = [VNRecognizeTextRequest new];
                request.recognitionLevel = VNRequestTextRecognitionLevelAccurate;
                request.usesLanguageCorrection = NO;
                request.usesCPUOnly = YES;
                VNImageRequestHandler *handler = [[VNImageRequestHandler alloc]
                    initWithURL:[NSURL fileURLWithPath:path] options:@{}];
                NSError *error = nil;
                BOOL ok = [handler performRequests:@[request] error:&error];
                NSMutableArray *lines = [NSMutableArray new];
                if (ok) for (VNRecognizedTextObservation *observation in request.results) {
                    VNRecognizedText *candidate = [[observation topCandidates:1] firstObject];
                    if (candidate) [lines addObject:candidate.string];
                }
                NSData *json = [NSJSONSerialization dataWithJSONObject:
                    @{ @"ok": @(ok), @"text": [lines componentsJoinedByString:@"\n"] }
                    options:0 error:nil];
                puts([[NSString alloc] initWithData:json encoding:NSUTF8StringEncoding].UTF8String);
                fflush(stdout);
            }
        }
        free(line);
    }
    return 0;
}
