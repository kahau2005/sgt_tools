"""Small XML-RPC client for the Odoo login flow."""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
import re
from urllib.parse import urlparse, urlunparse
from xmlrpc.client import Fault, SafeTransport, ServerProxy, Transport


LOCAL_TIMEZONE = timezone(timedelta(hours=7))
UTC = timezone.utc
ODOO_RPC_TIMEOUT_SECONDS = 30


class _TimeoutTransport(Transport):
    def __init__(self):
        super().__init__()
        self.timeout = ODOO_RPC_TIMEOUT_SECONDS

    def make_connection(self, host):
        connection = super().make_connection(host)
        connection.timeout = self.timeout
        return connection


class _TimeoutSafeTransport(SafeTransport):
    def __init__(self):
        super().__init__()
        self.timeout = ODOO_RPC_TIMEOUT_SECONDS

    def make_connection(self, host):
        connection = super().make_connection(host)
        connection.timeout = self.timeout
        return connection


@dataclass(frozen=True)
class OdooCredentials:
    url: str
    database: str
    username: str
    password: str
    uid: int


@dataclass(frozen=True)
class PublishHistory:
    id: int
    posted_at: str
    user_id: int | None
    user_name: str
    content_title: str
    project_id: int | None
    project_name: str
    group_link_id: int | None
    group_link_name: str
    is_free_group: bool
    free_group_url: str
    external_post_id: str
    external_post_url: str
    status: str
    detail: str
    error_message: str


@dataclass(frozen=True)
class GroupLink:
    id: int
    group_url: str
    alt_url: str
    group_name: str
    member_count: int
    group_type: str
    info_updated_at: str
    status: str


class OdooAuthenticationError(Exception):
    """Raised when Odoo cannot authenticate the supplied credentials."""


class OdooClient:
    def __init__(self, url: str, database: str, username: str, password: str):
        self.url = normalize_odoo_url(url)
        self.database = database.strip()
        self.username = username.strip()
        self.password = password

    def authenticate(self) -> OdooCredentials:
        if not self.database:
            raise OdooAuthenticationError("Database name is required.")
        if not self.username:
            raise OdooAuthenticationError("User is required.")
        if not self.password:
            raise OdooAuthenticationError("Password is required.")

        try:
            common = self._proxy("/xmlrpc/2/common")
            uid = common.authenticate(
                self.database,
                self.username,
                self.password,
                {},
            )
        except Exception as exc:
            raise OdooAuthenticationError(
                f"Could not connect to Odoo: {exc}"
            ) from exc

        if not isinstance(uid, int) or uid <= 0:
            raise OdooAuthenticationError(
                "Authentication failed. Check the Odoo URL, database, user and password."
            )

        credentials = OdooCredentials(
            url=self.url,
            database=self.database,
            username=self.username,
            password=self.password,
            uid=uid,
        )
        self.credentials = credentials
        return credentials

    def _object_proxy(self):
        return self._proxy("/xmlrpc/2/object")

    def _proxy(self, path):
        transport = (
            _TimeoutSafeTransport()
            if self.url.casefold().startswith("https://")
            else _TimeoutTransport()
        )
        return ServerProxy(
            f"{self.url}{path}",
            transport=transport,
            allow_none=True,
        )

    def search_read_publish_history(
        self,
        date_from: str | None = None,
        date_to: str | None = None,
        status: str | None = None,
    ) -> list[PublishHistory]:
        """Read dashboard history records from the sgt_gb_submit model."""
        domain = []
        if status:
            if status not in {"published", "failed", "blocked"}:
                raise ValueError(f"Unsupported history status: {status}")
            domain.append(("status", "=", status))
        if date_from:
            domain.append(("posted_at", ">=", _local_date_to_utc(date_from)))
        if date_to:
            next_day = datetime.strptime(date_to, "%Y-%m-%d").date() + timedelta(days=1)
            domain.append(
                ("posted_at", "<", _local_date_to_utc(next_day.isoformat()))
            )

        fields = [
            "id",
            "posted_at",
            "user_id",
            "user_name",
            "user_login",
            "user_display_name",
            "content_title",
            "project_id",
            "group_link_id",
            "is_free_group",
            "free_group_url",
            "external_post_id",
            "external_post_url",
            "status",
            "detail",
            "error_message",
        ]
        # Avoid requesting the complete history in one XML-RPC response.
        # Large responses can be closed by the server/proxy before the client
        # receives all bytes, which raises http.client.IncompleteRead.
        page_size = 200
        offset = 0
        records = []
        while True:
            page = self._object_proxy().execute_kw(
                self.database,
                self.credentials.uid,
                self.credentials.password,
                "sgt.social.publish.history",
                "search_read",
                [domain],
                {
                    "fields": fields,
                    "order": "posted_at desc, id desc",
                    "offset": offset,
                    "limit": page_size,
                },
            )
            records.extend(page)
            if len(page) < page_size:
                break
            offset += page_size

        return [
            _history_from_odoo(record)
            for record in records
            if isinstance(record, dict)
        ]

    def list_publish_history_weeks(self) -> list[tuple[str, str, str]]:
        """Return available local calendar weeks, newest first.

        Each item is ``(start_date, end_date, label)``.  ``read_group`` keeps
        the initial dashboard load small because it returns only aggregates.
        """
        groups = self._object_proxy().execute_kw(
            self.database,
            self.credentials.uid,
            self.credentials.password,
            "sgt.social.publish.history",
            "read_group",
            [[]],
            {
                "fields": ["posted_at"],
                "groupby": ["posted_at:week"],
                "orderby": "posted_at desc",
            },
        )
        weeks = _weeks_from_values(
            group.get("posted_at:week") or group.get("posted_at")
            for group in groups
        )
        if not weeks:
            raise OdooAuthenticationError(
                "Odoo trả về nhóm tuần nhưng không có giá trị ngày hợp lệ."
            )
        return weeks

    def update_publish_history_status(
        self,
        history_id: int,
        status: str,
        detail: str | None = None,
    ):
        if status not in {"published", "failed", "blocked"}:
            raise ValueError(f"Unsupported publishing history status: {status}")
        values = {"status": status}
        if detail is not None:
            values["detail"] = detail
        return self._execute_write(
            "sgt.social.publish.history",
            [history_id],
            values,
        )

    def batch_update_publish_history_status(self, updates):
        """Write history rows in groups sharing the same status/detail."""
        grouped = {}
        for history_id, status, detail in updates:
            if status not in {"published", "failed", "blocked"}:
                raise ValueError(f"Unsupported publishing history status: {status}")
            grouped.setdefault((status, detail), []).append(history_id)
        for (status, detail), history_ids in grouped.items():
            values = {"status": status, "detail": detail or False}
            self._execute_write("sgt.social.publish.history", history_ids, values)

    def update_group_link_status(self, group_link_id: int, status: str):
        if status not in {"available", "unavailable"}:
            raise ValueError(f"Unsupported group link status: {status}")
        return self._execute_write(
            "sgt.social.group.link",
            [group_link_id],
            {"status": status},
        )

    def batch_update_group_links(self, updates: list[dict]):
        """Update scraped group information without changing management status."""
        allowed = {
            "alt_url",
            "group_name",
            "member_count",
            "group_type",
        }
        payload = []
        for update in updates:
            group_link_id = update.get("id")
            if not isinstance(group_link_id, int):
                raise ValueError("Invalid group link ID.")
            values = {
                key: update[key]
                for key in allowed
                if key in update and update[key] is not None
            }
            if values:
                payload.append({"id": group_link_id, **values})
        if not payload:
            return []
        proxy = self._object_proxy()
        try:
            return proxy.execute_kw(
                self.database,
                self.credentials.uid,
                self.credentials.password,
                "sgt.social.group.link",
                "write_scraped_group_info_batch",
                [payload],
            )
        except Fault as error:
            if "write_scraped_group_info_batch" not in str(error):
                raise

            # Older Odoo deployments do not have the batch model method yet.
            # Keep syncing by using the supported public write API until the
            # module is upgraded on the server.
            updated_ids = []
            for item in payload:
                values = {
                    key: value
                    for key, value in item.items()
                    if key != "id"
                }
                self._execute_write(
                    "sgt.social.group.link",
                    [item["id"]],
                    values,
                )
                updated_ids.append(item["id"])
            return updated_ids

    def list_group_projects(self) -> list[tuple[int, str]]:
        records = self._object_proxy().execute_kw(
            self.database,
            self.credentials.uid,
            self.credentials.password,
            "sgt.social.destination",
            "search_read",
            [[]],
            {"fields": ["id", "name"], "order": "name asc, id asc"},
        )
        return [
            (record["id"], record.get("name") or f"Project {record['id']}")
            for record in records
        ]

    def list_group_links(
        self, project_id: int, link_type: str
    ) -> list[GroupLink]:
        if link_type not in {"pool", "blacklist"}:
            raise ValueError(f"Unsupported group link type: {link_type}")
        records = self._object_proxy().execute_kw(
            self.database,
            self.credentials.uid,
            self.credentials.password,
            "sgt.social.group.link",
            "search_read",
            [[
                ("project_id", "=", project_id),
                ("link_type", "=", link_type),
            ]],
            {
                "fields": [
                    "id",
                    "group_url",
                    "alt_url",
                    "group_name",
                    "member_count",
                    "group_type",
                    "info_updated_at",
                    "status",
                ],
                "order": "create_date desc, id desc",
                "limit": 200,
            },
        )
        return [_group_link_from_odoo(record) for record in records]

    def batch_update_group_link_status(self, updates):
        grouped = {}
        for group_link_id, status in updates:
            if status not in {"available", "unavailable"}:
                raise ValueError(f"Unsupported group link status: {status}")
            grouped.setdefault(status, []).append(group_link_id)
        for status, group_link_ids in grouped.items():
            self._execute_write(
                "sgt.social.group.link",
                list(set(group_link_ids)),
                {"status": status},
            )

    def _execute_write(self, model: str, record_ids: list[int], values: dict):
        return self._object_proxy().execute_kw(
            self.database,
            self.credentials.uid,
            self.credentials.password,
            model,
            "write",
            [record_ids, values],
        )

    @property
    def credentials(self) -> OdooCredentials:
        if not hasattr(self, "_credentials"):
            raise OdooAuthenticationError("Authenticate before using Odoo data APIs.")
        return self._credentials

    @credentials.setter
    def credentials(self, value: OdooCredentials):
        self._credentials = value


def _history_from_odoo(record: dict) -> PublishHistory:
    project = record.get("project_id") or []
    group_link = record.get("group_link_id") or []
    # The addon field displayed as "User" is user_id. It is the personal
    # publishing-history owner and is also the field used by Odoo's grouping.
    user_id, linked_user_name = _many2one_value(record.get("user_id") or [])
    user_name = (
        record.get("user_display_name")
        or record.get("user_name")
        or record.get("user_login")
        or linked_user_name
        or "Unknown User"
    )
    return PublishHistory(
        id=record["id"],
        posted_at=_format_odoo_datetime(record.get("posted_at")),
        user_id=user_id,
        user_name=user_name,
        content_title=record.get("content_title") or "",
        project_id=project[0] if project else None,
        project_name=project[1] if len(project) > 1 else "",
        group_link_id=group_link[0] if group_link else None,
        group_link_name=group_link[1] if len(group_link) > 1 else "",
        is_free_group=bool(record.get("is_free_group")),
        free_group_url=record.get("free_group_url") or "",
        external_post_id=record.get("external_post_id") or "",
        external_post_url=record.get("external_post_url") or "",
        status=record.get("status") or "",
        detail=record.get("detail") or "",
        error_message=record.get("error_message") or "",
    )


def _group_link_from_odoo(record: dict) -> GroupLink:
    return GroupLink(
        id=record["id"],
        group_url=record.get("group_url") or "",
        alt_url=record.get("alt_url") or "",
        group_name=record.get("group_name") or "",
        member_count=int(record.get("member_count") or 0),
        group_type=_selection_label(record.get("group_type")),
        info_updated_at=_format_odoo_datetime(record.get("info_updated_at")),
        status=_selection_label(record.get("status")),
    )


def _selection_label(value) -> str:
    if isinstance(value, (list, tuple)):
        value = value[1] if len(value) > 1 else (value[0] or "")
    labels = {
        "public": "Public Group",
        "private": "Private Group",
        "buy_sell": "Buy & Sell Group",
    }
    return labels.get(str(value), str(value or ""))
    return PublishHistory(
        id=record["id"],
        posted_at=_format_odoo_datetime(record.get("posted_at")),
        user_id=user_id,
        user_name=user_name,
        content_title=record.get("content_title") or "",
        project_id=project[0] if project else None,
        project_name=project[1] if len(project) > 1 else "",
        group_link_id=group_link[0] if group_link else None,
        group_link_name=group_link[1] if len(group_link) > 1 else "",
        is_free_group=bool(record.get("is_free_group")),
        free_group_url=record.get("free_group_url") or "",
        external_post_id=record.get("external_post_id") or "",
        external_post_url=record.get("external_post_url") or "",
        status=record.get("status") or "",
        detail=record.get("detail") or "",
        error_message=record.get("error_message") or "",
    )


def _many2one_value(value) -> tuple[int | None, str]:
    """Normalize Odoo many2one values returned by XML-RPC."""
    if isinstance(value, (list, tuple)):
        identifier = value[0] if value else None
        name = value[1] if len(value) > 1 else ""
        return identifier if isinstance(identifier, int) else None, str(name or "")
    if isinstance(value, dict):
        identifier = value.get("id")
        name = value.get("display_name") or value.get("name") or ""
        return identifier if isinstance(identifier, int) else None, str(name or "")
    if isinstance(value, str):
        return None, value.strip()
    return None, ""


def _format_odoo_datetime(value: str | None) -> str:
    """Convert Odoo's UTC-naive datetime string to local display time."""
    if not value:
        return ""
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed.astimezone(LOCAL_TIMEZONE).strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        return value


def _parse_odoo_group_date(value) -> date | None:
    """Parse Odoo read_group date keys, including values such as ``2026-W41``."""
    if isinstance(value, dict):
        value = value.get("value") or value.get("display_name")
    text = str(value or "").strip()
    if not text:
        return None

    week_match = re.search(r"(?<!\d)(\d{4})-W(\d{1,2})(?!\d)", text, re.I)
    if not week_match:
        week_match = re.search(
            r"\bW(\d{1,2})\s+(\d{4})\b", text, re.I
        )
        if week_match:
            week_match = (week_match.group(2), week_match.group(1))
    if week_match:
        try:
            if isinstance(week_match, tuple):
                iso_year, iso_week = week_match
            else:
                iso_year, iso_week = week_match.group(1), week_match.group(2)
            return datetime.strptime(
                f"{iso_year}-W{int(iso_week):02d}-1",
                "%G-W%V-%u",
            ).date()
        except ValueError:
            return None

    for candidate in (text, text[:10]):
        try:
            return datetime.fromisoformat(candidate.replace("Z", "+00:00")).date()
        except ValueError:
            continue
    return None


def _weeks_from_values(values) -> list[tuple[str, str, str]]:
    starts = set()
    for value in values:
        group_date = _parse_odoo_group_date(value)
        if group_date is None:
            continue
        starts.add(group_date - timedelta(days=group_date.weekday()))

    return [
        (
            week_start.isoformat(),
            (week_start + timedelta(days=6)).isoformat(),
            (
                f"W{week_start.isocalendar().week:02d} "
                f"{week_start.isocalendar().year}"
            ),
        )
        for week_start in sorted(starts, reverse=True)
    ]


def _local_date_to_utc(value: str) -> str:
    local_date = datetime.strptime(value, "%Y-%m-%d").date()
    local_start = datetime.combine(local_date, time.min, tzinfo=LOCAL_TIMEZONE)
    return local_start.astimezone(UTC).replace(tzinfo=None).strftime(
        "%Y-%m-%d %H:%M:%S"
    )


def normalize_odoo_url(value: str) -> str:
    """Return a clean HTTP(S) base URL without a trailing slash."""
    raw_url = value.strip()
    if not raw_url:
        raise OdooAuthenticationError("Odoo URL is required.")

    parsed = urlparse(raw_url if "://" in raw_url else f"https://{raw_url}")
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise OdooAuthenticationError("Enter a valid Odoo HTTP(S) URL.")

    return urlunparse((parsed.scheme, parsed.netloc, "", "", "", "")).rstrip("/")
