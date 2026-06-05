import sys

from ginext import Adw, Gio

from playground.window import PlaygroundWindow


class PlaygroundApplication(Adw.Application):
    def __init__(self):
        super().__init__(application_id="org.ginext.Playground")
        self.window = None

        quit_action = Gio.SimpleAction.new("quit", None)
        quit_action.activate.connect(self._on_quit, owner=self)
        self.add_action(quit_action)
        self.set_accels_for_action("app.quit", ["<primary>q"])

    def do_activate(self):
        if self.window is None:
            self.window = PlaygroundWindow(self)
        self.window.present()

    def _on_quit(self, _action, _param):
        self.quit()


def main(argv=None):
    app = PlaygroundApplication()
    return app.run(sys.argv if argv is None else argv)
