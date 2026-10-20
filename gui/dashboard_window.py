"""Dashboard window for published posts from sgt_gb_submit."""

import threading
import tkinter as tk
import calendar
import webbrowser
import os
import queue
import shutil
import tempfile
import time
from datetime import date, datetime
from tkinter import filedialog, messagebox, ttk

from services.odoo_client import OdooClient, OdooCredentials, PublishHistory
from services.link_checker import LibreWolfChecker, LinkCheckResult


PURPLE = "#684080"
PURPLE_DARK = "#56336c"
BACKGROUND = "#f4f5f7"
TEXT = "#172554"
MUTED = "#667085"


class DashboardWindow(tk.Toplevel):
    def __init__(self, parent, credentials: OdooCredentials, on_back=None):
        super().__init__(parent)
        self.credentials = credentials
        self.on_back = on_back
        self.client = OdooClient(
            credentials.url,
            credentials.database,
            credentials.username,
            credentials.password,
        )
        self.client.credentials = credentials
        self._load_thread = None
        self._load_request_id = 0
        self._check_thread = None
        self._stop_event = threading.Event()
        self._pending_check = False
        self._rows = {}
        self._last_results = {}
        self._librewolf_dir = ""
        self._all_rows = []
        self._filtered_rows = []
        self._week_ranges = {}
        self._selected_week = None
        self._build_styles()
        self._build_window()
        self._build_ui()
        self._load_weeks()

    def _build_styles(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Dashboard.TFrame", background=BACKGROUND)
        style.configure("Header.TFrame", background=PURPLE)
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
            font=("Segoe UI", 16, "bold"),
        )
        style.configure(
            "HeaderInfo.TLabel",
            background=PURPLE,
            foreground="#eee8f2",
            font=("Segoe UI", 9),
        )
        style.configure(
            "Panel.TFrame",
            background="white",
            relief="solid",
            borderwidth=1,
        )
        style.configure(
            "Field.TLabel",
            background="white",
            foreground=TEXT,
            font=("Segoe UI", 8, "bold"),
        )
        style.configure(
            "Primary.TButton",
            background="#087dcc",
            foreground="white",
            font=("Segoe UI", 9, "bold"),
            padding=(10, 6),
        )
        style.configure(
            "Purple.TButton",
            background=PURPLE,
            foreground="white",
            font=("Segoe UI", 9, "bold"),
            padding=(10, 6),
        )

    def _build_window(self):
        self.title("GB SUBMIT - Post Publisher Dashboard")
        self.geometry("1180x720")
        self.minsize(900, 560)
        self.configure(background=BACKGROUND)
        self.protocol("WM_DELETE_WINDOW", self._close)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

    def _build_ui(self):
        header = ttk.Frame(self, style="Header.TFrame", padding=(20, 10))
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(0, weight=1)
        ttk.Label(header, text="GB SUBMIT", style="HeaderSmall.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(
            header,
            text="Post Publisher Dashboard",
            style="HeaderTitle.TLabel",
        ).grid(row=1, column=0, sticky="w")
        ttk.Label(
            header,
            text=f"DB: {self.credentials.database} | {self.credentials.username}",
            style="HeaderInfo.TLabel",
        ).grid(row=0, column=1, rowspan=2, padx=(10, 18), sticky="e")
        ttk.Button(header, text="Logout", command=self._close).grid(
            row=0, column=2, rowspan=2, sticky="e"
        )
        ttk.Button(
            header,
            text="← Chọn tool",
            command=self._back_to_tool_selection,
        ).grid(row=0, column=1, rowspan=2, padx=(10, 10), sticky="e")

        body = ttk.Frame(self, style="Dashboard.TFrame", padding=(18, 18))
        body.grid(row=1, column=0, sticky="nsew")
        body.columnconfigure(0, weight=1)
        body.rowconfigure(1, weight=1)

        controls = ttk.Frame(body, style="Panel.TFrame", padding=(18, 6, 18, 12))
        controls.grid(row=0, column=0, sticky="ew", pady=(0, 14))
        controls.columnconfigure(2, weight=1)
        controls.columnconfigure(3, weight=1)
        controls.rowconfigure(1, weight=1)

        filter_panel = ttk.LabelFrame(
            controls,
            text="LỌC DỮ LIỆU & PHẠM VI KIỂM TRA",
            padding=(12, 2, 12, 8),
        )
        filter_panel.configure(width=350, height=86)
        filter_panel.grid_propagate(False)
        filter_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        self.date_from = tk.StringVar()
        self.date_from_display = tk.StringVar(value="Tất cả")
        self.week_var = tk.StringVar(value="Đang tải tuần...")
        ttk.Label(filter_panel, text="Tuần").grid(row=0, column=0, sticky="w")
        self.week_box = ttk.Combobox(
            filter_panel, textvariable=self.week_var, state="readonly", width=22
        )
        self.week_box.grid(row=1, column=0, padx=2, pady=(3, 0), sticky="w")
        self.week_box.bind("<<ComboboxSelected>>", self._on_week_selected)
        ttk.Label(filter_panel, text="Ngày").grid(row=0, column=1, padx=(10, 0), sticky="w")
        self.date_box = ttk.Combobox(
            filter_panel,
            textvariable=self.date_from_display,
            values=("Tất cả",),
            state="readonly",
            width=12,
        )
        self.date_box.grid(row=1, column=1, padx=(10, 2), pady=(3, 0), sticky="w")
        self.date_box.bind("<<ComboboxSelected>>", self._on_date_selected)

        run_panel = ttk.LabelFrame(
            controls, text="CHẠY KIỂM TRA", padding=(12, 2, 12, 8)
        )
        run_panel.configure(width=650, height=86)
        run_panel.grid_propagate(False)
        run_panel.grid(row=0, column=1, sticky="nsew", padx=(0, 10))
        self.start_check_button = ttk.Button(
            run_panel,
            text="▶ Recheck dòng đã chọn",
            style="Primary.TButton",
            command=self._start_check,
        )
        self.start_check_button.grid(
            row=0, column=0, rowspan=2, padx=(2, 14), pady=2, sticky="ns"
        )
        self.browser_count = tk.IntVar(value=1)
        ttk.Label(run_panel, text="Trình duyệt").grid(row=0, column=1, padx=2, sticky="w")
        ttk.Spinbox(
            run_panel,
            from_=1,
            to=8,
            textvariable=self.browser_count,
            width=4,
        ).grid(row=1, column=1, padx=2, pady=(3, 0), sticky="w")
        self.batch_size = tk.IntVar(value=25)
        ttk.Label(run_panel, text="Batch").grid(row=0, column=2, padx=(12, 2), sticky="w")
        ttk.Spinbox(
            run_panel,
            from_=1,
            to=500,
            textvariable=self.batch_size,
            width=5,
        ).grid(row=1, column=2, padx=(12, 2), pady=(3, 0), sticky="w")
        self.show_browser = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            run_panel,
            text="Hiện trình duyệt",
            variable=self.show_browser,
        ).grid(row=0, column=3, rowspan=2, padx=(14, 2), sticky="w")
        self.timeout_seconds = tk.StringVar(value="10")
        ttk.Label(run_panel, text="Timeout (giây)").grid(
            row=0, column=4, padx=(12, 2), sticky="w"
        )
        ttk.Spinbox(
            run_panel,
            from_=1,
            to=300,
            textvariable=self.timeout_seconds,
            width=5,
        ).grid(row=1, column=4, padx=(12, 2), pady=(3, 0), sticky="w")

        action_panel = ttk.LabelFrame(
            controls, text="THAO TÁC", padding=(12, 2, 12, 8)
        )
        action_panel.configure(width=350, height=102)
        action_panel.grid_propagate(False)
        action_panel.grid(
            row=1, column=0, sticky="w", padx=(0, 10), pady=(10, 0)
        )
        self.refresh_button = ttk.Button(
            action_panel,
            text="↻ Refresh",
            command=self._refresh_history,
        )
        self.refresh_button.grid(row=0, column=0, padx=(2, 8), pady=4, sticky="w")
        self.stop_button = ttk.Button(
            action_panel,
            text="■ Stop",
            command=self._stop_check,
            state="disabled",
        )
        self.stop_button.grid(row=0, column=1, padx=2, pady=4, sticky="w")
        ttk.Button(
            action_panel,
            text="Check lại lỗi / timeout",
            command=self._recheck_failed,
        ).grid(row=0, column=2, padx=(10, 2), pady=4, sticky="w")
        ttk.Button(
            action_panel,
            text="Chọn thư mục LibreWolf",
            command=self._choose_librewolf_dir,
        ).grid(row=1, column=0, columnspan=2, padx=2, pady=(4, 0), sticky="w")
        self.librewolf_display = tk.StringVar(value="Chưa chọn thư mục")
        ttk.Label(
            action_panel,
            textvariable=self.librewolf_display,
            foreground=MUTED,
        ).grid(row=1, column=2, padx=(10, 2), pady=(4, 0), sticky="w")
        self.status_var = tk.StringVar(value="Loading...")

        search_panel = ttk.LabelFrame(
            controls,
            text="TÌM KIẾM & LỌC TRẠNG THÁI",
            padding=(12, 2, 12, 8),
        )
        search_panel.configure(width=500, height=86)
        search_panel.grid_propagate(False)
        search_panel.grid(
            row=1, column=1, sticky="w", padx=(0, 10), pady=(10, 0)
        )
        ttk.Label(search_panel, text="Trạng thái").grid(row=0, column=0, sticky="w")
        self.status_filter = tk.StringVar(value="Tất cả")
        status_box = ttk.Combobox(
            search_panel,
            textvariable=self.status_filter,
            values=(
                "Tất cả",
                "PUBLISHED",
                "FAILED",
                "BLOCKED",
                "ALIVE",
                "DEAD",
                "ERROR",
                "TIMEOUT",
                "PENDING",
                "SKIPPED",
            ),
            state="readonly",
            width=12,
        )
        status_box.grid(row=1, column=0, padx=2, pady=(3, 0), sticky="w")
        status_box.bind("<<ComboboxSelected>>", lambda _event: self._apply_search())
        ttk.Label(search_panel, text="Tên / nội dung").grid(
            row=0, column=1, padx=(8, 0), sticky="w"
        )
        self.search_var = tk.StringVar()
        search_entry = ttk.Entry(search_panel, textvariable=self.search_var, width=18)
        search_entry.grid(row=1, column=1, padx=(12, 0), pady=(3, 0), ipady=5, sticky="w")
        search_entry.bind("<KeyRelease>", lambda _event: self._apply_search())
        ttk.Button(
            search_panel,
            text="Clear",
            command=self._clear_filters,
        ).grid(row=1, column=2, padx=(10, 2), pady=(3, 0), sticky="w")
        ttk.Label(
            controls,
            textvariable=self.status_var,
            foreground=MUTED,
        ).grid(row=1, column=2, columnspan=2, pady=(10, 0), sticky="w")
        activity_frame = ttk.Frame(controls)
        activity_frame.grid(
            row=2, column=0, columnspan=4, sticky="ew", pady=(8, 0)
        )
        self.activity_var = tk.StringVar(value="")
        ttk.Label(
            activity_frame,
            textvariable=self.activity_var,
            foreground=PURPLE_DARK,
        ).pack(side="left")
        self.activity_bar = ttk.Progressbar(
            activity_frame, mode="indeterminate", length=180
        )
        self.activity_bar.pack(side="left", padx=(10, 0))
        log_frame = ttk.LabelFrame(
            controls, text="NHẬT KÝ", padding=(6, 3)
        )
        log_frame.grid(row=3, column=0, columnspan=4, sticky="ew", pady=(6, 0))
        self.log_text = tk.Text(
            log_frame,
            height=3,
            state="disabled",
            wrap="word",
            relief="flat",
            background="white",
            foreground=MUTED,
            font=("Segoe UI", 8),
        )
        self.log_text.pack(fill="x")

        table_panel = ttk.Frame(body, style="Panel.TFrame", padding=10)
        table_panel.grid(row=1, column=0, sticky="nsew")
        table_panel.columnconfigure(0, weight=1)
        table_panel.rowconfigure(0, weight=1)
        table_panel.columnconfigure(0, weight=1)
        columns = (
            "id",
            "posted_at",
            "post_url",
            "odoo_status",
            "check_status",
            "interactions",
            "comments",
            "shares",
            "detail",
            "last_checked",
            "action",
        )
        self.tree = ttk.Treeview(
            table_panel,
            columns=columns,
            show="tree headings",
            selectmode="extended",
        )
        self.tree.heading("#0", text="PUBLISHING HISTORY")
        self.tree.heading("id", text="ID")
        self.tree.heading("posted_at", text="POSTED AT")
        self.tree.heading("post_url", text="POST URL")
        self.tree.heading("odoo_status", text="ODOO STATUS")
        self.tree.heading("check_status", text="CHECK STATUS")
        self.tree.heading("interactions", text="INTERACTIONS")
        self.tree.heading("comments", text="COMMENTS")
        self.tree.heading("shares", text="SHARES")
        self.tree.heading("detail", text="DETAIL")
        self.tree.heading("last_checked", text="LAST CHECKED")
        self.tree.heading("action", text="ACTION")
        self.tree.column("#0", width=170, stretch=False)
        self.tree.column("id", width=55, stretch=False)
        self.tree.column("posted_at", width=140, stretch=False)
        self.tree.column("post_url", width=380)
        self.tree.column("odoo_status", width=105, stretch=False)
        self.tree.column("check_status", width=105, stretch=False)
        self.tree.column("interactions", width=95, stretch=False, anchor="center")
        self.tree.column("comments", width=85, stretch=False, anchor="center")
        self.tree.column("shares", width=75, stretch=False, anchor="center")
        self.tree.column("detail", width=230)
        self.tree.column("last_checked", width=130, stretch=False)
        self.tree.column("action", width=85, stretch=False)
        self.tree.tag_configure("group", background="#f1edf5", foreground=PURPLE_DARK)
        self.tree.tag_configure("published", foreground="#176b36")
        self.tree.tag_configure("alive", foreground="#176b36")
        self.tree.tag_configure("dead", foreground="#a51d2d")
        self.tree.tag_configure("failed", foreground="#a51d2d")
        self.tree.tag_configure("error", foreground="#9a6700")
        self.tree.tag_configure("stopped", foreground=MUTED)
        self.tree.tag_configure("checking", background="#fff2a8", foreground="#7a5b00")
        self.tree.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(
            table_panel, orient="vertical", command=self.tree.yview
        )
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.bind("<Double-1>", self._open_post_url)
        self.tree.bind("<Motion>", self._update_cursor)
        self.tree.bind("<Button-1>", self._handle_row_action)
        self.tree.bind("<<TreeviewSelect>>", self._selection_changed)

        self.context_menu = tk.Menu(self.tree, tearoff=0)
        self.context_menu.add_command(
            label="Check lại dòng đã chọn",
            command=self._recheck_selected_context,
        )
        self.context_menu.add_command(
            label="Mở link bài viết",
            command=self._open_selected_post_url,
        )
        self.tree.bind("<Button-3>", self._show_context_menu)

    def _load_weeks(self):
        self._load_request_id += 1
        request_id = self._load_request_id
        self.status_var.set("Đang tải danh sách tuần...")
        self._set_activity(True, "Đang tải danh sách tuần...")
        self._append_log("Bắt đầu tải danh sách tuần từ Odoo.")
        self._load_thread = threading.Thread(
            target=self._load_weeks_worker,
            args=(request_id,),
            daemon=True,
        )
        self._load_thread.start()

    def _load_weeks_worker(self, request_id):
        try:
            weeks = self.client.list_publish_history_weeks()
        except Exception as exc:
            self.after(0, self._show_error_if_current, request_id, str(exc))
            return
        self.after(0, self._render_weeks_if_current, request_id, weeks)

    def _show_error_if_current(self, request_id, message):
        if request_id == self._load_request_id:
            self._set_activity(False)
            self._append_log(f"Lỗi tải dữ liệu: {message}")
            self._show_error(message)

    def _render_weeks_if_current(self, request_id, weeks):
        if request_id == self._load_request_id:
            self._render_weeks(weeks)

    def _render_weeks(self, weeks):
        self._set_activity(False)
        self._week_ranges = {label: (start, end) for start, end, label in weeks}
        labels = list(self._week_ranges)
        self.week_box.configure(values=labels)
        self._selected_week = None
        self._all_rows = []
        self._filtered_rows = []
        self._render_page()
        if labels:
            # Do not select a week automatically. Loading history is a
            # separate request and must happen only after an explicit choice.
            self.week_var.set("Chọn tuần")
            self.date_box.configure(values=("Tất cả",))
            self.date_from.set("")
            self.date_from_display.set("Tất cả")
            self.status_var.set("Chọn tuần để tải danh sách bài viết.")
            self._append_log(f"Đã tải {len(labels)} tuần.")
        else:
            self.week_var.set("Không có dữ liệu")
            self.status_var.set("Odoo không có lịch sử bài viết.")
            self._append_log("Odoo không có tuần dữ liệu nào.")

    def _on_week_selected(self, _event=None):
        selected = self._week_ranges.get(self.week_var.get())
        if not selected:
            return
        self._selected_week = selected
        self.date_from.set("")
        self.date_from_display.set("Tất cả")
        self._load_history(*selected)

    def _on_date_selected(self, _event=None):
        value = self.date_from_display.get()
        self.date_from.set("" if value == "Tất cả" else value)
        self._apply_search()

    def _load_history(self, date_from=None, date_to=None):
        self._load_request_id += 1
        request_id = self._load_request_id
        self.status_var.set("Đang tải dữ liệu bài viết...")
        self._set_activity(True, "Đang tải danh sách bài viết...")
        self._append_log(
            f"Bắt đầu tải bài viết ({date_from or 'không giới hạn'} - "
            f"{date_to or 'không giới hạn'})."
        )
        self._load_thread = threading.Thread(
            target=self._load_history_worker,
            args=(request_id, date_from, date_to),
            daemon=True,
        )
        self._load_thread.start()

    def _load_history_worker(self, request_id, date_from=None, date_to=None):
        try:
            rows = self.client.search_read_publish_history(date_from, date_to)
        except Exception as exc:
            self.after(0, self._show_error_if_current, request_id, str(exc))
            return
        self.after(
            0,
            self._render_history_if_current,
            request_id,
            rows,
            date_from,
            date_to,
        )

    def _render_history_if_current(self, request_id, rows, date_from, date_to):
        if request_id != self._load_request_id:
            return
        self._set_activity(False)
        self._render_history(rows, date_from, date_to)

    def _refresh_history(self):
        if self._check_thread and self._check_thread.is_alive():
            self.status_var.set("Không thể tải lại khi đang check. Hãy Stop trước.")
            return
        self._pending_check = False
        self._load_weeks()

    def _open_post_url(self, event):
        if self.tree.identify_region(event.x, event.y) != "cell":
            return
        if self.tree.identify_column(event.x) != "#3":
            return
        item_id = self.tree.identify_row(event.y)
        if not item_id or not item_id.startswith("record-"):
            return
        record_id = item_id.removeprefix("record-")
        record = self._rows.get(record_id)
        if record and record.external_post_url:
            webbrowser.open(record.external_post_url)

    def _update_cursor(self, event):
        if (
            self.tree.identify_region(event.x, event.y) == "cell"
            and self.tree.identify_column(event.x) in {"#3", "#11"}
        ):
            self.tree.configure(cursor="hand2")
        else:
            self.tree.configure(cursor="")

    def _render_history(
        self,
        rows: list[PublishHistory],
        date_from: str | None = None,
        date_to: str | None = None,
    ):
        rows = [row for row in rows if row is not None]
        if date_from and date_to:
            start = _parse_date(date_from)
            end = _parse_date(date_to)
            rows = [
                row for row in rows
                if _record_date(row)
                and start <= _parse_date(_record_date(row)) <= end
            ]
        self._all_rows = rows
        dates = sorted(
            {
                _record_date(row)
                for row in rows
                if _record_date(row)
            },
            reverse=True,
        )
        self.date_box.configure(values=("Tất cả", *dates))
        self.date_from.set("")
        self.date_from_display.set("Tất cả")
        self._apply_search(update_status=False)
        self.status_var.set(f"Đã tải {len(rows)} bài viết trong tuần đã chọn.")
        self._append_log(f"Đã tải {len(rows)} bài viết trong tuần đã chọn.")

    def _apply_search(self, update_status=True):
        search = self.search_var.get().strip().casefold()
        filter_date = _parse_date(self.date_from.get()) if self.date_from.get() else None
        selected_status = self.status_filter.get()
        if search:
            rows = [
                row for row in self._all_rows
                if search in row.user_name.casefold()
                or search in row.content_title.casefold()
            ]
        else:
            rows = list(self._all_rows)
        self._filtered_rows = [
            row for row in rows
            if _matches_filters(
                row,
                filter_date,
                filter_date,
                selected_status,
                self._last_results,
            )
        ]
        self._render_page()
        if update_status:
            self.status_var.set(
                f"{len(self._filtered_rows)}/{len(self._all_rows)} history records."
            )

    def _render_page(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        page_rows = self._filtered_rows
        self._rows = {str(row.id): row for row in page_rows}
        groups = {}
        for row in page_rows:
            groups.setdefault(row.user_name or "Unknown user", []).append(row)
        for user_name, user_rows in groups.items():
            group_id = self.tree.insert(
                "",
                "end",
                text=f"▼  {user_name}  ({len(user_rows)})",
                values=("", "", "", "", "", "", "", "", "", "", ""),
                tags=("group",),
                open=True,
            )
            for row in user_rows:
                initial_detail = row.detail or row.error_message
                if not row.external_post_url:
                    initial_check_status = "SKIPPED"
                elif (row.status or "").strip().casefold() == "published":
                    initial_check_status = "ALIVE"
                    if not initial_detail:
                        initial_detail = "OK"
                else:
                    initial_check_status = "PENDING"
                if not row.external_post_url and not initial_detail:
                    initial_detail = "Bỏ qua: không có Post URL"
                initial_last_checked = (
                    "ODOO"
                    if initial_check_status == "ALIVE"
                    else "—"
                )
                row_tag = (row.status or "").strip().casefold()
                self.tree.insert(
                    group_id,
                    "end",
                    iid=f"record-{row.id}",
                    text="",
                    values=(
                        row.id,
                        row.posted_at,
                        row.external_post_url,
                        row.status.upper(),
                        initial_check_status,
                        row.interaction_count,
                        row.comment_count,
                        row.share_count,
                        initial_detail,
                        initial_last_checked,
                        "Check lại" if row.external_post_url else "",
                    ),
                    tags=(row_tag,),
                )
        if self._pending_check:
            self._pending_check = False
            self.after(50, self._run_check_for_loaded_rows)

    def _start_check(self):
        if self._load_thread and self._load_thread.is_alive():
            return
        selected_records = self._selected_records()
        records_to_check = (
            selected_records if selected_records else self._filtered_rows
        )
        self._pending_check = False
        self.status_var.set(
            f"Đang chuẩn bị kiểm tra {len(records_to_check)} dòng..."
        )
        self._run_check_for_loaded_rows(records_to_check)

    def _selected_records(self):
        selected = []
        for item_id in self.tree.selection():
            if not item_id.startswith("record-"):
                continue
            record = self._rows.get(item_id.removeprefix("record-"))
            if record:
                selected.append(record)
        return selected

    def _selection_changed(self, _event=None):
        count = len(self._selected_records())
        if count >= 1:
            self.start_check_button.configure(
                text=f"▶ Recheck {count} dòng đã chọn"
            )
            self.status_var.set(
                f"Đã chọn {count} bài viết. Bấm nút để chỉ check các dòng này."
            )
        else:
            self.start_check_button.configure(text="▶ Check toàn bộ danh sách")
            self.status_var.set("Chưa chọn dòng; tool sẽ check toàn bộ danh sách.")

    def _choose_librewolf_dir(self):
        selected = filedialog.askdirectory(
            parent=self,
            title="Chọn thư mục LibreWolf của người dùng",
        )
        if not selected:
            return
        self._librewolf_dir = selected
        self.librewolf_display.set(os.path.basename(os.path.normpath(selected)))
        self.status_var.set(f"Đã chọn LibreWolf: {selected}")

    def _read_timeout(self):
        try:
            value = float(self.timeout_seconds.get())
        except (TypeError, ValueError):
            raise ValueError("Thời gian timeout phải là số từ 1 đến 300 giây.")
        if not 1 <= value <= 300:
            raise ValueError("Thời gian timeout phải từ 1 đến 300 giây.")
        return value

    def _recheck_failed(self):
        if self._check_thread and self._check_thread.is_alive():
            self.status_var.set("Hãy Stop lần check hiện tại trước.")
            return
        records = []
        for record in self._filtered_rows:
            if not record.external_post_url:
                continue
            result = self._last_results.get(record.id)
            item_id = f"record-{record.id}"
            check_status = ""
            detail = ""
            if self.tree.exists(item_id):
                values = self.tree.item(item_id, "values")
                check_status = str(values[4]).upper() if len(values) > 4 else ""
                detail = str(values[8]).upper() if len(values) > 8 else ""

            is_failed = False
            if result:
                if result.result.lower() in ("error", "stopped"):
                    is_failed = True
                elif "TIMEOUT" in (result.reason or "").upper():
                    is_failed = True
            elif check_status in ("ERROR", "TIMEOUT", "STOPPED"):
                is_failed = True
            elif "TIMEOUT" in detail or "ERROR" in detail:
                is_failed = True

            if is_failed:
                records.append(record)

        if not records:
            self.status_var.set("Không có dòng lỗi hoặc timeout cần check lại.")
            return
        self._launch_check(records, min(8, len(records)), 25)

    _recheck_timeouts = _recheck_failed

    def _show_context_menu(self, event):
        item_id = self.tree.identify_row(event.y)
        if item_id and item_id.startswith("record-"):
            current_selection = self.tree.selection()
            if item_id not in current_selection:
                self.tree.selection_set(item_id)
            try:
                self.context_menu.tk_popup(event.x_root, event.y_root)
            finally:
                self.context_menu.grab_release()

    def _recheck_selected_context(self):
        selected = self._selected_records()
        if not selected:
            self.status_var.set("Chưa chọn dòng nào để check lại.")
            return
        if self._check_thread and self._check_thread.is_alive():
            self.status_var.set("Hãy Stop lần check hiện tại trước.")
            return
        self._launch_check(selected, min(8, len(selected)), 25)

    def _open_selected_post_url(self):
        selected = self._selected_records()
        if selected and selected[0].external_post_url:
            webbrowser.open(selected[0].external_post_url)

    def _recheck_row(self, record):
        if self._check_thread and self._check_thread.is_alive():
            self.status_var.set("Hãy Stop lần check hiện tại trước.")
            return
        self._launch_check([record], 1, 1)

    def _handle_row_action(self, event):
        if self.tree.identify_region(event.x, event.y) != "cell":
            return
        if self.tree.identify_column(event.x) != "#11":
            return
        item_id = self.tree.identify_row(event.y)
        if item_id and item_id.startswith("record-"):
            record = self._rows.get(item_id.removeprefix("record-"))
            if record:
                self._recheck_row(record)

    def _run_check_for_loaded_rows(self, records=None):
        if self._check_thread and self._check_thread.is_alive():
            return
        records = [
            record for record in (records or self._filtered_rows)
            if record.external_post_url
        ]
        checkable_records = [
            record for record in self._filtered_rows if record.external_post_url
        ]
        if not records:
            self.status_var.set(
                "Không có link trong bộ lọc hiện tại "
                f"(có {len(checkable_records)} link có thể kiểm tra)."
            )
            return
        try:
            browser_count = max(1, min(8, int(self.browser_count.get())))
        except (TypeError, ValueError):
            self.status_var.set("Số trình duyệt phải là số từ 1 đến 8.")
            return
        try:
            batch_size = max(1, min(500, int(self.batch_size.get())))
        except (TypeError, ValueError):
            self.status_var.set("Kích thước batch phải là số từ 1 đến 500.")
            return
        browser_count = min(browser_count, len(records))
        self._launch_check(records, browser_count, batch_size)

    def _launch_check(self, records, browser_count, batch_size):
        if not self._librewolf_dir:
            messagebox.showwarning(
                "Chưa chọn LibreWolf",
                "Vui lòng chọn thư mục LibreWolf trước khi chạy kiểm tra.",
                parent=self,
            )
            return
        try:
            timeout_seconds = self._read_timeout()
        except ValueError as exc:
            self.status_var.set(str(exc))
            return
        librewolf_dir = self._librewolf_dir or None
        self._stop_event.clear()
        self.stop_button.configure(state="normal")
        self._set_activity(True, f"Đang check 0/{len(records)} bài viết...")
        self._append_log(
            f"Bắt đầu check {len(records)} bài viết, {browser_count} trình duyệt, "
            f"batch {batch_size}."
        )
        browser_count = min(browser_count, len(records))
        show_browser = bool(self.show_browser.get())
        self.status_var.set(
            f"Starting check for {len(records)} link(s) with "
            f"{browser_count} browser(s), batch size {batch_size}, "
            f"timeout {timeout_seconds:g}s, "
            f"{'visible' if show_browser else 'background'} mode"
            + "."
        )
        self._check_thread = threading.Thread(
            target=self._check_worker,
            args=(
                records,
                browser_count,
                batch_size,
                show_browser,
                timeout_seconds,
                librewolf_dir,
            ),
            daemon=True,
        )
        self._check_thread.start()

    def _check_worker(
        self,
        records,
        browser_count,
        batch_size,
        show_browser,
        timeout_seconds,
        librewolf_dir,
    ):
        counter = {"checked": 0}
        counter_lock = threading.Lock()
        worker_errors = []
        batch_buffer = []
        buffer_lock = threading.Lock()
        pending = queue.Queue()
        for record in records:
            pending.put(record)

        def flush_buffer(force=False):
            items_to_flush = []
            with buffer_lock:
                if (force and batch_buffer) or len(batch_buffer) >= batch_size:
                    items_to_flush = list(batch_buffer)
                    batch_buffer.clear()
            if items_to_flush:
                self._flush_odoo_batch(items_to_flush)
                self.after(
                    0,
                    self._append_log,
                    f"Đã đồng bộ Odoo batch: {len(items_to_flush)} bài viết.",
                )

        def worker():
            checker = None
            profile_dir = None
            try:
                checker = LibreWolfChecker(
                    self._stop_event,
                    headless=not show_browser,
                    librewolf_dir=librewolf_dir,
                )
                if browser_count > 1:
                    profile_dir = tempfile.mkdtemp(prefix="gbsubmit-profile-")
                    shutil.copytree(checker.profile, profile_dir, dirs_exist_ok=True)
                    checker = LibreWolfChecker(
                        self._stop_event,
                        profile_path=profile_dir,
                        headless=not show_browser,
                        librewolf_dir=librewolf_dir,
                    )
                checker.start()
                while not self._stop_event.is_set():
                    try:
                        record = pending.get_nowait()
                    except queue.Empty:
                        break

                    self.after(0, self._set_checking_row, record.id)
                    result = None
                    try:
                        result = checker.check(
                            record.external_post_url, timeout_seconds
                        )
                    except Exception as exc:
                        result = LinkCheckResult("error", f"CHECK_ERROR: {exc}")

                    # Check for driver crash or lost connection
                    is_driver_dead = (
                        result
                        and result.result == "error"
                        and any(
                            err_sig in str(result.reason)
                            for err_sig in (
                                "DRIVER_ERROR",
                                "WebDriverException",
                                "InvalidSessionIdException",
                                "NoSuchWindowException",
                                "MaxRetryError",
                                "Failed to establish a new connection",
                                "Connection refused",
                            )
                        )
                    )

                    if is_driver_dead and not self._stop_event.is_set():
                        self.after(
                            0,
                            self._append_log,
                            f"Trình duyệt gặp sự cố ({result.reason[:60]}...). Đang thử khởi động lại...",
                        )
                        try:
                            checker.stop()
                            time.sleep(1.0)
                            checker.start()
                            self.after(
                                0,
                                self._append_log,
                                "Khởi động lại trình duyệt thành công, thử kiểm tra lại link vừa rồi...",
                            )
                            result = checker.check(
                                record.external_post_url, timeout_seconds
                            )
                        except Exception as restart_exc:
                            self.after(
                                0,
                                self._append_log,
                                f"Không thể khởi động lại trình duyệt: {restart_exc}. Luồng này sẽ dừng lại.",
                            )
                            with counter_lock:
                                counter["checked"] += 1
                                checked = counter["checked"]

                            with buffer_lock:
                                batch_buffer.append((record, result))
                                should_flush = len(batch_buffer) >= batch_size

                            self.after(
                                0,
                                self._update_check_row,
                                record,
                                result,
                                checked,
                                len(records),
                            )
                            pending.task_done()
                            if should_flush:
                                flush_buffer()
                            break

                    with counter_lock:
                        counter["checked"] += 1
                        checked = counter["checked"]

                    with buffer_lock:
                        batch_buffer.append((record, result))
                        should_flush = len(batch_buffer) >= batch_size

                    self.after(
                        0,
                        self._update_check_row,
                        record,
                        result,
                        checked,
                        len(records),
                    )
                    pending.task_done()

                    if should_flush:
                        flush_buffer()

            except Exception as exc:
                worker_errors.append(exc)
                self.after(
                    0,
                    self._append_log,
                    f"Luồng kiểm tra gặp sự cố: {exc}",
                )
            finally:
                if checker:
                    checker.stop()
                if profile_dir:
                    shutil.rmtree(profile_dir, ignore_errors=True)

        effective_browser_count = min(browser_count, len(records))
        threads = [
            threading.Thread(target=worker, daemon=True)
            for _ in range(effective_browser_count)
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        # If any records remain in queue because all workers stopped/failed:
        if not pending.empty() and not self._stop_event.is_set():
            fallback_reason = (
                f"CHECK_WORKER_ERROR: {worker_errors[0]}"
                if worker_errors
                else "CHECK_WORKER_ERROR: Trình duyệt gặp sự cố"
            )
            while not pending.empty():
                try:
                    record = pending.get_nowait()
                except queue.Empty:
                    break
                result = LinkCheckResult("error", fallback_reason)
                with counter_lock:
                    counter["checked"] += 1
                    checked = counter["checked"]
                with buffer_lock:
                    batch_buffer.append((record, result))
                self.after(
                    0,
                    self._update_check_row,
                    record,
                    result,
                    checked,
                    len(records),
                )
                pending.task_done()

        # Flush any remaining items in buffer
        flush_buffer(force=True)

        self.after(
            0,
            self._check_finished,
            counter["checked"],
            len(records),
            worker_errors[0] if worker_errors else None,
        )

    def _flush_odoo_batch(self, updates):
        if not updates:
            return
        payload = []
        for record, result in updates:
            if result.result == "dead":
                payload.append({
                    "id": record.id,
                    "status": "failed",
                    "detail": result.reason,
                })
            elif result.result == "alive":
                payload.append({
                    "id": record.id,
                    "status": "published",
                    "detail": "OK",
                    "interaction_count": result.interactions,
                    "comment_count": result.comments,
                    "share_count": result.shares,
                })
        if not payload:
            for record, result in updates:
                if result.result == "alive":
                    self.after(
                        0,
                        self._set_check_detail,
                        record.id,
                        "OK",
                    )
            return
        try:
            self.client.batch_update_publish_history_full(payload)
            for record, result in updates:
                if result.result not in {"dead", "alive"}:
                    continue
                if result.result == "alive":
                    self.after(
                        0,
                        self._set_check_detail,
                        record.id,
                        "OK",
                    )
                if result.result == "alive" and record.status == "published":
                    continue
                self.after(
                    0,
                    self._set_odoo_status,
                    record.id,
                    "FAILED" if result.result == "dead" else "PUBLISHED",
                )
        except Exception as exc:
            for record, _result in updates:
                self.after(0, self._mark_update_error, record.id, str(exc))

    def _set_check_detail(self, record_id, detail):
        item_id = f"record-{record_id}"
        if self.tree.exists(item_id):
            values = list(self.tree.item(item_id, "values"))
            values[8] = detail
            self.tree.item(item_id, values=values)

    def _update_check_row(self, record, result, checked, total):
        item_id = f"record-{record.id}"
        if not self.tree.exists(item_id):
            return
        checked_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        values = list(self.tree.item(item_id, "values"))
        values[4] = result.result.upper()
        values[5] = result.interactions
        values[6] = result.comments
        values[7] = result.shares
        values[8] = (
            f"{result.reason} | Đã reload {result.reload_count} lần"
            if result.reload_count
            else result.reason
        )
        values[9] = checked_at
        values[10] = "Check lại"
        self._last_results[record.id] = result
        self.tree.item(item_id, values=values, tags=(result.result,))
        self.activity_var.set(f"Đang check {checked}/{total} bài viết...")
        self._append_log(
            f"[{checked}/{total}] ID {record.id}: "
            f"{result.result.upper()} - {result.reason} "
            f"(Likes: {result.interactions}, Comments: {result.comments}, Shares: {result.shares})"
        )
        self.status_var.set(f"Checked {checked}/{total}: {result.reason}")

    def _set_checking_row(self, record_id):
        item_id = f"record-{record_id}"
        if self.tree.exists(item_id):
            self.tree.item(item_id, tags=("checking",))

    def _set_odoo_status(self, record_id, status):
        item_id = f"record-{record_id}"
        if self.tree.exists(item_id):
            values = list(self.tree.item(item_id, "values"))
            values[3] = status
            self.tree.item(item_id, values=values)

    def _mark_update_error(self, record_id, message):
        item_id = f"record-{record_id}"
        if self.tree.exists(item_id):
            values = list(self.tree.item(item_id, "values"))
            values[3] = "UPDATE ERROR"
            self.tree.item(item_id, values=values)
        self.status_var.set(f"Odoo update failed for {record_id}: {message}")

    def _stop_check(self):
        if self._check_thread and self._check_thread.is_alive():
            self._stop_event.set()
            self._append_log("Người dùng yêu cầu dừng check.")
            self.status_var.set("Stopping check...")

    def _check_finished(self, checked, total, worker_error=None):
        self.stop_button.configure(state="disabled")
        self._set_activity(False)
        if worker_error:
            self.status_var.set(f"Check failed: {worker_error}")
            self._append_log(f"Check lỗi: {worker_error}")
            return
        if self._stop_event.is_set() and checked < total:
            self.status_var.set(f"Stopped after {checked}/{total} links.")
            self._append_log(f"Đã dừng check sau {checked}/{total} bài viết.")
        else:
            self.status_var.set(f"Check completed: {checked}/{total} links.")
            self._append_log(f"Check hoàn tất: {checked}/{total} bài viết.")

    def _show_error(self, message: str):
        self._pending_check = False
        self.status_var.set(f"Error: {message}")

    def _set_activity(self, active, message=""):
        if active:
            self.activity_var.set(message or "Đang xử lý...")
            self.activity_bar.start(12)
        else:
            self.activity_var.set("")
            self.activity_bar.stop()

    def _append_log(self, message):
        if not hasattr(self, "log_text"):
            return
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.configure(state="normal")
        self.log_text.insert("end", f"[{timestamp}] {message}\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _clear_filters(self):
        self.date_from.set("")
        self.date_from_display.set("Tất cả")
        self.search_var.set("")
        self.status_filter.set("Tất cả")
        self._apply_search()

    def _open_date_picker(self, target):
        values = {
            "from": (self.date_from, self.date_from_display),
        }
        variable, display = values[target]
        value = variable.get()
        DatePicker(self, value, lambda selected: self._set_date(target, selected))

    def _set_date(self, target, selected_date: date):
        value = selected_date.isoformat()
        if target == "from":
            self.date_from.set(value)
            self.date_from_display.set(value)
        self._apply_search()

    def _close(self):
        self._stop_event.set()
        self.destroy()

    def _back_to_tool_selection(self):
        if self._check_thread and self._check_thread.is_alive():
            self.status_var.set("Hãy Stop lần check hiện tại trước.")
            return
        self._stop_event.set()
        self.destroy()
        if self.on_back:
            self.on_back()


class DatePicker(tk.Toplevel):
    """Small dependency-free calendar popup for selecting a date."""

    def __init__(self, parent, value: str, on_select):
        super().__init__(parent)
        self.on_select = on_select
        selected = _parse_date(value) or date.today()
        self.year = selected.year
        self.month = selected.month
        self.title("Chọn ngày")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        self._build()
        self._render()

    def _build(self):
        toolbar = ttk.Frame(self, padding=8)
        toolbar.grid(row=0, column=0, sticky="ew")
        self.month_label = ttk.Label(toolbar, width=18, anchor="center")
        self.month_label.grid(row=0, column=1, padx=8)
        ttk.Button(toolbar, text="‹", width=3, command=self._previous_month).grid(
            row=0, column=0
        )
        ttk.Button(toolbar, text="›", width=3, command=self._next_month).grid(
            row=0, column=2
        )
        self.calendar_frame = ttk.Frame(self, padding=(8, 0, 8, 8))
        self.calendar_frame.grid(row=1, column=0)

    def _render(self):
        for child in self.calendar_frame.winfo_children():
            child.destroy()
        self.month_label.configure(
            text=f"{calendar.month_name[self.month]} {self.year}"
        )
        for column, weekday in enumerate(("Mo", "Tu", "We", "Th", "Fr", "Sa", "Su")):
            ttk.Label(
                self.calendar_frame,
                text=weekday,
                width=4,
                anchor="center",
            ).grid(row=0, column=column, pady=(0, 4))
        for row, week in enumerate(calendar.monthcalendar(self.year, self.month), 1):
            for column, day_number in enumerate(week):
                if not day_number:
                    continue
                ttk.Button(
                    self.calendar_frame,
                    text=str(day_number),
                    width=4,
                    command=lambda day=day_number: self._select(day),
                ).grid(row=row, column=column, padx=1, pady=1)

    def _select(self, day_number):
        self.on_select(date(self.year, self.month, day_number))
        self.destroy()

    def _previous_month(self):
        if self.month == 1:
            self.month, self.year = 12, self.year - 1
        else:
            self.month -= 1
        self._render()

    def _next_month(self):
        if self.month == 12:
            self.month, self.year = 1, self.year + 1
        else:
            self.month += 1
        self._render()


def _parse_date(value: str):
    value = value.strip()
    if not value:
        return None
    for pattern in ("%m/%d/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, pattern).date()
        except ValueError:
            continue
    raise ValueError("Ngày phải có dạng MM/DD/YYYY.")


def _record_date(record) -> str:
    if record is None:
        return ""
    value = (record.posted_at or "").strip()
    if not value:
        return ""
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        try:
            return _parse_date(value[:10]).isoformat()
        except ValueError:
            return ""


def _record_posted_on_or_after(record, start_date: date, end_date: date) -> bool:
    """Check an Odoo datetime against the inclusive desktop date range."""
    if record is None:
        return False
    value = (record.posted_at or "").strip()
    if not value:
        return False
    try:
        posted_date = datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError:
        posted_date = _parse_date(value[:10])
    return start_date <= posted_date <= end_date


def _matches_filters(
    record, start_date, end_date, selected_status, check_results=None
):
    if record is None:
        return False
    if selected_status != "Tất cả":
        odoo_status = (record.status or "").strip().upper()
        result = (check_results or {}).get(record.id)
        if result:
            check_status = result.result.upper()
            detail = result.reason.upper()
        else:
            post_url = (record.external_post_url or "").strip()
            if not post_url:
                check_status = "SKIPPED"
            elif odoo_status == "PUBLISHED":
                check_status = "ALIVE"
            else:
                check_status = "PENDING"
            detail = " ".join(
                str(value or "")
                for value in (record.detail, record.error_message)
            ).upper()
            if any(
                marker in detail
                for marker in (
                    "TIMEOUT",
                    "CHECK_ERROR",
                    "CHECK_WORKER_ERROR",
                    "DRIVER_ERROR",
                    "SESSION_LOGIN_CHECKPOINT",
                )
            ):
                check_status = "ERROR"

        status_matches = selected_status in {odoo_status, check_status}
        if selected_status == "TIMEOUT":
            status_matches = "TIMEOUT" in detail
        if not status_matches:
            return False
    if not start_date and not end_date:
        return True
    value = (record.posted_at or "").strip()
    if not value:
        return False
    try:
        posted_date = datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError:
        posted_date = _parse_date(value[:10])
    if start_date and posted_date < start_date:
        return False
    if end_date and posted_date > end_date:
        return False
    return True


def _matches_date_range(record, start_date: date, end_date: date) -> bool:
    if record is None:
        return False
    value = (record.posted_at or "").strip()
    if not value:
        return False
    try:
        posted_date = datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError:
        posted_date = _parse_date(value[:10])
    if start_date and posted_date < start_date:
        return False
    if end_date and posted_date > end_date:
        return False
    return True
