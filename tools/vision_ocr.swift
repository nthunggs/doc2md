import AppKit
import Foundation
import PDFKit
import Vision

final class LockedResults: @unchecked Sendable {
    private let lock = NSLock()
    private var storage: [String?]

    init(count: Int) {
        storage = Array(repeating: nil, count: count)
    }

    func set(_ value: String, at index: Int) {
        lock.lock()
        defer { lock.unlock() }
        storage[index] = value
    }

    func values() -> [String?] {
        lock.lock()
        defer { lock.unlock() }
        return storage
    }
}

func recognizePage(pdfURL: URL, pageIndex: Int) -> String {
    return autoreleasepool {
        guard
            let document = PDFDocument(url: pdfURL),
            let page = document.page(at: pageIndex)
        else {
            return "*(Khong doc duoc trang)*"
        }

        let bounds = page.bounds(for: .mediaBox)
        let scale = 2.0
        let targetSize = NSSize(width: bounds.width * scale, height: bounds.height * scale)
        let image = page.thumbnail(of: targetSize, for: .mediaBox)
        var imageRect = NSRect(origin: .zero, size: image.size)
        guard let cgImage = image.cgImage(forProposedRect: &imageRect, context: nil, hints: nil) else {
            return "*(Khong render duoc trang)*"
        }

        let request = VNRecognizeTextRequest()
        request.recognitionLevel = .accurate
        request.usesLanguageCorrection = true
        request.automaticallyDetectsLanguage = false
        let supported = (try? request.supportedRecognitionLanguages()) ?? []
        let preferred = ["vi-VN", "en-US"].filter { supported.contains($0) }
        if !preferred.isEmpty {
            request.recognitionLanguages = preferred
        }
        let handler = VNImageRequestHandler(cgImage: cgImage, options: [:])
        do {
            try handler.perform([request])
        } catch {
            return "*(Loi OCR: \(error.localizedDescription))*"
        }

        let observations = request.results ?? []
        let lines = observations.compactMap { $0.topCandidates(1).first?.string }
        return lines.isEmpty ? "*(Trang trang hoac khong tim thay chu)*" : lines.joined(separator: "\n\n")
    }
}

guard CommandLine.arguments.count == 3 else {
    FileHandle.standardError.write(Data("Usage: vision_ocr INPUT.pdf OUTPUT.md\n".utf8))
    exit(2)
}

let inputURL = URL(fileURLWithPath: CommandLine.arguments[1])
let outputURL = URL(fileURLWithPath: CommandLine.arguments[2])
guard let document = PDFDocument(url: inputURL) else {
    FileHandle.standardError.write(Data("Unable to open PDF\n".utf8))
    exit(1)
}

let pageCount = document.pageCount
let results = LockedResults(count: pageCount)
let queue = OperationQueue()
queue.maxConcurrentOperationCount = min(4, max(1, ProcessInfo.processInfo.activeProcessorCount / 2))

for pageIndex in 0..<pageCount {
    queue.addOperation {
        let text = recognizePage(pdfURL: inputURL, pageIndex: pageIndex)
        results.set("<!-- Page \(pageIndex + 1) -->\n\n\(text)", at: pageIndex)
    }
}
queue.waitUntilAllOperationsAreFinished()

let recognizedPages = results.values()
let successfulPages = recognizedPages.compactMap { $0 }.filter {
    !$0.contains("*(Loi OCR:") && !$0.contains("*(Khong render duoc trang)*")
}
if successfulPages.isEmpty && pageCount > 0 {
    FileHandle.standardError.write(Data("Apple Vision did not recognize any page\n".utf8))
    exit(1)
}

let markdown = recognizedPages.enumerated().map { index, value in
    value ?? "<!-- Page \(index + 1) -->\n\n*(Loi OCR khong xac dinh)*"
}.joined(separator: "\n\n---\n\n")

do {
    try markdown.write(to: outputURL, atomically: true, encoding: .utf8)
} catch {
    FileHandle.standardError.write(Data("Unable to write output: \(error.localizedDescription)\n".utf8))
    exit(1)
}
