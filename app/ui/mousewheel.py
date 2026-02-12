from __future__ import annotations

import tkinter as tk


def bind_mousewheel(widget: tk.Misc, yview_target) -> None:
    """
    Enable mouse-wheel vertical scrolling on a scrollable widget.

    Works for Windows/macOS (<MouseWheel>) and Linux (<Button-4/5>).
    """

    def _on_mousewheel(event: tk.Event) -> str | None:
        delta = 0
        if getattr(event, "delta", 0):
            # On Windows/mac: event.delta is typically multiples of 120
            delta = -1 if event.delta > 0 else 1
        elif getattr(event, "num", None) == 4:
            delta = -1
        elif getattr(event, "num", None) == 5:
            delta = 1

        if delta:
            yview_target("scroll", delta, "units")
            return "break"
        return None

    widget.bind("<MouseWheel>", _on_mousewheel, add="+")
    widget.bind("<Button-4>", _on_mousewheel, add="+")
    widget.bind("<Button-5>", _on_mousewheel, add="+")
    widget.bind("<Enter>", lambda _e: widget.focus_set(), add="+")
