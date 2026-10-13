"""Local Windows credential storage protected by the current user profile."""

import base64
import ctypes
import json
import os
from ctypes import POINTER, Structure, byref, c_char, c_void_p, cast, memmove
from ctypes.wintypes import DWORD


class _DataBlob(Structure):
    _fields_ = [("cbData", DWORD), ("pbData", POINTER(c_char))]


_CRYPTPROTECT_UI_FORBIDDEN = 0x1


def _storage_path():
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    folder = os.path.join(base, "GBSubmit")
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, "login.json")


def _protect(value: str) -> str:
    raw = value.encode("utf-8")
    source = _DataBlob(len(raw), cast(ctypes.create_string_buffer(raw), POINTER(c_char)))
    target = _DataBlob()
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    if not crypt32.CryptProtectData(
        byref(source), None, None, None, None, _CRYPTPROTECT_UI_FORBIDDEN, byref(target)
    ):
        raise OSError("Windows could not protect the saved password.")
    try:
        protected = ctypes.string_at(target.pbData, target.cbData)
        return base64.b64encode(protected).decode("ascii")
    finally:
        kernel32.LocalFree(target.pbData)


def _unprotect(value: str) -> str:
    protected = base64.b64decode(value)
    source = _DataBlob(
        len(protected),
        cast(ctypes.create_string_buffer(protected), POINTER(c_char)),
    )
    target = _DataBlob()
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    if not crypt32.CryptUnprotectData(
        byref(source), None, None, None, None, _CRYPTPROTECT_UI_FORBIDDEN, byref(target)
    ):
        raise OSError("Windows could not decrypt the saved password.")
    try:
        return ctypes.string_at(target.pbData, target.cbData).decode("utf-8")
    finally:
        kernel32.LocalFree(target.pbData)


def load_login():
    try:
        with open(_storage_path(), "r", encoding="utf-8") as file:
            data = json.load(file)
        password = _unprotect(data.get("password", "")) if data.get("password") else ""
        return {
            "url": data.get("url", ""),
            "database": data.get("database", ""),
            "username": data.get("username", ""),
            "password": password,
            "remember_password": bool(data.get("remember_password")),
        }
    except (OSError, ValueError, json.JSONDecodeError):
        return {}


def save_login(url, database, username, password, remember_password):
    data = {
        "url": url,
        "database": database,
        "username": username,
        "remember_password": bool(remember_password),
    }
    if remember_password and password:
        data["password"] = _protect(password)
    else:
        data["password"] = ""
    with open(_storage_path(), "w", encoding="utf-8") as file:
        json.dump(data, file)


def clear_saved_password():
    saved = load_login()
    if saved:
        save_login(
            saved.get("url", ""),
            saved.get("database", ""),
            saved.get("username", ""),
            "",
            False,
        )
