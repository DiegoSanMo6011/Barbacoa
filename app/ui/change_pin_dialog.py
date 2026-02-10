from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

import bcrypt
import customtkinter as ctk

from domain.auth import Role
from services.auth_service import AuthService
from services.supabase_service import SupabaseService
from ui.assets import load_logo


class ChangePinDialog(ctk.CTkToplevel):
    def __init__(self, master, supabase: SupabaseService, auth: AuthService, role: Role):
        super().__init__(master)
        self.title("Cambiar mi PIN")
        self.geometry("560x300")
        self.resizable(False, False)
        self.grab_set()

        self.db = supabase
        self.auth = auth
        self.role = role

        self.current_pin_var = tk.StringVar()
        self.new_pin_var = tk.StringVar()
        self.confirm_pin_var = tk.StringVar()

        self._build_ui()

    def _build_ui(self):
        header = ctk.CTkFrame(self, fg_color="#1f2937", height=60, corner_radius=0)
        header.pack(fill="x", side="top")
        self.logo_img = load_logo(36)
        if self.logo_img:
            tk.Label(header, image=self.logo_img, bg="#1f2937").pack(side="left", padx=(12, 6), pady=12)
        ctk.CTkLabel(header, text="CAMBIAR MI PIN", font=("Arial", 18, "bold"), text_color="white").pack(
            side="left", padx=(6, 12), pady=12
        )

        form = ctk.CTkFrame(self)
        form.pack(fill="both", expand=True, padx=12, pady=12)

        ctk.CTkLabel(form, text="Perfil:", font=("Arial", 12, "bold")).grid(row=0, column=0, padx=8, pady=8, sticky="w")
        ctk.CTkLabel(form, text=self.role.label, font=("Arial", 12, "bold")).grid(row=0, column=1, padx=8, pady=8, sticky="w")

        ctk.CTkLabel(form, text="PIN actual:", font=("Arial", 12, "bold")).grid(row=1, column=0, padx=8, pady=8, sticky="w")
        current_entry = ctk.CTkEntry(form, textvariable=self.current_pin_var, show="*", width=220)
        current_entry.grid(row=1, column=1, padx=8, pady=8, sticky="w")
        current_entry.focus_set()

        ctk.CTkLabel(form, text="PIN nuevo (4-6 dígitos):", font=("Arial", 12, "bold")).grid(
            row=2, column=0, padx=8, pady=8, sticky="w"
        )
        ctk.CTkEntry(form, textvariable=self.new_pin_var, show="*", width=220).grid(
            row=2, column=1, padx=8, pady=8, sticky="w"
        )

        ctk.CTkLabel(form, text="Confirmar PIN nuevo:", font=("Arial", 12, "bold")).grid(
            row=3, column=0, padx=8, pady=8, sticky="w"
        )
        ctk.CTkEntry(form, textvariable=self.confirm_pin_var, show="*", width=220).grid(
            row=3, column=1, padx=8, pady=8, sticky="w"
        )

        ctk.CTkLabel(
            form,
            text="El PIN debe ser numérico de 4 a 6 dígitos.",
            text_color="#6b7280",
        ).grid(row=4, column=0, columnspan=2, padx=8, pady=(2, 8), sticky="w")

        btns = ctk.CTkFrame(form, fg_color="transparent")
        btns.grid(row=5, column=0, columnspan=2, padx=8, pady=(4, 0), sticky="e")
        ttk.Button(btns, text="Cancelar", command=self.destroy).pack(side="left", padx=6)
        ttk.Button(btns, text="Guardar PIN", style="Accent.TButton", command=self._save).pack(side="left", padx=6)

        self.bind("<Return>", lambda _e: self._save())
        self.bind("<Escape>", lambda _e: self.destroy())

    def _save(self):
        current_pin = self.current_pin_var.get().strip()
        new_pin = self.new_pin_var.get().strip()
        confirm_pin = self.confirm_pin_var.get().strip()

        if len(new_pin) < 4 or len(new_pin) > 6 or not new_pin.isdigit():
            messagebox.showwarning("PIN inválido", "El PIN nuevo debe tener 4 a 6 dígitos.")
            return

        if new_pin != confirm_pin:
            messagebox.showwarning("PIN inválido", "La confirmación del PIN no coincide.")
            return

        result = self.auth.unlock(self.role, current_pin)
        if not result.success:
            messagebox.showwarning("PIN incorrecto", result.message)
            return

        password_hash = bcrypt.hashpw(new_pin.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

        try:
            self.db.set_role_pin(self.role.value, password_hash)
            self.auth.invalidate_role_cache(self.role)
            # Refresca cache y mantiene sesion activa con el nuevo PIN.
            self.auth.unlock(self.role, new_pin)
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo cambiar PIN:\n{e}")
            return

        messagebox.showinfo("OK", "PIN actualizado.")
        self.destroy()
