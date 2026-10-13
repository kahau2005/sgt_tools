"""Tkinter login window for the desktop Check Link application."""

import threading
import tkinter as tk
from tkinter import ttk
from typing import Callable, Optional

from services.odoo_client import OdooAuthenticationError, OdooClient, OdooCredentials
from services.credential_store import load_login, save_login


PURPLE = "#684080"
PURPLE_DARK = "#56336c"
TEXT = "#172554"
MUTED = "#667085"
BORDER = "#cbd5e1"
BACKGROUND = "#f4f5f7"


class LoginWindow(tk.Tk):
    def __init__(
        self,
        on_authenticated: Optional[Callable[[OdooCredentials], None]] = None,
    ):
        super().__init__()
        self.on_authenticated = on_authenticated
        self._login_thread = None
        self._saved_login = load_login()
        self._build_styles()
        self._build_window()
        self._build_form()

    def _build_styles(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("App.TFrame", background=BACKGROUND)
        style.configure("Header.TFrame", background=PURPLE)
        style.configure(
            "Card.TFrame",
            background="white",
            relief="solid",
            borderwidth=1,
        )
        style.configure(
            "HeaderSmall.TLabel",
            background=PURPLE,
            foreground="#ddd2e6",
            font=("Segoe UI", 9, "bold"),
        )
        style.configure(
            "HeaderTitle.TLabel",
            background=PURPLE,
            foreground="white",
            font=("Segoe UI", 18, "bold"),
        )
        style.configure(
            "Status.TLabel",
            background=PURPLE,
            foreground="white",
            font=("Segoe UI", 9, "bold"),
        )
        style.configure(
            "Section.TLabel",
            background="white",
            foreground=PURPLE_DARK,
            font=("Segoe UI", 11, "bold"),
        )
        style.configure(
            "Field.TLabel",
            background="white",
            foreground=TEXT,
            font=("Segoe UI", 9, "bold"),
        )
        style.configure(
            "Hint.TLabel",
            background="white",
            foreground=MUTED,
            font=("Segoe UI", 8),
            wraplength=280,
        )
        style.configure(
            "Connect.TButton",
            background=PURPLE,
            foreground="white",
            font=("Segoe UI", 10, "bold"),
            padding=(14, 8),
        )
        style.map(
            "Connect.TButton",
            background=[("active", PURPLE_DARK), ("disabled", "#b9a8c5")],
        )

    def _build_window(self):
        self.title("GB SUBMIT - Post Publisher")
        self.geometry("390x620")
        self.minsize(360, 560)
        self.configure(background=BACKGROUND)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

    def _build_form(self):
        header = ttk.Frame(self, style="Header.TFrame", padding=(22, 16))
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(0, weight=1)

        ttk.Label(header, text="GB SUBMIT", style="HeaderSmall.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(header, text="Post Publisher", style="HeaderTitle.TLabel").grid(
            row=1, column=0, sticky="w", pady=(2, 0)
        )
        self.status_label = ttk.Label(header, text="Offline", style="Status.TLabel")
        self.status_label.grid(row=0, column=1, rowspan=2, sticky="e")

        content = ttk.Frame(self, style="App.TFrame", padding=14)
        content.grid(row=1, column=0, sticky="nsew")
        content.columnconfigure(0, weight=1)
        content.rowconfigure(0, weight=1)

        card = ttk.Frame(content, style="Card.TFrame", padding=(14, 18))
        card.grid(row=0, column=0, sticky="new")
        card.columnconfigure(0, weight=1)

        ttk.Label(card, text="Odoo connection", style="Section.TLabel").grid(
            row=0, column=0, sticky="w", pady=(0, 16)
        )

        self.url_var = tk.StringVar(value="https://buyer.sge.vn")
        self.database_var = tk.StringVar()
        self.user_var = tk.StringVar()
        self.password_var = tk.StringVar()
        self.remember_password_var = tk.BooleanVar(
            value=self._saved_login.get("remember_password", False)
        )
        self.url_var.set(self._saved_login.get("url", self.url_var.get()))
        self.database_var.set(self._saved_login.get("database", ""))
        self.user_var.set(self._saved_login.get("username", ""))
        self.password_var.set(self._saved_login.get("password", ""))

        self._add_field(card, 1, "Odoo URL", self.url_var)
        self._add_field(card, 3, "Database name", self.database_var, "Database")
        self._add_field(card, 5, "User", self.user_var, "Email or login")
        self._add_field(card, 7, "Password", self.password_var, show="*")

        ttk.Checkbutton(
            card,
            text="Remember password",
            variable=self.remember_password_var,
        ).grid(row=9, column=0, sticky="w", pady=(12, 0))
        ttk.Label(
            card,
            text="The password is kept in memory only while this app is open.",
            style="Hint.TLabel",
        ).grid(row=10, column=0, sticky="w", pady=(8, 0))

        self.connect_button = ttk.Button(
            card,
            text="Connect",
            style="Connect.TButton",
            command=self._connect,
        )
        self.connect_button.grid(row=11, column=0, sticky="w", pady=(14, 0))

        self.message_var = tk.StringVar()
        self.message_label = ttk.Label(
            card,
            textvariable=self.message_var,
            style="Hint.TLabel",
        )
        self.message_label.grid(row=12, column=0, sticky="w", pady=(10, 0))

        self.entries = [
            self.odoo_url_entry,
            self.database_name_entry,
            self.user_entry,
            self.password_entry,
        ]
        self.password_entry.bind("<Return>", lambda _event: self._connect())

    def _add_field(
        self,
        parent,
        row: int,
        label: str,
        variable: tk.StringVar,
        placeholder: str = "",
        show: Optional[str] = None,
    ):
        ttk.Label(parent, text=label, style="Field.TLabel").grid(
            row=row, column=0, sticky="w", pady=(0, 5)
        )
        entry = ttk.Entry(parent, textvariable=variable, show=show or "")
        entry.grid(row=row + 1, column=0, sticky="ew", ipady=7)
        if placeholder:
            entry.insert(0, "")
        setattr(self, f"{label.lower().replace(' ', '_')}_entry", entry)

    def _connect(self):
        if self._login_thread and self._login_thread.is_alive():
            return

        self._set_busy(True)
        self.status_label.configure(text="Connecting...")
        self.message_var.set("Connecting to Odoo...")

        try:
            client = OdooClient(
                self.url_var.get(),
                self.database_var.get(),
                self.user_var.get(),
                self.password_var.get(),
            )
        except OdooAuthenticationError as exc:
            self._show_error(str(exc))
            return
        self._login_thread = threading.Thread(
            target=self._authenticate,
            args=(client,),
            daemon=True,
        )
        self._login_thread.start()

    def _authenticate(self, client: OdooClient):
        try:
            credentials = client.authenticate()
        except OdooAuthenticationError as exc:
            self.after(0, self._show_error, str(exc))
            return
        self.after(0, self._show_success, credentials)

    def _show_success(self, credentials: OdooCredentials):
        self._set_busy(False)
        self.status_label.configure(text="Online")
        self.message_var.set(f"Connected as {credentials.username} (UID {credentials.uid}).")
        save_login(
            self.url_var.get().strip(),
            self.database_var.get().strip(),
            self.user_var.get().strip(),
            self.password_var.get(),
            self.remember_password_var.get(),
        )
        if self.on_authenticated:
            self.on_authenticated(credentials)

    def _show_error(self, message: str):
        self._set_busy(False)
        self.status_label.configure(text="Offline")
        self.message_var.set(message)

    def _set_busy(self, busy: bool):
        self.connect_button.configure(state="disabled" if busy else "normal")
        for entry in self.entries:
            entry.configure(state="disabled" if busy else "normal")
