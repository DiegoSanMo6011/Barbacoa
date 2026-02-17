from __future__ import annotations

from datetime import date
import tkinter as tk
from tkinter import messagebox, ttk
import customtkinter as ctk

from domain.auth import Role
from domain.corte import calc_diferencia, calc_efectivo_teorico
from domain.ticket import build_corte_ticket_text
from ui.assets import load_logo
from ui.auth_unlock_dialog import ask_unlock_for_role
from services.corte_service import (
    actualizar_caja_chica_jornada,
    ESTADO_ABIERTO,
    ESTADO_CERRADO,
    cerrar_jornada,
    get_corte_por_fecha,
    get_gastos_total,
    get_propinas_tarjeta_resumen,
    get_ventas_por_metodo,
    iniciar_jornada,
    reabrir_jornada,
)
from services.auth_service import AuthService
from services.supabase_service import SupabaseService
from ui.mousewheel import bind_mousewheel
from ui.ticket_preview import TicketPreview


class CorteView(ctk.CTkToplevel):
    def __init__(self, master, supabase: SupabaseService, auth: AuthService | None = None):
        super().__init__(master)
        self.title("Corte de caja")
        self.geometry("1220x820")
        self.minsize(1040, 700)
        self.resizable(True, True)
        self.grab_set()
        self.bind("<Escape>", lambda _e: self.destroy())

        self.db = supabase
        self.auth = auth
        self._last = {}
        self._current_corte: dict | None = None

        self.fecha_var = tk.StringVar(value=date.today().isoformat())
        self.caja_chica_var = tk.StringVar(value="0.00")
        self.efectivo_contado_var = tk.StringVar()
        self.diferencia_var = tk.StringVar(value="$0.00")
        self.estado_jornada_var = tk.StringVar(value="NO INICIADO")
        self.status_var = tk.StringVar(value="")
        self.flujo_var = tk.StringVar(value="Paso 1: Inicia la jornada con caja chica.")

        self.total_ventas_var = tk.StringVar(value="0.00")
        self.ventas_efectivo_var = tk.StringVar(value="0.00")
        self.ventas_tarjeta_var = tk.StringVar(value="0.00")
        self.ventas_transfer_var = tk.StringVar(value="0.00")
        self.caja_chica_display_var = tk.StringVar(value="0.00")
        self.total_gastos_var = tk.StringVar(value="0.00")
        self.total_propinas_tarjeta_var = tk.StringVar(value="0.00")
        self.total_propinas_efectivo_var = tk.StringVar(value="0.00")
        self.total_propinas_reparto_var = tk.StringVar(value="0.00")
        self.total_terminal_var = tk.StringVar(value="0.00")
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
        self.btn_modificar_caja = ttk.Button(
            jornada,
            text="Modificar caja chica (Dueño)",
            command=self._modificar_caja_chica,
        )
        self.btn_modificar_caja.grid(row=0, column=4, padx=8, pady=8, sticky="e")
        self.btn_reabrir = ttk.Button(jornada, text="Reabrir / Editar (Dueño)", command=self._reabrir_jornada)
        self.btn_reabrir.grid(row=0, column=5, padx=8, pady=8, sticky="e")
        jornada.grid_columnconfigure(6, weight=1)

        flujo = ctk.CTkFrame(self, fg_color="#eef2ff")
        flujo.pack(fill="x", padx=12, pady=(0, 10))
        ctk.CTkLabel(flujo, text="Flujo sugerido:", font=("Arial", 12, "bold")).pack(side="left", padx=(10, 6), pady=8)
        ctk.CTkLabel(flujo, textvariable=self.flujo_var, text_color="#1f2937").pack(side="left", padx=6, pady=8)
        self.btn_empezar_cierre = ttk.Button(flujo, text="Empezar cierre del día", style="Accent.TButton", command=self._empezar_cierre)
        self.btn_empezar_cierre.pack(side="right", padx=(6, 10), pady=6)
        self.btn_imprimir = ttk.Button(flujo, text="Imprimir corte", command=self._imprimir_corte)
        self.btn_imprimir.pack(side="right", padx=6, pady=6)

        resumen = ctk.CTkFrame(self)
        resumen.pack(fill="x", padx=12, pady=(0, 10))
        resumen.grid_columnconfigure(0, weight=1)
        resumen.grid_columnconfigure(1, weight=1)

        resumen_ventas = ctk.CTkFrame(resumen)
        resumen_ventas.grid(row=0, column=0, padx=(0, 6), pady=0, sticky="nsew")
        resumen_caja = ctk.CTkFrame(resumen)
        resumen_caja.grid(row=0, column=1, padx=(6, 0), pady=0, sticky="nsew")

        def _row(parent: ctk.CTkFrame, label: str, var: tk.StringVar, r: int, *, highlight: bool = False):
            ctk.CTkLabel(parent, text=label).grid(row=r, column=0, padx=8, pady=4, sticky="w")
            ctk.CTkLabel(
                parent,
                textvariable=var,
                font=("Arial", 16 if highlight else 13, "bold"),
                text_color="#111827" if highlight else None,
            ).grid(row=r, column=1, padx=8, pady=4, sticky="e")

        ctk.CTkLabel(resumen_ventas, text="Ventas y terminal", font=("Arial", 14, "bold")).grid(
            row=0, column=0, columnspan=2, padx=8, pady=(8, 6), sticky="w"
        )
        _row(resumen_ventas, "Total ventas:", self.total_ventas_var, 1)
        _row(resumen_ventas, "Ventas EFECTIVO:", self.ventas_efectivo_var, 2)
        _row(resumen_ventas, "Ventas TARJETA:", self.ventas_tarjeta_var, 3)
        _row(resumen_ventas, "Ventas TRANSFER:", self.ventas_transfer_var, 4)
        _row(resumen_ventas, "Propinas TARJETA (terminal):", self.total_propinas_tarjeta_var, 5)
        _row(resumen_ventas, "Total terminal (venta+propina):", self.total_terminal_var, 6, highlight=True)
        ctk.CTkLabel(
            resumen_ventas,
            text="Total terminal = Ventas TARJETA + Propinas TARJETA",
            text_color="#4b5563",
        ).grid(row=7, column=0, columnspan=2, padx=8, pady=(2, 8), sticky="w")

        ctk.CTkLabel(resumen_caja, text="Caja y resultado", font=("Arial", 14, "bold")).grid(
            row=0, column=0, columnspan=2, padx=8, pady=(8, 6), sticky="w"
        )
        _row(resumen_caja, "Caja chica inicial:", self.caja_chica_display_var, 1)
        _row(resumen_caja, "Total gastos:", self.total_gastos_var, 2)
        _row(resumen_caja, "Efectivo esperado en caja:", self.efectivo_teorico_var, 3, highlight=True)
        _row(resumen_caja, "Neto:", self.neto_var, 4)
        ctk.CTkLabel(
            resumen_caja,
            text="Propinas en EFECTIVO: solo referencia, no afectan caja.",
            text_color="#4b5563",
        ).grid(row=5, column=0, columnspan=2, padx=8, pady=(2, 8), sticky="w")

        resumen_ventas.grid_columnconfigure(1, weight=1)
        resumen_caja.grid_columnconfigure(1, weight=1)

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

        ctk.CTkLabel(efectivo_frame, text="Diferencia (contado - esperado):").grid(row=0, column=4, padx=6, pady=6, sticky="w")
        self.diferencia_label = ctk.CTkLabel(
            efectivo_frame,
            textvariable=self.diferencia_var,
            font=("Arial", 14, "bold"),
            text_color="#92400e",
        )
        self.diferencia_label.grid(row=0, column=5, padx=6, pady=6, sticky="w")

        propinas_frame = ctk.CTkFrame(self)
        propinas_frame.pack(fill="both", expand=True, padx=12, pady=(0, 8))
        propinas_frame.grid_columnconfigure(0, weight=1)
        propinas_frame.grid_rowconfigure(3, weight=1)
        ctk.CTkLabel(
            propinas_frame,
            text="Reparto de propinas por mesero",
            font=("Arial", 14, "bold"),
        ).grid(row=0, column=0, padx=6, pady=(8, 4), sticky="w")
        ctk.CTkLabel(
            propinas_frame,
            text="Esta sección indica exactamente cuánto pagar a cada mesero por TARJETA y por EFECTIVO.",
            text_color="#4b5563",
        ).grid(row=1, column=0, padx=6, pady=(0, 4), sticky="w")

        propinas_totales = ctk.CTkFrame(propinas_frame, fg_color="#eef2ff")
        propinas_totales.grid(row=2, column=0, padx=6, pady=(4, 8), sticky="ew")
        propinas_totales.grid_columnconfigure(1, weight=1)
        propinas_totales.grid_columnconfigure(3, weight=1)
        propinas_totales.grid_columnconfigure(5, weight=1)
        ctk.CTkLabel(propinas_totales, text="Tarjeta a pagar hoy:", font=("Arial", 12, "bold")).grid(
            row=0, column=0, padx=(10, 6), pady=8, sticky="w"
        )
        ctk.CTkLabel(propinas_totales, textvariable=self.total_propinas_tarjeta_var, font=("Arial", 14, "bold")).grid(
            row=0, column=1, padx=6, pady=8, sticky="w"
        )
        ctk.CTkLabel(propinas_totales, text="Efectivo a pagar hoy:", font=("Arial", 12, "bold")).grid(
            row=0, column=2, padx=(18, 6), pady=8, sticky="w"
        )
        ctk.CTkLabel(propinas_totales, textvariable=self.total_propinas_efectivo_var, font=("Arial", 14, "bold")).grid(
            row=0, column=3, padx=6, pady=8, sticky="w"
        )
        ctk.CTkLabel(propinas_totales, text="Total a repartir:", font=("Arial", 12, "bold")).grid(
            row=0, column=4, padx=(18, 6), pady=8, sticky="w"
        )
        ctk.CTkLabel(propinas_totales, textvariable=self.total_propinas_reparto_var, font=("Arial", 15, "bold")).grid(
            row=0, column=5, padx=6, pady=8, sticky="w"
        )

        table_frame = ctk.CTkFrame(propinas_frame)
        table_frame.grid(row=3, column=0, padx=6, pady=(0, 8), sticky="nsew")
        table_frame.grid_columnconfigure(0, weight=1)
        table_frame.grid_rowconfigure(0, weight=1)

        self.propinas_tree = ttk.Treeview(
            table_frame,
            columns=("mesero", "total_tarjeta", "total_efectivo", "total_pagar", "instruccion"),
            show="headings",
            height=6,
        )
        self.propinas_tree.heading("mesero", text="Mesero", anchor="center")
        self.propinas_tree.heading("total_tarjeta", text="Tarjeta", anchor="center")
        self.propinas_tree.heading("total_efectivo", text="Efectivo", anchor="center")
        self.propinas_tree.heading("total_pagar", text="Total a pagar", anchor="center")
        self.propinas_tree.heading("instruccion", text="Indicacion de pago", anchor="center")
        self.propinas_tree.column("mesero", width=260, anchor="center")
        self.propinas_tree.column("total_tarjeta", width=140, anchor="center")
        self.propinas_tree.column("total_efectivo", width=140, anchor="center")
        self.propinas_tree.column("total_pagar", width=150, anchor="center")
        self.propinas_tree.column("instruccion", width=460, anchor="center")
        self.propinas_tree.grid(row=0, column=0, sticky="nsew")

        propinas_scroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.propinas_tree.yview)
        propinas_scroll.grid(row=0, column=1, sticky="ns")
        self.propinas_tree.configure(yscrollcommand=propinas_scroll.set)
        bind_mousewheel(self.propinas_tree, self.propinas_tree.yview)

        status_frame = ctk.CTkFrame(self, fg_color="transparent")
        status_frame.pack(fill="x", padx=12, pady=(0, 6))
        ctk.CTkLabel(status_frame, textvariable=self.status_var).pack(side="left", padx=6)
        ctk.CTkLabel(
            status_frame,
            text="Atajos: F5 recargar | Ctrl+I iniciar | Ctrl+Shift+C cerrar | Ctrl+R reabrir | Ctrl+M modificar caja",
            text_color="#6b7280",
        ).pack(side="right", padx=6)

    def _bind_shortcuts(self):
        self.bind("<F5>", lambda _e: self._refresh())
        self.bind("<Control-i>", lambda _e: self._iniciar_jornada())
        self.bind("<Control-I>", lambda _e: self._iniciar_jornada())
        self.bind("<Control-Shift-C>", lambda _e: self._cerrar_jornada())
        self.bind("<Control-r>", lambda _e: self._reabrir_jornada())
        self.bind("<Control-R>", lambda _e: self._reabrir_jornada())
        self.bind("<Control-m>", lambda _e: self._modificar_caja_chica())
        self.bind("<Control-M>", lambda _e: self._modificar_caja_chica())

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
            propinas_resumen = get_propinas_tarjeta_resumen(fecha, db=self.db)
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
            "total_propinas_tarjeta": float(propinas_resumen.get("total_propinas_tarjeta") or 0),
            "total_propinas_efectivo": float(propinas_resumen.get("total_propinas_efectivo") or 0),
            "total_propinas_reparto": float(propinas_resumen.get("total_propinas_reparto") or 0),
            "propinas_tarjeta_detalle": list(propinas_resumen.get("detalle") or []),
            "caja_chica_inicial": self._parse_amount(self.caja_chica_var.get(), default=0.0),
            "neto": 0.0,
            "efectivo_teorico": 0.0,
        }

        self._load_corte_existente(fecha)
        self._recalculate_totals()
        self._apply_state_ui()
        self._update_flujo()
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
                # En jornada cerrada mostramos snapshot inmutable del cierre.
                self._last["total_propinas_tarjeta"] = float(corte.get("total_propinas_tarjeta") or 0)
                detalle = self._normalized_propinas_detalle(corte.get("propinas_tarjeta_detalle"))
                self._last["propinas_tarjeta_detalle"] = detalle
                self._last["total_propinas_efectivo"] = round(
                    sum(float(item.get("total_efectivo") or 0) for item in detalle),
                    2,
                )
                self._last["total_propinas_reparto"] = round(
                    float(self._last.get("total_propinas_tarjeta") or 0)
                    + float(self._last.get("total_propinas_efectivo") or 0),
                    2,
                )
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

    def _normalized_propinas_detalle(self, raw: object) -> list[dict]:
        if not isinstance(raw, list):
            return []
        agg: dict[str, dict] = {}
        for item in raw:
            if not isinstance(item, dict):
                continue
            mesero = (item.get("mesero") or "Sin nombre").strip() or "Sin nombre"
            try:
                num_tarjeta = int(item.get("num_tarjeta") or 0)
            except Exception:
                num_tarjeta = 0
            try:
                total_tarjeta = float(item.get("total_tarjeta") or 0)
            except Exception:
                total_tarjeta = 0.0
            try:
                num_efectivo = int(item.get("num_efectivo") or 0)
            except Exception:
                num_efectivo = 0
            try:
                total_efectivo = float(item.get("total_efectivo") or 0)
            except Exception:
                total_efectivo = 0.0
            key = mesero.lower()
            base = agg.get(
                key,
                {
                    "mesero": mesero,
                    "num_tarjeta": 0,
                    "total_tarjeta": 0.0,
                    "num_efectivo": 0,
                    "total_efectivo": 0.0,
                    "total_pagar": 0.0,
                },
            )
            base["num_tarjeta"] += max(0, num_tarjeta)
            base["total_tarjeta"] += round(max(0.0, total_tarjeta), 2)
            base["num_efectivo"] += max(0, num_efectivo)
            base["total_efectivo"] += round(max(0.0, total_efectivo), 2)
            agg[key] = base

        rows = list(agg.values())
        for row in rows:
            row["total_tarjeta"] = round(float(row.get("total_tarjeta") or 0), 2)
            row["total_efectivo"] = round(float(row.get("total_efectivo") or 0), 2)
            row["total_pagar"] = round(row["total_tarjeta"] + row["total_efectivo"], 2)
        rows.sort(key=lambda x: (-float(x.get("total_pagar") or 0), x.get("mesero") or ""))
        return rows

    def _render_propinas_detalle(self):
        for row in self.propinas_tree.get_children():
            self.propinas_tree.delete(row)
        detalle = self._normalized_propinas_detalle(self._last.get("propinas_tarjeta_detalle"))
        for item in detalle:
            total_tarjeta = float(item.get("total_tarjeta") or 0)
            total_efectivo = float(item.get("total_efectivo") or 0)
            total_pagar = float(item.get("total_pagar") or 0)
            if total_tarjeta > 0 and total_efectivo > 0:
                instruccion = f"Pagar ${total_pagar:.2f}: ${total_tarjeta:.2f} tarjeta + ${total_efectivo:.2f} efectivo"
            elif total_tarjeta > 0:
                instruccion = f"Pagar ${total_pagar:.2f} de propina tarjeta"
            elif total_efectivo > 0:
                instruccion = f"Pagar ${total_pagar:.2f} de propina efectivo"
            else:
                instruccion = "Sin pago de propinas"
            self.propinas_tree.insert(
                "",
                "end",
                values=(
                    item.get("mesero") or "Sin nombre",
                    f"${total_tarjeta:.2f}",
                    f"${total_efectivo:.2f}",
                    f"${total_pagar:.2f}",
                    instruccion,
                ),
            )

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
        detalle_propinas = self._normalized_propinas_detalle(self._last.get("propinas_tarjeta_detalle"))
        propinas_tarjeta_total = float(self._last.get("total_propinas_tarjeta") or 0)
        propinas_efectivo_total = float(self._last.get("total_propinas_efectivo") or 0)
        if detalle_propinas:
            propinas_tarjeta_total = round(
                sum(float(item.get("total_tarjeta") or 0) for item in detalle_propinas),
                2,
            )
            propinas_efectivo_total = round(
                sum(float(item.get("total_efectivo") or 0) for item in detalle_propinas),
                2,
            )
        propinas_reparto_total = round(propinas_tarjeta_total + propinas_efectivo_total, 2)
        total_terminal = ventas_tarjeta + propinas_tarjeta_total

        neto = total_ventas - gastos_total
        efectivo_teorico = calc_efectivo_teorico(
            ventas_efectivo=ventas_efectivo,
            gastos_total=gastos_total,
            propinas_tarjeta_total=propinas_tarjeta_total,
            caja_chica_inicial=caja_chica,
        )

        self._last["caja_chica_inicial"] = caja_chica
        self._last["neto"] = neto
        self._last["efectivo_teorico"] = efectivo_teorico
        self._last["total_propinas_tarjeta"] = propinas_tarjeta_total
        self._last["total_propinas_efectivo"] = propinas_efectivo_total
        self._last["total_propinas_reparto"] = propinas_reparto_total
        self._last["propinas_tarjeta_detalle"] = detalle_propinas

        self.total_ventas_var.set(f"${total_ventas:.2f}")
        self.ventas_efectivo_var.set(f"${ventas_efectivo:.2f}")
        self.ventas_tarjeta_var.set(f"${ventas_tarjeta:.2f}")
        self.ventas_transfer_var.set(f"${ventas_transfer:.2f}")
        self.caja_chica_display_var.set(f"${caja_chica:.2f}")
        self.total_gastos_var.set(f"${gastos_total:.2f}")
        self.total_propinas_tarjeta_var.set(f"${propinas_tarjeta_total:.2f}")
        self.total_propinas_efectivo_var.set(f"${propinas_efectivo_total:.2f}")
        self.total_propinas_reparto_var.set(f"${propinas_reparto_total:.2f}")
        self.total_terminal_var.set(f"${total_terminal:.2f}")
        self.efectivo_teorico_var.set(f"${efectivo_teorico:.2f}")
        self.neto_var.set(f"${neto:.2f}")
        self._render_propinas_detalle()
        self._update_diferencia()
        self._update_flujo()

    def _update_diferencia(self):
        try:
            efectivo_contado = float(self.efectivo_contado_var.get().strip() or 0)
        except Exception:
            self.diferencia_var.set("$0.00")
            self.diferencia_label.configure(text_color="#92400e")
            return

        efectivo_teorico = float(self._last.get("efectivo_teorico") or 0)
        diff = calc_diferencia(efectivo_contado, efectivo_teorico)
        self.diferencia_var.set(f"${diff:+.2f}")
        if diff > 0:
            self.diferencia_label.configure(text_color="#166534")
        elif diff < 0:
            self.diferencia_label.configure(text_color="#b91c1c")
        else:
            self.diferencia_label.configure(text_color="#92400e")

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
        self.btn_modificar_caja.configure(state=("normal" if duenio and estado == "ABIERTO" else "disabled"))
        self.btn_reabrir.configure(state=("normal" if estado == "CERRADO" else "disabled"))
        self.btn_empezar_cierre.configure(state=("normal" if duenio and estado == "ABIERTO" else "disabled"))
        self.btn_imprimir.configure(state=("normal" if estado in {"ABIERTO", "CERRADO"} else "disabled"))

        if estado == "ABIERTO":
            self.estado_label.configure(text_color="#166534")
        elif estado == "CERRADO":
            self.estado_label.configure(text_color="#b91c1c")
        else:
            self.estado_label.configure(text_color="#92400e")

    def _update_flujo(self):
        estado = self.estado_jornada_var.get().strip().upper()
        if estado == "NO INICIADO":
            self.flujo_var.set("Paso 1: Define caja chica y presiona Iniciar día.")
            return
        if estado == "ABIERTO":
            self.flujo_var.set("Paso 2: Captura efectivo contado y presiona Cerrar día.")
            return
        self.flujo_var.set("Día cerrado. Puedes imprimir corte o reabrir con PIN de dueño.")

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

    def _empezar_cierre(self):
        estado = self.estado_jornada_var.get().strip().upper()
        if estado == "NO INICIADO":
            messagebox.showinfo("Flujo", "Primero inicia la jornada con caja chica inicial.")
            self.caja_chica_entry.focus_set()
            self.caja_chica_entry.select_range(0, tk.END)
            return
        if estado == "CERRADO":
            messagebox.showinfo("Flujo", "El día ya está cerrado. Usa Reabrir si necesitas editar.")
            return
        self.status_var.set("Captura efectivo contado para iniciar cierre.")
        self.efectivo_entry.focus_set()
        self.efectivo_entry.select_range(0, tk.END)

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
            propinas_tarjeta_total=float(self._last.get("total_propinas_tarjeta") or 0),
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
            "total_propinas_tarjeta": float(self._last.get("total_propinas_tarjeta") or 0),
            "propinas_tarjeta_detalle": self._normalized_propinas_detalle(
                self._last.get("propinas_tarjeta_detalle")
            ),
            "diferencia_efectivo": diferencia,
            "notas": None,
        }

        try:
            cerrar_jornada(payload, db=self.db)
            messagebox.showinfo("OK", "Día cerrado correctamente.")
            self._refresh()
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo cerrar jornada:\n{e}")

    def _modificar_caja_chica(self):
        if not self._require_duenio(confirm_pin=False):
            return

        estado = self.estado_jornada_var.get().strip().upper()
        if estado != "ABIERTO":
            messagebox.showwarning(
                "Jornada no editable",
                "Solo se puede modificar caja chica cuando la jornada está ABIERTO.",
            )
            return

        fecha = self._parse_fecha()
        if not fecha:
            return

        caja_chica = self._parse_amount(self.caja_chica_var.get(), default=0.0)
        if caja_chica < 0:
            messagebox.showwarning("Caja chica inválida", "La caja chica inicial debe ser un número >= 0.")
            return

        try:
            updated = actualizar_caja_chica_jornada(fecha, caja_chica, db=self.db)
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo modificar caja chica:\n{e}")
            return

        caja_actualizada = float(updated.get("caja_chica_inicial") or 0)
        self.caja_chica_var.set(f"{caja_actualizada:.2f}")
        if self._last:
            self._last["caja_chica_inicial"] = caja_actualizada
        self._current_corte = updated
        self._recalculate_totals()
        self.status_var.set("Caja chica actualizada para la jornada abierta.")
        messagebox.showinfo("OK", "Caja chica actualizada.")

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

    def _build_corte_print_payload(self) -> dict:
        return {
            "fecha": self._last.get("fecha") or self.fecha_var.get().strip(),
            "estado": self.estado_jornada_var.get().strip() or "NO INICIADO",
            "caja_chica_inicial": self._parse_amount(self.caja_chica_var.get(), default=0.0),
            "efectivo_contado": self._parse_amount(self.efectivo_contado_var.get(), default=0.0),
            "efectivo_teorico": float(self._last.get("efectivo_teorico") or 0),
            "diferencia": self._parse_amount(self.diferencia_var.get().replace("$", ""), default=0.0),
            "total_ventas": float(self._last.get("total_ventas") or 0),
            "ventas_efectivo": float(self._last.get("ventas_efectivo") or 0),
            "ventas_tarjeta": float(self._last.get("ventas_tarjeta") or 0),
            "ventas_transfer": float(self._last.get("ventas_transfer") or 0),
            "total_gastos": float(self._last.get("total_gastos") or 0),
            "total_terminal": self._parse_amount(self.total_terminal_var.get().replace("$", ""), default=0.0),
            "propinas_tarjeta": float(self._last.get("total_propinas_tarjeta") or 0),
            "propinas_efectivo": float(self._last.get("total_propinas_efectivo") or 0),
            "propinas_total": float(self._last.get("total_propinas_reparto") or 0),
            "propinas_detalle": self._normalized_propinas_detalle(self._last.get("propinas_tarjeta_detalle")),
        }

    def _imprimir_corte(self):
        if not self._last:
            self._refresh()
            if not self._last:
                return

        ticket_text = build_corte_ticket_text(self._build_corte_print_payload())
        TicketPreview(self, ticket_text, None)
