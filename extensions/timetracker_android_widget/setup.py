"""Package the repository-local Flutter extension alongside its tiny Python wheel."""

from pathlib import Path
from shutil import copytree, rmtree

from setuptools.command.build_py import build_py
from setuptools import setup


class BuildPython(build_py):
    def run(self):
        super().run()
        source = Path(__file__).parent / "flutter" / "timetracker_android_widget"
        # serious_python discovers Flutter extensions only from the wheel's
        # top-level ``flutter/`` directory (the same layout used by flet-video
        # and flet-charts). Keeping this inside the Python package makes the
        # Dart code compile in isolation but prevents Android's plugin manifest
        # from being registered in the final app.
        destination = Path(self.build_lib) / "flutter" / "timetracker_android_widget"
        if destination.exists():
            rmtree(destination)
        copytree(source, destination, dirs_exist_ok=True)


setup(cmdclass={"build_py": BuildPython})
