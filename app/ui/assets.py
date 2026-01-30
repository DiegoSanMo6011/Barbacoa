from __future__ import annotations

import os
import tkinter as tk


def load_logo(max_px: int = 32) -> tk.PhotoImage | None:
    base = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "assets"))
    candidates = ("logo_barbacoa.png", "logo.png", "file.png")
    for name in candidates:
        path = os.path.join(base, name)
        if not os.path.exists(path):
            continue
        try:
            img = tk.PhotoImage(file=path)
            if max_px and img.width() > max_px:
                factor = max(1, img.width() // max_px)
                img = img.subsample(factor, factor)
            return img
        except Exception:
            return None
    return None
