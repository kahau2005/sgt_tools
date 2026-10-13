"""Tool selection window shown after a successful Odoo login."""

import tkinter as tk
from tkinter import ttk

from services.odoo_client import OdooCredentials


PURPLE = "#684080"
PURPLE_DARK = "#56336c"
BACKGROUND = "#f4f5f7"
TEXT = "#172554"
MUTED = "#667085"


class ModeSelectionWindow(tk.Toplevel):
    """Let the user choose which checker application to open."""

    def __init__(self, parent, credentials: OdooCredentials, on_close, on_tool_back):
        super().__init__(parent)
        self.credentials = credentials
        self.on_close = on_close
        self.on_tool_back = on_tool_back
        self._build_styles()
        self.title("GB SUBMIT - Chọn chức năng")
        self.geometry("620x390")
        self.minsize(560, 360)
        self.configure(background=BACKGROUND)
        self.protocol("WM_DELETE_WINDOW", self._close)
        self._build_ui()
        # The root login window is hidden while this window is active.  Do not
        # make this Toplevel transient/modal because Windows may hide it with
        # its withdrawn owner.
        self.withdraw()

    def _build_styles(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Mode.TFrame", background=BACKGROUND)
        style.configure("ModeCard.TFrame", background="white", relief="solid", borderwidth=1)
        style.configure("ModeTitle.TLabel", background=BACKGROUND, foreground=TEXT, font=("Segoe UI", 18, "bold"))
        style.configure("ModeHint.TLabel", background=BACKGROUND, foreground=MUTED, font=("Segoe UI", 10))
        style.configure("ModeCardTitle.TLabel", background="white", foreground=PURPLE_DARK, font=("Segoe UI", 12, "bold"))
        style.configure("ModeCardText.TLabel", background="white", foreground=MUTED, font=("Segoe UI", 9), wraplength=220)
        style.configure("ModePrimary.TButton", background=PURPLE, foreground="white", font=("Segoe UI", 10, "bold"), padding=(12, 8))
        style.map("ModePrimary.TButton", background=[("active", PURPLE_DARK)])

    def _build_ui(self):
        content = ttk.Frame(self, style="Mode.TFrame", padding=28)
        content.pack(fill="both", expand=True)
        ttk.Label(content, text="Chọn chức năng kiểm tra", style="ModeTitle.TLabel").pack(anchor="w")
        ttk.Label(
            content,
            text=f"Đã đăng nhập Odoo: {self.credentials.username}",
            style="ModeHint.TLabel",
        ).pack(anchor="w", pady=(6, 22))

        cards = ttk.Frame(content, style="Mode.TFrame")
        cards.pack(fill="both", expand=True)
        cards.columnconfigure(0, weight=1)
        cards.columnconfigure(1, weight=1)

        self._add_card(
            cards,
            0,
            "CHECK POST FACEBOOK",
            "Kiểm tra các bài đăng Facebook theo tuần, ngày, nhân viên và các bộ lọc hiện có.",
            "Mở công cụ Check Post",
            self._open_user_checker,
        )
        self._add_card(
            cards,
            1,
            "CHECK GROUP",
            "Công cụ riêng để kiểm tra trạng thái các group Facebook.",
            "Mở công cụ Check Group",
            self._open_group_checker,
        )

    def _add_card(self, parent, column, title, description, button_text, command):
        card = ttk.Frame(parent, style="ModeCard.TFrame", padding=18)
        card.grid(row=0, column=column, sticky="nsew", padx=(0 if column == 0 else 10, 0 if column == 1 else 10))
        card.columnconfigure(0, weight=1)
        ttk.Label(card, text=title, style="ModeCardTitle.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(card, text=description, style="ModeCardText.TLabel").grid(row=1, column=0, sticky="nw", pady=(12, 18))
        ttk.Button(card, text=button_text, style="ModePrimary.TButton", command=command).grid(row=2, column=0, sticky="w")

    def _open_user_checker(self):
        from gui.dashboard_window import DashboardWindow

        self._launch(DashboardWindow)

    def _open_group_checker(self):
        from gui.group_check_window import GroupCheckWindow

        self._launch(GroupCheckWindow)

    def _launch(self, window_class):
        self.grab_release()
        self.destroy()
        window = window_class(
            self.master,
            self.credentials,
            on_back=self.on_tool_back,
        )
        # Keep the Toplevel alive after this callback returns.
        self.master.active_tool_window = window
        window.focus_force()
        window.protocol("WM_DELETE_WINDOW", lambda: self._return_to_login(window))

    def _return_to_login(self, window):
        window.destroy()
        self.master.active_tool_window = None
        self.on_close()

    def _close(self):
        self.grab_release()
        self.destroy()
        self.master.mode_selection_window = None
        self.on_close()
