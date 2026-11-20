// swift-tools-version:5.9
// Unit tests for the shared operator logic. The same source files are compiled
// straight into the iPhone app and the Safari extension by CreatorReset.xcodeproj.
// Run on a Mac or Linux:  cd Core && swift test
import PackageDescription

let package = Package(
    name: "OperatorCore",
    platforms: [.iOS(.v17), .macOS(.v13)],
    products: [.library(name: "OperatorCore", targets: ["OperatorCore"])],
    targets: [
        .target(name: "OperatorCore", path: "Sources/OperatorCore"),
        .testTarget(name: "OperatorCoreTests", dependencies: ["OperatorCore"], path: "Tests/OperatorCoreTests")
    ]
)
