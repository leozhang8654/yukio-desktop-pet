"""Write the installer layout directly, without automating a Finder session."""
import plistlib
import sys
from pathlib import Path

import dmgbuild

app, output, background = map(Path, sys.argv[1:])
with (app / "Contents/Info.plist").open("rb") as source:
    version = plistlib.load(source)["CFBundleShortVersionString"]

dmgbuild.build_dmg(
    str(output),
    f"Yukio {version}",
    settings={
        "format": "UDZO",
        "compression_level": 9,
        "files": [(str(app), "Yukio.app")],
        "symlinks": {"应用程序 Applications": "/Applications"},
        "background": str(background),
        "window_rect": ((200, 120), (720, 460)),
        "default_view": "icon-view",
        "icon_size": 88,
        "text_size": 13,
        "icon_locations": {"Yukio.app": (188, 224), "应用程序 Applications": (532, 224)},
        "show_status_bar": False,
        "show_toolbar": False,
        "show_sidebar": False,
        "show_tab_view": False,
        "show_pathbar": False,
    },
)
