from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

import customtkinter as ctk


_METODOS = ["EFECTIVO", "TARJETA", "TRANSFER"]


class PaymentsDialog(ctk.CTkToplevel):
    def __init__(self, master, *, total: float, initial_rows: list[dict] | None = None):
        super().__init__(master)
        self.title("Pagos mixtos")
        self.geometry("920x520")
        self.minsize(820, 440)
        self.resizable(True, True)
        self.grab_set()

        self.total = round(float(total or 0), 2)
        self.result: list[dict] | None = None
        self._rows: list[dict] = []

        self.total_var = tk.StringVar(value=f"${self.total:.2f}")
        self.suma_var = tk.StringVar(value="$0.00")
        self.diff_var = tk.StringVar(value="$0.00")

        self._build_ui()
        rows = initial_rows if initial_rows else [{"metodo_pago": "EFECTIVO", "monto": self.total, "propina": 0}]
        for row in rows:
            self._add_row(row)
        self._refresh_totals()

    def _build_ui(self):
        header = ctk.CTkFrame(self, fg_color="#1f2937", corner_radius=0, height=56)
        header.pack(fill="x", side="top")
        ctk.CTkLabel(
            header,
            text="PAGOS MIXTOS",
            font=("Arial", 16, "bold"),
            text_color="white",
        ).pack(side="left", padx=12, pady=12)

        info = ctk.CTkFrame(self)
        info.pack(fill="x", padx=12, pady=(10, 8))
        ctk.CTkLabel(info, text="Total comanda:", font=("Arial", 12, "bold")).pack(side="left", padx=6)
        ctk.CTkLabel(info, textvariable=self.total_var, font=("Arial", 13, "bold")).pack(side="left", padx=(0, 20))
        ctk.CTkLabel(info, text="Suma pagos:", font=("Arial", 12, "bold")).pack(side="left", padx=6)
        ctk.CTkLabel(info, textvariable=self.suma_var, font=("Arial", 12, "bold")).pack(side="left", padx=(0, 20))
        ctk.CTkLabel(info, text="Diferencia:", font=("Arial", 12, "bold")).pack(side="left", padx=6)
        self.diff_lbl = ctk.CTkLabel(info, textvariable=self.diff_var, font=("Arial", 12, "bold"))
        self.diff_lbl.pack(side="left", padx=(0, 6))

        toolbar = ctk.CTkFrame(self, fg_color="transparent")
        toolbar.pack(fill="x", padx=12, pady=(0, 6))
        ttk.Button(toolbar, text="Agregar método", command=self._add_row).pack(side="left", padx=4)
        ctk.CTkLabel(
            toolbar,
            text="Tip: cada renglón tiene monto + propina. El monto sí debe sumar el total.",
            text_color="#6b7280",
        ).pack(side="left", padx=8)

        wrap = ctk.CTkFrame(self)
        wrap.pack(fill="both", expand=True, padx=12, pady=(0, 10))
        wrap.grid_rowconfigure(1, weight=1)
        wrap.grid_columnconfigure(0, weight=1)

        head = ctk.CTkFrame(wrap, fg_color="#eef2ff")
        head.grid(row=0, column=0, sticky="ew", padx=6, pady=(6, 0))
        labels = ["Método", "Monto", "Propina", "Recibido", "Cambio", "Acciones"]
        widths = [18, 12, 12, 12, 12, 12]
        for idx, text in enumerate(labels):
            ctk.CTkLabel(head, text=text, font=("Arial", 11, "bold"), width=widths[idx] * 10).grid(
                row=0, column=idx, padx=4, pady=6, sticky="w"
            )

        self.canvas = tk.Canvas(wrap, highlightthickness=0, bg="#f8fafc")
        self.canvas.grid(row=1, column=0, sticky="nsew", padx=6, pady=6)
        scroll = ttk.Scrollbar(wrap, orient="vertical", command=self.canvas.yview)
        scroll.grid(row=1, column=1, sticky="ns", pady=6)
        self.canvas.configure(yscrollcommand=scroll.set)

        self.inner = ctk.CTkFrame(self.canvas, fg_color="transparent")
        self.window_id = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.inner.bind("<Configure>", lambda _e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", self._on_canvas_configure)

        actions = ctk.CTkFrame(self, fg_color="transparent")
        actions.pack(fill="x", padx=12, pady=(0, 12))
        ttk.Button(actions, text="Cancelar", command=self._cancel).pack(side="right", padx=4)
        ttk.Button(actions, text="Guardar pagos", style="Accent.TButton", command=self._save).pack(side="right", padx=4)

        self.bind("<Escape>", lambda _e: self._cancel())
        self.bind("<Return>", lambda _e: self._save())

    def _on_canvas_configure(self, event):
        self.canvas.itemconfigure(self.window_id, width=event.width)

    def _add_row(self, preset: dict | None = None):
        preset = preset or {}
        row = len(self._rows)

        frame = ctk.CTkFrame(self.inner)
        frame.grid(row=row, column=0, sticky="ew", padx=2, pady=2)
        frame.grid_columnconfigure(0, weight=1)

        metodo_var = tk.StringVar(value=str(preset.get("metodo_pago") or "EFECTIVO").strip().upper())
        monto_var = tk.StringVar(value=f"{float(preset.get('monto') or 0):.2f}")
        propina_var = tk.StringVar(value=f"{float(preset.get('propina') or 0):.2f}")
        recibido_raw = preset.get("recibido")
        recibido_var = tk.StringVar(value=(f"{float(recibido_raw):.2f}" if recibido_raw not in (None, "") else ""))
        cambio_var = tk.StringVar(value="0.00")

        metodo_menu = ttk.Combobox(frame, textvariable=metodo_var, values=_METODOS, state="readonly", width=14)
        metodo_menu.grid(row=0, column=0, padx=4, pady=4, sticky="w")
        monto_entry = ttk.Entry(frame, textvariable=monto_var, width=12)
        monto_entry.grid(row=0, column=1, padx=4, pady=4)
        propina_entry = ttk.Entry(frame, textvariable=propina_var, width=12)
        propina_entry.grid(row=0, column=2, padx=4, pady=4)
        recibido_entry = ttk.Entry(frame, textvariable=recibido_var, width=12)
        recibido_entry.grid(row=0, column=3, padx=4, pady=4)
        ttk.Label(frame, textvariable=cambio_var, width=12).grid(row=0, column=4, padx=4, pady=4)
        ttk.Button(frame, text="Quitar", command=lambda f=frame: self._remove_row(f)).grid(row=0, column=5, padx=4, pady=4)

        entry = {
            "frame": frame,
            "metodo_var": metodo_var,
            "monto_var": monto_var,
            "propina_var": propina_var,
            "recibido_var": recibido_var,
            "cambio_var": cambio_var,
            "recibido_entry": recibido_entry,
        }
        self._rows.append(entry)

        def _on_change(_event=None):
            self._refresh_row(entry)
            self._refresh_totals()

        metodo_menu.bind("<<ComboboxSelected>>", _on_change)
        for widget in (monto_entry, propina_entry, recibido_entry):
            widget.bind("<KeyRelease>", _on_change)
            widget.bind("<FocusOut>", _on_change)

        self._refresh_row(entry)
        self._refresh_totals()

    def _remove_row(self, frame):
        if len(self._rows) <= 1:
            messagebox.showwarning("Pagos", "Debe existir al menos un método de pago.")
            return
        keep: list[dict] = []
        for row in self._rows:
            if row["frame"] is frame:
                try:
                    row["frame"].destroy()
                except Exception:
                    pass
                continue
            keep.append(row)
        self._rows = keep
        for idx, row in enumerate(self._rows):
            row["frame"].grid_configure(row=idx)
        self._refresh_totals()

    @staticmethod
    def _to_float(raw: str, *, default: float = 0.0) -> float:
        txt = (raw or "").strip()
        if not txt:
            return default
        try:
            return float(txt)
        except Exception:
            return default

    @staticmethod
    def _to_optional_float(raw: str) -> float | None:
        txt = (raw or "").strip()
        if not txt:
            return None
        try:
            return float(txt)
        except Exception:
            return None

    def _refresh_row(self, row: dict):
        metodo = str(row["metodo_var"].get() or "").strip().upper()
        monto = self._to_float(row["monto_var"].get(), default=0.0)
        recibido = self._to_optional_float(row["recibido_var"].get())

        if metodo == "EFECTIVO":
            row["recibido_entry"].configure(state="normal")
            # Si recibido esta vacio, mostrar cambio neutro para evitar confusion visual.
            if recibido is None:
                row["cambio_var"].set("0.00")
            else:
                cambio = recibido - monto
                row["cambio_var"].set(f"{cambio:.2f}")
        else:
            row["recibido_entry"].configure(state="disabled")
            row["recibido_var"].set("")
            row["cambio_var"].set("0.00")

    def _refresh_totals(self):
        suma = 0.0
        for row in self._rows:
            suma += self._to_float(row["monto_var"].get(), default=0.0)
        suma = round(suma, 2)
        diff = round(suma - self.total, 2)
        self.suma_var.set(f"${suma:.2f}")
        self.diff_var.set(f"${diff:+.2f}")
        if diff == 0:
            self.diff_lbl.configure(text_color="#166534")
        elif diff < 0:
            self.diff_lbl.configure(text_color="#b91c1c")
        else:
            self.diff_lbl.configure(text_color="#92400e")

    def _validate(self) -> list[dict] | None:
        pagos: list[dict] = []
        for idx, row in enumerate(self._rows, start=1):
            metodo = str(row["metodo_var"].get() or "").strip().upper()
            if metodo not in _METODOS:
                messagebox.showwarning("Pagos", f"Método inválido en renglón {idx}.")
                return None

            monto = self._to_float(row["monto_var"].get(), default=-1)
            if monto <= 0:
                messagebox.showwarning("Pagos", f"Monto inválido en renglón {idx}. Debe ser > 0.")
                return None

            propina = self._to_float(row["propina_var"].get(), default=-1)
            if propina < 0:
                messagebox.showwarning("Pagos", f"Propina inválida en renglón {idx}. Debe ser >= 0.")
                return None

            recibido = None
            cambio = None
            if metodo == "EFECTIVO":
                recibido_txt = (row["recibido_var"].get() or "").strip()
                # Regla UX: en efectivo sin recibido capturado, asumir pago exacto.
                if not recibido_txt:
                    recibido = round(monto, 2)
                    row["recibido_var"].set(f"{recibido:.2f}")
                else:
                    parsed_recibido = self._to_optional_float(recibido_txt)
                    if parsed_recibido is None:
                        messagebox.showwarning(
                            "Pagos",
                            f"Recibido inválido en renglón {idx}.",
                        )
                        return None
                    recibido = parsed_recibido
                if recibido < monto:
                    messagebox.showwarning(
                        "Pagos",
                        f"En efectivo (renglón {idx}) el recibido debe ser >= monto de ese renglón.",
                    )
                    return None
                cambio = round(recibido - monto, 2)

            pagos.append(
                {
                    "orden": idx,
                    "metodo_pago": metodo,
                    "monto": round(monto, 2),
                    "propina": round(propina, 2),
                    "recibido": None if recibido is None else round(recibido, 2),
                    "cambio": None if cambio is None else round(cambio, 2),
                }
            )

        suma = round(sum(float(p["monto"]) for p in pagos), 2)
        if abs(suma - self.total) > 0.01:
            messagebox.showwarning(
                "Pagos",
                f"La suma de montos (${suma:.2f}) debe ser igual al total de comanda (${self.total:.2f}).",
            )
            return None
        return pagos

    def _save(self):
        pagos = self._validate()
        if pagos is None:
            return
        self.result = pagos
        self.destroy()

    def _cancel(self):
        self.result = None
        self.destroy()


def ask_split_payments(master, *, total: float, initial_rows: list[dict] | None = None) -> list[dict] | None:
    dlg = PaymentsDialog(master, total=total, initial_rows=initial_rows)
    master.wait_window(dlg)
    return dlg.result
