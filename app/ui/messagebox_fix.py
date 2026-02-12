from __future__ import annotations

import tkinter as tk
from tkinter import messagebox
from typing import Callable


_INSTALLED = False


def _safe_toplevel(widget: tk.Misc | None) -> tk.Misc | None:
    if widget is None:
        return None
    try:
        top = widget.winfo_toplevel()
    except Exception:
        return None
    try:
        if not int(top.winfo_exists()):
            return None
    except Exception:
        return None
    return top


def _resolve_parent(root: tk.Misc) -> tk.Misc | None:
    # Prefer the window currently holding a grab (dialogs use grab_set).
    try:
        grab_widget = root.grab_current()
    except Exception:
        grab_widget = None
    top = _safe_toplevel(grab_widget)
    if top is not None:
        return top

    # Fallback to focused widget/top-level.
    try:
        focus_widget = root.focus_get() or root.focus_displayof()
    except Exception:
        focus_widget = None
    top = _safe_toplevel(focus_widget)
    if top is not None:
        return top

    return _safe_toplevel(root)


def _bump_front(parent: tk.Misc) -> None:
    try:
        parent.lift()
        parent.update_idletasks()
        parent.attributes("-topmost", True)
        parent.after_idle(lambda p=parent: p.attributes("-topmost", False))
    except Exception:
        pass


def _wrap_messagebox(fn: Callable, root: tk.Misc) -> Callable:
    def wrapped(*args, **kwargs):
        if kwargs.get("parent") is None:
            parent = _resolve_parent(root)
            if parent is not None:
                kwargs["parent"] = parent
        parent = kwargs.get("parent")
        if parent is not None:
            _bump_front(parent)
        return fn(*args, **kwargs)

    return wrapped


def install_messagebox_parenting(root: tk.Misc) -> None:
    global _INSTALLED
    if _INSTALLED:
        return

    for name in (
        "showinfo",
        "showwarning",
        "showerror",
        "askquestion",
        "askokcancel",
        "askretrycancel",
        "askyesno",
        "askyesnocancel",
    ):
        fn = getattr(messagebox, name, None)
        if not callable(fn):
            continue
        setattr(messagebox, name, _wrap_messagebox(fn, root))

    _INSTALLED = True
