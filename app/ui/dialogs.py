import customtkinter as ctk
from tkinter import messagebox


class QuantityDialog(ctk.CTkToplevel):
    def __init__(self, master, product_name: str):
        super().__init__(master)
        self.title("Cantidad")
        self.geometry("320x170")
        self.resizable(False, False)
        self.grab_set()

        self.result = None

        header = ctk.CTkFrame(self, fg_color="#1f2937", height=48, corner_radius=0)
        header.pack(fill="x", side="top")
        ctk.CTkLabel(header, text="CANTIDAD", font=("Arial", 14, "bold"), text_color="white").pack(pady=10)

        ctk.CTkLabel(self, text="Cantidad para:", font=("Arial", 14, "bold")).pack(pady=(12, 2))
        ctk.CTkLabel(self, text=product_name).pack(pady=(0, 10))

        self.qty_var = ctk.StringVar(value="1")
        self.entry = ctk.CTkEntry(self, textvariable=self.qty_var, width=120, justify="center")
        self.entry.pack(pady=6)
        self.entry.focus()

        btns = ctk.CTkFrame(self, fg_color="transparent")
        btns.pack(pady=10)

        ctk.CTkButton(btns, text="Cancelar", command=self._cancel).pack(side="left", padx=6)
        ctk.CTkButton(btns, text="OK", command=self._ok).pack(side="left", padx=6)

        self.bind("<Return>", lambda _e: self._ok())
        self.bind("<Escape>", lambda _e: self._cancel())

    def _ok(self):
        try:
            qty = int(self.qty_var.get().strip())
            if qty <= 0:
                raise ValueError
        except Exception:
            messagebox.showwarning("Cantidad inválida", "La cantidad debe ser un entero mayor a 0.")
            return
        self.result = qty
        self.destroy()

    def _cancel(self):
        self.result = None
        self.destroy()


def ask_quantity(master, product_name: str) -> int | None:
    dlg = QuantityDialog(master, product_name)
    master.wait_window(dlg)
    return dlg.result
