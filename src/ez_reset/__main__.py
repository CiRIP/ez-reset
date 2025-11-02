import logging
import tkinter as tk
import traceback
from collections.abc import Iterable
from tkinter import messagebox, ttk

from .d4 import D4ControlBackend
from .devices import by_model
from .printer import Printer
from .status import InkColor, InkLevel
from .utils import parse_identifier
from .win_usbprint import USBPRINTTransport, enumerate_printers


class PrinterList(ttk.Frame):
    def __init__(self, master: tk.Misc) -> None:
        ttk.Frame.__init__(self, master)

        self._printers: list[str] = []

        self.list = tk.Listbox(self)
        self.list.pack(fill=tk.BOTH, expand=True)
        self.list.bind("<Double-Button-1>", self.open_printer)

        self.update_printers()

    def update_printers(self) -> None:
        self._printers = list(enumerate_printers())

        self.list.delete(0, tk.END)

        for idx, device in enumerate(self._printers):
            self.list.insert(idx, device)

    def open_printer(self, _event: tk.Event) -> None:
        selected_index = self.list.curselection()[0]

        usb_transport = USBPRINTTransport(self._printers[selected_index]).__enter__()
        backend = D4ControlBackend(usb_transport).__enter__()

        window = tk.Toplevel()
        window.minsize(200, 300)

        def on_closing() -> None:
            backend.__exit__(None, None, None)
            usb_transport.__exit__(None, None, None)
            window.destroy()

        window.protocol("WM_DELETE_WINDOW", on_closing)

        identifier = parse_identifier(backend.identify())
        window.title(identifier["DES"])

        device = by_model(identifier["MDL"])

        printer = Printer(backend, device=device)

        info = PrinterInfo(window, printer)
        info.pack(fill=tk.BOTH, expand=True)


class PrinterInfo(ttk.Frame):
    def __init__(self, master: tk.Misc, printer: Printer) -> None:
        ttk.Frame.__init__(self, master)

        self.printer = printer

        self.style = ttk.Style(master)

        self.levels_frame = ttk.LabelFrame(self, text="Ink Levels")
        self.levels_frame.pack(fill="x", padx=4)

        self.waste_frame = ttk.LabelFrame(self, text="Waste Levels")
        self.waste_frame.pack(fill="x", padx=4)

        self.waste_reset = ttk.Button(
            self.waste_frame,
            text="Reset All",
            command=self.reset_waste,
        )
        self.waste_reset.pack(fill="x", side="bottom", padx=2, pady=2)

        self.levels: dict[InkColor, Level] = {}
        self.waste: dict[int, Waste] = {}

        self.update = ttk.Button(self, text="Refresh", command=self.update_status)
        self.update.pack(side="bottom")

        self.update_status()

    def update_status(self) -> None:
        root.config(cursor="watch")
        root.update()

        status = self.printer.get_status()
        wastes = self.printer.get_waste()
        self.update_levels(status.levels)
        self.update_waste(wastes)

        root.config(cursor="")

    def update_levels(self, levels: Iterable[InkLevel]) -> None:
        for i, level in enumerate(levels):
            if level.color not in self.levels:
                self.levels[level.color] = Level(
                    self.levels_frame,
                    level.color.name,
                    level.level,
                )

            self.levels[level.color].update_level(level.level)
            self.levels[level.color].grid(column=i, row=0)
            self.levels_frame.columnconfigure(i, weight=1)

    def update_waste(self, levels: Iterable[tuple[int, int]]) -> None:
        for i, (level, max_level) in enumerate(levels):
            if i not in self.waste:
                self.waste[i] = Waste(
                    self.waste_frame,
                    level,
                    max_level,
                    f"Waste ink counter {i}",
                )

            self.waste[i].update_level(level)
            self.waste[i].pack(fill="x", padx=2, pady=2)

    def reset_waste(self) -> None:
        self.printer.reset_waste()

        self.update_status()

        messagebox.showinfo(
            "Restart printer",
            "Waste ink counters have been reset. You must now restart the printer.",
        )


class Level(ttk.Frame):
    def __init__(self, master: tk.Misc, color: str, level: int) -> None:
        ttk.Frame.__init__(self, master)

        self.color = color
        self.level = level
        self.style = ttk.Style()
        self.style.configure(
            f"{color}.Vertical.TProgressbar",
            background=color,
            thickness=24,
        )

        self.gauge = ttk.Progressbar(
            self,
            length=64,
            style=f"{color}.Vertical.TProgressbar",
            orient="vertical",
        )
        self.label = ttk.Label(self, text="", anchor="center")

        self.update_level(level)

        self.gauge.pack(side="top", fill="x")
        self.label.pack(side="bottom", fill="x")

    def update_level(self, level: int) -> None:
        self.gauge["value"] = level
        self.label["text"] = f"{level}%"


class Waste(ttk.Frame):
    def __init__(self, master: tk.Misc, level: int, max_level: int, waste_type: str) -> None:
        ttk.Frame.__init__(self, master)

        self.level = level
        self.max = max_level
        self.type = waste_type

        self.label = ttk.Label(self, text=waste_type, anchor="w")
        self.gauge = ttk.Progressbar(self)
        self.amount = ttk.Label(self, text="")

        self.columnconfigure(0, weight=1)
        self.label.grid(row=0, column=0, sticky="WE")
        self.gauge.grid(row=1, column=0, sticky="NSWE", columnspan=2)
        self.amount.grid(row=0, column=1)

        self.update_level(level)

    def update_level(self, level: int) -> None:
        self.gauge["value"] = (level / self.max) * 100
        self.amount["text"] = f"{level / self.max * 100: 0.2f}%"


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()

root = tk.Tk()
root.title("ez-reset")
style = ttk.Style(root)
style.theme_use("winnative")


def show_error(self, *args) -> None:  # noqa: ANN001,ANN002,ARG001
    err = traceback.format_exc()
    messagebox.showerror("Exception", str(err))


tk.Tk.report_callback_exception = show_error

root.minsize(400, 200)

app = PrinterList(root)
app.pack(fill="both", expand=True)

root.mainloop()
