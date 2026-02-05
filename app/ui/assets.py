from __future__ import annotations

import os
import tkinter as tk
_LOGO_CACHE = {}

def load_logo(max_px: int = 32) -> tk.PhotoImage | None:
    cache_key = f"logo_{max_px}"
    if cache_key in _LOGO_CACHE:
        return _LOGO_CACHE[cache_key]

    path = get_logo_path()
    if not path: return None
    
    try:
        img = tk.PhotoImage(file=path)
        if max_px and img.width() > max_px:
            factor = max(1, img.width() // max_px)
            img = img.subsample(factor, factor)
        
        _LOGO_CACHE[cache_key] = img  # Guardamos en "memoria de video"
        return img
    except Exception:
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
