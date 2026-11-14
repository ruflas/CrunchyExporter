"""Small month calendar to pick a date with the mouse, without extra dependencies."""

import calendar
from datetime import date
from typing import Callable, Optional

import customtkinter as ctk
from PIL import Image, ImageDraw

from gui import i18n

_GRAY_TEXT = ("gray55", "gray50")
_HOVER = ("gray80", "gray30")


def calendar_icon(size: int = 18) -> ctk.CTkImage:
    """Return a calendar glyph drawn with Pillow.

    Emoji such as 📅 don't render reliably in Tk on Windows, so the icon is
    drawn at four times the size and scaled down, in a light and a dark
    variant for CustomTkinter's appearance modes.
    """
    def draw(color: str) -> Image.Image:
        s, u = size * 4, size * 4 // 12  # canvas and grid unit
        img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.rounded_rectangle([u, 2 * u, s - u, s - u], radius=u, outline=color, width=u)
        d.rectangle([u, 2 * u, s - u, 4 * u], fill=color)            # header bar
        for x in (3 * u, s - 4 * u):                                  # binder rings
            d.rectangle([x, 0, x + u, 3 * u], fill=color)
        for row in range(2):                                          # days
            for col in range(3):
                x, y = 3 * u + col * 2 * u, 6 * u + row * 2 * u
                d.rectangle([x, y, x + u, y + u], fill=color)
        return img.resize((size, size), Image.LANCZOS)

    return ctk.CTkImage(light_image=draw("#333333"), dark_image=draw("#e0e0e0"),
                        size=(size, size))


class DatePicker(ctk.CTkToplevel):
    """A month calendar in a small window placed under a widget.

    Picking a day, "Today" or "Clear" calls ``on_pick`` and closes the window;
    Escape or closing it picks nothing.

    Args:
        anchor: Widget the window opens under.
        initial: Date shown and highlighted first, or None to open on the
            month of ``max_date``.
        on_pick: Called with the chosen date, or None when "Clear" is used.
        max_date: Last day that can be picked; later days are disabled.
            Defaults to today.
    """

    def __init__(self, anchor, initial: Optional[date],
                 on_pick: Callable[[Optional[date]], None],
                 max_date: Optional[date] = None) -> None:
        super().__init__(anchor)
        self.title(i18n.t("datepicker_title"))
        self.resizable(False, False)
        self._on_pick = on_pick
        self._max = max_date or date.today()
        self._selected = initial
        shown = initial or self._max
        self._year, self._month = shown.year, shown.month
        self._months = i18n.t("datepicker_months").split(",")

        self._build()
        self._render()
        self._place_under(anchor)
        self.transient(anchor.winfo_toplevel())
        self.bind("<Escape>", lambda _: self.destroy())
        self.after(50, self._grab)

    # ------------------------------------------------------------------ build

    def _build(self) -> None:
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=10, pady=(10, 4))
        nav = {"width": 30, "height": 28, "fg_color": "transparent",
               "hover_color": _HOVER, "text_color": ("gray10", "gray90")}
        ctk.CTkButton(header, text="«", command=lambda: self._shift(-12), **nav).pack(side="left")
        ctk.CTkButton(header, text="‹", command=lambda: self._shift(-1), **nav).pack(side="left")
        self._next_year = ctk.CTkButton(header, text="»", command=lambda: self._shift(12), **nav)
        self._next_year.pack(side="right")
        self._next_month = ctk.CTkButton(header, text="›", command=lambda: self._shift(1), **nav)
        self._next_month.pack(side="right")
        self._title = ctk.CTkLabel(header, text="", font=ctk.CTkFont(weight="bold"))
        self._title.pack(side="left", expand=True)

        grid = ctk.CTkFrame(self, fg_color="transparent")
        grid.pack(padx=10)
        for col, name in enumerate(i18n.t("datepicker_weekdays").split(",")):
            ctk.CTkLabel(grid, text=name, width=34, text_color=_GRAY_TEXT,
                         font=ctk.CTkFont(size=11)).grid(row=0, column=col)
        self._days = [
            ctk.CTkButton(grid, text="", width=34, height=28, corner_radius=6,
                          fg_color="transparent", hover_color=_HOVER, border_width=0)
            for _ in range(42)
        ]
        for i, btn in enumerate(self._days):
            btn.grid(row=1 + i // 7, column=i % 7, padx=1, pady=1)

        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(fill="x", padx=10, pady=(6, 10))
        secondary = {"height": 28, "fg_color": ("gray65", "gray35"), "hover_color": ("gray55", "gray28")}
        ctk.CTkButton(footer, text=i18n.t("datepicker_today"), width=90,
                      command=lambda: self._pick(self._max), **secondary).pack(side="left")
        ctk.CTkButton(footer, text=i18n.t("datepicker_clear"), width=90,
                      command=lambda: self._pick(None), **secondary).pack(side="right")

    # ----------------------------------------------------------------- render

    def _render(self) -> None:
        """Show the current month: six weeks starting on Monday."""
        self._title.configure(text=f"{self._months[self._month - 1]} {self._year}")
        weeks = calendar.Calendar(firstweekday=0).monthdatescalendar(self._year, self._month)
        days = [d for week in weeks for d in week]
        while len(days) < 42:  # always six rows, so the window doesn't jump
            days.append(date.fromordinal(days[-1].toordinal() + 1))
        accent = ctk.ThemeManager.theme["CTkButton"]["fg_color"]
        today = date.today()
        for btn, day in zip(self._days, days):
            selected = day == self._selected
            btn.configure(
                text=str(day.day),
                state="disabled" if day > self._max else "normal",
                fg_color=accent if selected else "transparent",
                text_color=("white" if selected else
                            ("gray10", "gray90") if day.month == self._month else _GRAY_TEXT),
                text_color_disabled=("gray75", "gray30"),
                border_width=1 if day == today and not selected else 0,
                border_color=accent,
                command=lambda d=day: self._pick(d),
            )
        last_shown = (self._year, self._month) >= (self._max.year, self._max.month)
        self._next_month.configure(state="disabled" if last_shown else "normal")
        self._next_year.configure(state="disabled" if last_shown else "normal")

    def _shift(self, months: int) -> None:
        """Move the calendar by a number of months, never past ``max_date``'s month."""
        index = self._year * 12 + self._month - 1 + months
        index = min(index, self._max.year * 12 + self._max.month - 1)
        self._year, self._month = divmod(index, 12)
        self._month += 1
        self._render()

    # ---------------------------------------------------------------- helpers

    def _pick(self, day: Optional[date]) -> None:
        self._on_pick(day)
        self.destroy()

    def _place_under(self, anchor) -> None:
        anchor.update_idletasks()
        x = anchor.winfo_rootx()
        y = anchor.winfo_rooty() + anchor.winfo_height() + 4
        self.geometry(f"+{x}+{y}")

    def _grab(self) -> None:
        # Grabbing before the window is visible fails on some platforms.
        try:
            self.grab_set()
            self.focus_force()
        except Exception:
            pass
