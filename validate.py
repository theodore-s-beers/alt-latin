import argparse
import hashlib
import json
import plistlib
import re
import struct
import xml.etree.ElementTree as ET
from pathlib import Path

from build import DEFAULT_OUTPUT, ROOT, source_files


def require(condition, message):
    if not condition:
        raise ValueError(message)


def unique(elements, attribute, context):
    values = [element.get(attribute) for element in elements]
    require(
        None not in values and len(values) == len(set(values)),
        f"Missing or duplicate {attribute} in {context}",
    )


def parse_layout(data):
    # Expat is XML 1.0 only. Temporarily encode XML 1.1 control references in
    # unused PUA slots, then restore them in memory.
    text = data.decode("utf-8")
    require(
        not any(chr(0xE000 + i) in text for i in range(32)),
        "Layout contains reserved parser-placeholder characters",
    )

    def replace(match):
        value = int(match[1][1:], 16) if match[1].startswith("x") else int(match[1])
        require(value != 0, "NUL character reference is not valid")
        return chr(0xE000 + value) if value < 32 else match[0]

    text = re.sub(r"&#(x[0-9a-fA-F]+|[0-9]+);", replace, text)
    root = ET.fromstring(text)
    for element in root.iter():
        for key, value in list(element.attrib.items()):
            element.set(
                key,
                "".join(
                    chr(ord(c) - 0xE000) if 0xE000 <= ord(c) < 0xE020 else c
                    for c in value
                ),
            )
    return root


def check_layout(root):
    require(root.tag == "keyboard", "Expected keyboard root")
    require(
        root.get("group") == "126" and int(root.get("id")) < 0,
        "Unicode layout must have group 126 and a negative ID",
    )
    for tag in ("layouts", "actions", "terminators"):
        require(len(root.findall(tag)) == 1, f"Expected exactly one {tag} block")
    unique(root.findall("keyMapSet"), "id", "map sets")
    unique(root.findall("modifierMap"), "id", "modifier maps")
    unique(root.findall("./actions/action"), "id", "actions")
    actions = {a.get("id"): a for a in root.findall("./actions/action")}
    maps = {}
    for ms in root.findall("keyMapSet"):
        unique(ms.findall("keyMap"), "index", "key maps")
        for m in ms:
            unique(
                m.findall("key"),
                "code",
                "key map " + ms.get("id") + "/" + m.get("index"),
            )
            require(
                ("baseMapSet" in m.attrib) == ("baseIndex" in m.attrib),
                "Incomplete inheritance reference",
            )
            maps[ms.get("id"), m.get("index")] = m
            for key in m:
                require(
                    ("output" in key.attrib) != ("action" in key.attrib),
                    "Key needs exactly one output or action",
                )
                if key.get("action"):
                    require(
                        key.get("action") in actions,
                        "Missing action " + key.get("action"),
                    )

    def effective(key, visited=()):
        require(key in maps, "Missing map " + str(key))
        require(key not in visited, "Map inheritance cycle")
        m = maps[key]
        result = (
            effective((m.get("baseMapSet"), m.get("baseIndex")), visited + (key,))
            if m.get("baseMapSet")
            else {}
        )
        result.update({int(k.get("code")): k for k in m})
        return result

    for key in maps:
        require(
            set(range(51)) <= effective(key).keys(),
            "Missing main-key entry in " + str(key),
        )
    modifiers = {m.get("id"): m for m in root.findall("modifierMap")}
    ranges = []
    for layout in root.findall("./layouts/layout"):
        require(layout.get("modifiers") in modifiers, "Unknown modifier map")
        mm = modifiers[layout.get("modifiers")]
        for index in [mm.get("defaultIndex")] + [sel.get("mapIndex") for sel in mm]:
            require(
                (layout.get("mapSet"), index) in maps, "Selected map does not exist"
            )
        first, last = int(layout.get("first")), int(layout.get("last"))
        require(first <= last, "Invalid hardware range")
        require(
            all(max(first, a) > min(last, b) for a, b in ranges),
            "Overlapping hardware ranges",
        )
        ranges.append((first, last))
    states, used = set(), set()
    for action in actions.values():
        unique(action.findall("when"), "state", "action " + action.get("id"))
        require(
            len(action) > 0 and action[0].get("state") == "none",
            "Base action state must be first",
        )
        for when in action:
            require(
                "output" in when.attrib or "next" in when.attrib, "Empty action result"
            )
            used.add(when.get("state"))
            if when.get("next") and when.get("next") != "none":
                states.add(when.get("next"))
    terms = root.findall("./terminators/when")
    unique(terms, "state", "terminators")
    require(
        states == used - {"none"} == {w.get("state") for w in terms},
        "Dead-state coverage mismatch",
    )
    for term in terms:
        require(
            "output" in term.attrib and "next" not in term.attrib, "Invalid terminator"
        )
    return {
        "map_count": len(maps),
        "action_count": len(actions),
        "dead_state_count": len(states),
    }


def check_icon(data):
    require(
        data[:4] == b"icns" and struct.unpack(">I", data[4:8])[0] == len(data),
        "Invalid ICNS header",
    )
    offset, chunks = 8, []
    while offset < len(data):
        require(offset + 8 <= len(data), "Truncated ICNS chunk")
        tag, size = struct.unpack(">4sI", data[offset : offset + 8])
        require(size >= 8 and offset + size <= len(data), "Invalid ICNS chunk size")
        chunks.append(tag.decode("ascii"))
        offset += size
    require(len(chunks) > 1, "Expected multi-resolution icon")
    return chunks


def validate(bundle):
    expected = source_files()
    actual = {
        str(p.relative_to(bundle)): p.read_bytes()
        for p in bundle.rglob("*")
        if p.is_file()
    }
    require(
        actual.keys() == expected.keys(), "Bundle file inventory differs from sources"
    )
    for path in expected:
        require(actual[path] == expected[path], "Bundle differs from source: " + path)
    layout = parse_layout(actual["Contents/Resources/Alt-Latin.keylayout"])
    counts = check_layout(layout)
    info = plistlib.loads(actual["Contents/Info.plist"])
    version = plistlib.loads(actual["Contents/version.plist"])
    name = layout.get("name")
    require(
        name == "Alt-Latin" and info["CFBundleName"] == name, "Inconsistent layout name"
    )
    require(version["ProjectName"] == name, "Inconsistent project name")
    release = info["CFBundleShortVersionString"]
    require(re.fullmatch(r"\d+\.\d+", release), "Expected major.minor release version")
    require(
        info["CFBundleVersion"]
        == version["BuildVersion"]
        == version["SourceVersion"]
        == release,
        "Version fields disagree",
    )
    require(
        info["CFBundleIdentifier"] == "com.theobeers.keyboardlayout.alt-latin",
        "Unexpected bundle identifier",
    )
    require(
        info["KLInfo_" + name]
        == {
            "TISInputSourceID": "com.theobeers.keyboardlayout.alt-latin.main",
            "TISIntendedLanguage": "en",
        },
        "Unexpected input-source metadata",
    )
    strings = actual["Contents/Resources/en.lproj/InfoPlist.strings"].decode("utf-16")
    require(
        strings.strip() == '"Alt-Latin" = "Alt-Latin";', "Unexpected localized name"
    )
    chunks = check_icon(actual["Contents/Resources/Alt-Latin.icns"])
    return {
        "status": "passed",
        "version": release,
        "numeric_keyboard_id": int(layout.get("id")),
        **counts,
        "icon_chunks": chunks,
        "bundle_matches_sources": True,
        "file_sha256": {
            path: hashlib.sha256(data).hexdigest()
            for path, data in sorted(actual.items())
        },
        "scope": "Static structure and packaging checks; not macOS runtime or strict XML DTD validation",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--report", type=Path, default=ROOT / "build" / "validation.json"
    )
    args = parser.parse_args()
    try:
        report = validate(args.bundle)
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        print(
            "PASS: bundle matches local sources; layout, metadata, and icon structure checks passed."
        )
        print(args.report)
    except (
        OSError,
        ValueError,
        KeyError,
        TypeError,
        ET.ParseError,
        struct.error,
    ) as error:
        parser.exit(1, f"Validation failed: {error}\n")
