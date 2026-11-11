import Foundation
import Vision
import AppKit

let path = CommandLine.arguments[1]
guard let img = NSImage(contentsOfFile: path),
      let data = img.tiffRepresentation,
      let rep = NSBitmapImageRep(data: data),
      let cg = rep.cgImage else { exit(1) }
let req = VNRecognizeTextRequest()
req.recognitionLevel = .accurate
req.usesLanguageCorrection = false
if CommandLine.arguments.count < 3 || CommandLine.arguments[2] != "--full" {
    req.regionOfInterest = CGRect(x: 0.05, y: 0.55, width: 0.75, height: 0.42)
}
let handler = VNImageRequestHandler(cgImage: cg, options: [:])
try handler.perform([req])
for obs in req.results ?? [] {
    if let c = obs.topCandidates(1).first { print(c.string) }
}
