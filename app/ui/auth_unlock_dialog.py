from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

import customtkinter as ctk

from domain.auth import Role
from services.auth_service import AuthService, UnlockResult
from ui.assets import load_logo


class AuthUnlockDialog(ctk.CTkToplevel):
    def __init__(
        self,
        master,
        auth: AuthService,
        *,
        fixed_role: Role | None = None,
        title_text: str = "Desbloquear perfil",
        header_text: str = "DESBLOQUEAR PERFIL",
    ):
        super().__init__(master)
        self.title(title_text)
        self.geometry("520x250")
        self.resizable(False, False)
        self.grab_set()

        self.auth = auth
        self.fixed_role = fixed_role
        self.header_text = header_text
        self.result: UnlockResult | None = None

        default_role = fixed_role.label if fixed_role else Role.GERENTE.label
        self.role_var = tk.StringVar(value=default_role)
        self.pin_var = tk.StringVar()

        self._build_ui()

    def _build_ui(self):
        header = ctk.CTkFrame(self, fg_color="#1f2937", height=60, corner_radius=0)
        header.pack(fill="x", side="top")
        self.logo_img = load_logo(36)
        if self.logo_img:
            tk.Label(header, image=self.logo_img, bg="#1f2937").pack(side="left", padx=(12, 6), pady=12)
        ctk.CTkLabel(header, text=self.header_text, font=("Arial", 18, "bold"), text_color="white").pack(
            side="left", padx=(6, 12), pady=12
        )

        form = ctk.CTkFrame(self)
        form.pack(fill="both", expand=True, padx=12, pady=12)

        ctk.CTkLabel(form, text="Rol:", font=("Arial", 12, "bold")).grid(row=0, column=0, padx=8, pady=8, sticky="w")
        if self.fixed_role:
            ctk.CTkLabel(form, text=self.fixed_role.label, font=("Arial", 12, "bold")).grid(
                row=0, column=1, padx=8, pady=8, sticky="w"
            )
        else:
            self.role_menu = ctk.CTkOptionMenu(
                form,
                values=[Role.GERENTE.label, Role.DUENIO.label],
                variable=self.role_var,
                width=220,
            )
            self.role_menu.grid(row=0, column=1, padx=8, pady=8, sticky="w")

        ctk.CTkLabel(form, text="PIN (4-6 dígitos):", font=("Arial", 12, "bold")).grid(
            row=1, column=0, padx=8, pady=8, sticky="w"
        )
        self.pin_entry = ctk.CTkEntry(form, textvariable=self.pin_var, show="*", width=220)
        self.pin_entry.grid(row=1, column=1, padx=8, pady=8, sticky="w")
        self.pin_entry.focus_set()

        ctk.CTkLabel(
            form,
            text="Usa este acceso solo para funciones administrativas.",
            text_color="#6b7280",
        ).grid(row=2, column=0, columnspan=2, padx=8, pady=(2, 8), sticky="w")

        btns = ctk.CTkFrame(form, fg_color="transparent")
        btns.grid(row=3, column=0, columnspan=2, padx=8, pady=(6, 0), sticky="e")
        ttk.Button(btns, text="Cancelar", command=self._cancel).pack(side="left", padx=6)
        ttk.Button(btns, text="Desbloquear", style="Accent.TButton", command=self._unlock).pack(side="left", padx=6)

        self.bind("<Return>", lambda _e: self._unlock())
        self.bind("<Escape>", lambda _e: self._cancel())

    def _unlock(self):
        result = self.auth.unlock(self.role_var.get(), self.pin_var.get())
        if not result.success:
            messagebox.showwarning("Acceso denegado", result.message)
            self.pin_entry.select_range(0, tk.END)
            self.pin_entry.focus_set()
            return

        if result.source == "offline":
            messagebox.showinfo("Acceso offline", result.message)

        self.result = result
        self.destroy()

    def _cancel(self):
        self.result = None
        self.destroy()


def ask_unlock(master, auth: AuthService) -> UnlockResult | None:
    dlg = AuthUnlockDialog(master, auth)
    master.wait_window(dlg)
    return dlg.result


def ask_unlock_for_role(
    master,
    auth: AuthService,
    role: Role,
    *,
    title_text: str = "Confirmar acceso",
    header_text: str = "CONFIRMAR PIN",
) -> UnlockResult | None:
    dlg = AuthUnlockDialog(
        master,
        auth,
        fixed_role=role,
        title_text=title_text,
        header_text=header_text,
    )
    master.wait_window(dlg)
    return dlg.result
