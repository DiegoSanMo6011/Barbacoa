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
        self.geometry("420x520")
        self.resizable(False, False)
        self.grab_set()
        self.ticket_text = ticket_text

        header = ctk.CTkFrame(self)
        header.pack(fill="x", padx=12, pady=12)
        ctk.CTkLabel(header, text="Ticket de venta", font=("Arial", 16, "bold")).pack(side="left", padx=6)

        body = ctk.CTkFrame(self)
        body.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self.text = tk.Text(body, width=44, height=22, font=("Courier", 10))
        self.text.pack(fill="both", expand=True, padx=8, pady=8)
        self.text.insert("1.0", ticket_text)
        self.text.configure(state="disabled")

        actions = ctk.CTkFrame(self, fg_color="transparent")
        actions.pack(fill="x", padx=12, pady=(0, 12))
        ttk.Button(actions, text="Imprimir", command=self._print_ticket).pack(side="left", padx=6)
        if file_path:
            ttk.Button(actions, text="Ruta del archivo", command=lambda: self._show_path(file_path)).pack(
                side="left", padx=6
            )
        ttk.Button(actions, text="Cerrar", style="Danger.TButton", command=self.destroy).pack(side="right", padx=6)

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
