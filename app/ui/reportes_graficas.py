from __future__ import annotations

from datetime import date
import tkinter as tk
import customtkinter as ctk


class ReportesGraficas(ctk.CTkToplevel):
    def __init__(
        self,
        master,
        fecha_inicio: date,
        fecha_fin: date,
        ventas_por_metodo: dict,
        ventas_por_dia: list[dict],
        ventas_por_mesero: list[dict],
    ):
        super().__init__(master)
        self.title("Gráficas")
        self.geometry("980x640")
        self.resizable(False, False)
        # Evita conflicto de grab con la ventana Reportes

        self.fecha_inicio = fecha_inicio
        self.fecha_fin = fecha_fin
        self.ventas_por_metodo = ventas_por_metodo
        self.ventas_por_dia = ventas_por_dia
        self.ventas_por_mesero = ventas_por_mesero

        self._build_ui()

    def _build_ui(self):
        header = ctk.CTkFrame(self, fg_color="#1f2937", height=60, corner_radius=0)
        header.pack(fill="x", side="top")
        title = f"Gráficas {self.fecha_inicio.isoformat()} a {self.fecha_fin.isoformat()}"
        ctk.CTkLabel(header, text=title, font=("Arial", 16, "bold"), text_color="white").pack(side="left", padx=12, pady=12)

        grid = ctk.CTkFrame(self)
        grid.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        left = ctk.CTkFrame(grid)
        left.pack(side="left", fill="both", expand=True, padx=(0, 6))
        right = ctk.CTkFrame(grid)
        right.pack(side="right", fill="both", expand=True, padx=(6, 0))

        ctk.CTkLabel(left, text="Ventas por método", font=("Arial", 13, "bold")).pack(anchor="w", padx=8, pady=(8, 0))
        metodo_canvas = tk.Canvas(left, width=440, height=220, bg="#f3f4f6", highlightthickness=0)
        metodo_canvas.pack(padx=8, pady=8)
        self._draw_bar_chart(
            metodo_canvas,
            [
                ("EFECTIVO", self.ventas_por_metodo.get("EFECTIVO", 0)),
                ("TARJETA", self.ventas_por_metodo.get("TARJETA", 0)),
                ("TRANSFER", self.ventas_por_metodo.get("TRANSFER", 0)),
            ],
            bar_color="#e76f51",
        )

        ctk.CTkLabel(left, text="Ventas por día", font=("Arial", 13, "bold")).pack(anchor="w", padx=8, pady=(2, 0))
        dia_canvas = tk.Canvas(left, width=440, height=240, bg="#f3f4f6", highlightthickness=0)
        dia_canvas.pack(padx=8, pady=8)
        dia_data = [(r.get("fecha"), r.get("total", 0)) for r in self.ventas_por_dia]
        self._draw_bar_chart(dia_canvas, dia_data, bar_color="#2a9d8f")

        ctk.CTkLabel(right, text="Ventas por mesero (Top)", font=("Arial", 13, "bold")).pack(anchor="w", padx=8, pady=(8, 0))
        mesero_canvas = tk.Canvas(right, width=440, height=480, bg="#f3f4f6", highlightthickness=0)
        mesero_canvas.pack(padx=8, pady=8)
        mesero_data = [(r.get("mesero"), r.get("total", 0)) for r in self.ventas_por_mesero]
        self._draw_bar_chart(mesero_canvas, mesero_data, bar_color="#457b9d", rotate_labels=True)

    def _draw_bar_chart(self, canvas: tk.Canvas, data: list[tuple], bar_color: str, rotate_labels: bool = False):
        canvas.delete("all")
        if not data:
            canvas.create_text(220, 110, text="Sin datos", fill="#6b7280", font=("Arial", 12, "bold"))
            return

        width = int(canvas["width"])
        height = int(canvas["height"])
        padding = 30
        max_value = max(float(v or 0) for _, v in data) or 1.0
        bar_width = max(18, (width - padding * 2) // max(1, len(data)))

        for i, (label, value) in enumerate(data):
            v = float(value or 0)
            bar_h = int((height - padding * 2) * (v / max_value))
            x0 = padding + i * bar_width + 8
            y0 = height - padding - bar_h
            x1 = x0 + bar_width - 16
            y1 = height - padding

            canvas.create_rectangle(x0, y0, x1, y1, fill=bar_color, outline="")
            canvas.create_text((x0 + x1) // 2, y0 - 10, text=f"${v:.0f}", fill="#111827", font=("Arial", 9))

            if rotate_labels:
                canvas.create_text((x0 + x1) // 2, height - padding + 18, text=label, fill="#374151", angle=30, font=("Arial", 8))
            else:
                canvas.create_text((x0 + x1) // 2, height - padding + 12, text=label, fill="#374151", font=("Arial", 9))
