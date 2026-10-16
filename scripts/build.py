# SPDX-License-Identifier: GPL-3.0-or-later
"""Build the installable extension: ``python scripts/build.py``.

Writes ``dist/sketch_to_hardsurface-<version>.zip`` (Blender 4.2+: Edit >
Preferences > Get Extensions > Install from Disk). Equivalent to Blender's
``blender --command extension build --source-dir sketch_to_hardsurface``,
without needing Blender.
"""

import pathlib
import re
import zipfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
SOURCE = ROOT / "sketch_to_hardsurface"


def main():
    manifest = (SOURCE / "blender_manifest.toml").read_text(encoding="utf-8")
    version = re.search(r'^version\s*=\s*"([^"]+)"', manifest, re.MULTILINE).group(1)
    out = ROOT / "dist" / ("sketch_to_hardsurface-%s.zip" % version)
    out.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(SOURCE.rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
                archive.write(path, path.relative_to(SOURCE).as_posix())
    print(out)


if __name__ == "__main__":
    main()
