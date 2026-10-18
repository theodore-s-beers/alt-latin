# Alt-Latin

Alt-Latin is a macOS keyboard layout that makes it easy to type Latin-script letters with a wide variety of diacritics. Most users of the layout (to my knowledge) are academics in fields like Near Eastern studies and linguistics.

The original creator of Alt-Latin was someone called Kino; I've been maintaining the layout since ca. 2019. For more background, see this [old blog post](https://medium.com/@tbeers/the-alt-latin-keyboard-layout-macos-version-f5be707cf272).

## Build and validate

This requires only Python, no dependencies:

```sh
python3 build.py
python3 validate.py
```

## Install

Copy `build/Alt-Latin.bundle` to `~/Library/Keyboard Layouts/`, then add Alt-Latin in macOS input source settings. A reboot may be needed for the layout to become available.

## Modify

Mappings and metadata can be edited in `src/`. The build script will refuse to overwrite an existing bundle; either remove the previous output or specify an alternate path with `--output PATH`. The validation script also accepts an argument `--bundle PATH`.

The icon file used by the build is `icon/Alt-Latin.icns`. That is defined in turn by `icon/Alt-Latin.svg`. After any edits to the SVG, regenerate the icon set:

```sh
swift icon/rasterize.swift icon/Alt-Latin.svg icon/Alt-Latin.iconset
iconutil -c icns -o icon/Alt-Latin.icns icon/Alt-Latin.iconset
```
