"""Application entry point for the desktop Check Link tool."""

from gui.login_window import LoginWindow
from gui.mode_selection_window import ModeSelectionWindow


def main():
    app = LoginWindow()
    app.on_authenticated = lambda credentials: _open_dashboard(app, credentials)
    app.mainloop()


def _open_dashboard(login, credentials):
    login.withdraw()
    _show_mode_selection(login, credentials)


def _show_mode_selection(login, credentials):
    login.mode_selection_window = ModeSelectionWindow(
        login,
        credentials,
        on_close=login.deiconify,
        on_tool_back=lambda: _show_mode_selection(login, credentials),
    )
    login.mode_selection_window.deiconify()
    login.mode_selection_window.lift()
    login.mode_selection_window.focus_force()


if __name__ == "__main__":
    main()
