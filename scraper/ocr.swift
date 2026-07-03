import Vision
import AppKit
import Foundation

// Usage: ocr <image-path>
// Prints one line per recognized text region: "<text>\t<x>\t<y>\t<w>\t<h>"
// Box coordinates are normalized (0-1), origin bottom-left, per Vision's convention.

let args = CommandLine.arguments
guard args.count > 1, let img = NSImage(contentsOfFile: args[1]),
      let cgImage = img.cgImage(forProposedRect: nil, context: nil, hints: nil) else {
    FileHandle.standardError.write("ERROR: could not load image at \(args.count > 1 ? args[1] : "?")\n".data(using: .utf8)!)
    exit(1)
}

let request = VNRecognizeTextRequest { (request, error) in
    guard let observations = request.results as? [VNRecognizedTextObservation] else { return }
    for obs in observations {
        if let candidate = obs.topCandidates(1).first {
            let box = obs.boundingBox
            print("\(candidate.string)\t\(box.origin.x)\t\(box.origin.y)\t\(box.size.width)\t\(box.size.height)")
        }
    }
}
request.recognitionLevel = .accurate
request.usesLanguageCorrection = false

let handler = VNImageRequestHandler(cgImage: cgImage, options: [:])
try? handler.perform([request])
