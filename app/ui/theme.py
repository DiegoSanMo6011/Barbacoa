from __future__ import annotations

from tkinter import ttk
import customtkinter as ctk

THEME = {
    "header_bg": "#1f2937",
    "header_fg": "#ffffff",
    "surface": "#f3f4f6",
    "surface_alt": "#e5e7eb",
    "text": "#111827",
    "text_muted": "#374151",
    "accent": "#1d4ed8",
    "accent_hover": "#1e40af",
    "danger": "#dc2626",
    "danger_hover": "#b91c1c",
    "row_even": "#ffffff",
    "row_odd": "#f3f4f6",
}

FONTS = {
    "header": ("Arial", 18, "bold"),
    "section": ("Arial", 12, "bold"),
    "body": ("Arial", 12),
    "table": ("Arial", 13),
}


def apply_ttk_style(root) -> None:
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except Exception:
        pass

    style.configure("TButton", padding=8, font=("Arial", 10, "bold"))
    style.configure("Accent.TButton", padding=10, font=("Arial", 11, "bold"), foreground="white", background=THEME["accent"])
    style.map("Accent.TButton", background=[("active", THEME["accent_hover"])])
    style.configure("Danger.TButton", padding=8, font=("Arial", 10, "bold"), foreground="white", background=THEME["danger"])
    style.map("Danger.TButton", background=[("active", THEME["danger_hover"])])

    style.configure("Treeview.Heading", font=("Arial", 13, "bold"))
    style.configure("Treeview", rowheight=40, font=FONTS["table"])


def build_header(parent, title: str, logo_img=None) -> ctk.CTkFrame:
    header = ctk.CTkFrame(parent, fg_color=THEME["header_bg"], height=60, corner_radius=0)
    header.pack(fill="x", side="top")
    if logo_img:
        ctk.CTkLabel(header, text="", image=logo_img).pack(side="left", padx=(12, 6), pady=12)
    ctk.CTkLabel(header, text=title, font=FONTS["header"], text_color=THEME["header_fg"]).pack(
        side="left", padx=(6, 12), pady=12
    )
    return header
