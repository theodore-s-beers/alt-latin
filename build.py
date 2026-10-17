import argparse
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DEFAULT_OUTPUT = ROOT / "build" / "Alt-Latin.bundle"
SOURCE_FILES = {
    "Contents/Info.plist": "src/Info.plist",
    "Contents/version.plist": "src/version.plist",
    "Contents/Resources/Alt-Latin.keylayout": "src/Alt-Latin.keylayout",
    "Contents/Resources/en.lproj/InfoPlist.strings": "src/en.lproj/InfoPlist.strings",
    "Contents/Resources/Alt-Latin.icns": "icon/Alt-Latin.icns",
}


def source_files():
    return {
        destination: (ROOT / source).read_bytes()
        for destination, source in SOURCE_FILES.items()
    }


def build(destination):
    destination = Path(destination).absolute()
    if destination.exists() or destination.is_symlink():
        raise ValueError(f"Refusing to overwrite existing bundle: {destination}")
    files = source_files()
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=".alt-latin-", dir=destination.parent
    ) as tmp:
        staged = Path(tmp) / "Alt-Latin.bundle"
        for relative, data in files.items():
            target = staged / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        if destination.exists() or destination.is_symlink():
            raise ValueError(f"Destination appeared during build: {destination}")
        staged.rename(destination)
    return destination


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    try:
        print(build(args.output))
    except (OSError, ValueError) as error:
        parser.exit(1, f"Build failed: {error}\n")
