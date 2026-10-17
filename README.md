# Alt-Latin

Alt-Latin is a macOS keyboard layout originally created by someone called Kino, maintained by me since ~2019. [Background](https://medium.com/@tbeers/the-alt-latin-keyboard-layout-macos-version-f5be707cf272).

Build and validate with Python (no dependencies):

```sh
python3 build.py
python3 validate.py
```

Copy `build/Alt-Latin.bundle` to `~/Library/Keyboard Layouts/`, then add Alt-Latin in macOS input source settings. A reboot may be needed for the layout to become available.

Edit mappings and metadata in `src/`. Builds refuse to overwrite an existing bundle; remove the previous output or use `--output PATH` and validate with `--bundle PATH`.

The build uses `icon/Alt-Latin.icns`. After any edits to the SVG, regenerate the icon:

```sh
swift icon/rasterize.swift icon/Alt-Latin.svg icon/Alt-Latin.iconset
iconutil -c icns -o icon/Alt-Latin.icns icon/Alt-Latin.iconset
```
