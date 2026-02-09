from __future__ import annotations

from datetime import date
import tkinter as tk
from tkinter import messagebox, ttk
import customtkinter as ctk

from domain.auth import Role
from domain.corte import calc_diferencia, calc_efectivo_teorico
from ui.assets import load_logo
from ui.auth_unlock_dialog import ask_unlock_for_role
from services.corte_service import (
    ESTADO_ABIERTO,
    ESTADO_CERRADO,
    cerrar_jornada,
    get_corte_por_fecha,
    get_gastos_total,
    get_propinas_total,
    get_ventas_por_metodo,
    iniciar_jornada,
    reabrir_jornada,
)
from services.auth_service import AuthService
from services.supabase_service import SupabaseService


class CorteView(ctk.CTkToplevel):
    def __init__(self, master, supabase: SupabaseService, auth: AuthService | None = None):
        super().__init__(master)
        self.title("Corte de caja")
        self.geometry("980x620")
        self.resizable(False, False)
        self.grab_set()
        self.bind("<Escape>", lambda _e: self.destroy())

        self.db = supabase
        self.auth = auth
        self._last = {}
        self._current_corte: dict | None = None

        self.fecha_var = tk.StringVar(value=date.today().isoformat())
        self.caja_chica_var = tk.StringVar(value="0.00")
        self.efectivo_contado_var = tk.StringVar()
        self.diferencia_var = tk.StringVar(value="0.00")
        self.estado_jornada_var = tk.StringVar(value="NO INICIADO")
        self.status_var = tk.StringVar(value="")

        self.total_ventas_var = tk.StringVar(value="0.00")
        self.ventas_efectivo_var = tk.StringVar(value="0.00")
        self.ventas_tarjeta_var = tk.StringVar(value="0.00")
        self.ventas_transfer_var = tk.StringVar(value="0.00")
        self.caja_chica_display_var = tk.StringVar(value="0.00")
        self.total_gastos_var = tk.StringVar(value="0.00")
        self.total_propinas_var = tk.StringVar(value="0.00")
        self.efectivo_teorico_var = tk.StringVar(value="0.00")
        self.neto_var = tk.StringVar(value="0.00")

        self._build_ui()
        self._bind_shortcuts()
        self._refresh()

    def _build_ui(self):
        header = ctk.CTkFrame(self, fg_color="#1f2937", height=60, corner_radius=0)
        header.pack(fill="x", side="top")
        self.logo_img = load_logo(40)
        if self.logo_img:
            tk.Label(header, image=self.logo_img, bg="#1f2937").pack(side="left", padx=(12, 6), pady=12)
        ctk.CTkLabel(header, text="CORTE DE CAJA", font=("Arial", 18, "bold"), text_color="white").pack(side="left", padx=(6, 12), pady=12)

        top_bar = ctk.CTkFrame(self)
        top_bar.pack(fill="x", padx=12, pady=(12, 8))

        ctk.CTkLabel(top_bar, text="Jornada del día", font=("Arial", 14, "bold")).pack(side="left", padx=6)

        date_row = ctk.CTkFrame(top_bar, fg_color="transparent")
        date_row.pack(side="right")
        ctk.CTkLabel(date_row, text="Fecha (YYYY-MM-DD):").pack(side="left", padx=6)
        self.fecha_entry = ctk.CTkEntry(date_row, textvariable=self.fecha_var, width=140)
        self.fecha_entry.pack(side="left", padx=6)
        self.fecha_entry.bind("<Return>", lambda _e: self._refresh())
        self.btn_cargar = ttk.Button(date_row, text="Cargar", command=self._refresh)
        self.btn_cargar.pack(side="left", padx=6)

        jornada = ctk.CTkFrame(self)
        jornada.pack(fill="x", padx=12, pady=(0, 10))
        ctk.CTkLabel(jornada, text="Estado jornada:").grid(row=0, column=0, padx=8, pady=8, sticky="w")
        self.estado_label = ctk.CTkLabel(jornada, textvariable=self.estado_jornada_var, font=("Arial", 13, "bold"))
        self.estado_label.grid(
            row=0, column=1, padx=8, pady=8, sticky="w"
        )
        self.btn_iniciar = ttk.Button(jornada, text="Iniciar día", style="Accent.TButton", command=self._iniciar_jornada)
        self.btn_iniciar.grid(row=0, column=2, padx=8, pady=8, sticky="e")
        self.btn_cerrar = ttk.Button(jornada, text="Cerrar día", style="Accent.TButton", command=self._cerrar_jornada)
        self.btn_cerrar.grid(row=0, column=3, padx=8, pady=8, sticky="e")
        self.btn_reabrir = ttk.Button(jornada, text="Reabrir / Editar (Dueño)", command=self._reabrir_jornada)
        self.btn_reabrir.grid(row=0, column=4, padx=8, pady=8, sticky="e")
        jornada.grid_columnconfigure(5, weight=1)

        resumen = ctk.CTkFrame(self)
        resumen.pack(fill="x", padx=12, pady=(0, 12))

        def _row(label: str, var: tk.StringVar, r: int):
            ctk.CTkLabel(resumen, text=label).grid(row=r, column=0, padx=6, pady=4, sticky="w")
            ctk.CTkLabel(resumen, textvariable=var, font=("Arial", 13, "bold")).grid(
                row=r, column=1, padx=6, pady=4, sticky="e"
            )

        _row("Total ventas:", self.total_ventas_var, 0)
        _row("Ventas EFECTIVO:", self.ventas_efectivo_var, 1)
        _row("Ventas TARJETA:", self.ventas_tarjeta_var, 2)
        _row("Ventas TRANSFER:", self.ventas_transfer_var, 3)
        _row("Caja chica inicial:", self.caja_chica_display_var, 4)
        _row("Total gastos:", self.total_gastos_var, 5)
        _row("Total propinas:", self.total_propinas_var, 6)
        _row("Efectivo esperado en caja:", self.efectivo_teorico_var, 7)
        _row("Neto:", self.neto_var, 8)

        resumen.grid_columnconfigure(1, weight=1)

        efectivo_frame = ctk.CTkFrame(self)
        efectivo_frame.pack(fill="x", padx=12, pady=(0, 12))

        ctk.CTkLabel(efectivo_frame, text="Caja chica inicial:").grid(row=0, column=0, padx=6, pady=6, sticky="w")
        self.caja_chica_entry = ctk.CTkEntry(efectivo_frame, textvariable=self.caja_chica_var, width=140)
        self.caja_chica_entry.grid(row=0, column=1, padx=6, pady=6, sticky="w")
        self.caja_chica_entry.bind("<KeyRelease>", lambda _e: self._recalculate_totals())
        self.caja_chica_entry.bind("<Return>", lambda _e: self._on_enter_caja_chica())

        ctk.CTkLabel(efectivo_frame, text="Efectivo contado:").grid(row=0, column=2, padx=6, pady=6, sticky="w")
        self.efectivo_entry = ctk.CTkEntry(efectivo_frame, textvariable=self.efectivo_contado_var, width=140)
        self.efectivo_entry.grid(row=0, column=3, padx=6, pady=6, sticky="w")
        self.efectivo_entry.bind("<KeyRelease>", lambda _e: self._update_diferencia())
        self.efectivo_entry.bind("<Return>", lambda _e: self._on_enter_efectivo())

        ctk.CTkLabel(efectivo_frame, text="Diferencia:").grid(row=0, column=4, padx=6, pady=6, sticky="w")
        ctk.CTkLabel(efectivo_frame, textvariable=self.diferencia_var, font=("Arial", 13, "bold")).grid(
            row=0, column=5, padx=6, pady=6, sticky="w"
        )

        status_frame = ctk.CTkFrame(self, fg_color="transparent")
        status_frame.pack(fill="x", padx=12, pady=(0, 6))
        ctk.CTkLabel(status_frame, textvariable=self.status_var).pack(side="left", padx=6)
        ctk.CTkLabel(
            status_frame,
            text="Atajos: F5 recargar | Ctrl+I iniciar | Ctrl+Shift+C cerrar | Ctrl+R reabrir",
            text_color="#6b7280",
        ).pack(side="right", padx=6)

    def _bind_shortcuts(self):
        self.bind("<F5>", lambda _e: self._refresh())
        self.bind("<Control-i>", lambda _e: self._iniciar_jornada())
        self.bind("<Control-I>", lambda _e: self._iniciar_jornada())
        self.bind("<Control-Shift-C>", lambda _e: self._cerrar_jornada())
        self.bind("<Control-r>", lambda _e: self._reabrir_jornada())
        self.bind("<Control-R>", lambda _e: self._reabrir_jornada())

    def _parse_fecha(self) -> date | None:
        txt = self.fecha_var.get().strip()
        try:
            return date.fromisoformat(txt)
        except Exception:
            messagebox.showwarning("Fecha inválida", "Usa el formato YYYY-MM-DD.")
            return None

    def _refresh(self):
        fecha = self._parse_fecha()
        if not fecha:
            return

        self.status_var.set("Cargando jornada...")
        self.update_idletasks()

        try:
            ventas = get_ventas_por_metodo(fecha, db=self.db)
            gastos_total = get_gastos_total(fecha, db=self.db)
            propinas_total = get_propinas_total(fecha, db=self.db)
        except Exception as e:
            self.status_var.set("")
            messagebox.showerror("Error", f"No se pudo cargar el resumen:\n{e}")
            return

        self._last = {
            "fecha": fecha.isoformat(),
            "total_ventas": float(ventas.get("total") or 0),
            "ventas_efectivo": float(ventas.get("EFECTIVO") or 0),
            "ventas_tarjeta": float(ventas.get("TARJETA") or 0),
            "ventas_transfer": float(ventas.get("TRANSFER") or 0),
            "total_gastos": gastos_total,
            "total_propinas": propinas_total,
            "caja_chica_inicial": self._parse_amount(self.caja_chica_var.get(), default=0.0),
            "neto": 0.0,
            "efectivo_teorico": 0.0,
        }

        self._load_corte_existente(fecha)
        self._recalculate_totals()
        self._apply_state_ui()
        self._focus_primary()

    def _load_corte_existente(self, fecha: date):
        try:
            corte = get_corte_por_fecha(fecha, db=self.db)
        except Exception:
            corte = None

        self._current_corte = corte
        if corte:
            estado = (corte.get("estado") or ESTADO_CERRADO).upper()
            if estado == ESTADO_ABIERTO:
                self.estado_jornada_var.set("ABIERTO")
                self.status_var.set(f"Jornada iniciada para {fecha.isoformat()}.")
            else:
                self.estado_jornada_var.set("CERRADO")
                reaperturas = int(corte.get("reaperturas") or 0)
                self.status_var.set(f"Día cerrado. Reaperturas: {reaperturas}.")
            self.caja_chica_var.set(f"{float(corte.get('caja_chica_inicial') or 0):.2f}")
            if estado == ESTADO_CERRADO:
                self.efectivo_contado_var.set(f"{float(corte.get('efectivo_reportado') or 0):.2f}")
            else:
                self.efectivo_contado_var.set("")
        else:
            self.estado_jornada_var.set("NO INICIADO")
            self.status_var.set("Primero inicia el día con caja chica inicial.")
            self.caja_chica_var.set("0.00")
            self.efectivo_contado_var.set("")

    def _parse_amount(self, value: str, default: float = 0.0) -> float:
        txt = (value or "").strip()
        if not txt:
            return float(default)
        try:
            return float(txt)
        except Exception:
            return float(default)

    def _recalculate_totals(self):
        if not self._last:
            return

        caja_chica = self._parse_amount(self.caja_chica_var.get(), default=0.0)
        if caja_chica < 0:
            caja_chica = 0.0

        total_ventas = float(self._last.get("total_ventas") or 0)
        ventas_efectivo = float(self._last.get("ventas_efectivo") or 0)
        ventas_tarjeta = float(self._last.get("ventas_tarjeta") or 0)
        ventas_transfer = float(self._last.get("ventas_transfer") or 0)
        gastos_total = float(self._last.get("total_gastos") or 0)
        propinas_total = float(self._last.get("total_propinas") or 0)

        neto = total_ventas - gastos_total
        efectivo_teorico = calc_efectivo_teorico(
            ventas_efectivo=ventas_efectivo,
            gastos_total=gastos_total,
            propinas_total=propinas_total,
            caja_chica_inicial=caja_chica,
        )

        self._last["caja_chica_inicial"] = caja_chica
        self._last["neto"] = neto
        self._last["efectivo_teorico"] = efectivo_teorico

        self.total_ventas_var.set(f"${total_ventas:.2f}")
        self.ventas_efectivo_var.set(f"${ventas_efectivo:.2f}")
        self.ventas_tarjeta_var.set(f"${ventas_tarjeta:.2f}")
        self.ventas_transfer_var.set(f"${ventas_transfer:.2f}")
        self.caja_chica_display_var.set(f"${caja_chica:.2f}")
        self.total_gastos_var.set(f"${gastos_total:.2f}")
        self.total_propinas_var.set(f"${propinas_total:.2f}")
        self.efectivo_teorico_var.set(f"${efectivo_teorico:.2f}")
        self.neto_var.set(f"${neto:.2f}")
        self._update_diferencia()

    def _update_diferencia(self):
        try:
            efectivo_contado = float(self.efectivo_contado_var.get().strip() or 0)
        except Exception:
            self.diferencia_var.set("0.00")
            return

        efectivo_teorico = float(self._last.get("efectivo_teorico") or 0)
        diff = calc_diferencia(efectivo_contado, efectivo_teorico)
        self.diferencia_var.set(f"{diff:.2f}")

    def _is_duenio(self) -> bool:
        if not self.auth:
            return False
        return self.auth.current_role() == Role.DUENIO

    def _require_duenio(self, *, confirm_pin: bool = False) -> bool:
        if not self.auth:
            messagebox.showwarning("Auth requerida", "No hay contexto de autenticación.")
            return False
        if not self._is_duenio():
            result = ask_unlock_for_role(
                self,
                self.auth,
                Role.DUENIO,
                title_text="Acceso de dueño requerido",
                header_text="DUEÑO REQUERIDO",
            )
            if not result:
                return False
            self._apply_state_ui()
            return True
        if confirm_pin:
            result = ask_unlock_for_role(
                self,
                self.auth,
                Role.DUENIO,
                title_text="Confirmar PIN de dueño",
                header_text="CONFIRMAR REAPERTURA",
            )
            if not result:
                return False
        return True

    def _apply_state_ui(self):
        estado = self.estado_jornada_var.get().strip().upper()
        duenio = self._is_duenio()
        allow_edit = duenio and estado != "CERRADO"
        self.caja_chica_entry.configure(state=("normal" if allow_edit else "disabled"))
        self.efectivo_entry.configure(state=("normal" if allow_edit else "disabled"))

        self.btn_iniciar.configure(state=("normal" if duenio and estado == "NO INICIADO" else "disabled"))
        self.btn_cerrar.configure(state=("normal" if duenio and estado == "ABIERTO" else "disabled"))
        self.btn_reabrir.configure(state=("normal" if estado == "CERRADO" else "disabled"))

        if estado == "ABIERTO":
            self.estado_label.configure(text_color="#166534")
        elif estado == "CERRADO":
            self.estado_label.configure(text_color="#b91c1c")
        else:
            self.estado_label.configure(text_color="#92400e")

    def _focus_primary(self):
        estado = self.estado_jornada_var.get().strip().upper()
        duenio = self._is_duenio()
        if estado == "NO INICIADO":
            if duenio:
                self.caja_chica_entry.focus_set()
                self.caja_chica_entry.select_range(0, tk.END)
            else:
                self.fecha_entry.focus_set()
            return
        if estado == "ABIERTO":
            if duenio:
                self.efectivo_entry.focus_set()
                self.efectivo_entry.select_range(0, tk.END)
            else:
                self.fecha_entry.focus_set()
            return
        if estado == "CERRADO" and duenio:
            self.btn_reabrir.focus_set()
            return
        self.fecha_entry.focus_set()

    def _on_enter_caja_chica(self):
        estado = self.estado_jornada_var.get().strip().upper()
        if estado == "NO INICIADO":
            self._iniciar_jornada()
            return
        if estado == "ABIERTO":
            self.efectivo_entry.focus_set()
            self.efectivo_entry.select_range(0, tk.END)

    def _on_enter_efectivo(self):
        estado = self.estado_jornada_var.get().strip().upper()
        if estado == "ABIERTO":
            self._cerrar_jornada()

    def _iniciar_jornada(self):
        if not self._require_duenio(confirm_pin=False):
            return
        fecha = self._parse_fecha()
        if not fecha:
            return
        caja_chica = self._parse_amount(self.caja_chica_var.get(), default=0.0)
        if caja_chica < 0:
            messagebox.showwarning("Caja chica inválida", "La caja chica inicial debe ser un número >= 0.")
            return
        try:
            iniciar_jornada(fecha, caja_chica, db=self.db)
            messagebox.showinfo("OK", "Jornada iniciada.")
            self._refresh()
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo iniciar jornada:\n{e}")

    def _cerrar_jornada(self):
        if not self._require_duenio(confirm_pin=False):
            return
        if not self._last:
            self._refresh()
            if not self._last:
                return

        caja_chica = self._parse_amount(self.caja_chica_var.get(), default=0.0)
        if caja_chica < 0:
            messagebox.showwarning("Caja chica inválida", "La caja chica inicial debe ser un número >= 0.")
            return

        try:
            efectivo_contado = float(self.efectivo_contado_var.get().strip())
            if efectivo_contado < 0:
                raise ValueError
        except Exception:
            messagebox.showwarning("Efectivo inválido", "El efectivo contado debe ser un número >= 0.")
            return

        efectivo_teorico = calc_efectivo_teorico(
            ventas_efectivo=float(self._last.get("ventas_efectivo") or 0),
            gastos_total=float(self._last.get("total_gastos") or 0),
            propinas_total=float(self._last.get("total_propinas") or 0),
            caja_chica_inicial=caja_chica,
        )
        diferencia = calc_diferencia(efectivo_contado, efectivo_teorico)
        payload = {
            "fecha": self._last.get("fecha"),
            "total_ventas": self._last.get("total_ventas"),
            "total_gastos": self._last.get("total_gastos"),
            "neto": self._last.get("neto"),
            "efectivo_reportado": efectivo_contado,
            "caja_chica_inicial": caja_chica,
            "diferencia_efectivo": diferencia,
            "notas": None,
        }

        try:
            cerrar_jornada(payload, db=self.db)
            messagebox.showinfo("OK", "Día cerrado correctamente.")
            self._refresh()
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo cerrar jornada:\n{e}")

    def _reabrir_jornada(self):
        fecha = self._parse_fecha()
        if not fecha:
            return
        if not self._require_duenio(confirm_pin=True):
            return
        try:
            reabrir_jornada(fecha, db=self.db)
            messagebox.showinfo("OK", "Jornada reabierta. Ya puedes editar y volver a cerrar.")
            self._refresh()
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo reabrir jornada:\n{e}")
