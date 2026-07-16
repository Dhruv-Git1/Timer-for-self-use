"""Android entry point used by Flet's embedded-Python launcher.

Flet executes this module as ``python -m mobile_build_entry``.  Importing
``mobile.main`` alone is not enough because its desktop-only ``__main__``
guard does not run in that case, so explicitly start the Flet app here.
"""

import os

import flet as ft

from mobile.main import main


# Flet's Android bootstrap is expected to set this.  Set the Android-specific
# fallback as well so a packaged app always selects Flet's embedded bridge
# instead of a desktop/socket server that immediately shuts down.
os.environ.setdefault("FLET_PLATFORM", "android")

ft.run(main)
