import signal
import sys
from collections.abc import Sequence

from ginext import Adw, Gio, GLib, GLibUnix, Gtk

from commander.components.settings import CommanderSettings
from commander.components.window import CommanderWindow
from commander.providers import CommanderProviderRegistry
from commander.providers.builtin import builtin_providers

APP_ID = "org.ginext.Commander"


class CommanderApp(Gtk.Application, type_name="GoiCommanderApp"):

    def __init__(self) -> None:
        super().__init__(
            application_id=APP_ID,
            flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE,
        )
        self._sigint_handle = 0
        self.settings = CommanderSettings()
        self.providers = CommanderProviderRegistry()
        self.providers.register_many(builtin_providers())

    def do_startup(self) -> None:
        Gtk.Application.do_startup(self)
        Adw.init()
        self.providers.load_entry_points()
        self._install_sigint_handler()

    def _install_sigint_handler(self) -> None:
        try:
            self._sigint_handle = GLibUnix.signal_add(
                GLib.PRIORITY_DEFAULT,
                signal.SIGINT,
                self._on_sigint,
            )
        except AttributeError:
            signal.signal(signal.SIGINT, lambda *_: self.quit())

    def _on_sigint(self, *_args: object) -> bool:
        print("\n[commander] caught SIGINT, quitting", file=sys.stderr)
        self.quit()
        return False

    def do_activate(self) -> None:
        window = self.get_active_window()
        if window is None:
            window = CommanderWindow(application=self)
        window.present()

    def do_command_line(self, command_line: Gio.ApplicationCommandLine) -> int:
        self.activate()
        return 0


def main(argv: Sequence[str] | None = None) -> int:
    app = CommanderApp()
    return app.run(list(sys.argv if argv is None else argv))
