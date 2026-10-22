import CoreGraphics
import Foundation
import ImageIO
import UniformTypeIdentifiers

final class SVG: NSObject, XMLParserDelegate {
  var rect = [String: String](), glyph = [String: String]()
  func parser(
    _ parser: XMLParser, didStartElement name: String, namespaceURI: String?,
    qualifiedName: String?, attributes: [String: String]
  ) {
    if name == "rect" { rect = attributes }
    if name == "path" { glyph = attributes }
  }
}
let source = URL(fileURLWithPath: CommandLine.arguments[1])
let folder = URL(fileURLWithPath: CommandLine.arguments[2])
try FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true)
let delegate = SVG()
let parser = XMLParser(contentsOf: source)!
parser.delegate = delegate
precondition(parser.parse())
precondition(delegate.glyph["transform"] == "translate(0 512) scale(1 -1)")
precondition(delegate.glyph["fill"] == "#FFFFFF")
precondition(delegate.rect["width"] == "512" && delegate.rect["height"] == "512")
let data = delegate.glyph["d"]!
let regex = try NSRegularExpression(
  pattern: "[MLQCZ]|[-+]?(?:[0-9]*\\.)?[0-9]+(?:[eE][-+]?[0-9]+)?")
let tokens = regex.matches(in: data, range: NSRange(data.startIndex..., in: data)).map {
  String(data[Range($0.range, in: data)!])
}
let path = CGMutablePath()
var i = 0
func number() -> CGFloat {
  let n = Double(tokens[i])!
  i += 1
  return CGFloat(n)
}
func point() -> CGPoint {
  let x = number()
  let y = number()
  return CGPoint(x: x, y: y)
}
while i < tokens.count {
  let command = tokens[i]
  i += 1
  switch command {
  case "M": path.move(to: point())
  case "L": path.addLine(to: point())
  case "Q":
    let c = point()
    path.addQuadCurve(to: point(), control: c)
  case "C":
    let c1 = point()
    let c2 = point()
    path.addCurve(to: point(), control1: c1, control2: c2)
  case "Z": path.closeSubpath()
  default: fatalError("Unsupported SVG command")
  }
}
let hex = delegate.rect["fill"]!.dropFirst()
let rgb = UInt32(hex, radix: 16)!
let radius = CGFloat(Double(delegate.rect["rx"]!)!)
let space = CGColorSpace(name: CGColorSpace.sRGB)!
let slots = [
  ("icon_16x16", 16), ("icon_16x16@2x", 32), ("icon_32x32", 32), ("icon_32x32@2x", 64),
  ("icon_128x128", 128), ("icon_128x128@2x", 256), ("icon_256x256", 256),
  ("icon_256x256@2x", 512),
  ("icon_512x512", 512), ("icon_512x512@2x", 1024),
]
var smallIcons = [String: Data]()
for (name, size) in slots {
  let ctx = CGContext(
    data: nil, width: size, height: size, bitsPerComponent: 8, bytesPerRow: size * 4,
    space: space,
    bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue)!
  ctx.scaleBy(x: CGFloat(size) / 512, y: CGFloat(size) / 512)
  ctx.setFillColor(
    CGColor(
      colorSpace: space,
      components: [
        CGFloat((rgb >> 16) & 255) / 255, CGFloat((rgb >> 8) & 255) / 255,
        CGFloat(rgb & 255) / 255,
        1,
      ])!)
  ctx.addPath(
    CGPath(
      roundedRect: CGRect(x: 0, y: 0, width: 512, height: 512), cornerWidth: radius,
      cornerHeight: radius, transform: nil))
  ctx.fillPath()
  ctx.setFillColor(CGColor(gray: 1, alpha: 1))
  ctx.addPath(path)
  ctx.fillPath()
  if name == "icon_16x16" || name == "icon_32x32" {
    // Small ARGB icons use premultiplied channels, just like this context.
    let pixels = ctx.data!.assumingMemoryBound(to: UInt8.self)
    var packed = Data("ARGB".utf8)
    for channel in [3, 0, 1, 2] {
      for start in stride(from: 0, to: size * size, by: 128) {
        let count = min(128, size * size - start)
        packed.append(UInt8(count - 1))
        for pixel in start..<(start + count) {
          packed.append(pixels[pixel * 4 + channel])
        }
      }
    }
    // The macOS decoder needs a trailing byte after the final literal run.
    packed.append(0)
    smallIcons[name] = packed
  }
  let dest = CGImageDestinationCreateWithURL(
    folder.appendingPathComponent(name + ".png") as CFURL, UTType.png.identifier as CFString, 1,
    nil
  )!
  CGImageDestinationAddImage(dest, ctx.makeImage()!, nil)
  precondition(CGImageDestinationFinalize(dest))
}
print("Rendered 10 PNG representations directly from SVG; no font dependencies.")

// Pack small icons as premultiplied ARGB; preserve PNGs for the other slots.
if CommandLine.arguments.count > 3 {
  let types = ["ic04", "ic11", "ic05", "ic12", "ic07", "ic13", "ic08", "ic14", "ic09", "ic10"]
  func chunk(_ type: String, _ payload: Data) -> Data {
    var result = Data(type.utf8)
    var length = UInt32(payload.count + 8).bigEndian
    withUnsafeBytes(of: &length) { result.append(contentsOf: $0) }
    result.append(payload)
    return result
  }
  var contents = Data()
  for ((name, _), type) in zip(slots, types) {
    let png = try Data(contentsOf: folder.appendingPathComponent(name + ".png"))
    contents.append(chunk(type, smallIcons[name] ?? png))
  }
  try chunk("icns", contents).write(to: URL(fileURLWithPath: CommandLine.arguments[3]))
  print("Packed ICNS with premultiplied small icons and PNG representations.")
}
