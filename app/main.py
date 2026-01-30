import os
import tkinter as tk
from tkinter import ttk, messagebox

from services.supabase_service import SupabaseService
from domain.calc import calcular_subtotal, calcular_total
from ui.gastos_dialog import GastosDialog
from ui.propinas_dialog import PropinasDialog
from ui.corte_view import CorteView
from ui.reportes_view import ReportesView


class POSApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Barbacoa POS - Demo Profesional (Tk)")
        self.geometry("1100x700")

        # Estilo ttk (se ve pro)
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure("TButton", padding=8)
        style.configure("Header.TButton", padding=6)
        style.configure("Treeview.Heading", font=("Arial", 11, "bold"))
        style.configure("Treeview", rowheight=28, font=("Arial", 10))

        self.db = SupabaseService()
        self.productos = self.db.get_productos()

        self.items = []  # dict: producto_id, nombre_snapshot, precio_unitario, cantidad, subtotal

        self._build_ui()
        self._refresh_catalog()

    # ---------------- UI ----------------
    def _build_ui(self):
        # Top bar
        top = ttk.Frame(self, padding=10)
        top.pack(fill="x")

        left_header = ttk.Frame(top)
        left_header.pack(side="left")

        self.logo_img = self._load_logo()
        if self.logo_img:
            ttk.Label(left_header, image=self.logo_img).pack(side="left", padx=(0, 10))

        title_box = ttk.Frame(left_header)
        title_box.pack(side="left")
        ttk.Label(title_box, text="BARBACOA POS", font=("Arial", 18, "bold")).pack(anchor="w")
        ttk.Label(title_box, text="Sistema de ventas y control", font=("Arial", 9)).pack(anchor="w")

        btns = ttk.Frame(top)
        btns.pack(side="left", padx=14)
        ttk.Button(btns, text="Gastos", style="Header.TButton", width=10, command=self._open_gastos).pack(side="left", padx=4)
        ttk.Button(btns, text="Propinas", style="Header.TButton", width=10, command=self._open_propinas).pack(side="left", padx=4)
        ttk.Button(btns, text="Corte", style="Header.TButton", width=10, command=self._open_corte).pack(side="left", padx=4)
        ttk.Button(btns, text="Reportes", style="Header.TButton", width=10, command=self._open_reportes).pack(side="left", padx=4)

        right_header = ttk.Frame(top)
        right_header.pack(side="right")
        ttk.Label(right_header, text="Mesero:").pack(side="left", padx=(0, 6))
        self.mesero_var = tk.StringVar()
        ttk.Entry(right_header, textvariable=self.mesero_var, width=20).pack(side="left")

        ttk.Separator(self, orient="horizontal").pack(fill="x")

        # Main split
        main = ttk.Frame(self, padding=10)
        main.pack(fill="both", expand=True)

        left = ttk.Frame(main)
        left.pack(side="left", fill="y", padx=(0, 10))

        right = ttk.Frame(main)
        right.pack(side="right", fill="both", expand=True)

        # Left: filters + catalog
        ttk.Label(left, text="Catálogo", font=("Arial", 12, "bold")).pack(anchor="w")

        self.search_var = tk.StringVar()
        search_entry = ttk.Entry(left, textvariable=self.search_var, width=30)
        search_entry.pack(fill="x", pady=(6, 6))
        search_entry.bind("<KeyRelease>", lambda _e: self._refresh_catalog())

        cats = sorted({p.get("categoria", "GENERAL") for p in self.productos})
        self.cat_var = tk.StringVar(value="TODAS")
        cat_values = ["TODAS"] + cats
        self.cat_menu = ttk.Combobox(left, textvariable=self.cat_var, values=cat_values, state="readonly")
        self.cat_menu.pack(fill="x", pady=(0, 8))
        self.cat_menu.bind("<<ComboboxSelected>>", lambda _e: self._refresh_catalog())

        # Product listbox
        self.prod_list = tk.Listbox(left, height=25)
        self.prod_list.pack(fill="both", expand=True)
        self.prod_list.bind("<Double-Button-1>", lambda _e: self._add_selected_product())

        qty_row = ttk.Frame(left)
        qty_row.pack(fill="x", pady=8)
        ttk.Label(qty_row, text="Cantidad:").pack(side="left")
        self.qty_var = tk.StringVar(value="1")
        ttk.Entry(qty_row, textvariable=self.qty_var, width=6).pack(side="left", padx=6)

        ttk.Button(left, text="Agregar →", command=self._add_selected_product).pack(fill="x")

        # Right: ticket table
        ttk.Label(right, text="Comanda (Ticket)", font=("Arial", 12, "bold")).pack(anchor="w")

        table_frame = ttk.Frame(right)
        table_frame.pack(fill="both", expand=True, pady=8)

        self.tree = ttk.Treeview(table_frame, columns=("qty", "prod", "unit", "sub"), show="headings")
        self.tree.heading("qty", text="Cant")
        self.tree.heading("prod", text="Producto")
        self.tree.heading("unit", text="P.Unit")
        self.tree.heading("sub", text="Subtotal")

        self.tree.column("qty", width=70, anchor="center")
        self.tree.column("prod", width=430, anchor="w")
        self.tree.column("unit", width=100, anchor="e")
        self.tree.column("sub", width=110, anchor="e")

        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<Delete>", lambda _e: self._remove_selected())

        btns = ttk.Frame(right)
        btns.pack(fill="x")
        ttk.Button(btns, text="Eliminar seleccionado (Del)", command=self._remove_selected).pack(side="left", padx=5)
        ttk.Button(btns, text="Vaciar", command=self._clear_all).pack(side="left", padx=5)

        # Payment + total
        pay = ttk.Frame(right, padding=(0, 10))
        pay.pack(fill="x")

        self.total_var = tk.StringVar(value="0.00")
        ttk.Label(pay, text="TOTAL:", font=("Arial", 16, "bold")).pack(side="left")
        ttk.Label(pay, textvariable=self.total_var, font=("Arial", 16, "bold")).pack(side="left", padx=(6, 0))

        pay2 = ttk.Frame(right)
        pay2.pack(fill="x")

        ttk.Label(pay2, text="Método:").pack(side="left")
        self.metodo_var = tk.StringVar(value="EFECTIVO")
        metodo = ttk.Combobox(pay2, textvariable=self.metodo_var, values=["EFECTIVO", "TARJETA", "TRANSFER"], state="readonly", width=12)
        metodo.pack(side="left", padx=6)
        metodo.bind("<<ComboboxSelected>>", lambda _e: self._toggle_cash_fields())

        ttk.Label(pay2, text="Propina:").pack(side="left", padx=(12, 0))
        self.propina_var = tk.StringVar()
        ttk.Entry(pay2, textvariable=self.propina_var, width=10).pack(side="left", padx=6)

        self.cash_frame = ttk.Frame(right)
        self.cash_frame.pack(fill="x", pady=(6, 0))

        ttk.Label(self.cash_frame, text="Recibido:").pack(side="left")
        self.recibido_var = tk.StringVar()
        recibido_entry = ttk.Entry(self.cash_frame, textvariable=self.recibido_var, width=12)
        recibido_entry.pack(side="left", padx=6)
        recibido_entry.bind("<KeyRelease>", lambda _e: self._update_change())

        ttk.Label(self.cash_frame, text="Cambio:").pack(side="left", padx=(10, 0))
        self.cambio_var = tk.StringVar(value="0.00")
        ttk.Label(self.cash_frame, textvariable=self.cambio_var, font=("Arial", 12, "bold")).pack(side="left", padx=6)

        self._toggle_cash_fields()

        ttk.Button(right, text="GUARDAR COMANDA", command=self._save_comanda).pack(fill="x", pady=10)

    # ---------------- Logic ----------------
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

    def _refresh_ticket(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        for idx, it in enumerate(self.items):
            self.tree.insert(
                "", "end", iid=str(idx),
                values=(it["cantidad"], it["nombre_snapshot"],
                        f"${float(it['precio_unitario']):.2f}",
                        f"${float(it['subtotal']):.2f}")
            )
        total = calcular_total(self.items) if self.items else 0.0
        self.total_var.set(f"${total:.2f}")
        self._update_change()

    def _remove_selected(self):
        sel = self.tree.selection()
        if not sel:
            return
        idx = int(sel[0])
        if 0 <= idx < len(self.items):
            self.items.pop(idx)
            self._refresh_ticket()

    def _clear_all(self):
        self.items = []
        self._refresh_ticket()
        if hasattr(self, "propina_var"):
            self.propina_var.set("")

    def _toggle_cash_fields(self):
        if self.metodo_var.get() == "EFECTIVO":
            self.cash_frame.pack(fill="x", pady=(6, 0))
        else:
            self.cash_frame.pack_forget()
            self.recibido_var.set("")
            self.cambio_var.set("0.00")

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
            messagebox.showinfo("OK", f"Comanda guardada ✅\nTotal: ${total:.2f}\nMétodo: {metodo}")
            self._clear_all()
            self.mesero_var.set("")
            self.recibido_var.set("")
            self.cambio_var.set("0.00")
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

    def _load_logo(self) -> tk.PhotoImage | None:
        base = os.path.join(os.path.dirname(__file__), "assets")
        candidates = ("logo_barbacoa.png", "file.png", "logo.png")
        for name in candidates:
            path = os.path.join(base, name)
            if not os.path.exists(path):
                continue
            try:
                img = tk.PhotoImage(file=path)
                max_px = 48
                if img.width() > max_px:
                    factor = max(1, img.width() // max_px)
                    img = img.subsample(factor, factor)
                return img
            except Exception:
                return None
        return None


if __name__ == "__main__":
    app = POSApp()
    app.mainloop()
