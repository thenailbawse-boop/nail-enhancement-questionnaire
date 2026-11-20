#!/usr/bin/env python3
"""Writes CreatorReset.xcodeproj (project.pbxproj + shared scheme).

Run from anywhere:  python3 iphone-operator/tools/generate_xcodeproj.py
Re-run after adding or removing source files. IDs are stable (derived from names).
"""
import glob
import hashlib
import re
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJ = os.path.join(ROOT, "CreatorReset.xcodeproj")
BUNDLE_PREFIX = "com.thenailbawse"
VERSION = "0.2.0"
BUILD = "1"
DEPLOYMENT = "17.0"

APP = "CreatorReset"
EXT = "CreatorResetSafari"


def oid(*parts):
    return hashlib.md5("/".join(parts).encode()).hexdigest()[:24].upper()


def q(value):
    """Quote a pbxproj string when needed."""
    s = str(value)
    if s and all(c.isalnum() or c in "._/$" for c in s) and not s.startswith("$("):
        return s
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def rel(paths):
    return sorted(os.path.relpath(p, ROOT) for p in paths)


app_sources = rel(glob.glob(os.path.join(ROOT, "App/**/*.swift"), recursive=True))
shared_sources = rel(glob.glob(os.path.join(ROOT, "Shared/*.swift")))
core_sources = rel(glob.glob(os.path.join(ROOT, "Core/Sources/OperatorCore/*.swift")))
ext_sources = ["SafariExtension/SafariWebExtensionHandler.swift"]

app_target_sources = app_sources + shared_sources + core_sources
ext_target_sources = ext_sources + ["Shared/OnDeviceAIStatus.swift", "Core/Sources/OperatorCore/WebPlan.swift"]

# Every file reference shown in the Xcode navigator.
file_refs = {}  # path -> (id, fileType)


def ftype(path):
    if path.endswith(".swift"):
        return "sourcecode.swift"
    if path.endswith(".plist"):
        return "text.plist.xml"
    if path.endswith(".xcassets"):
        return "folder.assetcatalog"
    if path.endswith(".md"):
        return "net.daringfireball.markdown"
    return "folder"


for p in sorted(set(app_target_sources + ext_target_sources + [
        "App/Info.plist", "App/Assets.xcassets", "SafariExtension/Info.plist", "SafariExtension/Resources",
        "START_HERE.md"])):
    if os.path.exists(os.path.join(ROOT, p)):
        file_refs[p] = (oid("ref", p), ftype(p))

# Group tree from directories.
groups = {"": {"id": oid("group", "<main>"), "children": [], "name": None}}


def ensure_group(d):
    if d in groups:
        return groups[d]
    parent = ensure_group(os.path.dirname(d))
    g = {"id": oid("group", d), "children": [], "name": os.path.basename(d)}
    groups[d] = g
    parent["children"].append(("group", d))
    return g


for p in file_refs:
    ensure_group(os.path.dirname(p))["children"].append(("file", p))

products_group = oid("group", "<products>")
app_product = oid("product", APP)
ext_product = oid("product", EXT)

objs = []  # (isa, id, body-lines)
sections = {}


def add(isa, ident, fields, comment=""):
    sections.setdefault(isa, []).append((ident, comment, fields))


# Build files
def build_file(target, path):
    ident = oid("build", target, path)
    add("PBXBuildFile", ident, [("fileRef", file_refs[path][0])], os.path.basename(path))
    return ident


app_src_bf = [build_file(APP, p) for p in app_target_sources]
ext_src_bf = [build_file(EXT, p) for p in ext_target_sources]
app_res_bf = [build_file(APP, "App/Assets.xcassets")]
ext_res_bf = [build_file(EXT, "SafariExtension/Resources")]
embed_bf = oid("build", APP, "embed", EXT)
add("PBXBuildFile", embed_bf, [("fileRef", ext_product), ("settings", "{ATTRIBUTES = (RemoveHeadersOnCopy, ); }")], EXT + ".appex")

# File references
for p, (ident, t) in file_refs.items():
    add("PBXFileReference", ident, [("lastKnownFileType", t), ("path", q(os.path.basename(p))), ("sourceTree", '"<group>"')],
        os.path.basename(p))
add("PBXFileReference", app_product, [("explicitFileType", "wrapper.application"), ("includeInIndex", "0"),
                                      ("path", APP + ".app"), ("sourceTree", "BUILT_PRODUCTS_DIR")], APP + ".app")
add("PBXFileReference", ext_product, [("explicitFileType", '"wrapper.app-extension"'), ("includeInIndex", "0"),
                                      ("path", EXT + ".appex"), ("sourceTree", "BUILT_PRODUCTS_DIR")], EXT + ".appex")

# Groups
for d, g in groups.items():
    kids = []
    for kind, ref in sorted(g["children"], key=lambda c: (c[0] != "group", c[1])):
        kids.append(groups[ref]["id"] if kind == "group" else file_refs[ref][0])
    if d == "":
        kids.append(products_group)
        add("PBXGroup", g["id"], [("children", kids), ("sourceTree", '"<group>"')])
    else:
        add("PBXGroup", g["id"], [("children", kids), ("path", q(g["name"])), ("sourceTree", '"<group>"')], g["name"])
add("PBXGroup", products_group, [("children", [app_product, ext_product]), ("name", "Products"), ("sourceTree", '"<group>"')], "Products")

# Build phases
phase = {}
for t, srcs, res in ((APP, app_src_bf, app_res_bf), (EXT, ext_src_bf, ext_res_bf)):
    phase[t] = {"src": oid("phase", t, "src"), "res": oid("phase", t, "res"), "fw": oid("phase", t, "fw")}
    add("PBXSourcesBuildPhase", phase[t]["src"], [("buildActionMask", "2147483647"), ("files", srcs),
                                                  ("runOnlyForDeploymentPostprocessing", "0")], "Sources")
    add("PBXResourcesBuildPhase", phase[t]["res"], [("buildActionMask", "2147483647"), ("files", res),
                                                    ("runOnlyForDeploymentPostprocessing", "0")], "Resources")
    add("PBXFrameworksBuildPhase", phase[t]["fw"], [("buildActionMask", "2147483647"), ("files", []),
                                                    ("runOnlyForDeploymentPostprocessing", "0")], "Frameworks")
embed_phase = oid("phase", APP, "embed")
add("PBXCopyFilesBuildPhase", embed_phase, [("buildActionMask", "2147483647"), ("dstPath", '""'), ("dstSubfolderSpec", "13"),
                                            ("files", [embed_bf]), ("name", '"Embed Foundation Extensions"'),
                                            ("runOnlyForDeploymentPostprocessing", "0")], "Embed Foundation Extensions")

# Targets + dependency
app_target = oid("target", APP)
ext_target = oid("target", EXT)
project_id = oid("project")
proxy = oid("proxy", EXT)
dep = oid("dependency", EXT)
add("PBXContainerItemProxy", proxy, [("containerPortal", project_id), ("proxyType", "1"),
                                     ("remoteGlobalIDString", ext_target), ("remoteInfo", EXT)], "PBXContainerItemProxy")
add("PBXTargetDependency", dep, [("target", ext_target), ("targetProxy", proxy)], "PBXTargetDependency")


def config_list(owner, settings_debug, settings_release, comment):
    debug = oid("config", owner, "Debug")
    release = oid("config", owner, "Release")
    add("XCBuildConfiguration", debug, [("buildSettings", settings_debug), ("name", "Debug")], "Debug")
    add("XCBuildConfiguration", release, [("buildSettings", settings_release), ("name", "Release")], "Release")
    lst = oid("configlist", owner)
    add("XCConfigurationList", lst, [("buildConfigurations", [debug, release]), ("defaultConfigurationIsVisible", "0"),
                                     ("defaultConfigurationName", "Release")], comment)
    return lst


common = {
    "ALWAYS_SEARCH_USER_PATHS": "NO",
    "ASSETCATALOG_COMPILER_GENERATE_SWIFT_ASSET_SYMBOL_EXTENSIONS": "YES",
    "CLANG_ANALYZER_NONNULL": "YES",
    "CLANG_ENABLE_MODULES": "YES",
    "CLANG_ENABLE_OBJC_ARC": "YES",
    "CLANG_ENABLE_OBJC_WEAK": "YES",
    "CLANG_WARN_DOCUMENTATION_COMMENTS": "YES",
    "COPY_PHASE_STRIP": "NO",
    "CR_BUNDLE_PREFIX": BUNDLE_PREFIX,
    "ENABLE_STRICT_OBJC_MSGSEND": "YES",
    "ENABLE_USER_SCRIPT_SANDBOXING": "YES",
    "GCC_C_LANGUAGE_STANDARD": "gnu17",
    "GCC_NO_COMMON_BLOCKS": "YES",
    "IPHONEOS_DEPLOYMENT_TARGET": DEPLOYMENT,
    "LOCALIZATION_PREFERS_STRING_CATALOGS": "YES",
    "MTL_FAST_MATH": "YES",
    "SDKROOT": "iphoneos",
    "SWIFT_STRICT_CONCURRENCY": "minimal",
    "SWIFT_VERSION": "5.0",
}
project_debug = dict(common, **{
    "DEBUG_INFORMATION_FORMAT": "dwarf", "ENABLE_TESTABILITY": "YES", "GCC_OPTIMIZATION_LEVEL": "0",
    "GCC_PREPROCESSOR_DEFINITIONS": ["DEBUG=1", "$(inherited)"], "MTL_ENABLE_DEBUG_INFO": "INCLUDE_SOURCE",
    "ONLY_ACTIVE_ARCH": "YES", "SWIFT_ACTIVE_COMPILATION_CONDITIONS": "DEBUG $(inherited)", "SWIFT_OPTIMIZATION_LEVEL": "-Onone"})
project_release = dict(common, **{
    "DEBUG_INFORMATION_FORMAT": "dwarf-with-dsym", "ENABLE_NS_ASSERTIONS": "NO", "MTL_ENABLE_DEBUG_INFO": "NO",
    "SWIFT_COMPILATION_MODE": "wholemodule", "VALIDATE_PRODUCT": "YES"})

app_settings = {
    "ASSETCATALOG_COMPILER_APPICON_NAME": "AppIcon",
    "ASSETCATALOG_COMPILER_GLOBAL_ACCENT_COLOR_NAME": "AccentColor",
    "CODE_SIGN_STYLE": "Automatic",
    "CURRENT_PROJECT_VERSION": BUILD,
    "DEVELOPMENT_TEAM": "",
    "ENABLE_PREVIEWS": "YES",
    "GENERATE_INFOPLIST_FILE": "YES",
    "INFOPLIST_FILE": "App/Info.plist",
    "INFOPLIST_KEY_CFBundleDisplayName": "Creator Reset",
    "INFOPLIST_KEY_LSApplicationCategoryType": "public.app-category.photography",
    "INFOPLIST_KEY_NSPhotoLibraryUsageDescription": "Creator Reset sorts only the photos and videos you allow into review albums on this iPhone. It never deletes, edits or uploads them.",
    "INFOPLIST_KEY_NSPhotoLibraryAddUsageDescription": "Creator Reset can add clearly labeled FAKE test photos so you can practice safely.",
    "INFOPLIST_KEY_UIApplicationSceneManifest_Generation": "YES",
    "INFOPLIST_KEY_UIApplicationSupportsIndirectInputEvents": "YES",
    "INFOPLIST_KEY_UILaunchScreen_Generation": "YES",
    "INFOPLIST_KEY_UISupportedInterfaceOrientations_iPhone": "UIInterfaceOrientationPortrait",
    "LD_RUNPATH_SEARCH_PATHS": ["$(inherited)", "@executable_path/Frameworks"],
    "MARKETING_VERSION": VERSION,
    "PRODUCT_BUNDLE_IDENTIFIER": "$(CR_BUNDLE_PREFIX).creatorreset",
    "PRODUCT_NAME": "$(TARGET_NAME)",
    "SWIFT_EMIT_LOC_STRINGS": "YES",
    "TARGETED_DEVICE_FAMILY": "1",
}
ext_settings = {
    "CODE_SIGN_STYLE": "Automatic",
    "CURRENT_PROJECT_VERSION": BUILD,
    "DEVELOPMENT_TEAM": "",
    "GENERATE_INFOPLIST_FILE": "YES",
    "INFOPLIST_FILE": "SafariExtension/Info.plist",
    "INFOPLIST_KEY_CFBundleDisplayName": "Creator Reset",
    "INFOPLIST_KEY_NSHumanReadableCopyright": "",
    "LD_RUNPATH_SEARCH_PATHS": ["$(inherited)", "@executable_path/Frameworks", "@executable_path/../../Frameworks"],
    "MARKETING_VERSION": VERSION,
    "PRODUCT_BUNDLE_IDENTIFIER": "$(CR_BUNDLE_PREFIX).creatorreset.safari",
    "PRODUCT_NAME": "$(TARGET_NAME)",
    "SKIP_INSTALL": "YES",
    "SWIFT_EMIT_LOC_STRINGS": "YES",
    "TARGETED_DEVICE_FAMILY": "1",
}

project_cl = config_list("project", project_debug, project_release, 'Build configuration list for PBXProject "%s"' % APP)
app_cl = config_list(APP, app_settings, app_settings, 'Build configuration list for PBXNativeTarget "%s"' % APP)
ext_cl = config_list(EXT, ext_settings, ext_settings, 'Build configuration list for PBXNativeTarget "%s"' % EXT)

add("PBXNativeTarget", app_target, [
    ("buildConfigurationList", app_cl),
    ("buildPhases", [phase[APP]["src"], phase[APP]["fw"], phase[APP]["res"], embed_phase]),
    ("buildRules", []), ("dependencies", [dep]), ("name", APP), ("productName", APP),
    ("productReference", app_product), ("productType", '"com.apple.product-type.application"')], APP)
add("PBXNativeTarget", ext_target, [
    ("buildConfigurationList", ext_cl),
    ("buildPhases", [phase[EXT]["src"], phase[EXT]["fw"], phase[EXT]["res"]]),
    ("buildRules", []), ("dependencies", []), ("name", EXT), ("productName", EXT),
    ("productReference", ext_product), ("productType", '"com.apple.product-type.app-extension"')], EXT)

add("PBXProject", project_id, [
    ("attributes", "{BuildIndependentTargetsInParallel = 1; LastSwiftUpdateCheck = 2600; LastUpgradeCheck = 2600; "
                   "TargetAttributes = {%s = {CreatedOnToolsVersion = 26.0; }; %s = {CreatedOnToolsVersion = 26.0; }; }; }"
     % (app_target, ext_target)),
    ("buildConfigurationList", project_cl), ("compatibilityVersion", '"Xcode 14.0"'), ("developmentRegion", "en"),
    ("hasScannedForEncodings", "0"), ("knownRegions", ["en", "Base"]), ("mainGroup", groups[""]["id"]),
    ("productRefGroup", products_group), ("projectDirPath", '""'), ("projectRoot", '""'),
    ("targets", [app_target, ext_target])], "Project object")


def fmt_setting(v, indent):
    if isinstance(v, list):
        pad = "\t" * indent
        return "(\n" + "".join("%s\t%s,\n" % (pad, q(x)) for x in v) + pad + ")"
    return q(v) if v != "" else '""'


out = ["// !$*UTF8*$!", "{", "\tarchiveVersion = 1;", "\tclasses = {", "\t};", "\tobjectVersion = 56;", "\tobjects = {", ""]
for isa in sorted(sections):
    out.append("/* Begin %s section */" % isa)
    for ident, comment, fields in sorted(sections[isa]):
        out.append("\t\t%s%s = {" % (ident, " /* %s */" % comment if comment else ""))
        out.append("\t\t\tisa = %s;" % isa)
        for key, value in fields:
            if key == "buildSettings":
                out.append("\t\t\tbuildSettings = {")
                for k in sorted(value):
                    out.append("\t\t\t\t%s = %s;" % (k, fmt_setting(value[k], 4)))
                out.append("\t\t\t};")
            elif isinstance(value, list):
                out.append("\t\t\t%s = (" % key)
                for item in value:
                    out.append("\t\t\t\t%s," % (item if re.fullmatch(r"[0-9A-F]{24}", item) else q(item)))
                out.append("\t\t\t);")
            else:
                out.append("\t\t\t%s = %s;" % (key, value))
        out.append("\t\t};")
    out.append("/* End %s section */" % isa)
    out.append("")
out += ["\t};", "\trootObject = %s /* Project object */;" % project_id, "}", ""]

os.makedirs(os.path.join(PROJ, "xcshareddata", "xcschemes"), exist_ok=True)
with open(os.path.join(PROJ, "project.pbxproj"), "w") as f:
    f.write("\n".join(out))

ref = lambda tid, name, product: (
    '<BuildableReference BuildableIdentifier = "primary" BlueprintIdentifier = "%s" BuildableName = "%s" '
    'BlueprintName = "%s" ReferencedContainer = "container:CreatorReset.xcodeproj"> </BuildableReference>' % (tid, product, name))
scheme = """<?xml version="1.0" encoding="UTF-8"?>
<Scheme LastUpgradeVersion = "2600" version = "1.7">
   <BuildAction parallelizeBuildables = "YES" buildImplicitDependencies = "YES">
      <BuildActionEntries>
         <BuildActionEntry buildForTesting = "YES" buildForRunning = "YES" buildForProfiling = "YES" buildForArchiving = "YES" buildForAnalyzing = "YES">
            %(app)s
         </BuildActionEntry>
      </BuildActionEntries>
   </BuildAction>
   <TestAction buildConfiguration = "Debug" selectedDebuggerIdentifier = "Xcode.DebuggerFoundation.Debugger.LLDB" selectedLauncherIdentifier = "Xcode.DebuggerFoundation.Launcher.LLDB" shouldUseLaunchSchemeArgsEnv = "YES">
   </TestAction>
   <LaunchAction buildConfiguration = "Debug" selectedDebuggerIdentifier = "Xcode.DebuggerFoundation.Debugger.LLDB" selectedLauncherIdentifier = "Xcode.DebuggerFoundation.Launcher.LLDB" launchStyle = "0" useCustomWorkingDirectory = "NO" ignoresPersistentStateOnLaunch = "NO" debugDocumentVersioning = "YES" debugServiceExtension = "internal" allowLocationSimulation = "YES">
      <BuildableProductRunnable runnableDebuggingMode = "0">
         %(app)s
      </BuildableProductRunnable>
   </LaunchAction>
   <ProfileAction buildConfiguration = "Release" shouldUseLaunchSchemeArgsEnv = "YES" savedToolIdentifier = "" useCustomWorkingDirectory = "NO" debugDocumentVersioning = "YES">
      <BuildableProductRunnable runnableDebuggingMode = "0">
         %(app)s
      </BuildableProductRunnable>
   </ProfileAction>
   <AnalyzeAction buildConfiguration = "Debug">
   </AnalyzeAction>
   <ArchiveAction buildConfiguration = "Release" revealArchiveInOrganizer = "YES">
   </ArchiveAction>
</Scheme>
""" % {"app": ref(app_target, APP, APP + ".app")}
with open(os.path.join(PROJ, "xcshareddata", "xcschemes", APP + ".xcscheme"), "w") as f:
    f.write(scheme)

print("Wrote %s with %d app sources and %d extension sources" % (PROJ, len(app_target_sources), len(ext_target_sources)))
