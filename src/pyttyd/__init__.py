from __future__ import annotations

import os
from pathlib import Path

__version__ = "2.0.1"

__basepath__ = os.path.dirname(os.path.abspath(__file__))
__static__ = os.path.join(__basepath__, "static")
__template__ = os.path.join(__basepath__, "template")


def read_template(name: str) -> str:
    path = Path(__template__) / name
    return path.read_text(encoding="utf-8")
