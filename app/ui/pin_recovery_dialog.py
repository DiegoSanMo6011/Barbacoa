from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

import customtkinter as ctk

from domain.auth import Role
from services.auth_service import AuthService, RecoverPinResult
from ui.assets import load_logo


class PinRecoveryDialog(ctk.CTkToplevel):
    def __init__(
        self,
        master,
        auth: AuthService,
        *,
        fixed_role: Role | None = None,
        title_text: str = "Recuperar PIN",
        header_text: str = "RECUPERAR PIN",
    ):
        super().__init__(master)
        self.title(title_text)
        self.geometry("640x380")
        self.minsize(600, 350)
        self.resizable(True, True)
        self.grab_set()

        self.auth = auth
        self.fixed_role = fixed_role
        self.header_text = header_text
        self.result: RecoverPinResult | None = None

        default_role = fixed_role.label if fixed_role else Role.GERENTE.label
        self.role_var = tk.StringVar(value=default_role)
        self.recovery_code_var = tk.StringVar()
        self.new_pin_var = tk.StringVar()
        self.confirm_pin_var = tk.StringVar()
        self.hint_var = tk.StringVar(value="")
        self.destination_var = tk.StringVar(value=self.auth.recovery_destination())

        self._build_ui()
        self._refresh_hint()

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
            role_menu = ctk.CTkOptionMenu(
                form,
                values=[Role.GERENTE.label, Role.DUENIO.label],
                variable=self.role_var,
                width=240,
                command=lambda _value: self._refresh_hint(),
            )
            role_menu.grid(row=0, column=1, padx=8, pady=8, sticky="w")

        ctk.CTkLabel(form, text="Codigo de recuperacion:", font=("Arial", 12, "bold")).grid(
            row=1,
            column=0,
            padx=8,
            pady=8,
            sticky="w",
        )
        recovery_entry = ctk.CTkEntry(form, textvariable=self.recovery_code_var, show="*", width=240)
        recovery_entry.grid(row=1, column=1, padx=8, pady=8, sticky="w")
        recovery_entry.focus_set()
        ttk.Button(form, text="Enviar codigo al correo", command=self._request_code).grid(
            row=1, column=2, padx=(6, 8), pady=8, sticky="w"
        )

        ctk.CTkLabel(
            form,
            text="Correo destino:",
            font=("Arial", 12, "bold"),
        ).grid(row=2, column=0, padx=8, pady=8, sticky="w")
        ctk.CTkLabel(form, textvariable=self.destination_var).grid(row=2, column=1, padx=8, pady=8, sticky="w")

        ctk.CTkLabel(form, text="PIN nuevo (4-6 digitos):", font=("Arial", 12, "bold")).grid(
            row=3, column=0, padx=8, pady=8, sticky="w"
        )
        ctk.CTkEntry(form, textvariable=self.new_pin_var, show="*", width=240).grid(
            row=3, column=1, padx=8, pady=8, sticky="w"
        )

        ctk.CTkLabel(form, text="Confirmar PIN nuevo:", font=("Arial", 12, "bold")).grid(
            row=4,
            column=0,
            padx=8,
            pady=8,
            sticky="w",
        )
        ctk.CTkEntry(form, textvariable=self.confirm_pin_var, show="*", width=240).grid(
            row=4, column=1, padx=8, pady=8, sticky="w"
        )

        ctk.CTkLabel(
            form,
            textvariable=self.hint_var,
            text_color="#6b7280",
            justify="left",
            wraplength=560,
        ).grid(row=5, column=0, columnspan=3, padx=8, pady=(4, 10), sticky="w")

        btns = ctk.CTkFrame(form, fg_color="transparent")
        btns.grid(row=6, column=0, columnspan=3, padx=8, pady=(6, 0), sticky="e")
        ttk.Button(btns, text="Cancelar", command=self._cancel).pack(side="left", padx=6)
        ttk.Button(btns, text="Restablecer PIN", style="Accent.TButton", command=self._recover).pack(side="left", padx=6)

        self.bind("<Return>", lambda _e: self._recover())
        self.bind("<Escape>", lambda _e: self._cancel())

    def _current_role(self) -> Role:
        return self.fixed_role or Role.from_raw(self.role_var.get())

    def _refresh_hint(self):
        role = self._current_role()
        self.destination_var.set(self.auth.recovery_destination())
        if self.auth.has_recovery_channel(role):
            self.hint_var.set(
                f"Solicita el codigo para {role.label}. El codigo de recuperacion es temporal."
            )
            return
        self.hint_var.set(
            "Falta configurar SMTP en .env para enviar el codigo: "
            "BARBACOA_SMTP_USER y BARBACOA_SMTP_PASSWORD."
        )

    def _request_code(self):
        role = self._current_role()
        result = self.auth.request_recovery_code(role)
        if not result.success:
            messagebox.showwarning("No se pudo enviar", result.message)
            return
        messagebox.showinfo("Codigo enviado", result.message)

    def _recover(self):
        role = self._current_role()
        new_pin = self.new_pin_var.get().strip()
        confirm_pin = self.confirm_pin_var.get().strip()
        if new_pin != confirm_pin:
            messagebox.showwarning("PIN invalido", "La confirmacion del PIN no coincide.")
            return

        result = self.auth.recover_pin(role, self.recovery_code_var.get(), new_pin)
        if not result.success:
            messagebox.showwarning("No se pudo recuperar", result.message)
            return

        self.result = result
        messagebox.showinfo("PIN recuperado", result.message)
        self.destroy()

    def _cancel(self):
        self.result = None
        self.destroy()


def ask_pin_recovery(
    master,
    auth: AuthService,
    *,
    fixed_role: Role | None = None,
    title_text: str = "Recuperar PIN",
    header_text: str = "RECUPERAR PIN",
) -> RecoverPinResult | None:
    dlg = PinRecoveryDialog(
        master,
        auth,
        fixed_role=fixed_role,
        title_text=title_text,
        header_text=header_text,
    )
    master.wait_window(dlg)
    return dlg.result
