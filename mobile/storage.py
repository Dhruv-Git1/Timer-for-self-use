"""
Builds (and caches) the single AppContext the whole mobile app shares.

``config.py`` already resolves ``FLET_APP_STORAGE_DATA`` on its own (see its
``_STORAGE_ROOT``) — this module's only job is to construct ``AppContext``
exactly once and hand the same instance to every screen, mirroring how the
desktop app's ``AppWindow`` holds one shared ``self.ctx``.
"""

from __future__ import annotations

from typing import Optional

from app.services.context import AppContext

_context: Optional[AppContext] = None


def get_context() -> AppContext:
    global _context
    if _context is None:
        _context = AppContext()
    return _context
