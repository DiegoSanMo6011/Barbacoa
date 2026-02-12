import json
import os
import sys
import logging
import threading
import time as pytime
from datetime import datetime
from typing import Callable
import tkinter as tk
from tkinter import ttk, messagebox
import customtkinter as ctk

from domain.auth import Permission, Role
from services.supabase_service import SupabaseService
from services.auth_service import AuthService
from domain.calc import calcular_subtotal, calcular_total
from domain.ticket import build_ticket_text
from ui.assets import load_logo
from ui.auth_unlock_dialog import ask_unlock
from ui.gastos_dialog import GastosDialog
from ui.propinas_dialog import PropinasDialog
from ui.corte_view import CorteView
from ui.reportes_view import ReportesView
from ui.personal_dialog import PersonalDialog
from ui.productos_dialog import ProductosDialog
from ui.ticket_preview import TicketPreview
from ui.change_pin_dialog import ChangePinDialog
from ui.messagebox_fix import install_messagebox_parenting
from services.printer import print_ticket_text, should_autoprint
from ui.mousewheel import bind_mousewheel


class POSApp(tk.Tk):
    def __init__(self):
        super().__init__()
        install_messagebox_parenting(self)
        self.logger = logging.getLogger("barbacoa.pos")
        self.ui_scale = self._load_ui_scale()
        self.ui_start_mode = self._load_ui_start_mode()
        self.open_comandas_mode = self._load_open_comandas_mode()
        ctk.set_appearance_mode("light")
        ctk.set_widget_scaling(self.ui_scale)
        ctk.set_window_scaling(self.ui_scale)
        try:
            self.tk.call("tk", "scaling", max(1.0, self.ui_scale))
        except tk.TclError:
            pass

        self.title("AutoNoma POS")
        self._configure_window_mode()
        self.bind("<Escape>", lambda _e: self._exit_fullscreen())

        # Estilo ttk (se ve pro)
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except Exception:
            pass
        self.option_add("*Font", f"Arial {self._ui_px(13)}")
        style.configure(
            "TButton",
            padding=(self._ui_px(9), self._ui_px(7)),
            font=("Arial", self._ui_px(13), "bold"),
        )
        style.configure(
            "Accent.TButton",
            padding=(self._ui_px(12), self._ui_px(8)),
            font=("Arial", self._ui_px(14), "bold"),
            foreground="white",
            background="#1d4ed8",
        )
        style.map("Accent.TButton", background=[("active", "#1e40af")])
        style.configure(
            "Danger.TButton",
            padding=(self._ui_px(12), self._ui_px(8)),
            font=("Arial", self._ui_px(14), "bold"),
            foreground="white",
            background="#dc2626",
        )
        style.map("Danger.TButton", background=[("active", "#b91c1c")])
        style.configure(
            "Touch.TButton",
            padding=(self._ui_px(13), self._ui_px(9)),
            font=("Arial", self._ui_px(14), "bold"),
        )
        style.configure(
            "CatalogAdd.TButton",
            padding=(self._ui_px(10), self._ui_px(8)),
            font=("Arial", self._ui_px(14), "bold"),
            foreground="white",
            background="#16a34a",
        )
        style.map("CatalogAdd.TButton", background=[("active", "#15803d")])
        style.configure(
            "QtyMinus.TButton",
            padding=(self._ui_px(8), self._ui_px(6)),
            font=("Arial", self._ui_px(14), "bold"),
            foreground="white",
            background="#ef4444",
        )
        style.map("QtyMinus.TButton", background=[("active", "#dc2626")])
        style.configure(
            "QtyPlus.TButton",
            padding=(self._ui_px(8), self._ui_px(6)),
            font=("Arial", self._ui_px(14), "bold"),
            foreground="white",
            background="#16a34a",
        )
        style.map("QtyPlus.TButton", background=[("active", "#15803d")])
        style.configure("TLabel", font=("Arial", self._ui_px(13)))
        style.configure("TEntry", padding=(self._ui_px(7), self._ui_px(7)), font=("Arial", self._ui_px(13)))
        style.configure("TCombobox", padding=(self._ui_px(7), self._ui_px(7)), font=("Arial", self._ui_px(13)))
        style.configure("Treeview.Heading", font=("Arial", self._ui_px(18), "bold"))
        style.configure("Treeview", rowheight=self._ui_px(54), font=("Arial", self._ui_px(17)))
        style.configure("Header.TLabel", font=("Arial", self._ui_px(18), "bold"))
        style.configure("Section.TLabel", font=("Arial", self._ui_px(14), "bold"))
        style.configure("Total.TLabel", font=("Arial", self._ui_px(30), "bold"))

        self.db = SupabaseService()
        self.auth = AuthService(self.db)
        self.productos = self.db.get_productos()
        self._meseros_activos: list[str] = []
        self._meseros_last_refresh_at = 0.0
        self._meseros_refresh_ttl_s = self._load_meseros_refresh_ttl()
        self._sync_in_progress = False
        self._admin_dialogs: dict[str, tk.Toplevel] = {}

        self.items = []  # dict: producto_id, nombre_snapshot, precio_unitario, cantidad, subtotal
        self.filtered = []
        self._gramaje_vars: dict[int, tk.StringVar] = {}
        self.comandas = []
        self.active_comanda = None
        self._comandas_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "data", "comandas_abiertas.json"))

        self._build_ui()
        self.after(100, lambda: self.mesero_menu.focus_set())
        self._load_comandas()
        self._refresh_meseros_dropdown(force=True)
        self._refresh_catalog()
        self._bind_shortcuts()
        self._apply_role_to_ui()
        self._tick_clock()
        self._sync_loop()

    def _load_ui_scale(self) -> float:
        raw = os.getenv("BARBACOA_UI_SCALE", "1.1").strip()
        try:
            value = float(raw)
        except Exception:
            return 1.1
        return max(0.9, min(value, 1.6))

    def _load_ui_start_mode(self) -> str:
        raw = (os.getenv("BARBACOA_UI_START_MODE") or "maximized").strip().lower()
        if raw not in {"maximized", "fullscreen", "windowed"}:
            return "maximized"
        return raw

    def _load_open_comandas_mode(self) -> str:
        raw = (os.getenv("BARBACOA_UI_OPEN_COMANDAS") or "collapsed").strip().lower()
        if raw not in {"collapsed", "visible"}:
            return "collapsed"
        return raw

    def _load_meseros_refresh_ttl(self) -> float:
        raw = (os.getenv("BARBACOA_MESEROS_REFRESH_TTL_SECONDS") or "45").strip()
        try:
            value = float(raw)
        except Exception:
            return 45.0
        return max(5.0, min(value, 300.0))

    def _configure_window_mode(self) -> None:
        self.geometry("1366x768")
        self.minsize(1200, 700)
        if self.ui_start_mode == "fullscreen":
            self.attributes("-fullscreen", True)
            return
        self.attributes("-fullscreen", False)
        if self.ui_start_mode == "maximized":
            try:
                self.state("zoomed")
            except tk.TclError:
                self.geometry("1366x768")

    def _exit_fullscreen(self) -> None:
        if self.attributes("-fullscreen"):
            self.attributes("-fullscreen", False)
            if self.ui_start_mode == "maximized":
                try:
                    self.state("zoomed")
                except tk.TclError:
                    pass

    def _ui_px(self, value: int) -> int:
        return max(8, int(round(value * self.ui_scale)))

    # ---------------- UI ----------------
    def _build_ui(self):
        root = ttk.Frame(self, padding=(self._ui_px(8), self._ui_px(6), self._ui_px(8), self._ui_px(8)))
        root.pack(fill="both", expand=True)

        self._build_header_compacto(root)

        self.main_pane = tk.PanedWindow(
            root,
            orient=tk.HORIZONTAL,
            sashwidth=self._ui_px(6),
            bd=0,
            bg="#d1d5db",
        )
        self.main_pane.pack(fill="both", expand=True, pady=(self._ui_px(6), 0))

        self.catalog_panel = tk.Frame(self.main_pane, bg="#f8fafc")
        self.comanda_panel = tk.Frame(self.main_pane, bg="#f8fafc")
        self.main_pane.add(self.catalog_panel, minsize=self._ui_px(360))
        self.main_pane.add(self.comanda_panel, minsize=self._ui_px(520))

        self._build_catalog_panel(self.catalog_panel)
        self._build_comanda_panel(self.comanda_panel)
        self.after(120, self._set_initial_pane_split)

    def _build_header_compacto(self, parent: tk.Widget) -> None:
        header = tk.Frame(parent, bg="#111827", height=self._ui_px(62))
        header.pack(fill="x")
        header.pack_propagate(False)

        left = tk.Frame(header, bg="#111827")
        left.pack(side="left", padx=self._ui_px(8))
        self.logo_img = load_logo(self._ui_px(40))
        if self.logo_img:
            tk.Label(left, image=self.logo_img, bg="#111827").pack(side="left", padx=(0, self._ui_px(8)))
        tk.Label(
            left,
            text="AUTONOMA POS",
            bg="#111827",
            fg="#f9fafb",
            font=("Arial", self._ui_px(17), "bold"),
        ).pack(side="left")

        center = tk.Frame(header, bg="#111827")
        center.pack(side="left", fill="x", expand=True, padx=self._ui_px(8))
        tk.Label(center, text="Mesero", bg="#111827", fg="#e5e7eb", font=("Arial", self._ui_px(12), "bold")).pack(
            side="left", padx=(0, self._ui_px(4))
        )
        self.mesero_var = tk.StringVar()
        self.mesero_menu = ttk.Combobox(center, textvariable=self.mesero_var, state="readonly", width=17)
        self.mesero_menu.pack(side="left")
        self.mesero_menu.bind("<<ComboboxSelected>>", lambda _e: self._save_current_to_state())
        self.mesero_menu.bind("<Return>", lambda _e: self.search_entry.focus_set() if hasattr(self, "search_entry") else None)
        self.mesero_menu.bind("<Button-1>", lambda _e: self._refresh_meseros_dropdown())

        tk.Label(center, text="Mesa", bg="#111827", fg="#e5e7eb", font=("Arial", self._ui_px(12), "bold")).pack(
            side="left", padx=(self._ui_px(12), self._ui_px(4))
        )
        self.mesa_var = tk.StringVar()
        self.mesa_entry = ttk.Entry(center, textvariable=self.mesa_var, width=8)
        self.mesa_entry.pack(side="left")
        self.mesa_entry.bind("<KeyRelease>", lambda _e: self._save_current_to_state())

        self.mesero_status_var = tk.StringVar(value="")
        tk.Label(
            center,
            textvariable=self.mesero_status_var,
            bg="#111827",
            fg="#fca5a5",
            font=("Arial", self._ui_px(11), "bold"),
        ).pack(side="left", padx=(self._ui_px(10), 0))

        right = tk.Frame(header, bg="#111827")
        right.pack(side="right", padx=self._ui_px(8))
        self.clock_var = tk.StringVar()
        tk.Label(
            right,
            textvariable=self.clock_var,
            bg="#111827",
            fg="#e5e7eb",
            font=("Arial", self._ui_px(12), "bold"),
        ).pack(side="left", padx=(0, self._ui_px(8)))

        self.role_var = tk.StringVar(value="Rol: MESERO")
        tk.Label(
            right,
            textvariable=self.role_var,
            bg="#111827",
            fg="#fbbf24",
            font=("Arial", self._ui_px(12), "bold"),
        ).pack(side="left", padx=(0, self._ui_px(8)))

        self.btn_unlock = ttk.Button(right, text="Desbloquear", style="Accent.TButton", command=self._unlock_role)
        self.btn_unlock.pack(side="left", padx=(0, self._ui_px(6)))
        self.btn_lock = ttk.Button(right, text="Bloquear", command=self._lock_role)
        self.btn_lock.pack(side="left", padx=(0, self._ui_px(6)))

        self.btn_more = ttk.Menubutton(right, text="Mas")
        self.btn_more.pack(side="left", padx=(0, self._ui_px(6)))
        self._setup_more_menu()

        ttk.Button(right, text="Salir", style="Danger.TButton", command=self._exit_app).pack(side="left")

    def _setup_more_menu(self) -> None:
        self.more_menu = tk.Menu(self.btn_more, tearoff=0)
        self._more_menu_indexes: dict[str, int] = {}
        self._add_more_menu_item("gastos", "Gastos", self._open_gastos)
        self._add_more_menu_item("propinas", "Propinas", self._open_propinas)
        self._add_more_menu_item("personal", "Personal", self._open_personal)
        self._add_more_menu_item("productos", "Productos", self._open_productos)
        self._add_more_menu_item("corte", "Corte", self._open_corte)
        self._add_more_menu_item("reportes", "Reportes", self._open_reportes)
        self.more_menu.add_separator()
        self._add_more_menu_item("change_pin", "Cambiar PIN", self._open_change_pin)
        self.btn_more.configure(menu=self.more_menu)

    def _add_more_menu_item(self, key: str, label: str, command) -> None:
        self.more_menu.add_command(label=label, command=command)
        self._more_menu_indexes[key] = int(self.more_menu.index("end"))

    def _build_catalog_panel(self, panel: tk.Widget) -> None:
        panel.grid_columnconfigure(0, weight=1)
        panel.grid_rowconfigure(2, weight=1)

        self.search_var = tk.StringVar()
        self.search_entry = ttk.Entry(panel, textvariable=self.search_var)
        self.search_entry.grid(
            row=0,
            column=0,
            sticky="ew",
            padx=self._ui_px(8),
            pady=(self._ui_px(8), self._ui_px(6)),
        )
        self.search_entry.bind("<KeyRelease>", lambda _e: self._refresh_catalog())
        self.search_entry.bind("<Return>", lambda _e: self._focus_catalog())

        controls = ttk.Frame(panel)
        controls.grid(row=1, column=0, sticky="ew", padx=self._ui_px(8), pady=(0, self._ui_px(6)))
        controls.grid_columnconfigure(1, weight=1)

        ttk.Label(controls, text="Categoria").grid(row=0, column=0, sticky="w")
        cats = sorted({p.get("categoria", "GENERAL") for p in self.productos})
        self.cat_var = tk.StringVar(value="TODAS")
        cat_values = ["TODAS"] + cats
        self.cat_menu = ttk.Combobox(controls, textvariable=self.cat_var, values=cat_values, state="readonly", width=15)
        self.cat_menu.grid(row=0, column=1, sticky="ew", padx=(self._ui_px(6), self._ui_px(8)))
        self.cat_menu.bind("<<ComboboxSelected>>", lambda _e: self._refresh_catalog())

        ttk.Label(controls, text="Cant").grid(row=0, column=2, sticky="w")
        self.qty_var = tk.StringVar(value="1")
        self.qty_entry = ttk.Entry(controls, textvariable=self.qty_var, width=5)
        self.qty_entry.grid(row=0, column=3, sticky="w", padx=(self._ui_px(6), self._ui_px(8)))
        self.qty_entry.bind("<Return>", lambda _e: self._add_selected_product())
        ttk.Button(controls, text="Agregar", style="CatalogAdd.TButton", command=self._add_selected_product).grid(
            row=0, column=4, sticky="e"
        )

        self.catalog_wrap = ttk.Frame(panel)
        self.catalog_wrap.grid(row=2, column=0, sticky="nsew", padx=self._ui_px(8), pady=(0, self._ui_px(8)))
        self.catalog_wrap.grid_columnconfigure(0, weight=1)
        self.catalog_wrap.grid_rowconfigure(0, weight=1)

        self.catalog_canvas = tk.Canvas(self.catalog_wrap, bg="#eef2ff", highlightthickness=0)
        self.catalog_canvas.grid(row=0, column=0, sticky="nsew")
        self.catalog_scroll = ttk.Scrollbar(self.catalog_wrap, orient="vertical", command=self.catalog_canvas.yview)
        self.catalog_scroll.grid(row=0, column=1, sticky="ns")
        self.catalog_canvas.configure(yscrollcommand=self.catalog_scroll.set)

        self.catalog_inner = tk.Frame(self.catalog_canvas, bg="#eef2ff")
        self._catalog_window = self.catalog_canvas.create_window((0, 0), window=self.catalog_inner, anchor="nw")
        self.catalog_inner.bind("<Configure>", self._on_catalog_inner_configure)
        self.catalog_canvas.bind("<Configure>", self._on_catalog_canvas_configure)
        bind_mousewheel(self.catalog_canvas, self.catalog_canvas.yview)
        bind_mousewheel(self.catalog_inner, self.catalog_canvas.yview)
        bind_mousewheel(self.catalog_wrap, self.catalog_canvas.yview)
        self.catalog_card_buttons: list[tk.Widget] = []
        self._selected_catalog_index = 0

    def _build_comanda_panel(self, panel: tk.Widget) -> None:
        panel.grid_columnconfigure(0, weight=1)
        panel.grid_rowconfigure(2, weight=1)

        top = ttk.Frame(panel)
        top.grid(row=0, column=0, sticky="ew", padx=self._ui_px(8), pady=(self._ui_px(8), self._ui_px(6)))
        top.grid_columnconfigure(0, weight=1)
        ttk.Label(top, text="Comanda", style="Header.TLabel").grid(row=0, column=0, sticky="w")
        actions = ttk.Frame(top)
        actions.grid(row=0, column=1, sticky="e")
        ttk.Button(actions, text="Nueva", command=self._new_comanda).pack(side="left", padx=(0, self._ui_px(4)))
        ttk.Button(actions, text="Cerrar", command=self._close_comanda).pack(side="left", padx=(0, self._ui_px(4)))
        self.open_orders_visible = self.open_comandas_mode == "visible"
        self.toggle_orders_var = tk.StringVar()
        self.toggle_orders_btn = ttk.Button(
            actions,
            textvariable=self.toggle_orders_var,
            command=self._toggle_open_orders_panel,
        )
        self.toggle_orders_btn.pack(side="left")

        self.open_orders_panel = tk.Frame(panel, bg="#eef2ff", highlightthickness=1, highlightbackground="#c7d2fe")
        self.open_orders_panel.grid(row=1, column=0, sticky="ew", padx=self._ui_px(8), pady=(0, self._ui_px(6)))
        self.comandas_list = tk.Listbox(
            self.open_orders_panel,
            height=4,
            font=("Arial", self._ui_px(13)),
            activestyle="none",
            selectbackground="#1d4ed8",
            selectforeground="white",
            highlightthickness=0,
        )
        self.comandas_list.pack(fill="x", padx=self._ui_px(6), pady=self._ui_px(6))
        self.comandas_list.bind("<<ListboxSelect>>", lambda _e: self._on_select_comanda())
        self._apply_open_orders_visibility()

        table_frame = ttk.Frame(panel)
        table_frame.grid(row=2, column=0, sticky="nsew", padx=self._ui_px(8), pady=(0, self._ui_px(6)))
        table_frame.grid_columnconfigure(0, weight=1)
        table_frame.grid_rowconfigure(0, weight=1)
        self.tree = ttk.Treeview(table_frame, columns=("dec", "qty", "inc", "prod", "unit", "sub"), show="headings")
        self.tree.heading("dec", text="Quitar")
        self.tree.heading("qty", text="Cant")
        self.tree.heading("inc", text="Sumar")
        self.tree.heading("prod", text="Producto")
        self.tree.heading("unit", text="P.Unit")
        self.tree.heading("sub", text="Subtotal")
        self.tree.column("dec", width=self._ui_px(96), anchor="center")
        self.tree.column("qty", width=self._ui_px(86), anchor="center")
        self.tree.column("inc", width=self._ui_px(96), anchor="center")
        self.tree.column("prod", width=self._ui_px(400), anchor="w")
        self.tree.column("unit", width=self._ui_px(120), anchor="center")
        self.tree.column("sub", width=self._ui_px(125), anchor="center")
        self.tree.grid(row=0, column=0, sticky="nsew")
        self.tree.bind("<Button-1>", self._on_tree_click)
        self.tree.bind("<Delete>", lambda _e: self._remove_selected())
        self.tree.bind("<plus>", lambda _e: self._inc_selected())
        self.tree.bind("<minus>", lambda _e: self._dec_selected())
        self.tree.bind("<Double-Button-1>", self._on_tree_double_click)

        btns = ttk.Frame(panel)
        btns.grid(row=3, column=0, sticky="ew", padx=self._ui_px(8), pady=(0, self._ui_px(6)))
        for col in range(2):
            btns.columnconfigure(col, weight=1)
        ttk.Button(btns, text="Eliminar", style="Touch.TButton", command=self._remove_selected).grid(
            row=0, column=0, padx=(0, self._ui_px(4)), sticky="ew"
        )
        ttk.Button(btns, text="Vaciar", style="Touch.TButton", command=self._clear_all).grid(
            row=0, column=1, sticky="ew"
        )

        cobro = tk.Frame(panel, bg="#f3f4f6")
        cobro.grid(row=4, column=0, sticky="ew", padx=self._ui_px(8), pady=(0, self._ui_px(8)))
        self._build_cobro_panel(cobro)

    def _build_cobro_panel(self, panel: tk.Widget) -> None:
        pay = tk.Frame(panel, bg="#e5e7eb")
        pay.pack(fill="x")
        self.total_var = tk.StringVar(value="0.00")
        tk.Label(
            pay,
            text="TOTAL:",
            font=("Arial", self._ui_px(20), "bold"),
            fg="#111827",
            bg="#e5e7eb",
        ).pack(side="left", padx=self._ui_px(8), pady=self._ui_px(6))
        tk.Label(
            pay,
            textvariable=self.total_var,
            font=("Arial", self._ui_px(26), "bold"),
            fg="#dc2626",
            bg="#e5e7eb",
        ).pack(side="left")

        pay2 = ttk.Frame(panel)
        pay2.pack(fill="x", pady=(self._ui_px(6), 0))
        ttk.Label(pay2, text="Metodo:").pack(side="left")
        self.metodo_var = tk.StringVar(value="EFECTIVO")
        metodo = ttk.Combobox(
            pay2,
            textvariable=self.metodo_var,
            values=["EFECTIVO", "TARJETA", "TRANSFER"],
            state="readonly",
            width=12,
        )
        metodo.pack(side="left", padx=self._ui_px(8))
        metodo.bind("<<ComboboxSelected>>", lambda _e: self._toggle_cash_fields())

        ttk.Label(pay2, text="Propina:").pack(side="left", padx=(self._ui_px(12), 0))
        self.propina_var = tk.StringVar()
        self.propina_entry = ttk.Entry(pay2, textvariable=self.propina_var, width=10)
        self.propina_entry.pack(side="left", padx=self._ui_px(8))
        self.propina_entry.bind("<Return>", lambda _e: self._save_comanda())
        self.propina_entry.bind("<KeyRelease>", lambda _e: self._save_current_to_state())

        self.cash_frame = ttk.Frame(panel)
        self.cash_frame.pack(fill="x", pady=(self._ui_px(6), 0))
        ttk.Label(self.cash_frame, text="Recibido:").pack(side="left")
        self.recibido_var = tk.StringVar()
        self.recibido_entry = ttk.Entry(self.cash_frame, textvariable=self.recibido_var, width=12)
        self.recibido_entry.pack(side="left", padx=self._ui_px(8))
        self.recibido_entry.bind("<KeyRelease>", lambda _e: self._update_change())
        self.recibido_entry.bind("<Return>", lambda _e: self._save_comanda())
        ttk.Label(self.cash_frame, text="Cambio:").pack(side="left", padx=(self._ui_px(12), 0))
        self.cambio_var = tk.StringVar(value="0.00")
        ttk.Label(
            self.cash_frame,
            textvariable=self.cambio_var,
            font=("Arial", self._ui_px(15), "bold"),
        ).pack(side="left", padx=self._ui_px(8))

        self._toggle_cash_fields()
        self.save_btn = ttk.Button(panel, text="GUARDAR COMANDA", style="Accent.TButton", command=self._save_comanda)
        self.save_btn.pack(fill="x", pady=(self._ui_px(8), self._ui_px(6)))

    def _set_initial_pane_split(self) -> None:
        try:
            width = self.main_pane.winfo_width()
            if width <= 1:
                self.after(100, self._set_initial_pane_split)
                return
            self.main_pane.sash_place(0, int(width * 0.45), 0)
        except Exception:
            pass

    def _apply_open_orders_visibility(self) -> None:
        if self.open_orders_visible:
            self.open_orders_panel.grid()
            self.toggle_orders_var.set("Ocultar comandas")
        else:
            self.open_orders_panel.grid_remove()
            self.toggle_orders_var.set("Mostrar comandas")

    def _toggle_open_orders_panel(self) -> None:
        self.open_orders_visible = not self.open_orders_visible
        self._apply_open_orders_visibility()

    # ---------------- Logic ----------------
    def _bind_shortcuts(self):
        # Atajos globales para flujo rápido
        self.bind_all("<Control-s>", lambda _e: self._save_comanda())
        self.bind_all("<Control-n>", lambda _e: self._new_comanda())
        self.bind_all("<Control-f>", lambda _e: self.search_entry.focus_set())
        self.bind_all("<Control-m>", lambda _e: self.mesero_menu.focus_set())
        self.bind_all("<Control-d>", lambda _e: self._remove_selected())
        self.bind_all("<Control-l>", lambda _e: self._clear_all())
        self.bind_all("<Control-plus>", lambda _e: self._inc_selected())
        self.bind_all("<Control-equal>", lambda _e: self._inc_selected())
        self.bind_all("<Control-minus>", lambda _e: self._dec_selected())
        self.bind_all("<Control-q>", lambda _e: self._exit_app())

    def _apply_role_to_ui(self):
        role = self.auth.current_role()
        self.role_var.set(f"Rol: {role.label}")
        self.btn_lock.configure(state=("disabled" if role == Role.MESERO else "normal"))

        menu_permissions = {
            "gastos": self.auth.can(Permission.GASTOS),
            "propinas": self.auth.can(Permission.PROPINAS),
            "corte": self.auth.can(Permission.CORTE),
            "reportes": self.auth.can(Permission.REPORTES),
            "personal": self.auth.can(Permission.PERSONAL),
            "productos": self.auth.can(Permission.PRODUCTOS),
        }
        for key, enabled in menu_permissions.items():
            idx = self._more_menu_indexes.get(key)
            if idx is not None:
                self.more_menu.entryconfigure(idx, state=("normal" if enabled else "disabled"))

        change_pin_idx = self._more_menu_indexes.get("change_pin")
        if change_pin_idx is not None:
            self.more_menu.entryconfigure(
                change_pin_idx,
                state=("disabled" if role == Role.MESERO else "normal"),
            )

    def _unlock_role(self):
        result = ask_unlock(self, self.auth)
        if not result:
            return
        self._apply_role_to_ui()

    def _lock_role(self):
        self.auth.lock()
        self._apply_role_to_ui()

    def _ensure_permission(self, permission: Permission, action_label: str) -> bool:
        if self.auth.can(permission):
            return True
        messagebox.showwarning(
            "Sin permisos",
            f"No tienes permisos para {action_label}.\nDesbloquea un perfil con privilegios.",
        )
        return False

    def _sync_loop(self):
        if self._sync_in_progress:
            return

        self._sync_in_progress = True
        root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

        def _job():
            try:
                self.db.sync_offline()
                self.db.offline.daily_backup(root_dir)
            except Exception:
                pass
            try:
                self.after(0, self._finish_sync_loop)
            except Exception:
                pass

        threading.Thread(target=_job, daemon=True, name="offline-sync").start()

    def _finish_sync_loop(self):
        self._sync_in_progress = False
        self.after(30000, self._sync_loop)

    def _exit_app(self):
        if messagebox.askyesno("Salir", "¿Cerrar el POS?"):
            self.destroy()

    def _tick_clock(self):
        self.clock_var.set(datetime.now().strftime("%H:%M:%S"))
        self.after(1000, self._tick_clock)

    def _focus_catalog(self):
        if self.catalog_card_buttons:
            self._selected_catalog_index = 0
            self.catalog_card_buttons[0].focus_set()

    def _on_catalog_inner_configure(self, _event=None):
        self.catalog_canvas.configure(scrollregion=self.catalog_canvas.bbox("all"))

    def _on_catalog_canvas_configure(self, event):
        self.catalog_canvas.itemconfigure(self._catalog_window, width=event.width)
        self._render_catalog_cards()

    def _on_catalog_mousewheel(self, event):
        if not hasattr(self, "catalog_canvas"):
            return
        if not self.catalog_canvas.winfo_ismapped():
            return
        delta = getattr(event, "delta", 0)
        if delta == 0:
            return
        self.catalog_canvas.yview_scroll(int(-1 * (delta / 120)), "units")

    def _category_color(self, category: str) -> str:
        palette = [
            "#2563eb",
            "#0891b2",
            "#16a34a",
            "#ca8a04",
            "#dc2626",
            "#7c3aed",
            "#db2777",
            "#0f766e",
        ]
        seed = sum(ord(ch) for ch in category.upper())
        return palette[seed % len(palette)]

    def _bind_catalog_mousewheel(self, widget: tk.Misc) -> None:
        bind_mousewheel(widget, self.catalog_canvas.yview)
        for child in widget.winfo_children():
            self._bind_catalog_mousewheel(child)

    def _product_badge(self, product: dict) -> str:
        nombre = str(product.get("nombre") or "").strip()
        if not nombre:
            return "PR"
        chunks = [part[0] for part in nombre.split() if part]
        if len(chunks) >= 2:
            return (chunks[0] + chunks[1]).upper()
        if len(nombre) >= 2:
            return nombre[:2].upper()
        return nombre[0].upper()

    def _format_weight_label(self, grams: int) -> str:
        if grams == 500:
            return "1/2 kg"
        if grams >= 1000:
            kilos = grams / 1000.0
            kilos_txt = f"{kilos:.2f}".rstrip("0").rstrip(".")
            return f"{kilos_txt} kg"
        return f"{grams} g"

    def _gramaje_var_for_producto(self, producto_id: int) -> tk.StringVar:
        if producto_id not in self._gramaje_vars:
            self._gramaje_vars[producto_id] = tk.StringVar(value="500")
        return self._gramaje_vars[producto_id]

    def _parse_weight_grams(self, raw: str) -> int | None:
        try:
            grams = int((raw or "").strip())
        except Exception:
            return None
        if grams <= 0:
            return None
        return grams

    def _render_catalog_cards(self):
        if not hasattr(self, "catalog_inner"):
            return

        for child in self.catalog_inner.winfo_children():
            child.destroy()
        self.catalog_card_buttons = []

        if not self.filtered:
            empty = tk.Label(
                self.catalog_inner,
                text="No hay productos para este filtro",
                bg="#eef2ff",
                fg="#374151",
                font=("Arial", self._ui_px(12), "bold"),
            )
            empty.grid(row=0, column=0, padx=self._ui_px(12), pady=self._ui_px(12), sticky="w")
            return

        canvas_width = max(self.catalog_canvas.winfo_width(), self._ui_px(320))
        card_w = self._ui_px(185)
        card_h = self._ui_px(150)
        gap = self._ui_px(8)
        cols = max(2, canvas_width // (card_w + gap))

        for col in range(cols):
            self.catalog_inner.grid_columnconfigure(col, weight=1)

        for idx, p in enumerate(self.filtered):
            row = idx // cols
            col = idx % cols
            categoria = str(p.get("categoria", "GENERAL"))
            accent = self._category_color(categoria)
            is_by_weight = bool(p.get("venta_por_gramo"))

            card = tk.Frame(
                self.catalog_inner,
                bg="#ffffff",
                bd=1,
                relief="solid",
                highlightthickness=1,
                highlightbackground=accent,
            )
            card.grid(row=row, column=col, padx=gap // 2, pady=gap // 2, sticky="nsew")
            card.configure(width=card_w, height=(self._ui_px(190) if is_by_weight else card_h))
            card.grid_propagate(False)

            cat_chip = tk.Label(
                card,
                text=categoria[:14],
                bg=accent,
                fg="white",
                font=("Arial", self._ui_px(11), "bold"),
                anchor="w",
                padx=self._ui_px(6),
            )
            cat_chip.pack(fill="x")

            top = tk.Frame(card, bg="#ffffff")
            top.pack(fill="both", expand=True, padx=self._ui_px(6), pady=(self._ui_px(5), self._ui_px(2)))

            badge = tk.Label(
                top,
                text=self._product_badge(p),
                width=4,
                bg="#e0e7ff",
                fg="#1e3a8a",
                font=("Arial", self._ui_px(12), "bold"),
                relief="ridge",
                bd=1,
            )
            badge.pack(anchor="w")

            name_lbl = tk.Label(
                top,
                text=str(p.get("nombre") or "Producto"),
                bg="#ffffff",
                fg="#111827",
                font=("Arial", self._ui_px(15), "bold"),
                justify="left",
                wraplength=card_w - self._ui_px(12),
                anchor="w",
            )
            name_lbl.pack(fill="x", pady=(self._ui_px(4), self._ui_px(2)))

            price_lbl = tk.Label(
                top,
                text=f"${float(p.get('precio') or 0):.2f}",
                bg="#ffffff",
                fg="#dc2626",
                font=("Arial", self._ui_px(17), "bold"),
                anchor="w",
            )
            price_lbl.pack(fill="x")
            if is_by_weight:
                tk.Label(
                    top,
                    text="Precio por kg",
                    bg="#ffffff",
                    fg="#475569",
                    font=("Arial", self._ui_px(10), "bold"),
                    anchor="w",
                ).pack(fill="x")
                grams_row = tk.Frame(card, bg="#ffffff")
                grams_row.pack(fill="x", padx=self._ui_px(6), pady=(0, self._ui_px(4)))
                tk.Label(
                    grams_row,
                    text="Gramaje:",
                    bg="#ffffff",
                    fg="#334155",
                    font=("Arial", self._ui_px(10), "bold"),
                ).pack(side="left")
                product_id = int(p.get("id") or 0)
                grams_var = self._gramaje_var_for_producto(product_id)
                grams_entry = ttk.Entry(grams_row, textvariable=grams_var, width=5, justify="center")
                grams_entry.pack(side="left", padx=(self._ui_px(4), self._ui_px(4)))
                grams_entry.bind("<Return>", lambda _e, prod=p, i=idx: self._add_product_from_catalog(prod, i))
                tk.Label(
                    grams_row,
                    text="g",
                    bg="#ffffff",
                    fg="#334155",
                    font=("Arial", self._ui_px(10), "bold"),
                ).pack(side="left")

                preset_var = tk.StringVar(value="1/2 kg")
                preset_menu = ttk.Combobox(
                    grams_row,
                    textvariable=preset_var,
                    values=["100 g", "250 g", "1/2 kg", "1 kg"],
                    state="readonly",
                    width=6,
                )
                preset_menu.pack(side="left", padx=(self._ui_px(4), 0))

                def _on_preset(_event=None, *, grams_text_var=grams_var, choice_var=preset_var):
                    preset_map = {"100 g": 100, "250 g": 250, "1/2 kg": 500, "1 kg": 1000}
                    grams_value = preset_map.get((choice_var.get() or "").strip())
                    if grams_value:
                        grams_text_var.set(str(grams_value))

                preset_menu.bind("<<ComboboxSelected>>", _on_preset)

            add_btn = ttk.Button(
                card,
                text="Agregar",
                style="CatalogAdd.TButton",
                command=lambda prod=p, i=idx: self._add_product_from_catalog(prod, i),
            )
            add_btn.pack(fill="x", padx=self._ui_px(6), pady=(0, self._ui_px(6)))
            self.catalog_card_buttons.append(add_btn)
            self._bind_catalog_mousewheel(card)

            for widget in (card, top, badge, cat_chip, name_lbl, price_lbl):
                widget.bind(
                    "<Button-1>",
                    lambda _e, prod=p, i=idx: self._add_product_from_catalog(prod, i),
                )

    def _comanda_snapshot(self) -> dict:
        return {
            "folio_local": self.comandas[self.active_comanda].get("folio_local") if self.active_comanda is not None else None,
            "created_at": self.comandas[self.active_comanda].get("created_at") if self.active_comanda is not None else None,
            "mesero": self.mesero_var.get().strip(),
            "mesa": self.mesa_var.get().strip(),
            "metodo": self.metodo_var.get(),
            "propina": self.propina_var.get().strip(),
            "recibido": self.recibido_var.get().strip(),
            "items": [it.copy() for it in self.items],
        }

    def _apply_snapshot(self, snap: dict):
        self.mesero_var.set(snap.get("mesero", ""))
        self.mesa_var.set(snap.get("mesa", ""))
        self.metodo_var.set(snap.get("metodo", "EFECTIVO"))
        self.propina_var.set(snap.get("propina", ""))
        self.recibido_var.set(snap.get("recibido", ""))
        self.items = [it.copy() for it in snap.get("items", [])]
        self._toggle_cash_fields()
        self._refresh_ticket()

    def _save_current_to_state(self):
        if self.active_comanda is None:
            return
        self.comandas[self.active_comanda] = self._comanda_snapshot()
        self._update_comandas_list()
        self._persist_comandas()

    def _new_comanda(self):
        if self.active_comanda is not None:
            self._save_current_to_state()
        default_mesa = self._next_mesa_default()
        self.comandas.append({
            "folio_local": f"TMP-{datetime.now().strftime('%H%M%S')}",
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "mesero": self.mesero_var.get().strip(),
            "mesa": default_mesa,
            "metodo": "EFECTIVO",
            "propina": "",
            "recibido": "",
            "items": [],
        })
        self.active_comanda = len(self.comandas) - 1
        self._apply_snapshot(self.comandas[self.active_comanda])
        self._update_comandas_list()
        self._persist_comandas()

    def _on_select_comanda(self):
        sel = self.comandas_list.curselection()
        if not sel:
            return
        idx = sel[0]
        if idx == self.active_comanda:
            return
        self._save_current_to_state()
        self.active_comanda = idx
        self._apply_snapshot(self.comandas[idx])
        self._persist_comandas()

    def _update_comandas_list(self):
        self.comandas_list.delete(0, tk.END)
        for i, c in enumerate(self.comandas):
            total = calcular_total(c.get("items", [])) if c.get("items") else 0.0
            mesero = c.get("mesero") or "Sin mesero"
            mesa = c.get("mesa") or "-"
            folio = c.get("folio_local") or f"{i+1}"
            marker = "*" if i == self.active_comanda else " "
            label = f"{marker} {folio} | Mesa {mesa} - {mesero} - ${total:.2f}"
            self.comandas_list.insert(tk.END, label)
            bg = "#ffffff" if i % 2 == 0 else "#f3f4f6"
            self.comandas_list.itemconfig(i, bg=bg)
        if self.active_comanda is not None and self.comandas_list.size() > 0:
            self.comandas_list.selection_clear(0, tk.END)
            self.comandas_list.selection_set(self.active_comanda)
            self.comandas_list.activate(self.active_comanda)

    def _next_mesa_default(self) -> str:
        # Busca el último número de mesa usado y suma 1
        last = 0
        for c in self.comandas:
            mesa = str(c.get("mesa") or "").strip()
            if mesa.isdigit():
                last = max(last, int(mesa))
        return str(last + 1) if last else "1"

    def _close_comanda(self):
        if self.active_comanda is None:
            return
        if not messagebox.askyesno("Cerrar comanda", "¿Descartar esta comanda sin guardar?"):
            return
        self.comandas.pop(self.active_comanda)
        if self.comandas:
            self.active_comanda = min(self.active_comanda, len(self.comandas) - 1)
            self._apply_snapshot(self.comandas[self.active_comanda])
        else:
            self.active_comanda = None
            self.items = []
            self._refresh_ticket()
            self._new_comanda()
        self._persist_comandas()

    def _persist_comandas(self):
        data = {
            "active_index": self.active_comanda,
            "comandas": self.comandas,
        }
        try:
            os.makedirs(os.path.dirname(self._comandas_path), exist_ok=True)
            with open(self._comandas_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
        except Exception:
            pass

    def _load_comandas(self):
        try:
            with open(self._comandas_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.comandas = data.get("comandas") or []
            self.active_comanda = data.get("active_index")
        except Exception:
            self.comandas = []
            self.active_comanda = None

        if not self.comandas:
            self._new_comanda()
            return

        if self.active_comanda is None or not (0 <= self.active_comanda < len(self.comandas)):
            self.active_comanda = 0
        self._apply_snapshot(self.comandas[self.active_comanda])
        self._update_comandas_list()

    def _refresh_catalog(self):
        q = self.search_var.get().strip().lower()
        cat = self.cat_var.get()

        self.filtered = []

        for p in self.productos:
            if not p.get("activo", True):
                continue
            pcat = p.get("categoria", "GENERAL")
            if cat != "TODAS" and pcat != cat:
                continue
            if q and (q not in p["nombre"].lower()) and (q not in pcat.lower()):
                continue
            self.filtered.append(p)
        self.filtered.sort(
            key=lambda p: (
                int(p.get("orden_catalogo") or 1000),
                str(p.get("categoria") or "GENERAL"),
                str(p.get("nombre") or ""),
            )
        )
        self._render_catalog_cards()

    def _add_selected_product(self):
        if not self.filtered:
            messagebox.showwarning("Sin productos", "No hay productos disponibles para agregar.")
            return
        idx = min(self._selected_catalog_index, len(self.filtered) - 1)
        self._add_product_from_catalog(self.filtered[idx], idx)

    def _add_product_from_catalog(self, product: dict, index: int):
        self._selected_catalog_index = max(0, index)
        try:
            qty = int(self.qty_var.get().strip())
            if qty <= 0:
                raise ValueError
        except Exception:
            messagebox.showwarning("Cantidad inválida", "Cantidad debe ser entero > 0.")
            return

        unit = float(product["precio"])
        nombre_snapshot = str(product.get("nombre") or "Producto")
        if bool(product.get("venta_por_gramo")):
            product_id = int(product.get("id") or 0)
            grams_var = self._gramaje_var_for_producto(product_id)
            gramos = self._parse_weight_grams(grams_var.get())
            if gramos is None:
                messagebox.showwarning(
                    "Peso inválido",
                    "Para este producto escribe un gramaje válido en su tarjeta (ej. 100, 250, 500, 1000).",
                )
                return
            unit = round((unit * gramos) / 1000.0, 2)
            nombre_snapshot = f"{nombre_snapshot} ({self._format_weight_label(gramos)})"

        sub = calcular_subtotal(unit, qty)
        self.items.append({
            "producto_id": product["id"],
            "nombre_snapshot": nombre_snapshot,
            "precio_unitario": unit,
            "cantidad": qty,
            "subtotal": sub,
        })
        self._refresh_ticket()
        self._save_current_to_state()

    def _refresh_ticket(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        for idx, it in enumerate(self.items):
            tag = "even" if idx % 2 == 0 else "odd"
            self.tree.insert(
                "", "end", iid=str(idx),
                values=(
                    "[ - ]",
                    it["cantidad"],
                    "[ + ]",
                    it["nombre_snapshot"],
                    f"${float(it['precio_unitario']):.2f}",
                    f"${float(it['subtotal']):.2f}",
                ),
                tags=(tag,),
            )
        self.tree.tag_configure("even", background="#ffffff")
        self.tree.tag_configure("odd", background="#f3f4f6")
        total = calcular_total(self.items) if self.items else 0.0
        self.total_var.set(f"${total:.2f}")
        self._update_change()
        self._update_comandas_list()

    def _remove_selected(self):
        sel = self.tree.selection()
        if not sel:
            return
        idx = int(sel[0])
        if 0 <= idx < len(self.items):
            self.items.pop(idx)
            self._refresh_ticket()
            self._save_current_to_state()

    def _clear_all(self):
        self.items = []
        self._refresh_ticket()
        if hasattr(self, "propina_var"):
            self.propina_var.set("")
        self.mesero_menu.focus_set()
        self._save_current_to_state()

    def _inc_selected(self):
        sel = self.tree.selection()
        if not sel:
            return
        idx = int(sel[0])
        if 0 <= idx < len(self.items):
            it = self.items[idx]
            it["cantidad"] = int(it["cantidad"]) + 1
            it["subtotal"] = calcular_subtotal(it["precio_unitario"], it["cantidad"])
            self._refresh_ticket()
            self._save_current_to_state()

    def _dec_selected(self):
        sel = self.tree.selection()
        if not sel:
            return
        idx = int(sel[0])
        if 0 <= idx < len(self.items):
            it = self.items[idx]
            qty = int(it["cantidad"]) - 1
            if qty <= 0:
                self.items.pop(idx)
            else:
                it["cantidad"] = qty
                it["subtotal"] = calcular_subtotal(it["precio_unitario"], it["cantidad"])
            self._refresh_ticket()
            self._save_current_to_state()

    def _on_tree_click(self, event):
        row_id = self.tree.identify_row(event.y)
        col = self.tree.identify_column(event.x)
        if not row_id:
            return
        self.tree.selection_set(row_id)
        self.tree.focus(row_id)
        if col == "#1":
            self._dec_selected()
            return "break"
        if col == "#3":
            self._inc_selected()
            return "break"

    def _on_tree_double_click(self, event):
        row_id = self.tree.identify_row(event.y)
        if not row_id:
            return
        col = self.tree.identify_column(event.x)
        # Solo editar cantidad (columna Cant = #2)
        if col != "#2":
            return
        idx = int(row_id)
        if not (0 <= idx < len(self.items)):
            return
        it = self.items[idx]

        editor = ttk.Entry(self.tree)
        editor.insert(0, str(it.get("cantidad", "")))
        editor.select_range(0, tk.END)
        editor.focus_set()

        def _commit(_e=None):
            try:
                qty = int(editor.get().strip())
                if qty <= 0:
                    raise ValueError
            except Exception:
                editor.destroy()
                return
            it["cantidad"] = qty
            it["subtotal"] = calcular_subtotal(it["precio_unitario"], it["cantidad"])
            editor.destroy()
            self._refresh_ticket()
            self._save_current_to_state()

        def _cancel(_e=None):
            editor.destroy()

        editor.bind("<Return>", _commit)
        editor.bind("<Escape>", _cancel)
        editor.bind("<FocusOut>", _commit)

        x, y, w, h = self.tree.bbox(row_id, col)
        editor.place(x=x, y=y, width=w, height=h)

    def _toggle_cash_fields(self):
        if self.metodo_var.get() == "EFECTIVO":
            self.cash_frame.pack(fill="x", pady=(self._ui_px(8), 0))
        else:
            self.cash_frame.pack_forget()
            self.recibido_var.set("")
            self.cambio_var.set("0.00")
        self._save_current_to_state()

    def _update_change(self):
        if self.metodo_var.get() != "EFECTIVO":
            return
        total = calcular_total(self.items) if self.items else 0.0
        txt = self.recibido_var.get().strip()
        if not txt:
            self.cambio_var.set("0.00")
            return
        try:
            recibido = float(txt)
        except Exception:
            self.cambio_var.set("0.00")
            return
        self.cambio_var.set(f"{(recibido - total):.2f}")

    def _save_comanda(self):
        if not self._meseros_activos:
            messagebox.showwarning(
                "Meseros requeridos",
                "No hay meseros activos.\nDesbloquea gerente/dueño para crear o activar personal.",
            )
            return

        if not self.items:
            messagebox.showwarning("Comanda vacía", "Agrega productos antes de guardar.")
            return

        mesero = self.mesero_var.get().strip()
        if not mesero or mesero not in self._meseros_activos:
            messagebox.showwarning("Mesero inválido", "Selecciona un mesero activo de la lista.")
            return
        metodo = self.metodo_var.get()
        total = calcular_total(self.items)

        propina_txt = (self.propina_var.get().strip() if hasattr(self, "propina_var") else "")
        propina = 0.0
        if propina_txt:
            try:
                propina = float(propina_txt)
                if propina < 0:
                    raise ValueError
            except Exception:
                messagebox.showwarning("Propina inválida", "La propina debe ser un número >= 0.")
                return

        recibido = None
        cambio = None

        if metodo == "EFECTIVO":
            try:
                recibido = float(self.recibido_var.get().strip())
            except Exception:
                messagebox.showwarning("Recibido inválido", "Escribe cuánto recibiste.")
                return
            if recibido < total:
                messagebox.showwarning("Insuficiente", "El recibido debe ser >= total.")
                return
            cambio = recibido - total

        try:
            self.logger.info("save_comanda:start metodo=%s total=%.2f mesero=%s", metodo, total, mesero)
            result = self.db.guardar_comanda(mesero, metodo, total, recibido, cambio, self.items, propina)
            ticket_path, ticket_text = self._create_ticket(result, mesero, metodo, total, propina)
            if result.get("offline"):
                messagebox.showinfo("OK", f"Comanda guardada localmente.\nTotal: ${total:.2f}\nMétodo: {metodo}")
            else:
                messagebox.showinfo("OK", f"Comanda guardada.\nTotal: ${total:.2f}\nMétodo: {metodo}")
            self._maybe_print_ticket(ticket_text)
            self._show_ticket_preview(ticket_text, ticket_path)
            # Cerrar comanda actual y abrir una nueva
            if self.active_comanda is not None:
                self.comandas.pop(self.active_comanda)
                if self.comandas:
                    self.active_comanda = min(self.active_comanda, len(self.comandas) - 1)
                    self._apply_snapshot(self.comandas[self.active_comanda])
                else:
                    self.active_comanda = None
                    self.items = []
                    self._refresh_ticket()
            self._persist_comandas()
            self._new_comanda()
            self.logger.info("save_comanda:done folio=%s", result.get("folio"))
        except Exception as e:
            self.logger.exception("save_comanda:error")
            messagebox.showerror("Error", f"No se pudo guardar en Supabase:\n{e}")

    # ---------------- Dialogs ----------------
    def _focus_existing_admin_dialog(self, key: str) -> bool:
        dlg = self._admin_dialogs.get(key)
        if dlg is None:
            return False
        try:
            if int(dlg.winfo_exists()):
                dlg.deiconify()
                dlg.lift()
                dlg.focus_force()
                try:
                    dlg.grab_set()
                except Exception:
                    pass
                return True
        except Exception:
            pass
        self._admin_dialogs.pop(key, None)
        return False

    def _open_admin_dialog(
        self,
        key: str,
        factory: Callable[[], tk.Toplevel],
        *,
        on_close: Callable[[], None] | None = None,
    ) -> None:
        if self._focus_existing_admin_dialog(key):
            return
        dlg = factory()
        self._admin_dialogs[key] = dlg
        try:
            self.wait_window(dlg)
        finally:
            if self._admin_dialogs.get(key) is dlg:
                self._admin_dialogs.pop(key, None)
            if on_close is not None:
                on_close()

    def _open_gastos(self):
        if not self._ensure_permission(Permission.GASTOS, "abrir Gastos"):
            return
        self._open_admin_dialog("gastos", lambda: GastosDialog(self, self.db))

    def _open_propinas(self):
        if not self._ensure_permission(Permission.PROPINAS, "abrir Propinas"):
            return
        self._open_admin_dialog("propinas", lambda: PropinasDialog(self, self.db))

    def _open_corte(self):
        if not self._ensure_permission(Permission.CORTE, "abrir Corte"):
            return
        self._open_admin_dialog(
            "corte",
            lambda: CorteView(self, self.db, self.auth),
            on_close=self._apply_role_to_ui,
        )

    def _open_reportes(self):
        if not self._ensure_permission(Permission.REPORTES, "abrir Reportes"):
            return
        self._open_admin_dialog("reportes", lambda: ReportesView(self, self.db))

    def _open_personal(self):
        if not self._ensure_permission(Permission.PERSONAL, "abrir Personal"):
            return
        self._open_admin_dialog(
            "personal",
            lambda: PersonalDialog(self, self.db),
            on_close=lambda: self._refresh_meseros_dropdown(force=True),
        )

    def _open_productos(self):
        if not self._ensure_permission(Permission.PRODUCTOS, "abrir Productos"):
            return
        self._open_admin_dialog(
            "productos",
            lambda: ProductosDialog(self, self.db),
            on_close=self._reload_productos_catalogo,
        )

    def _open_change_pin(self):
        role = self.auth.current_role()
        if role == Role.MESERO:
            messagebox.showwarning(
                "Sin perfil",
                "Desbloquea GERENTE o DUEÑO para cambiar PIN.",
            )
            return
        self._open_admin_dialog(
            "change_pin",
            lambda: ChangePinDialog(self, self.db, self.auth, role),
            on_close=self._apply_role_to_ui,
        )

    def _reload_productos_catalogo(self):
        self.productos = self.db.get_productos()
        self._refresh_catalog()
        self._apply_role_to_ui()

    def _refresh_meseros_dropdown(self, *, force: bool = False):
        now = pytime.monotonic()
        if (
            not force
            and self._meseros_activos
            and (now - self._meseros_last_refresh_at) < self._meseros_refresh_ttl_s
        ):
            return
        try:
            meseros = self.db.listar_meseros_activos()
            nombres = [m.get("nombre") for m in meseros if m.get("nombre")]
            self._meseros_last_refresh_at = now
        except Exception:
            nombres = list(self._meseros_activos)
        current = self.mesero_var.get().strip()
        self._meseros_activos = nombres
        self.mesero_menu.configure(values=nombres)
        if current in nombres:
            self.mesero_var.set(current)
        elif nombres:
            self.mesero_var.set(nombres[0])
        else:
            self.mesero_var.set("")
        self._update_mesero_gate()

    def _update_mesero_gate(self):
        if not hasattr(self, "save_btn"):
            return
        if self._meseros_activos:
            self.save_btn.configure(state="normal")
            self.mesero_status_var.set("")
            return
        self.save_btn.configure(state="disabled")
        self.mesero_status_var.set("Sin meseros activos")

    def _create_ticket(self, comanda: dict, mesero: str, metodo: str, total: float, propina: float) -> tuple[str, str]:
        if not self._ticket_save_enabled():
            return "", build_ticket_text({
                "negocio": "Barbacoa de Miranda",
                "folio": comanda.get("folio") or f"LOCAL-{datetime.now().strftime('%Y%m%d%H%M%S')}",
                "fecha_hora": datetime.now(),
                "mesa": self.mesa_var.get().strip() if hasattr(self, "mesa_var") else "",
                "mesero": mesero,
                "metodo_pago": metodo,
                "propina": propina or 0,
                "total": total,
                "items": list(self.items),
            })
        folio = comanda.get("folio")
        ts = datetime.now()
        if not folio:
            folio = f"LOCAL-{ts.strftime('%Y%m%d%H%M%S')}"

        payload = {
            "negocio": "Barbacoa de Miranda",
            "folio": folio,
            "fecha_hora": ts,
            "mesa": self.mesa_var.get().strip() if hasattr(self, "mesa_var") else "",
            "mesero": mesero,
            "metodo_pago": metodo,
            "propina": propina or 0,
            "total": total,
            "items": list(self.items),
        }
        ticket_text = build_ticket_text(payload)

        base = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "exports", "tickets"))
        os.makedirs(base, exist_ok=True)
        filename = os.path.join(base, f"ticket_{folio}.txt")
        with open(filename, "w", encoding="utf-8") as f:
            f.write(ticket_text)
        return filename, ticket_text

    def _maybe_print_ticket(self, ticket_text: str):
        if not should_autoprint():
            return
        def _job():
            try:
                self.logger.info("print_ticket:start")
                print_ticket_text(ticket_text)
                self.logger.info("print_ticket:done")
            except Exception as e:
                self.logger.exception("print_ticket:error")
                self.after(0, lambda: messagebox.showerror("Impresión", f"No se pudo imprimir el ticket:\n{e}"))

        threading.Thread(target=_job, daemon=True).start()

    def _show_ticket_preview(self, ticket_text: str, ticket_path: str):
        if not self._ticket_preview_enabled():
            return
        TicketPreview(self, ticket_text, ticket_path if ticket_path else None)

    def _ticket_preview_enabled(self) -> bool:
        raw = os.getenv("BARBACOA_TICKET_PREVIEW")
        if raw is None:
            return True
        return raw.strip().lower() in {"1", "true", "yes", "on"}

    def _ticket_save_enabled(self) -> bool:
        raw = os.getenv("BARBACOA_TICKET_SAVE")
        if raw is None:
            return True
        return raw.strip().lower() in {"1", "true", "yes", "on"}


    def _load_data_async(self):
        # Creamos un hilo para que no bloquee el renderizado
        def task():
            try:
                # La petición pesada ocurre aquí (background)
                data = self.db.get_productos()
                # Una vez que tenemos la data, actualizamos la UI en el hilo principal
                self.after(0, lambda: self._update_ui_with_data(data))
            except Exception as e:
                print(f"Error en el hyperespacio: {e}")

        threading.Thread(target=task, daemon=True).start()


if __name__ == "__main__":
    def _setup_logging() -> None:
        base = os.path.abspath(os.path.join(os.path.dirname(__file__), "data", "logs"))
        os.makedirs(base, exist_ok=True)
        logfile = os.path.join(base, "pos.log")
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(levelname)s %(name)s: %(message)s",
            handlers=[logging.FileHandler(logfile, encoding="utf-8"), logging.StreamHandler(sys.stdout)],
        )

        def _excepthook(exc_type, exc, tb):
            logging.getLogger("barbacoa.pos").exception("uncaught", exc_info=(exc_type, exc, tb))

        sys.excepthook = _excepthook
        if hasattr(threading, "excepthook"):
            def _thread_excepthook(args):
                logging.getLogger("barbacoa.pos").exception("thread_uncaught", exc_info=(args.exc_type, args.exc_value, args.exc_traceback))
            threading.excepthook = _thread_excepthook

    _setup_logging()
    app = POSApp()
    app.mainloop()
