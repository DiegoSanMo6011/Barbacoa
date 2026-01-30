from __future__ import annotations

import os
import tkinter as tk


def get_logo_path() -> str | None:
    base = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "assets"))
    # Prefer AutoNoma branding; fall back to previous assets if missing.
    candidates = (
        "logo_autonoma_256.png",
        "logo_autonoma.png",
        "logo_autonoma.svg",
        "logo_barbacoa.png",
        "logo.png",
        "file.png",
    )
    for name in candidates:
        path = os.path.join(base, name)
        if os.path.exists(path):
            return path
    return None


def load_logo(max_px: int = 32) -> tk.PhotoImage | None:
    path = get_logo_path()
    if not path:
        print("WARN: No logo asset found in app/assets.")
        return None
    if path.lower().endswith(".svg"):
        print("WARN: SVG logo found but Tkinter cannot render SVG. Provide a PNG export.")
        return None
    try:
        img = tk.PhotoImage(file=path)
        if max_px and img.width() > max_px:
            factor = max(1, img.width() // max_px)
            img = img.subsample(factor, factor)
        return img
    except Exception:
        print(f"WARN: Failed to load logo at {path}")
        return None
