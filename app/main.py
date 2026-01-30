import json
import os
from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox
import customtkinter as ctk

from services.supabase_service import SupabaseService
from domain.calc import calcular_subtotal, calcular_total
from ui.assets import load_logo
from ui.gastos_dialog import GastosDialog
from ui.propinas_dialog import PropinasDialog
from ui.corte_view import CorteView
from ui.reportes_view import ReportesView


class POSApp(tk.Tk):
    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("light")
        self.title("Barbacoa POS")
        self.geometry("1100x700")
        self.attributes("-fullscreen", True)
        self.bind("<Escape>", lambda _e: self.attributes("-fullscreen", False))

        # Estilo ttk (se ve pro)
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure("TButton", padding=8, font=("Arial", 10, "bold"))
        style.configure("Accent.TButton", padding=10, font=("Arial", 11, "bold"), foreground="white", background="#1d4ed8")
        style.map("Accent.TButton", background=[("active", "#1e40af")])
        style.configure("Treeview.Heading", font=("Arial", 14, "bold"))
        style.configure("Treeview", rowheight=44, font=("Arial", 14))
        style.configure("Header.TLabel", font=("Arial", 18, "bold"))
        style.configure("Section.TLabel", font=("Arial", 12, "bold"))
        style.configure("Total.TLabel", font=("Arial", 18, "bold"))

        self.db = SupabaseService()
        self.productos = self.db.get_productos()

        self.items = []  # dict: producto_id, nombre_snapshot, precio_unitario, cantidad, subtotal
        self.comandas = []
        self.active_comanda = None
        self._comandas_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "data", "comandas_abiertas.json"))

        self._build_ui()
        self.after(100, lambda: self.mesero_entry.focus_set())
        self._load_comandas()
        self._refresh_catalog()
        self._bind_shortcuts()
        self._tick_clock()

    # ---------------- UI ----------------
    def _build_ui(self):
        # Top bar
        top = tk.Frame(self, bg="#1f2937")
        top.pack(fill="x")

        left_top = tk.Frame(top, bg="#1f2937")
        left_top.pack(side="left", padx=12, pady=8)

        self.logo_img = load_logo(44)
        if self.logo_img:
            tk.Label(left_top, image=self.logo_img, bg="#1f2937").pack(side="left", padx=(0, 8))
        tk.Label(left_top, text="BARBACOA POS", font=("Arial", 18, "bold"), fg="white", bg="#1f2937").pack(side="left")

        center_top = tk.Frame(top, bg="#1f2937")
        center_top.pack(side="left", padx=16, pady=6)
        ttk.Button(center_top, text="Gastos", command=self._open_gastos).pack(side="left", padx=4, pady=6)
        ttk.Button(center_top, text="Propinas", command=self._open_propinas).pack(side="left", padx=4, pady=6)
        ttk.Button(center_top, text="Corte", command=self._open_corte).pack(side="left", padx=4, pady=6)
        ttk.Button(center_top, text="Reportes", command=self._open_reportes).pack(side="left", padx=4, pady=6)

        right_top = tk.Frame(top, bg="#1f2937")
        right_top.pack(side="right", padx=12, pady=6)
        tk.Label(right_top, text="Mesero", fg="#e5e7eb", bg="#1f2937", font=("Arial", 9, "bold")).pack(anchor="e")
        self.mesero_var = tk.StringVar()
        self.mesero_entry = ttk.Entry(right_top, textvariable=self.mesero_var, width=24)
        self.mesero_entry.pack(anchor="e", pady=(2, 0))
        self.mesero_entry.bind("<Return>", lambda _e: self.search_entry.focus_set())
        self.mesero_entry.bind("<KeyRelease>", lambda _e: self._save_current_to_state())

        tk.Label(right_top, text="Mesa", fg="#e5e7eb", bg="#1f2937", font=("Arial", 9, "bold")).pack(anchor="e", pady=(6, 0))
        self.mesa_var = tk.StringVar()
        self.mesa_entry = ttk.Entry(right_top, textvariable=self.mesa_var, width=24)
        self.mesa_entry.pack(anchor="e", pady=(2, 0))
        self.mesa_entry.bind("<KeyRelease>", lambda _e: self._save_current_to_state())

        self.clock_var = tk.StringVar()
        tk.Label(right_top, textvariable=self.clock_var, fg="#e5e7eb", bg="#1f2937", font=("Arial", 10, "bold")).pack(anchor="e", pady=(6, 0))

        # Main split
        main = ttk.Frame(self, padding=10)
        main.pack(fill="both", expand=True)

        left = ttk.Frame(main)
        left.pack(side="left", fill="y", padx=(0, 10))

        right = ttk.Frame(main)
        right.pack(side="right", fill="both", expand=True)

        # Left: comandas + filters + catalog
        cmd_box = tk.Frame(left, bg="#f3f4f6")
        cmd_box.pack(fill="x", pady=(0, 8))
        tk.Label(cmd_box, text="Comandas abiertas", font=("Arial", 12, "bold"), fg="#111827", bg="#f3f4f6").pack(anchor="w", padx=6, pady=4)
        self.comandas_list = tk.Listbox(
            left,
            height=6,
            font=("Arial", 11),
            activestyle="none",
            selectbackground="#1d4ed8",
            selectforeground="white",
            highlightthickness=1,
            highlightbackground="#d1d5db",
        )
        self.comandas_list.pack(fill="x", pady=(0, 8))
        self.comandas_list.bind("<<ListboxSelect>>", lambda _e: self._on_select_comanda())

        cmd_btns = ttk.Frame(left)
        cmd_btns.pack(fill="x", pady=(0, 12))
        ttk.Button(cmd_btns, text="Nueva comanda", command=self._new_comanda).pack(side="left", padx=4)
        ttk.Button(cmd_btns, text="Cerrar comanda", command=self._close_comanda).pack(side="left", padx=4)

        atajos_box = tk.Frame(left, bg="#f3f4f6")
        atajos_box.pack(fill="x", pady=(0, 8))
        tk.Label(atajos_box, text="Atajos", font=("Arial", 11, "bold"), fg="#111827", bg="#f3f4f6").pack(anchor="w", padx=6, pady=4)
        atajos_txt = (
            "Ctrl+S Guardar  |  Ctrl+N Nueva\n"
            "Ctrl+F Buscar   |  Ctrl+M Mesero\n"
            "Ctrl+D Eliminar |  Ctrl+L Vaciar\n"
            "Enter agrega / guarda"
        )
        tk.Label(atajos_box, text=atajos_txt, font=("Arial", 9), fg="#374151", bg="#f3f4f6", justify="left").pack(anchor="w", padx=6, pady=(0, 6))

        cat_box = tk.Frame(left, bg="#f3f4f6")
        cat_box.pack(fill="x", pady=(0, 4))
        tk.Label(cat_box, text="Catálogo", font=("Arial", 12, "bold"), fg="#111827", bg="#f3f4f6").pack(anchor="w", padx=6, pady=4)

        self.search_var = tk.StringVar()
        self.search_entry = ttk.Entry(left, textvariable=self.search_var, width=30)
        self.search_entry.pack(fill="x", pady=(6, 6))
        self.search_entry.bind("<KeyRelease>", lambda _e: self._refresh_catalog())
        self.search_entry.bind("<Return>", lambda _e: self._focus_catalog())

        cats = sorted({p.get("categoria", "GENERAL") for p in self.productos})
        self.cat_var = tk.StringVar(value="TODAS")
        cat_values = ["TODAS"] + cats
        self.cat_menu = ttk.Combobox(left, textvariable=self.cat_var, values=cat_values, state="readonly")
        self.cat_menu.pack(fill="x", pady=(0, 8))
        self.cat_menu.bind("<<ComboboxSelected>>", lambda _e: self._refresh_catalog())

        # Product listbox
        self.prod_list = tk.Listbox(
            left,
            height=25,
            font=("Arial", 11),
            activestyle="none",
            selectbackground="#1d4ed8",
            selectforeground="white",
            highlightthickness=1,
            highlightbackground="#d1d5db",
        )
        self.prod_list.pack(fill="both", expand=True)
        self.prod_list.bind("<Double-Button-1>", lambda _e: self._add_selected_product())
        self.prod_list.bind("<Return>", lambda _e: self._add_selected_product())

        qty_row = ttk.Frame(left)
        qty_row.pack(fill="x", pady=8)
        ttk.Label(qty_row, text="Cantidad:").pack(side="left")
        self.qty_var = tk.StringVar(value="1")
        self.qty_entry = ttk.Entry(qty_row, textvariable=self.qty_var, width=6)
        self.qty_entry.pack(side="left", padx=6)
        self.qty_entry.bind("<Return>", lambda _e: self._add_selected_product())

        ttk.Button(left, text="Agregar", command=self._add_selected_product).pack(fill="x")

        # Right: ticket table
        cmd_hdr = tk.Frame(right, bg="#f3f4f6")
        cmd_hdr.pack(fill="x")
        tk.Label(cmd_hdr, text="Comanda", font=("Arial", 12, "bold"), fg="#111827", bg="#f3f4f6").pack(anchor="w", padx=6, pady=4)

        table_frame = ttk.Frame(right)
        table_frame.pack(fill="both", expand=True, pady=8)

        self.tree = ttk.Treeview(table_frame, columns=("dec", "qty", "inc", "prod", "unit", "sub"), show="headings")
        self.tree.heading("dec", text="")
        self.tree.heading("qty", text="Cant")
        self.tree.heading("inc", text="")
        self.tree.heading("prod", text="Producto")
        self.tree.heading("unit", text="P.Unit")
        self.tree.heading("sub", text="Subtotal")

        self.tree.column("dec", width=42, anchor="center")
        self.tree.column("qty", width=80, anchor="center")
        self.tree.column("inc", width=42, anchor="center")
        self.tree.column("prod", width=430, anchor="center")
        self.tree.column("unit", width=110, anchor="center")
        self.tree.column("sub", width=120, anchor="center")

        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<Delete>", lambda _e: self._remove_selected())
        self.tree.bind("<plus>", lambda _e: self._inc_selected())
        self.tree.bind("<minus>", lambda _e: self._dec_selected())
        self.tree.bind("<Button-1>", self._on_tree_click)
        self.tree.bind("<Double-Button-1>", self._on_tree_double_click)

        btns = ttk.Frame(right)
        btns.pack(fill="x")
        ttk.Button(btns, text="Eliminar seleccionado (Del)", command=self._remove_selected).pack(side="left", padx=5)
        ttk.Button(btns, text="Vaciar", command=self._clear_all).pack(side="left", padx=5)

        ttk.Separator(right, orient="horizontal").pack(fill="x", pady=(10, 6))
        cobro_hdr = tk.Frame(right, bg="#e5e7eb")
        cobro_hdr.pack(fill="x", pady=(0, 6))
        tk.Label(cobro_hdr, text="Cobro", font=("Arial", 12, "bold"), fg="#111827", bg="#e5e7eb").pack(anchor="w", padx=6, pady=4)

        # Payment + total
        pay = tk.Frame(right, bg="#f3f4f6")
        pay.pack(fill="x", pady=(0, 6))

        self.total_var = tk.StringVar(value="0.00")
        tk.Label(pay, text="TOTAL:", font=("Arial", 22, "bold"), fg="#111827", bg="#f3f4f6").pack(side="left", padx=6, pady=6)
        tk.Label(pay, textvariable=self.total_var, font=("Arial", 24, "bold"), fg="#dc2626", bg="#f3f4f6").pack(side="left", padx=(6, 0))

        pay2 = ttk.Frame(right)
        pay2.pack(fill="x")

        ttk.Label(pay2, text="Método:").pack(side="left")
        self.metodo_var = tk.StringVar(value="EFECTIVO")
        metodo = ttk.Combobox(pay2, textvariable=self.metodo_var, values=["EFECTIVO", "TARJETA", "TRANSFER"], state="readonly", width=12)
        metodo.pack(side="left", padx=6)
        metodo.bind("<<ComboboxSelected>>", lambda _e: self._toggle_cash_fields())

        ttk.Label(pay2, text="Propina:").pack(side="left", padx=(12, 0))
        self.propina_var = tk.StringVar()
        self.propina_entry = ttk.Entry(pay2, textvariable=self.propina_var, width=10)
        self.propina_entry.pack(side="left", padx=6)
        self.propina_entry.bind("<Return>", lambda _e: self._save_comanda())
        self.propina_entry.bind("<KeyRelease>", lambda _e: self._save_current_to_state())

        self.cash_frame = ttk.Frame(right)
        self.cash_frame.pack(fill="x", pady=(6, 0))

        ttk.Label(self.cash_frame, text="Recibido:").pack(side="left")
        self.recibido_var = tk.StringVar()
        self.recibido_entry = ttk.Entry(self.cash_frame, textvariable=self.recibido_var, width=12)
        self.recibido_entry.pack(side="left", padx=6)
        self.recibido_entry.bind("<KeyRelease>", lambda _e: self._update_change())
        self.recibido_entry.bind("<Return>", lambda _e: self._save_comanda())

        ttk.Label(self.cash_frame, text="Cambio:").pack(side="left", padx=(10, 0))
        self.cambio_var = tk.StringVar(value="0.00")
        ttk.Label(self.cash_frame, textvariable=self.cambio_var, font=("Arial", 12, "bold")).pack(side="left", padx=6)

        self._toggle_cash_fields()

        ttk.Button(right, text="GUARDAR COMANDA", style="Accent.TButton", command=self._save_comanda).pack(fill="x", pady=10)

    # ---------------- Logic ----------------
    def _bind_shortcuts(self):
        # Atajos globales para flujo rápido
        self.bind_all("<Control-s>", lambda _e: self._save_comanda())
        self.bind_all("<Control-n>", lambda _e: self._new_comanda())
        self.bind_all("<Control-f>", lambda _e: self.search_entry.focus_set())
        self.bind_all("<Control-m>", lambda _e: self.mesero_entry.focus_set())
        self.bind_all("<Control-d>", lambda _e: self._remove_selected())
        self.bind_all("<Control-l>", lambda _e: self._clear_all())

    def _tick_clock(self):
        self.clock_var.set(datetime.now().strftime("%H:%M:%S"))
        self.after(1000, self._tick_clock)

    def _focus_catalog(self):
        if self.prod_list.size() > 0:
            if not self.prod_list.curselection():
                self.prod_list.selection_set(0)
            self.prod_list.activate(0)
        self.prod_list.focus_set()

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
        self.comandas.append({
            "folio_local": f"TMP-{datetime.now().strftime('%H%M%S')}",
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "mesero": "",
            "mesa": "",
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
        self.prod_list.delete(0, tk.END)

        for p in self.productos:
            if not p.get("activo", True):
                continue
            pcat = p.get("categoria", "GENERAL")
            if cat != "TODAS" and pcat != cat:
                continue
            label = f"[{pcat}] {p['nombre']}  -  ${float(p['precio']):.2f}"
            if q and (q not in p["nombre"].lower()) and (q not in pcat.lower()):
                continue
            self.filtered.append(p)
            self.prod_list.insert(tk.END, label)
            idx = self.prod_list.size() - 1
            bg = "#ffffff" if idx % 2 == 0 else "#f3f4f6"
            self.prod_list.itemconfig(idx, bg=bg)

    def _add_selected_product(self):
        sel = self.prod_list.curselection()
        if not sel:
            messagebox.showwarning("Selecciona producto", "Doble click o selecciona un producto para agregar.")
            return
        p = self.filtered[sel[0]]
        try:
            qty = int(self.qty_var.get().strip())
            if qty <= 0:
                raise ValueError
        except Exception:
            messagebox.showwarning("Cantidad inválida", "Cantidad debe ser entero > 0.")
            return

        unit = float(p["precio"])
        sub = calcular_subtotal(unit, qty)
        self.items.append({
            "producto_id": p["id"],
            "nombre_snapshot": p["nombre"],
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
                values=("[-]", it["cantidad"], "[+]", it["nombre_snapshot"],
                        f"${float(it['precio_unitario']):.2f}",
                        f"${float(it['subtotal']):.2f}")
                , tags=(tag,)
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
        self.mesero_entry.focus_set()
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
        if not row_id:
            return
        col = self.tree.identify_column(event.x)
        self.tree.selection_set(row_id)
        if col == "#1":
            self._dec_selected()
        elif col == "#3":
            self._inc_selected()

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
            self.cash_frame.pack(fill="x", pady=(6, 0))
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
        if not self.items:
            messagebox.showwarning("Comanda vacía", "Agrega productos antes de guardar.")
            return

        mesero = self.mesero_var.get().strip() or "Sin nombre"
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
            comanda = self.db.crear_comanda(mesero, metodo, total, recibido, cambio)
            self.db.agregar_items(comanda["id"], self.items)
            if propina > 0:
                snapshot = mesero if mesero.strip() else "(SIN MESERO)"
                self.db.crear_propina(
                    monto=propina,
                    mesero_id=None,
                    mesero_nombre_snapshot=snapshot,
                    fuente="COMANDA",
                    comanda_id=comanda["id"],
                )
            messagebox.showinfo("OK", f"Comanda guardada.\nTotal: ${total:.2f}\nMétodo: {metodo}")
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
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo guardar en Supabase:\n{e}")

    # ---------------- Dialogs ----------------
    def _open_gastos(self):
        GastosDialog(self, self.db)

    def _open_propinas(self):
        PropinasDialog(self, self.db)

    def _open_corte(self):
        CorteView(self, self.db)

    def _open_reportes(self):
        ReportesView(self, self.db)


if __name__ == "__main__":
    app = POSApp()
    app.mainloop()
