// Prints the text lines macOS can read in an image, with their boxes (0..1, top-left origin), as JSON.
import Foundation
import Vision
import AppKit

let url = URL(fileURLWithPath: CommandLine.arguments[1])
guard let img = NSImage(contentsOf: url), let cg = img.cgImage(forProposedRect: nil, context: nil, hints: nil) else {
    print("[]"); exit(0)
}
let req = VNRecognizeTextRequest()
req.recognitionLevel = .accurate
req.usesLanguageCorrection = false
try? VNImageRequestHandler(cgImage: cg, options: [:]).perform([req])
var out: [[String: Any]] = []
for o in req.results ?? [] {
    guard let t = o.topCandidates(1).first else { continue }
    let b = o.boundingBox
    out.append(["text": t.string, "conf": t.confidence, "x": b.minX, "y": 1 - b.maxY, "w": b.width, "h": b.height])
}
print(String(data: try! JSONSerialization.data(withJSONObject: out), encoding: .utf8)!)
