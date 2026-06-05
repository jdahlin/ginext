python
import gdb


def _signal_number():
    try:
        siginfo = gdb.parse_and_eval("$_siginfo")
    except gdb.error:
        return None

    if siginfo.type.code == gdb.TYPE_CODE_VOID:
        return None

    try:
        return int(siginfo["si_signo"])
    except gdb.error:
        return None


def _select_live_inferior():
    for inferior in gdb.inferiors():
        if not inferior.is_valid() or inferior.pid == 0:
            continue
        try:
            threads = inferior.threads()
            if not threads:
                continue
        except gdb.error:
            continue
        threads[0].switch()
        return inferior
    return None


class GoiRunToSigabrt(gdb.Command):
    """Run and continue past normal child exits until SIGABRT or process exit."""

    def __init__(self):
        super().__init__("goi-run-to-sigabrt", gdb.COMMAND_RUNNING)

    def invoke(self, arg, from_tty):
        gdb.execute("run")

        while True:
            signo = _signal_number()
            if signo is not None:
                if signo == 6:
                    print("[goi-gdb] stopped on SIGABRT")
                else:
                    print("[goi-gdb] stopped on signal %d" % signo)
                return

            inferior = _select_live_inferior()
            if inferior is None:
                print("[goi-gdb] all inferiors exited")
                return

            print("[goi-gdb] continuing after non-signal stop")
            gdb.execute("continue")


GoiRunToSigabrt()
end
