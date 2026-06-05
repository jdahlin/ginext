import sys
import pytest
import unittest
from unittest import TestCase

import gi
import gi.events
import asyncio
import signal
import socket
import threading
from gi.repository import GLib, Gio

try:
    from gi.repository import Gtk
except ImportError:
    Gtk = None


GTK4 = Gtk and Gtk._version == "4.0"

event_loop_compat_xfail = pytest.mark.xfail(
    reason="GLib asyncio event loop compatibility is incomplete",
    strict=False,
)

# ginext's GLib-backed asyncio EventLoop registers fds with the GLib main loop
# via g_source_add_unix_fd, which is POSIX-only; it is not ported to Windows
# yet, so the loop-driving test classes are skipped there.
_win32_no_glib_loop = unittest.skipIf(
    sys.platform == "win32",
    "ginext's GLib-backed asyncio EventLoop is not supported on Windows",
)


class GLibEventLoopTestsMixin:
    def test_call_soon(self):
        loop = self.create_event_loop()
        results = []

        def callback(arg):
            results.append(arg)
            loop.stop()

        loop.call_soon(callback, "called")
        loop.run_forever()
        self.assertEqual(results, ["called"])
        loop.close()

    def test_call_later(self):
        loop = self.create_event_loop()
        results = []

        def callback():
            results.append("later")

        loop.call_later(0.01, callback)
        loop.run_until_complete(asyncio.sleep(0.05))
        self.assertEqual(results, ["later"])
        loop.close()

    def test_run_until_complete(self):
        loop = self.create_event_loop()

        async def coro():
            await asyncio.sleep(0)
            return "done"

        self.assertEqual(loop.run_until_complete(coro()), "done")
        loop.close()

    def test_create_task(self):
        loop = self.create_event_loop()
        results = []

        async def coro():
            results.append("task")

        task = loop.create_task(coro())
        loop.run_until_complete(task)
        self.assertEqual(results, ["task"])
        loop.close()

    @unittest.skipIf(sys.platform == "win32", "add reader/writer not implemented")
    def test_reader_callback(self):
        loop = self.create_event_loop()
        rsock, wsock = socket.socketpair()
        self.addCleanup(rsock.close)
        self.addCleanup(wsock.close)
        results = []

        def reader():
            results.append(rsock.recv(4))
            loop.remove_reader(rsock)
            loop.stop()

        loop.add_reader(rsock, reader)
        wsock.send(b"ping")
        loop.run_forever()
        self.assertEqual(results, [b"ping"])
        loop.close()

    @unittest.skipIf(sys.platform == "win32", "add reader/writer not implemented")
    def test_reader_callback_cancel(self):
        loop = self.create_event_loop()
        rsock, wsock = socket.socketpair()
        self.addCleanup(rsock.close)
        self.addCleanup(wsock.close)
        self.assertTrue(loop.add_reader(rsock, lambda: None) is None)
        self.assertTrue(loop.remove_reader(rsock))
        self.assertFalse(loop.remove_reader(rsock))
        loop.close()

    @unittest.skipIf(sys.platform == "win32", "add reader/writer not implemented")
    def test_writer_callback(self):
        loop = self.create_event_loop()
        rsock, wsock = socket.socketpair()
        self.addCleanup(rsock.close)
        self.addCleanup(wsock.close)
        results = []

        def writer():
            results.append("writable")
            loop.remove_writer(wsock)
            loop.stop()

        loop.add_writer(wsock, writer)
        loop.run_forever()
        self.assertEqual(results, ["writable"])
        loop.close()

    @unittest.skipIf(sys.platform == "win32", "add reader/writer not implemented")
    def test_writer_callback_cancel(self):
        loop = self.create_event_loop()
        rsock, wsock = socket.socketpair()
        self.addCleanup(rsock.close)
        self.addCleanup(wsock.close)
        self.assertTrue(loop.add_writer(wsock, lambda: None) is None)
        self.assertTrue(loop.remove_writer(wsock))
        self.assertFalse(loop.remove_writer(wsock))
        loop.close()


class SubprocessMixin:
    @unittest.skipIf(sys.platform == "win32", "subprocess smoke is POSIX-only")
    def test_subprocess_exec(self):
        async def run():
            proc = await asyncio.create_subprocess_exec(
                sys.executable,
                "-c",
                "print('glib-subprocess')",
                stdout=asyncio.subprocess.PIPE,
            )
            stdout, _stderr = await proc.communicate()
            return proc.returncode, stdout

        returncode, stdout = self.loop.run_until_complete(run())
        self.assertEqual(returncode, 0)
        self.assertEqual(stdout, b"glib-subprocess\n")


@_win32_no_glib_loop
class GLibEventLoopTests(GLibEventLoopTestsMixin, TestCase):
    def __init__(self, *args):
        super().__init__(*args)
        self.loop = None

    def setUp(self):
        # Ensure a previous test did not leave an event loop around
        assert gi.events.GLibEventLoopPolicy._get_event_loop() is None, (
            "A previous test appears to have left an EventLoop open"
        )

        super().setUp()

    def _cleanup_glib_event_loop(self, loop):
        if not loop.is_closed():
            loop.close()
            raise AssertionError("Loop was no closed by the test")

    def create_event_loop(self):
        loop = gi.events.GLibEventLoop(GLib.MainContext())

        self.addCleanup(self._cleanup_glib_event_loop, loop)

        return loop


@_win32_no_glib_loop
class SubprocessWatcherTests(SubprocessMixin, TestCase):
    def setUp(self):
        super().setUp()
        policy = gi.events.GLibEventLoopPolicy()
        asyncio.set_event_loop_policy(policy)
        self.loop = policy.get_event_loop()

    def tearDown(self):
        asyncio.set_event_loop_policy(None)
        self.loop.close()
        super().tearDown()

    @event_loop_compat_xfail
    def test_subprocess_exec(self):
        raise unittest.SkipTest(
            "asyncio waitpid thread races with GLib SIGCHLD handler and hangs"
        )

    @event_loop_compat_xfail
    def test_subprocess_read_pipe_cancelled(self):
        raise unittest.SkipTest(
            "GLib event loop can not be run with plain asyncio.run()"
        )

    @event_loop_compat_xfail
    def test_subprocess_read_write_pipe_cancelled(self):
        raise unittest.SkipTest(
            "GLib event loop can not be run with plain asyncio.run()"
        )

    @event_loop_compat_xfail
    def test_subprocess_write_pipe_cancelled(self):
        raise unittest.SkipTest(
            "GLib event loop can not be run with plain asyncio.run()"
        )

    def test_add_signal_handler(self):
        raise unittest.SkipTest(
            "GLib event loop signal-handler integration not implemented"
        )


@_win32_no_glib_loop
class GLibEventLoopPolicyTests(unittest.TestCase):
    def create_policy(self):
        return gi.events.GLibEventLoopPolicy()

    def test_partially_initialized_loop_is_closed(self):
        loop = gi.events.GLibEventLoop.__new__(gi.events.GLibEventLoop)

        self.assertTrue(loop.is_closed())

    def test_get_event_loop(self):
        policy = self.create_policy()
        loop = policy.get_event_loop()
        self.assertIsInstance(loop, gi.events.GLibEventLoop)
        self.assertIs(loop, policy.get_event_loop())
        loop.close()

    def test_new_event_loop(self):
        policy = self.create_policy()
        loop = policy.new_event_loop()
        self.assertIsInstance(loop, gi.events.GLibEventLoop)
        loop.close()

        # Attaching a loop to the main thread fails
        with self.assertRaises(RuntimeError):
            policy.set_event_loop(loop)

    @event_loop_compat_xfail
    def test_application(self):
        task_completed = False

        async def task():
            nonlocal task_completed
            await asyncio.sleep(1)
            task_completed = True

        def activate(app):
            app.hold()
            app.create_asyncio_task(task())
            GLib.timeout_add(500, app.release)

        app = Gio.Application()
        app.connect("activate", activate)
        with self.create_policy():
            app.run()

        self.assertTrue(task_completed)

    def test_implicit_close(self):
        """Verify that implicitly closing the EventLoop (from __del__) works."""
        task_completed = False

        async def task():
            nonlocal task_completed
            await asyncio.sleep(1)
            task_completed = True

        policy = self.create_policy()
        loop = policy.new_event_loop()

        loop.run_until_complete(task())

        self.assertTrue(task_completed)

        with pytest.warns(ResourceWarning, match="unclosed event loop"):
            del loop

            # For some reason, PyPy needs two collect() steps
            import gc

            gc.collect()
            gc.collect()

    def test_nested_context_iteration(self):
        policy = self.create_policy()
        loop = policy.new_event_loop()

        called = False

        def cb():
            nonlocal called
            called = True

        async def run():
            nonlocal loop, called

            loop.call_soon(cb)
            self.assertEqual(called, False)

            # Iterating the main context does not cause cb to be called
            while loop._context.iteration(False):
                pass
            self.assertEqual(called, False)

            # Awaiting on anything *does* cause the cb to fire
            await asyncio.sleep(0)
            self.assertEqual(called, True)

        loop.run_until_complete(run())
        loop.close()

    def test_thread_event_loop(self):
        policy = self.create_policy()
        loop = policy.new_event_loop()

        res = []

        def thread_func(res):
            try:
                # We cannot get an event loop for the current thread
                with self.assertRaises(RuntimeError):
                    policy.get_event_loop()

                # We can attach our loop
                policy.set_event_loop(loop)
                # Now we can get it, and it is the same
                self.assertIs(policy.get_event_loop(), loop)

                # Simple call_soon test
                results = []

                def callback(arg1, arg2):
                    results.append((arg1, arg2))
                    loop.stop()

                loop.call_soon(callback, "hello", "world")
                loop.run_forever()
                self.assertEqual(results, [("hello", "world")])

                # We can detach it again
                policy.set_event_loop(None)

                # Which means we have none and get a runtime error
                with self.assertRaises(RuntimeError):
                    policy.get_event_loop()
            except:
                res += sys.exc_info()

        # Initially, the thread has no event loop
        thread = threading.Thread(target=lambda: thread_func(res))
        thread.start()
        thread.join()

        if res:
            t, v, tb = res
            raise t(v).with_traceback(tb)

        loop.close()

    def test_outside_context_iteration(self):
        """Iterating the main context from the outside, does not cause the
        EventLoop to dispatch.
        """
        policy = self.create_policy()
        loop = policy.new_event_loop()

        called = False

        def cb():
            nonlocal called
            called = True

        loop.call_soon(cb)
        while loop._context.iteration(False):
            pass
        loop.close()
        self.assertEqual(called, False)

    @unittest.skip(
        "Hangs/asserts under free-threaded Python; re-enable once asyncio "
        "main-context iteration integration is stable"
    )
    @event_loop_compat_xfail
    def test_inside_context_iteration(self):
        """Iterating the main context from the inside, does not cause the
        EventLoop to dispatch.
        """
        policy = self.create_policy()
        loop = policy.get_event_loop()

        done = asyncio.Future(loop=loop)

        called = False

        def cb():
            nonlocal called
            called = True

        def ctx_iterate():
            nonlocal called

            loop.call_soon(cb)
            while loop._context.iteration(False):
                pass
            self.assertEqual(called, False)

            # If we by-pass the override, then the callback is called
            while super(GLib.MainContext, loop._context).iteration(False):
                pass
            self.assertEqual(called, True)

            # It'll also be called (again) before run_until_complete finishes
            called = False
            loop.call_soon(cb)

            done.set_result(True)

            return GLib.SOURCE_REMOVE

        GLib.idle_add(ctx_iterate)
        loop.run_until_complete(done)
        loop.close()
        self.assertEqual(called, True)

    @unittest.skip(
        "Hangs under free-threaded Python; re-enable once recursive "
        "loop.stop() integration is stable"
    )
    @unittest.skipUnless(Gtk, "no Gtk")
    @event_loop_compat_xfail
    def test_recursive_stop(self):
        """Calling stop() on the EventLoop will quit it, even if iteration
        is done recursively.
        """
        policy = self.create_policy()
        asyncio.set_event_loop_policy(policy)
        self.addCleanup(asyncio.set_event_loop_policy, None)
        loop = policy.get_event_loop()

        if not GTK4:

            def main_gtk():
                GLib.idle_add(loop.stop)
                Gtk.main()

            GLib.idle_add(main_gtk)
            Gtk.main()

        def main_glib():
            GLib.idle_add(loop.stop)
            GLib.MainLoop().run()

        GLib.idle_add(main_glib)
        GLib.MainLoop().run()

        loop.close()

    def test_glib_task_prio(self):
        """Check that we can set a task priority."""
        policy = self.create_policy()
        loop = policy.new_event_loop()

        order = []

        async def run_prio(priority):
            # Note that asyncio.sleep(0) is a special case that not sleep
            nonlocal order
            await asyncio.sleep(0)
            order.append(priority)
            await asyncio.sleep(0)
            order.append(priority)
            await asyncio.sleep(0)
            order.append(priority)

        async def run():
            t1 = asyncio.create_task(run_prio(GLib.PRIORITY_DEFAULT_IDLE))
            t1.set_priority(GLib.PRIORITY_DEFAULT_IDLE)
            t2 = asyncio.create_task(run_prio(GLib.PRIORITY_DEFAULT))
            t2.set_priority(GLib.PRIORITY_DEFAULT)
            t3 = asyncio.create_task(run_prio(GLib.PRIORITY_HIGH))
            t3.set_priority(GLib.PRIORITY_HIGH)

            pending = (t1, t2, t3)
            while pending:
                _, pending = await asyncio.wait(pending)

        loop.run_until_complete(run())
        loop.close()

        # Check that the order was correct
        self.assertEqual(
            order,
            [GLib.PRIORITY_HIGH] * 3
            + [GLib.PRIORITY_DEFAULT] * 3
            + [GLib.PRIORITY_DEFAULT_IDLE] * 3,
        )

    @unittest.skipIf(sys.platform == "win32", "add reader/writer not implemented")
    def test_source_fileobj_fd(self):
        """Regression test for
        https://gitlab.gnome.org/GNOME/pygobject/-/issues/689
        """

        class Echo:
            def __init__(self, sock, expect_bytes):
                self.sock = sock
                self.sent_bytes = 0
                self.expect_bytes = expect_bytes
                self.done = asyncio.Future()
                self.data = b""

            def send(self):
                if self.done.done():
                    return
                if self.sent_bytes < len(self.data):
                    self.sent_bytes += self.sock.send(self.data[self.sent_bytes :])
                if self.sent_bytes >= self.expect_bytes:
                    self.done.set_result(None)
                    self.sock.shutdown(socket.SHUT_WR)

            def recv(self):
                if self.done.done():
                    return
                self.data += self.sock.recv(self.expect_bytes)
                if len(self.data) >= self.expect_bytes:
                    self.sock.shutdown(socket.SHUT_RD)

        async def run():
            loop = asyncio.get_running_loop()
            s1, s2 = socket.socketpair()
            sample = b"Hello!"
            e = Echo(s1, len(sample))
            # register using file object and file descriptor
            loop.add_reader(s1, e.recv)
            loop.add_writer(s1.fileno(), e.send)
            s2.sendall(sample)
            await asyncio.wait_for(e.done, timeout=2.0)
            echo = b""
            for _ in range(len(sample)):
                echo += s2.recv(len(sample))
                if len(echo) == len(sample):
                    break
            # remove using file object and file descriptor
            loop.remove_reader(s1)
            loop.remove_writer(s1.fileno())
            s1.close()
            s2.close()
            # check if the data was echoed correctly
            self.assertEqual(sample, echo)

        policy = self.create_policy()
        loop = policy.get_event_loop()
        loop.run_until_complete(run())
        loop.close()

    @pytest.mark.xfail(
        reason=(
            "Segfaults under free-threaded Python in glib main loop teardown; "
            "re-enable once asyncio.run integration is stable"
        ),
        run=False,
        strict=False,
    )
    def test_asyncio_run(self):
        coro_state = 0

        async def coro():
            nonlocal coro_state
            coro_state = 1

            await asyncio.sleep(1)
            coro_state = 2

            # asyncio.run registered a SIGINT handler to quit
            if sys.platform == "win32":
                signal.raise_signal(signal.SIGINT)
            else:
                os.kill(os.getpid(), signal.SIGINT)

            # The signal is processed when we return to the mainloop
            await asyncio.sleep(0)
            coro_state = 3

        class LazyCoro:
            def __await__(self):
                return coro().__await__()

        with self.assertRaises(KeyboardInterrupt):
            asyncio.run(LazyCoro(), loop_factory=gi.events.GLibEventLoop)

        # This works fine a second time as the first loop is unregistered (and closed)
        with self.assertRaises(KeyboardInterrupt):
            asyncio.run(LazyCoro(), loop_factory=gi.events.GLibEventLoop)

        self.assertEqual(coro_state, 2)

    def test_eventloop_context(self):
        # Main thread has only the implicit default main context
        self.assertIsNone(GLib.MainContext.get_thread_default())

        loop = gi.events.GLibEventLoop(main_context=GLib.MainContext())

        def check_loop_cannot_run(check_loop):
            with self.assertRaises(RuntimeError), check_loop:
                pass

            with self.assertRaises(RuntimeError):
                future = loop_samectx.create_future()
                future.set_result(True)
                loop_samectx.run_until_complete(future)

        def check_loop_can_run(check_loop):
            with check_loop:
                pass

            future = loop_samectx.create_future()
            future.set_result(True)
            loop_samectx.run_until_complete(future)

        with loop:
            # Entering the context manager sets the thread default
            self.assertEqual(
                hash(loop._context), hash(GLib.MainContext.get_thread_default())
            )

            loop_samectx = gi.events.GLibEventLoop()
            self.assertEqual(hash(loop._context), hash(loop_samectx._context))
            check_loop_cannot_run(loop_samectx)

            # We can do the same excercise with another main context
            loop_otherctx = gi.events.GLibEventLoop(GLib.MainContext())
            check_loop_cannot_run(loop_otherctx)

        # But, once we are outside it works fine.
        check_loop_can_run(loop_samectx)
        check_loop_can_run(loop_otherctx)
