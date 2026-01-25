import tkinter as tk
from tkinter import ttk, messagebox
import customtkinter as ctk

from domain.calc import calcular_subtotal, calcular_total
from ui.dialogs import ask_quantity


class ComandaView(ctk.CTkFrame):
    def __init__(self, master, db):
        super().__init__(master)
        self.db = db

        self.productos = self.db.get_productos()
        self.items = []  # list of dict items

        self._build_ui()

    def _build_ui(self):
        # Layout: left catalog buttons, right ticket
        left = ctk.CTkFrame(self)
        right = ctk.CTkFrame(self)
        left.pack(side="left", fill="y", padx=10, pady=10)
        right.pack(side="right", fill="both", expand=True, padx=10, pady=10)

        # Header ticket info
        header = ctk.CTkFrame(right)
        header.pack(fill="x", padx=10, pady=(10, 6))
        ctk.CTkLabel(header, text="COMANDA", font=("Arial", 18, "bold")).pack(side="left", padx=8)

        self.mesero_var = tk.StringVar()
        self.mesero_entry = ctk.CTkEntry(header, textvariable=self.mesero_var, placeholder_text="Mesero", width=180)
        self.mesero_entry.pack(side="right", padx=8)

        # Catalog by categories (buttons)
        ctk.CTkLabel(left, text="Productos", font=("Arial", 16, "bold")).pack(pady=(10, 6))

        # category dropdown
        cats = sorted({p.get("categoria", "GENERAL") for p in self.productos})
        self.cat_var = tk.StringVar(value=cats[0] if cats else "GENERAL")
        self.cat_menu = ctk.CTkOptionMenu(left, values=cats if cats else ["GENERAL"], variable=self.cat_var, command=lambda _v: self._render_product_buttons())
        self.cat_menu.pack(fill="x", padx=10, pady=(0, 8))

        self.products_scroll = ctk.CTkScrollableFrame(left, width=250, height=520)
        self.products_scroll.pack(fill="both", expand=True, padx=10, pady=10)

        self._render_product_buttons()

        # Ticket table (Treeview)
        table_frame = ctk.CTkFrame(right)
        table_frame.pack(fill="both", expand=True, padx=10, pady=6)

        self.tree = ttk.Treeview(table_frame, columns=("qty", "prod", "unit", "sub"), show="headings", height=14)
        self.tree.heading("qty", text="Cant")
        self.tree.heading("prod", text="Producto")
        self.tree.heading("unit", text="P.Unit")
        self.tree.heading("sub", text="Subtotal")

        self.tree.column("qty", width=70, anchor="center")
        self.tree.column("prod", width=420, anchor="w")
        self.tree.column("unit", width=100, anchor="e")
        self.tree.column("sub", width=110, anchor="e")

        self.tree.pack(fill="both", expand=True)

        # Bind delete key
        self.tree.bind("<Delete>", lambda _e: self.remove_selected())

        # Buttons under table
        btns = ctk.CTkFrame(right)
        btns.pack(fill="x", padx=10, pady=(0, 6))
        ctk.CTkButton(btns, text="❌ Eliminar seleccionado", command=self.remove_selected).pack(side="left", padx=6)
        ctk.CTkButton(btns, text="🧹 Vaciar", command=self.clear_all).pack(side="left", padx=6)

        # Payment section
        pay = ctk.CTkFrame(right)
        pay.pack(fill="x", padx=10, pady=6)

        ctk.CTkLabel(pay, text="Método:", font=("Arial", 13, "bold")).grid(row=0, column=0, padx=6, pady=6, sticky="w")
        self.metodo_var = tk.StringVar(value="EFECTIVO")
        self.metodo_menu = ctk.CTkOptionMenu(pay, values=["EFECTIVO", "TARJETA", "TRANSFER"], variable=self.metodo_var, command=lambda _v: self._toggle_cash_fields())
        self.metodo_menu.grid(row=0, column=1, padx=6, pady=6, sticky="w")

        self.total_label = ctk.CTkLabel(pay, text="TOTAL: $0.00", font=("Arial", 20, "bold"))
        self.total_label.grid(row=0, column=2, padx=10, pady=6, sticky="e")

        pay.grid_columnconfigure(2, weight=1)

        self.cash_frame = ctk.CTkFrame(right)
        self.cash_frame.pack(fill="x", padx=10, pady=(0, 6))

        self.recibido_var = tk.StringVar()
        self.cambio_var = tk.StringVar(value="0.00")

        ctk.CTkLabel(self.cash_frame, text="Recibido (efectivo):").grid(row=0, column=0, padx=6, pady=6, sticky="w")
        self.recibido_entry = ctk.CTkEntry(self.cash_frame, textvariable=self.recibido_var, width=140)
        self.recibido_entry.grid(row=0, column=1, padx=6, pady=6, sticky="w")
        self.recibido_entry.bind("<KeyRelease>", lambda _e: self._update_change())

        ctk.CTkLabel(self.cash_frame, text="Cambio:").grid(row=0, column=2, padx=6, pady=6, sticky="w")
        self.cambio_label = ctk.CTkLabel(self.cash_frame, textvariable=self.cambio_var, font=("Arial", 14, "bold"))
        self.cambio_label.grid(row=0, column=3, padx=6, pady=6, sticky="w")

        # Save button
        self.save_btn = ctk.CTkButton(right, text="✅ GUARDAR COMANDA", height=42, command=self.save_comanda)
        self.save_btn.pack(fill="x", padx=10, pady=(6, 12))

        self._toggle_cash_fields()
        self._refresh_table()

    def _render_product_buttons(self):
        # clear scroll frame
        for w in self.products_scroll.winfo_children():
            w.destroy()

        cat = self.cat_var.get()
        filtered = [p for p in self.productos if (p.get("categoria", "GENERAL") == cat)]

        for p in filtered:
            name = p["nombre"]
            price = float(p["precio"])
            b = ctk.CTkButton(
                self.products_scroll,
                text=f"{name}\n${price:.2f}",
                height=48,
                command=lambda p=p: self.add_product(p),
            )
            b.pack(fill="x", padx=6, pady=4)

    def _toggle_cash_fields(self):
        metodo = self.metodo_var.get()
        if metodo == "EFECTIVO":
            self.cash_frame.pack(fill="x", padx=10, pady=(0, 6))
        else:
            self.cash_frame.pack_forget()
            self.recibido_var.set("")
            self.cambio_var.set("0.00")

    def add_product(self, producto):
        qty = ask_quantity(self, producto["nombre"])
        if qty is None:
            return

        unit = float(producto["precio"])
        sub = calcular_subtotal(unit, qty)

        self.items.append({
            "producto_id": producto["id"],
            "nombre_snapshot": producto["nombre"],
            "precio_unitario": unit,
            "cantidad": qty,
            "subtotal": sub
        })

        self._refresh_table()
        self._update_total()
        self._update_change()

    def _refresh_table(self):
        for row in self.tree.get_children():
            self.tree.delete(row)

        for idx, it in enumerate(self.items):
            self.tree.insert(
                "",
                "end",
                iid=str(idx),
                values=(
                    it["cantidad"],
                    it["nombre_snapshot"],
                    f"${float(it['precio_unitario']):.2f}",
                    f"${float(it['subtotal']):.2f}",
                )
            )

    def _update_total(self):
        total = calcular_total(self.items) if self.items else 0.0
        self.total_label.configure(text=f"TOTAL: ${total:.2f}")

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

        cambio = recibido - total
        self.cambio_var.set(f"{cambio:.2f}")

    def remove_selected(self):
        sel = self.tree.selection()
        if not sel:
            return
        idx = int(sel[0])
        if idx < 0 or idx >= len(self.items):
            return
        self.items.pop(idx)
        self._refresh_table()
        self._update_total()
        self._update_change()

    def clear_all(self):
        self.items = []
        self._refresh_table()
        self._update_total()
        self._update_change()

    def save_comanda(self):
        if not self.items:
            messagebox.showwarning("Comanda vacía", "Agrega productos antes de guardar.")
            return

        mesero = (self.mesero_var.get().strip() or "Sin nombre")
        metodo = self.metodo_var.get()
        total = calcular_total(self.items)

        recibido = None
        cambio = None

        if metodo == "EFECTIVO":
            try:
                recibido = float(self.recibido_var.get().strip())
            except Exception:
                messagebox.showwarning("Recibido inválido", "Escribe cuánto te dieron en efectivo.")
                return

            if recibido < total:
                messagebox.showwarning("Efectivo insuficiente", "El recibido debe ser mayor o igual al total.")
                return
            cambio = recibido - total

        try:
            comanda = self.db.crear_comanda(mesero, metodo, total, recibido, cambio)
            self.db.agregar_items(comanda["id"], self.items)
            messagebox.showinfo("OK", f"✅ Comanda guardada.\nTotal: ${total:.2f}\nMétodo: {metodo}")
            self.clear_all()
            self.mesero_var.set("")
            self.recibido_var.set("")
            self.cambio_var.set("0.00")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo guardar en Supabase:\n{e}")
