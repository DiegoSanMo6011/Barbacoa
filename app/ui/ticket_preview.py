from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
import threading
import customtkinter as ctk

from services.printer import print_ticket_text

class TicketPreview(ctk.CTkToplevel):
    def __init__(self, master, ticket_text: str, file_path: str | None = None):
        super().__init__(master)
        self.title("Vista previa de ticket")
        self.geometry("640x760")
        self.minsize(560, 640)
        self.resizable(True, True)
        self.grab_set()
        self.ticket_text = ticket_text

        header = ctk.CTkFrame(self)
        header.pack(fill="x", padx=12, pady=12)
        ctk.CTkLabel(header, text="Ticket de venta", font=("Arial", 20, "bold")).pack(side="left", padx=8, pady=8)

        body = ctk.CTkFrame(self)
        body.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self.text = tk.Text(body, width=44, height=24, font=("Courier", 14), wrap="none")
        self.text.pack(side="left", fill="both", expand=True, padx=(8, 0), pady=8)
        y_scroll = ttk.Scrollbar(body, orient="vertical", command=self.text.yview)
        y_scroll.pack(side="right", fill="y", padx=(0, 8), pady=8)
        self.text.configure(yscrollcommand=y_scroll.set)
        self.text.insert("1.0", ticket_text)
        self.text.configure(state="disabled")

        actions = ctk.CTkFrame(self, fg_color="transparent")
        actions.pack(fill="x", padx=12, pady=(0, 12))
        actions.columnconfigure(0, weight=1)
        actions.columnconfigure(1, weight=1)
        actions.columnconfigure(2, weight=1)
        ttk.Button(actions, text="Imprimir", style="Touch.TButton", command=self._print_ticket).grid(
            row=0, column=0, padx=6, sticky="ew"
        )
        if file_path:
            ttk.Button(
                actions,
                text="Ruta del archivo",
                style="Touch.TButton",
                command=lambda: self._show_path(file_path),
            ).grid(
                row=0, column=1, padx=6, sticky="ew"
            )
        ttk.Button(actions, text="Cerrar", style="Danger.TButton", command=self.destroy).grid(
            row=0, column=2, padx=6, sticky="ew"
        )

    def _show_path(self, path: str):
        messagebox.showinfo("Ticket guardado", f"Archivo: {path}")

    def _print_ticket(self):
        def _job():
            try:
                print_ticket_text(self.ticket_text)
                self.after(0, lambda: messagebox.showinfo("Impresión", "Ticket enviado a la impresora."))
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Impresión", f"No se pudo imprimir el ticket:\n{e}"))

        threading.Thread(target=_job, daemon=True).start()
