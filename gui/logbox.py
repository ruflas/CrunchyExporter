import customtkinter as ctk


class LogBox(ctk.CTkTextbox):
    """Log widget con colores por nivel. Llamar solo desde el hilo principal."""

    _COLORS = {
        "ok":    "#4caf50",
        "error": "#f44336",
        "warn":  "#ff9800",
        "info":  "#e0e0e0",
    }

    def __init__(self, master, **kwargs):
        kwargs.setdefault("state", "disabled")
        kwargs.setdefault("font", ctk.CTkFont(family="Consolas", size=12))
        super().__init__(master, **kwargs)
        for tag, color in self._COLORS.items():
            self._textbox.tag_configure(tag, foreground=color)

    def append(self, text: str, level: str = "info") -> None:
        self._textbox.configure(state="normal")
        self._textbox.insert("end", text + "\n", level)
        self._textbox.see("end")
        self._textbox.configure(state="disabled")

    def clear(self) -> None:
        self._textbox.configure(state="normal")
        self._textbox.delete("1.0", "end")
        self._textbox.configure(state="disabled")
