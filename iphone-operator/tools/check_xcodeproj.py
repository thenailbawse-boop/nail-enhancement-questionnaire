#!/usr/bin/env python3
"""Sanity-checks CreatorReset.xcodeproj without Xcode.

Parses project.pbxproj (old-style plist), then checks: every object ID that is referenced
exists; every file reference resolves to a real file on disk; every target has the build
phases it needs; Info.plist files and the extension manifest are valid.
This is NOT a substitute for compiling in Xcode — it catches structural mistakes early.
"""
import json
import os
import plistlib
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PBX = os.path.join(ROOT, "CreatorReset.xcodeproj", "project.pbxproj")


class Parser:
    def __init__(self, text):
        self.s = text
        self.i = 0

    def ws(self):
        while self.i < len(self.s):
            if self.s[self.i].isspace():
                self.i += 1
            elif self.s.startswith("//", self.i):
                self.i = self.s.index("\n", self.i) + 1
            elif self.s.startswith("/*", self.i):
                self.i = self.s.index("*/", self.i) + 2
            else:
                break

    def value(self):
        self.ws()
        c = self.s[self.i]
        if c == "{":
            self.i += 1
            d = {}
            while True:
                self.ws()
                if self.s[self.i] == "}":
                    self.i += 1
                    return d
                k = self.value()
                self.ws()
                assert self.s[self.i] == "=", "expected = at %d" % self.i
                self.i += 1
                d[k] = self.value()
                self.ws()
                assert self.s[self.i] == ";", "expected ; at %d near %r" % (self.i, self.s[self.i - 40:self.i + 10])
                self.i += 1
        if c == "(":
            self.i += 1
            a = []
            while True:
                self.ws()
                if self.s[self.i] == ")":
                    self.i += 1
                    return a
                a.append(self.value())
                self.ws()
                if self.s[self.i] == ",":
                    self.i += 1
        if c == '"':
            self.i += 1
            out = []
            while self.s[self.i] != '"':
                if self.s[self.i] == "\\":
                    self.i += 1
                out.append(self.s[self.i])
                self.i += 1
            self.i += 1
            return "".join(out)
        m = re.compile(r"[A-Za-z0-9_$./:\-+<>]+").match(self.s, self.i)
        assert m, "unexpected character %r at %d" % (c, self.i)
        self.i = m.end()
        return m.group(0)


def main():
    errors = []
    root = Parser(open(PBX, encoding="utf-8").read()).value()
    objects = root["objects"]
    ids = set(objects)

    def walk(v):
        if isinstance(v, dict):
            for x in v.values():
                yield from walk(x)
        elif isinstance(v, list):
            for x in v:
                yield from walk(x)
        elif isinstance(v, str) and re.fullmatch(r"[0-9A-F]{24}", v):
            yield v

    for oid, obj in objects.items():
        if "isa" not in obj:
            errors.append("object %s has no isa" % oid)
        for ref in walk({k: v for k, v in obj.items() if k != "isa"}):
            if ref not in ids:
                errors.append("%s (%s) points at missing object %s" % (oid, obj.get("isa"), ref))

    # Resolve file paths through the group tree.
    parent = {}
    for oid, obj in objects.items():
        if obj.get("isa") == "PBXGroup":
            for child in obj.get("children", []):
                parent[child] = oid

    def full_path(oid):
        parts = []
        while oid in objects:
            p = objects[oid].get("path")
            if p:
                parts.append(p)
            oid = parent.get(oid)
        return os.path.join(ROOT, *reversed(parts))

    files = 0
    for oid, obj in objects.items():
        if obj.get("isa") == "PBXFileReference" and obj.get("sourceTree") == "<group>":
            files += 1
            if not os.path.exists(full_path(oid)):
                errors.append("file reference missing on disk: %s" % full_path(oid))

    targets = {o["name"]: o for o in objects.values() if o.get("isa") == "PBXNativeTarget"}
    for name in ("CreatorReset", "CreatorResetSafari"):
        if name not in targets:
            errors.append("missing target %s" % name)
            continue
        isas = [objects[p]["isa"] for p in targets[name]["buildPhases"]]
        for need in ("PBXSourcesBuildPhase", "PBXResourcesBuildPhase"):
            if need not in isas:
                errors.append("%s lacks %s" % (name, need))
        srcs = [p for p in targets[name]["buildPhases"] if objects[p]["isa"] == "PBXSourcesBuildPhase"][0]
        print("%-20s %2d source files" % (name, len(objects[srcs]["files"])))
    embed = [o for o in objects.values() if o.get("isa") == "PBXCopyFilesBuildPhase"]
    if not embed or embed[0].get("dstSubfolderSpec") != "13":
        errors.append("Safari extension is not embedded into the app (PlugIns)")

    for plist in ("App/Info.plist", "SafariExtension/Info.plist"):
        with open(os.path.join(ROOT, plist), "rb") as f:
            plistlib.load(f)
    manifest = json.load(open(os.path.join(ROOT, "SafariExtension/Resources/manifest.json")))
    for key in ("background", "action", "icons"):
        for path in (lambda v: v.values() if isinstance(v, dict) else [])(manifest[key].get("default_icon", {}) if key == "action" else manifest[key] if key == "icons" else {}):
            if not os.path.exists(os.path.join(ROOT, "SafariExtension/Resources", path)):
                errors.append("manifest icon missing: %s" % path)
    for script in manifest["background"]["scripts"] + [manifest["action"]["default_popup"]]:
        if not os.path.exists(os.path.join(ROOT, "SafariExtension/Resources", script)):
            errors.append("manifest file missing: %s" % script)

    print("%d objects, %d file references checked" % (len(objects), files))
    if errors:
        print("\n".join("ERROR: " + e for e in errors))
        sys.exit(1)
    print("project structure OK")


main()
