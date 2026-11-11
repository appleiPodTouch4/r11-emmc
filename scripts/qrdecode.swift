import Foundation
import Vision
import AppKit
let path = CommandLine.arguments[1]
guard let img = NSImage(contentsOfFile: path),
      let data = img.tiffRepresentation,
      let rep = NSBitmapImageRep(data: data),
      let cg = rep.cgImage else { exit(1) }
let req = VNDetectBarcodesRequest()
req.symbologies = [.qr]
let h = VNImageRequestHandler(cgImage: cg, options: [:])
try h.perform([req])
for o in req.results ?? [] {
    if let p = o.payloadStringValue { print(p) }
}
