"""Separate window reserved for the group checker."""

import tkinter as tk
import threading
import os
import webbrowser
import shutil
import tempfile
import queue
import time
from datetime import datetime
from tkinter import ttk
from tkinter import filedialog, messagebox

from services.odoo_client import GroupLink, OdooClient, OdooCredentials
from services.link_checker import LibreWolfChecker

PURPLE = "#684080"
PURPLE_DARK = "#56336c"
BACKGROUND = "#f4f5f7"
TEXT = "#172554"
MUTED = "#667085"


class GroupCheckWindow(tk.Toplevel):
    """Display group links loaded from Odoo."""

    def __init__(
        self, parent, credentials: OdooCredentials, on_back=None
    ):
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
        self._projects = {}
        self._request_id = 0
        self._loaded_links = {"pool": [], "blacklist": []}
        self._check_status = {}
        self._check_thread = None
        self._stop_event = threading.Event()
        self.project_var = tk.StringVar(value="Đang tải project...")
        self.status_filter_var = tk.StringVar(value="Tất cả")
        self.status_var = tk.StringVar(value="Đang tải project...")
        self.loading_var = tk.StringVar(value="")
        self.browser_count = tk.IntVar(value=1)
        self.batch_size = tk.IntVar(value=25)
        self.show_browser = tk.BooleanVar(value=False)
        self._librewolf_dir = ""
        self.librewolf_display = tk.StringVar(value="Chưa chọn thư mục")
        self._build_styles()
        self.title("GB SUBMIT - Check Group")
        self.geometry("1240x650")
        self.minsize(900, 520)
        self.configure(background=BACKGROUND)
        self._build_ui()
        self._load_projects()

    def _build_styles(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Group.TFrame", background=BACKGROUND)
        style.configure("GroupHeader.TFrame", background=PURPLE)
        style.configure("GroupHeaderSmall.TLabel", background=PURPLE,
                        foreground="#ddd2e6", font=("Segoe UI", 9, "bold"))
        style.configure("GroupHeaderTitle.TLabel", background=PURPLE,
                        foreground="white", font=("Segoe UI", 16, "bold"))
        style.configure("GroupHeaderInfo.TLabel", background=PURPLE,
                        foreground="#eee8f2", font=("Segoe UI", 9))
        style.configure("GroupPanel.TLabelframe", background="white",
                        foreground=TEXT)
        style.configure("GroupPanel.TLabelframe.Label", background="white",
                        foreground=PURPLE_DARK, font=("Segoe UI", 9, "bold"))
        style.configure("GroupPanel.TFrame", background="white")
        style.configure("GroupPanel.TLabel", background="white", foreground=TEXT)
        style.configure("Group.Treeview", rowheight=28,
                        background="white", fieldbackground="white",
                        foreground=TEXT)
        style.configure("Group.Treeview.Heading", background=PURPLE,
                        foreground="white", font=("Segoe UI", 9, "bold"))
        style.map("Group.Treeview.Heading",
                  background=[("active", PURPLE_DARK)])
        style.configure("GroupPrimary.TButton", background=PURPLE,
                        foreground="white", font=("Segoe UI", 9, "bold"),
                        padding=(10, 5))
        style.map("GroupPrimary.TButton",
                  background=[("active", PURPLE_DARK), ("disabled", "#b9a8c5")])

    def _build_ui(self):
        header = ttk.Frame(self, style="GroupHeader.TFrame", padding=(20, 12))
        header.pack(fill="x")
        ttk.Label(header, text="GB SUBMIT",
                  style="GroupHeaderSmall.TLabel").pack(anchor="w")
        ttk.Label(header, text="Check Group",
                  style="GroupHeaderTitle.TLabel").pack(anchor="w")
        ttk.Label(
            header,
            text=f"Odoo: {self.credentials.username}",
            style="GroupHeaderInfo.TLabel",
        ).pack(anchor="w", pady=(3, 0))
        ttk.Button(
            header,
            text="← Chọn tool",
            command=self._back_to_tool_selection,
        ).pack(anchor="e")

        run_panel = ttk.LabelFrame(
            self, text="CHẠY KIỂM TRA GROUP",
            style="GroupPanel.TLabelframe", padding=(12, 8)
        )
        run_panel.pack(fill="x", padx=24, pady=(0, 12))
        ttk.Label(run_panel, text="Số trình duyệt",
                  style="GroupPanel.TLabel").grid(
            row=0, column=0, padx=2, sticky="w"
        )
        ttk.Spinbox(
            run_panel,
            from_=1,
            to=8,
            textvariable=self.browser_count,
            width=5,
        ).grid(row=1, column=0, padx=2, pady=(3, 0), sticky="w")
        ttk.Label(run_panel, text="Batch",
                  style="GroupPanel.TLabel").grid(
            row=0, column=1, padx=(16, 2), sticky="w"
        )
        ttk.Spinbox(
            run_panel,
            from_=1,
            to=500,
            textvariable=self.batch_size,
            width=6,
        ).grid(row=1, column=1, padx=(16, 2), pady=(3, 0), sticky="w")
        ttk.Checkbutton(
            run_panel,
            text="Hiện trình duyệt",
            variable=self.show_browser,
        ).grid(row=0, column=2, rowspan=2, padx=(20, 2), sticky="w")
        ttk.Button(
            run_panel,
            text="Chọn thư mục LibreWolf",
            command=self._choose_librewolf_dir,
            style="GroupPrimary.TButton",
        ).grid(row=0, column=3, padx=(20, 8), sticky="w")
        ttk.Label(
            run_panel,
            textvariable=self.librewolf_display,
            style="GroupPanel.TLabel",
        ).grid(row=1, column=3, padx=(20, 8), pady=(3, 0), sticky="w")
        self.check_button = ttk.Button(
            run_panel,
            text="Check toàn bộ danh sách",
            command=self._start_check,
            style="GroupPrimary.TButton",
        )
        self.check_button.grid(row=0, column=4, rowspan=2, padx=(18, 8), sticky="w")
        self.stop_button = ttk.Button(
            run_panel,
            text="■ Stop",
            command=self._stop_check,
            state="disabled",
        )
        self.stop_button.grid(row=0, column=5, rowspan=2, padx=(4, 8), sticky="w")

        controls = ttk.Frame(self, style="GroupPanel.TFrame",
                             padding=(12, 8))
        controls.pack(fill="x")
        ttk.Label(controls, text="Project",
                  style="GroupPanel.TLabel").pack(side="left")
        self.project_box = ttk.Combobox(
            controls,
            textvariable=self.project_var,
            state="readonly",
            width=42,
        )
        self.project_box.pack(side="left", padx=(8, 16))
        self.project_box.bind("<<ComboboxSelected>>", self._project_selected)
        ttk.Label(
            controls, text="Check Status", style="GroupPanel.TLabel"
        ).pack(side="left", padx=(18, 0))
        self.status_filter_box = ttk.Combobox(
            controls,
            textvariable=self.status_filter_var,
            values=("Tất cả", "PENDING", "ALIVE", "PARTIAL", "DEAD",
                    "ERROR", "TIMEOUT", "STOPPED"),
            state="readonly",
            width=14,
        )
        self.status_filter_box.pack(side="left", padx=(8, 16))
        self.status_filter_box.bind(
            "<<ComboboxSelected>>", self._status_filter_selected
        )
        self.reload_button = ttk.Button(
            controls,
            text="Tải lại",
            command=self._load_current_links,
            style="GroupPrimary.TButton",
            state="disabled",
        )
        self.reload_button.pack(side="left")

        ttk.Label(
            self,
            textvariable=self.status_var,
            foreground=MUTED,
        ).pack(anchor="w", padx=24, pady=(0, 2))
        loading_row = ttk.Frame(self, style="GroupPanel.TFrame")
        loading_row.pack(fill="x", padx=24, pady=(0, 4))
        ttk.Label(
            loading_row,
            textvariable=self.loading_var,
            foreground=PURPLE_DARK,
        ).pack(side="left")
        self.loading_bar = ttk.Progressbar(
            loading_row, mode="indeterminate", length=180
        )
        self.loading_bar.pack(side="left", padx=(10, 0))
        log_frame = ttk.LabelFrame(
            self, text="NHẬT KÝ", style="GroupPanel.TLabelframe", padding=(6, 3)
        )
        log_frame.pack(fill="x", padx=24, pady=(0, 8))
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

        self.tabs = ttk.Notebook(self)
        self.tabs.pack(fill="both", expand=True, padx=24, pady=(0, 8))
        self.pool_tab = ttk.Frame(self.tabs)
        self.blacklist_tab = ttk.Frame(self.tabs)
        self.tabs.add(self.pool_tab, text="Pool")
        self.tabs.add(self.blacklist_tab, text="Blacklist")
        self.tabs.bind("<<NotebookTabChanged>>", self._tab_selected)
        self._build_table(self.pool_tab)
        self._build_table(self.blacklist_tab)
        self._set_loading(True, "Đang tải danh sách project...")
        self._append_log("Bắt đầu tải danh sách project từ Odoo.")

    def _build_table(self, parent):
        columns = (
            "group_url",
            "alt_url",
            "group_name",
            "members",
            "type",
            "updated",
            "status",
            "check_status",
            "action",
        )
        tree = ttk.Treeview(
            parent,
            columns=columns,
            show="headings",
            selectmode="extended",
            style="Group.Treeview",
        )
        headings = {
            "group_url": "Group URL",
            "alt_url": "Alt URL",
            "group_name": "Group Name",
            "members": "Members",
            "type": "Type",
            "updated": "Information Updated On",
            "status": "Status",
            "check_status": "Check Status",
            "action": "Action",
        }
        for column, heading in headings.items():
            tree.heading(column, text=heading)
        tree.column("group_url", width=270)
        tree.column("alt_url", width=230)
        tree.column("group_name", width=190)
        tree.column("members", width=85, anchor="e")
        tree.column("type", width=125)
        tree.column("updated", width=165)
        tree.column("status", width=115)
        tree.column("check_status", width=115)
        tree.column("action", width=95, anchor="center")
        tree.tag_configure("available", foreground="#176b36")
        tree.tag_configure("caution", foreground="#9a6700")
        tree.tag_configure("unavailable", foreground="#a51d2d")
        tree.tag_configure("alive", foreground="#176b36")
        tree.tag_configure("partial", foreground="#9a6700")
        tree.tag_configure("dead", foreground="#a51d2d")
        tree.tag_configure("error", foreground="#9a6700")
        tree.tag_configure("timeout", foreground="#9a6700")
        tree.tag_configure("stopped", foreground=MUTED)
        tree.tag_configure("checking", background="#fff2a8", foreground="#7a5b00")
        tree.tag_configure("unknown", foreground=TEXT)
        tree.pack(fill="both", expand=True, side="left")
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=tree.yview)
        scrollbar.pack(fill="y", side="right")
        tree.configure(yscrollcommand=scrollbar.set)
        tree.bind("<Button-1>", self._handle_table_click)
        tree.bind("<<TreeviewSelect>>", self._selection_changed)
        tree.bind("<Double-1>", self._open_group_url)
        parent.tree = tree

    def _load_projects(self):
        self.status_var.set("Đang tải danh sách project...")
        self._set_loading(True, "Đang tải dữ liệu project...")
        threading.Thread(target=self._projects_worker, daemon=True).start()

    def _projects_worker(self):
        try:
            projects = self.client.list_group_projects()
        except Exception as exc:
            self.after(0, self._project_load_error, str(exc))
            return
        self.after(0, self._render_projects, projects)

    def _project_load_error(self, message):
        self._set_loading(False)
        self.status_var.set(f"Lỗi tải project: {message}")
        self._append_log(f"Lỗi tải project: {message}")

    def _render_projects(self, projects):
        self._set_loading(False)
        self._projects = {
            f"{name} (ID {project_id})": project_id
            for project_id, name in projects
        }
        labels = list(self._projects)
        self.project_box.configure(values=labels)
        if labels:
            self.project_var.set("Chọn project")
            self.status_var.set("Chọn project, sau đó chọn Pool hoặc Blacklist.")
            self._append_log(f"Đã tải {len(labels)} project.")
        else:
            self.project_var.set("Không có project")
            self.status_var.set("Odoo không có project.")
            self._append_log("Odoo không có project nào.")

    def _project_selected(self, _event=None):
        self.reload_button.configure(state="normal")
        self._append_log(f"Đã chọn project: {self.project_var.get()}.")
        self._load_current_links()

    def _tab_selected(self, _event=None):
        if self._projects.get(self.project_var.get()):
            self._load_current_links()

    def _load_current_links(self):
        project_id = self._projects.get(self.project_var.get())
        if not project_id:
            self.status_var.set("Vui lòng chọn project trước.")
            return
        link_type = "pool" if self.tabs.index("current") == 0 else "blacklist"
        self._request_id += 1
        request_id = self._request_id
        self.status_var.set(f"Đang tải danh sách {link_type.title()}...")
        self._set_loading(True, f"Đang tải dữ liệu {link_type.title()}...")
        self._append_log(
            f"Bắt đầu tải {link_type.title()} của project {self.project_var.get()}."
        )
        self._clear_table(link_type)
        threading.Thread(
            target=self._links_worker,
            args=(request_id, project_id, link_type),
            daemon=True,
        ).start()

    def _links_worker(self, request_id, project_id, link_type):
        try:
            links = self.client.list_group_links(project_id, link_type)
        except Exception as exc:
            self.after(0, self._show_link_error, request_id, str(exc))
            return
        self.after(0, self._render_links, request_id, link_type, links)

    def _show_link_error(self, request_id, message):
        if request_id == self._request_id:
            self._set_loading(False)
            self.status_var.set(f"Lỗi tải group link: {message}")
            self._append_log(f"Lỗi tải group link: {message}")

    def _render_links(self, request_id, link_type, links: list[GroupLink]):
        if request_id != self._request_id:
            return
        self._set_loading(False)
        self._loaded_links[link_type] = links
        self._render_filtered_links(link_type)
        self.status_var.set(
            f"Đã tải {len(links)} group link trong {link_type.title()}."
        )
        self._append_log(
            f"Đã tải {len(links)} group link trong {link_type.title()}."
        )

    def _set_loading(self, loading, message=""):
        if loading:
            self.loading_var.set(message or "Đang tải dữ liệu...")
            self.loading_bar.start(12)
            self.project_box.configure(state="disabled")
            self.status_filter_box.configure(state="disabled")
            self.reload_button.configure(state="disabled")
            self.check_button.configure(state="disabled")
            self.tabs.state(["disabled"])
        else:
            self.loading_var.set("")
            self.loading_bar.stop()
            self.project_box.configure(state="readonly")
            self.status_filter_box.configure(state="readonly")
            self.tabs.state(["!disabled"])
            self.reload_button.configure(
                state="normal" if self._projects.get(self.project_var.get()) else "disabled"
            )
            self.check_button.configure(state="normal")

    def _append_log(self, message):
        if not hasattr(self, "log_text"):
            return
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.configure(state="normal")
        self.log_text.insert("end", f"[{timestamp}] {message}\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _status_filter_selected(self, _event=None):
        link_type = "pool" if self.tabs.index("current") == 0 else "blacklist"
        self._render_filtered_links(link_type)

    def _render_filtered_links(self, link_type):
        tree = self.pool_tab.tree if link_type == "pool" else self.blacklist_tab.tree
        for item in tree.get_children():
            tree.delete(item)
        selected_status = self.status_filter_var.get()
        links = self._loaded_links[link_type]
        if selected_status != "Tất cả":
            links = [
                link for link in links
                if self._check_status.get(link.id, "PENDING").casefold()
                == selected_status.casefold()
            ]
        for link in links:
            status_key = self._check_status.get(link.id, "PENDING").casefold()
            if status_key not in {
                "pending", "alive", "partial", "dead", "error",
                "timeout", "stopped",
            }:
                status_key = "unknown"
            tree.insert(
                "",
                "end",
                iid=f"group-{link.id}",
                tags=(status_key,),
                values=(
                    link.group_url,
                    link.alt_url,
                    link.group_name,
                    f"{link.member_count:,}",
                    link.group_type,
                    link.info_updated_at,
                    link.status,
                    self._check_status.get(link.id, "PENDING"),
                    "Check lại",
                ),
            )
        if self._loaded_links[link_type]:
            self.status_var.set(
                f"Hiển thị {len(links)}/{len(self._loaded_links[link_type])} "
                f"group link trong {link_type.title()}."
            )

    def _clear_table(self, link_type):
        tree = self.pool_tab.tree if link_type == "pool" else self.blacklist_tab.tree
        self._loaded_links[link_type] = []
        for item in tree.get_children():
            tree.delete(item)

    def _handle_table_click(self, event):
        tree = event.widget
        if tree.identify_region(event.x, event.y) != "cell":
            return
        if tree.identify_column(event.x) == "#9":
            item_id = tree.identify_row(event.y)
            if item_id and item_id.startswith("group-"):
                self._check_one(int(item_id.removeprefix("group-")))
            self.status_var.set(
                "Đã đưa group vào hàng đợi kiểm tra."
            )

    def _open_group_url(self, event):
        tree = event.widget
        if tree.identify_region(event.x, event.y) != "cell":
            return
        column = tree.identify_column(event.x)
        if column not in {"#1", "#2"}:
            return
        item_id = tree.identify_row(event.y)
        if not item_id:
            return
        values = tree.item(item_id, "values")
        value_index = 0 if column == "#1" else 1
        url = str(values[value_index]).strip() if len(values) > value_index else ""
        if url:
            webbrowser.open(url)

    def _current_links(self):
        link_type = "pool" if self.tabs.index("current") == 0 else "blacklist"
        links = list(self._loaded_links[link_type])
        selected = self.status_filter_var.get()
        if selected != "Tất cả":
            links = [
                link for link in links
                if link.status.casefold() == selected.casefold()
            ]
        return links

    def _start_check(self):
        if not self._require_librewolf_dir():
            return
        if self._check_thread and self._check_thread.is_alive():
            self.status_var.set("Đang check, hãy Stop trước.")
            return
        selected_links = self._selected_links()
        selected_only = len(selected_links) >= 2
        links = selected_links if selected_only else []
        if not links:
            links = self._current_links()
        if not links:
            self.status_var.set("Không có group link phù hợp để check.")
            self._append_log("Không có group link phù hợp để check.")
            return
        try:
            browser_count = max(1, min(8, int(self.browser_count.get())))
            batch_size = max(1, int(self.batch_size.get()))
        except (TypeError, ValueError):
            self.status_var.set("Số trình duyệt và Batch phải là số hợp lệ.")
            return
        self._stop_event.clear()
        self.stop_button.configure(state="normal")
        self.check_button.configure(state="disabled")
        self._set_loading(True, f"Đang check 0/{len(links)} group...")
        self._append_log(
            f"Bắt đầu check {'các dòng đã chọn' if selected_only else 'danh sách hiện tại'}: "
            f"{len(links)} group, {browser_count} trình duyệt, "
            f"batch {batch_size}."
        )
        self._check_thread = threading.Thread(
            target=self._check_worker,
            args=(links, browser_count, batch_size, bool(self.show_browser.get())),
            daemon=True,
        )
        self._check_thread.start()

    def _selected_links(self):
        link_type = "pool" if self.tabs.index("current") == 0 else "blacklist"
        tree = self.pool_tab.tree if link_type == "pool" else self.blacklist_tab.tree
        selected_ids = {
            item_id for item_id in tree.selection()
            if item_id.startswith("group-")
        }
        return [
            link for link in self._loaded_links[link_type]
            if f"group-{link.id}" in selected_ids
        ]

    def _selection_changed(self, _event=None):
        count = len(self._selected_links())
        if count >= 2:
            self.check_button.configure(text=f"Check {count} dòng đã chọn")
            self.status_var.set(
                f"Đã chọn {count} group. Bấm nút để chỉ check các dòng này."
            )
        else:
            self.check_button.configure(text="Check toàn bộ danh sách")
            if count == 1:
                self.status_var.set(
                    "Đã chọn 1 group; tool sẽ check toàn bộ danh sách hiện tại."
                )
            else:
                self.status_var.set("Chưa chọn nhiều dòng; tool sẽ check toàn bộ danh sách.")

    def _check_one(self, link_id):
        if not self._require_librewolf_dir():
            return
        link = next(
            (item for item in self._loaded_links["pool"] + self._loaded_links["blacklist"]
             if item.id == link_id),
            None,
        )
        if not link:
            return
        if self._check_thread and self._check_thread.is_alive():
            self.status_var.set("Đang check danh sách, hãy Stop trước.")
            return
        self._stop_event.clear()
        self.stop_button.configure(state="normal")
        self.check_button.configure(state="disabled")
        self._set_loading(True, "Đang check 1 group...")
        self._append_log(f"Bắt đầu check riêng group ID {link.id}.")
        self._check_thread = threading.Thread(
            target=self._check_worker,
            args=([link], 1, 1, bool(self.show_browser.get())),
            daemon=True,
        )
        self._check_thread.start()

    def _check_worker(self, links, browser_count, batch_size, show_browser):
        checked = 0
        worker_error = None
        for batch_start in range(0, len(links), batch_size):
            batch = links[batch_start:batch_start + batch_size]
            pending = queue.Queue()
            for link in batch:
                pending.put(link)
            results = []
            results_lock = threading.Lock()
            progress_lock = threading.Lock()
            progress = {"checked": 0}

            def worker():
                checker = None
                profile_dir = None
                try:
                    checker = LibreWolfChecker(
                        self._stop_event,
                        headless=not show_browser,
                        librewolf_dir=self._librewolf_dir or None,
                    )
                    if browser_count > 1:
                        profile_dir = tempfile.mkdtemp(prefix="gbsubmit-group-profile-")
                        shutil.copytree(
                            checker.profile, profile_dir, dirs_exist_ok=True
                        )
                        checker = LibreWolfChecker(
                            self._stop_event,
                            profile_path=profile_dir,
                            headless=not show_browser,
                            librewolf_dir=self._librewolf_dir or None,
                        )
                    checker.start()
                    while not pending.empty():
                        try:
                            link = pending.get_nowait()
                        except queue.Empty:
                            break
                        self.after(0, self._set_group_checking, link.id)
                        result = checker.check_group(
                            link.group_url,
                            link.alt_url,
                        )
                        with results_lock:
                            results.append((link, result))
                        with progress_lock:
                            progress["checked"] += 1
                            checked_number = progress["checked"]
                        self.after(
                            0,
                            self._update_group_row,
                            link,
                            result,
                            checked_number + batch_start,
                            len(links),
                        )
                        pending.task_done()
                except Exception as exc:
                    nonlocal worker_error
                    worker_error = exc
                finally:
                    if checker:
                        checker.stop()
                    if profile_dir:
                        shutil.rmtree(profile_dir, ignore_errors=True)

            threads = [
                threading.Thread(target=worker, daemon=True)
                for _ in range(min(browser_count, len(batch)))
            ]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
            updates = []
            for link, result in results:
                updates.append(self._group_update_payload(link, result))
            checked += len(results)
            if updates:
                try:
                    self.after(
                        0,
                        self._append_log,
                        f"Đang đồng bộ batch {batch_start // batch_size + 1} "
                        f"({len(updates)} group) lên Odoo...",
                    )
                    sync_started = time.perf_counter()
                    updated_ids = self.client.batch_update_group_links(updates)
                    sync_elapsed = time.perf_counter() - sync_started
                    self.after(
                        0,
                        self._append_log,
                        f"Đã gửi batch {batch_start // batch_size + 1} "
                        f"({len(updates)} group) lên Odoo trong "
                        f"{sync_elapsed:.2f} giây.",
                    )
                    if len(updated_ids) != len(updates):
                        self.after(
                            0,
                            self._append_log,
                            f"Odoo chỉ cập nhật được {len(updated_ids)}/{len(updates)} "
                            f"group trong batch này.",
                        )
                    else:
                        self.after(
                            0,
                            self._append_log,
                            f"Đồng bộ batch {batch_start // batch_size + 1} hoàn tất.",
                        )
                except Exception as exc:
                    worker_error = exc
                    self.after(0, self._append_log, f"Lỗi cập nhật Odoo: {exc}")
            if self._stop_event.is_set():
                break
        self.after(0, self._check_finished, checked, len(links), worker_error)

    @staticmethod
    def _group_update_payload(link, result):
        values = {"id": link.id}
        if result.alt_url:
            values["alt_url"] = result.alt_url
        if result.group_name:
            values["group_name"] = result.group_name
        if result.member_count is not None:
            values["member_count"] = result.member_count
        group_type = result.group_type.casefold().strip()
        if group_type in {"public", "private", "buy_sell"}:
            values["group_type"] = group_type
        elif group_type in {"public group", "công khai"}:
            values["group_type"] = "public"
        elif group_type in {"private group", "riêng tư"}:
            values["group_type"] = "private"
        elif group_type in {"buy & sell", "buy&sell", "buy sell"}:
            values["group_type"] = "buy_sell"
        return values

    def _set_group_checking(self, link_id):
        for tab in (self.pool_tab, self.blacklist_tab):
            item_id = f"group-{link_id}"
            if tab.tree.exists(item_id):
                tab.tree.item(item_id, tags=("checking",))

    def _update_group_row(self, link, result, checked, total):
        self._check_status[link.id] = result.result
        item_id = f"group-{link.id}"
        values_update = {
            "alt_url": result.alt_url,
            "group_name": result.group_name,
            "member_count": result.member_count,
            "group_type": result.group_type,
            "check_status": result.result,
        }
        for tab in (self.pool_tab, self.blacklist_tab):
            tree = tab.tree
            if not tree.exists(item_id):
                continue
            values = list(tree.item(item_id, "values"))
            if values_update["alt_url"]:
                values[1] = values_update["alt_url"]
            if values_update["group_name"]:
                values[2] = values_update["group_name"]
            if values_update["member_count"] is not None:
                values[3] = f"{values_update['member_count']:,}"
            if values_update["group_type"]:
                values[4] = values_update["group_type"]
            values[7] = values_update["check_status"]
            tree.item(item_id, values=values, tags=(result.result.casefold(),))
            break
        self.loading_var.set(f"Đang check {checked}/{total} group...")
        self.status_var.set(f"Checked {checked}/{total}: {result.reason}")
        self._append_log(
            f"[{checked}/{total}] ID {link.id}: {result.result} - {result.reason}"
        )
        if result.alt_url:
            self._append_log(f"ID {link.id}: lấy được Alt URL {result.alt_url}")

    def _check_finished(self, checked, total, worker_error=None):
        self.stop_button.configure(state="disabled")
        self.check_button.configure(state="normal")
        self._set_loading(False)
        if worker_error:
            self.status_var.set(f"Lỗi check: {worker_error}")
            self._append_log(f"Check lỗi: {worker_error}")
        elif self._stop_event.is_set() and checked < total:
            self.status_var.set(f"Đã dừng sau {checked}/{total} group.")
            self._append_log(f"Đã dừng sau {checked}/{total} group.")
        else:
            self.status_var.set(f"Check hoàn tất: {checked}/{total} group.")
            self._append_log(f"Check hoàn tất: {checked}/{total} group.")

    def _stop_check(self):
        if self._check_thread and self._check_thread.is_alive():
            self._stop_event.set()
            self.status_var.set("Đang dừng check...")
            self._append_log("Người dùng yêu cầu dừng check.")

    def _choose_librewolf_dir(self):
        selected = filedialog.askdirectory(
            parent=self,
            title="Chọn thư mục LibreWolf của người dùng",
        )
        if not selected:
            return
        self._librewolf_dir = selected
        self.librewolf_display.set(
            os.path.basename(os.path.normpath(selected))
        )
        self.status_var.set(f"Đã chọn LibreWolf: {selected}")

    def _require_librewolf_dir(self):
        if self._librewolf_dir:
            return True
        messagebox.showwarning(
            "Chưa chọn LibreWolf",
            "Vui lòng chọn thư mục LibreWolf trước khi chạy kiểm tra.",
            parent=self,
        )
        return False

    def _back_to_tool_selection(self):
        self.destroy()
        if self.on_back:
            self.on_back()
