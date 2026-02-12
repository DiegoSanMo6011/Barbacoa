from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

import bcrypt
import customtkinter as ctk

from domain.auth import Role
from services.auth_service import AuthService
from services.supabase_service import SupabaseService
from ui.assets import load_logo


class UsuariosDialog(ctk.CTkToplevel):
    def __init__(self, master, supabase: SupabaseService, auth: AuthService):
        super().__init__(master)
        self.title("Usuarios y seguridad")
        self.geometry("980x660")
        self.minsize(860, 560)
        self.resizable(True, True)
        self.grab_set()

        self.db = supabase
        self.auth = auth

        self.role_var = tk.StringVar(value=Role.GERENTE.label)
        self.pin_var = tk.StringVar()
        self.pin_confirm_var = tk.StringVar()

        self._records: dict[str, dict] = {}

        self._build_ui()
        self._load_roles()

    def _build_ui(self):
        header = ctk.CTkFrame(self, fg_color="#1f2937", height=60, corner_radius=0)
        header.pack(fill="x", side="top")
        self.logo_img = load_logo(40)
        if self.logo_img:
            tk.Label(header, image=self.logo_img, bg="#1f2937").pack(side="left", padx=(12, 6), pady=12)
        ctk.CTkLabel(
            header,
            text="USUARIOS Y SEGURIDAD",
            font=("Arial", 18, "bold"),
            text_color="white",
        ).pack(side="left", padx=(6, 12), pady=12)

        top = ctk.CTkFrame(self)
        top.pack(fill="x", padx=12, pady=12)

        ctk.CTkLabel(top, text="Credenciales por rol", font=("Arial", 14, "bold")).pack(anchor="w", padx=6, pady=(6, 8))

        self.tree = ttk.Treeview(
            top,
            columns=("rol", "usuario", "nombre", "activo", "actualizado"),
            show="headings",
            height=6,
        )
        self.tree.heading("rol", text="Rol")
        self.tree.heading("usuario", text="Usuario")
        self.tree.heading("nombre", text="Nombre")
        self.tree.heading("activo", text="Activo")
        self.tree.heading("actualizado", text="Actualizado")

        self.tree.column("rol", width=120, anchor="center")
        self.tree.column("usuario", width=180, anchor="w")
        self.tree.column("nombre", width=220, anchor="w")
        self.tree.column("activo", width=90, anchor="center")
        self.tree.column("actualizado", width=200, anchor="center")
        self.tree.pack(fill="x", padx=6, pady=(0, 6))

        btns = ctk.CTkFrame(top, fg_color="transparent")
        btns.pack(fill="x", padx=6, pady=(0, 6))
        ttk.Button(btns, text="Refrescar", command=self._load_roles).pack(side="left", padx=6)
        ttk.Button(btns, text="Activar/Desactivar gerente", command=self._toggle_gerente).pack(side="left", padx=6)

        form = ctk.CTkFrame(self)
        form.pack(fill="x", padx=12, pady=(0, 12))

        ctk.CTkLabel(form, text="Cambiar PIN", font=("Arial", 14, "bold")).grid(
            row=0,
            column=0,
            columnspan=4,
            padx=8,
            pady=(8, 10),
            sticky="w",
        )

        ctk.CTkLabel(form, text="Rol:").grid(row=1, column=0, padx=8, pady=6, sticky="w")
        ctk.CTkOptionMenu(
            form,
            values=[Role.GERENTE.label, Role.DUENIO.label],
            variable=self.role_var,
            width=160,
        ).grid(row=1, column=1, padx=8, pady=6, sticky="w")

        ctk.CTkLabel(form, text="PIN nuevo (4-6):").grid(row=1, column=2, padx=8, pady=6, sticky="w")
        self.pin_entry = ctk.CTkEntry(form, textvariable=self.pin_var, show="*", width=160)
        self.pin_entry.grid(row=1, column=3, padx=8, pady=6, sticky="w")

        ctk.CTkLabel(form, text="Confirmar PIN:").grid(row=2, column=2, padx=8, pady=6, sticky="w")
        self.pin_confirm_entry = ctk.CTkEntry(form, textvariable=self.pin_confirm_var, show="*", width=160)
        self.pin_confirm_entry.grid(row=2, column=3, padx=8, pady=6, sticky="w")

        ttk.Button(form, text="Guardar PIN", style="Accent.TButton", command=self._save_pin).grid(
            row=3,
            column=3,
            padx=8,
            pady=10,
            sticky="e",
        )

    def _load_roles(self):
        for row in self.tree.get_children():
            self.tree.delete(row)

        try:
            rows = self.db.listar_usuarios_roles()
        except Exception as e:
            messagebox.showerror("Error", f"No se pudieron cargar usuarios:\n{e}")
            return

        self._records = {Role.GERENTE.value: {}, Role.DUENIO.value: {}}
        for row in rows:
            role = (row.get("rol") or "").strip().upper()
            if role == "ADMIN":
                role = Role.DUENIO.value
            if role in self._records and not self._records[role]:
                self._records[role] = row

        for role in (Role.GERENTE.value, Role.DUENIO.value):
            record = self._records.get(role) or {}
            usuario = record.get("usuario") or "-"
            nombre = record.get("nombre") or "-"
            activo = "SI" if record.get("activo", False) else "NO"
            updated = (record.get("updated_at") or record.get("created_at") or "-").replace("T", " ")[:19]
            self.tree.insert("", "end", iid=role, values=(Role.from_raw(role).label, usuario, nombre, activo, updated))

    def _save_pin(self):
        role_raw = self.role_var.get().strip()
        try:
            role = Role.from_raw(role_raw).value
        except Exception:
            role = ""
        pin = self.pin_var.get().strip()
        pin_confirm = self.pin_confirm_var.get().strip()

        if role not in {Role.GERENTE.value, Role.DUENIO.value}:
            messagebox.showwarning("Rol inválido", "Selecciona un rol válido.")
            return

        if len(pin) < 4 or len(pin) > 6 or not pin.isdigit():
            messagebox.showwarning("PIN inválido", "El PIN debe tener 4 a 6 dígitos.")
            return

        if pin != pin_confirm:
            messagebox.showwarning("PIN inválido", "La confirmación del PIN no coincide.")
            return

        password_hash = bcrypt.hashpw(pin.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

        try:
            self.db.set_role_pin(role, password_hash)
            self.auth.invalidate_role_cache(role)
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo actualizar el PIN:\n{e}")
            return

        self.pin_var.set("")
        self.pin_confirm_var.set("")
        self._load_roles()
        messagebox.showinfo("OK", f"PIN actualizado para {Role.from_raw(role).label}.")

    def _toggle_gerente(self):
        record = self._records.get(Role.GERENTE.value) or {}
        if not record:
            messagebox.showwarning(
                "Sin gerente",
                "No hay credencial de GERENTE. Configura un PIN primero.",
            )
            return

        activo_actual = bool(record.get("activo", True))
        try:
            self.db.set_role_active(Role.GERENTE.value, not activo_actual)
            self.auth.invalidate_role_cache(Role.GERENTE.value)
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo actualizar GERENTE:\n{e}")
            return

        self._load_roles()
