#!/usr/bin/env python3
"""GNOME D-Bus Dashboard — a comprehensive D-Bus *client* showcase for ginext.

A single-window Adwaita app that talks to the well-known services a GNOME
desktop exposes and lays their state out across seven pages. The session-bus
pages (what GNOME *apps* actually speak) come first, then the system-bus
infrastructure pages:

    Media     org.mpris.MediaPlayer2.*   (session) — players + transport control
    Desktop   org.freedesktop.Notifications + portal.Settings + Mutter idle
    System    org.freedesktop.hostname1 + systemd identity
    Power     org.freedesktop.UPower (battery/line-power) + PowerProfiles
    Sessions  org.freedesktop.login1 (seats, sessions, users, inhibitors)
    systemd   org.freedesktop.systemd1 (unit inventory, failed units)
    Network   org.freedesktop.NetworkManager (state, devices, connections)

It is meant to demonstrate the D-Bus client surface ginext exposes through Gio:

    * bus_get_sync                          -> system and session DBusConnections
    * connection.call_sync(...)             -> method calls / property Get/GetAll
                                               (MPRIS PlayPause/Next, Notify, ...)
    * org.freedesktop.DBus.Properties.Set   -> writing a property (PowerProfiles)
    * connection.signal_subscribe(...)      -> live PropertiesChanged / MPRIS /
                                               NameOwnerChanged updates

Every service call is defensive: missing services, polkit refusals, and absent
hardware (e.g. a desktop with no battery, or no media player running) degrade to
a dimmed row rather than a crash, so the same binary is a useful demo on a
laptop, a server, or a full GNOME session.

Run via:
    PYTHONPATH=build/cpython-3.14t/src \\
      .venv-cpython-3.14t/bin/python3 src/playground/dbus_dashboard.py

Pass --self-test to build the window, run one refresh, and quit (used to verify
the app constructs without a human at the keyboard).
"""

from __future__ import annotations

import sys
from typing import Any, Callable, cast

from ginext import Adw, Gio, GLib, GObject, Gtk

TIMEOUT_MS = 5000
PROPS_IFACE = "org.freedesktop.DBus.Properties"


# --------------------------------------------------------------------------- #
# D-Bus client helper
# --------------------------------------------------------------------------- #
class Bus:
    """Thin convenience wrapper over a Gio.DBusConnection.

    This is the entire D-Bus client API the app relies on; the rest is GTK.
    The same surface serves both the system bus (hardware/init services) and
    the session bus (the per-user services GNOME apps talk to: MPRIS, portals,
    notifications, ...).
    """

    def __init__(self, bus_type: Gio.BusType) -> None:
        self.conn = Gio.bus_get_sync(bus_type)

    def list_names(self) -> list[str]:
        return cast(
            "list[str]",
            self.call(
                "org.freedesktop.DBus",
                "/org/freedesktop/DBus",
                "org.freedesktop.DBus",
                "ListNames",
            )[0],
        )

    def call(
        self,
        name: str,
        path: str,
        iface: str,
        method: str,
        params: GLib.Variant | None = None,
    ) -> tuple[Any, ...]:
        reply = self.conn.call_sync(
            name,
            path,
            iface,
            method,
            params,
            None,
            Gio.DBusCallFlags.NONE,
            TIMEOUT_MS,
            None,
        )
        return cast("tuple[Any, ...]", reply.unpack())

    def get(self, name: str, path: str, iface: str, prop: str) -> Any:
        return self.call(
            name,
            path,
            PROPS_IFACE,
            "Get",
            GLib.Variant("(ss)", (iface, prop)),
        )[0]

    def get_all(self, name: str, path: str, iface: str) -> dict[str, Any]:
        return cast(
            "dict[str, Any]",
            self.call(
                name,
                path,
                PROPS_IFACE,
                "GetAll",
                GLib.Variant("(s)", (iface,)),
            )[0],
        )

    def set(
        self, name: str, path: str, iface: str, prop: str, value: GLib.Variant
    ) -> None:
        self.call(
            name,
            path,
            PROPS_IFACE,
            "Set",
            GLib.Variant("(ssv)", (iface, prop, value)),
        )

    def subscribe(
        self,
        sender: str | None,
        iface: str | None,
        member: str | None,
        callback: Callable[..., None],
        path: str | None = None,
    ) -> Any:
        # callback receives (conn, sender, path, iface, signal, params)
        return self.conn.signal_subscribe(sender, iface, member, path, callback)


# --------------------------------------------------------------------------- #
# Enum / value formatting
# --------------------------------------------------------------------------- #
UPOWER_STATE: dict[Any, str] = {
    0: "Unknown",
    1: "Charging",
    2: "Discharging",
    3: "Empty",
    4: "Fully charged",
    5: "Pending charge",
    6: "Pending discharge",
}
UPOWER_TYPE: dict[Any, str] = {
    0: "Unknown",
    1: "Line power",
    2: "Battery",
    3: "UPS",
    4: "Monitor",
    5: "Mouse",
    6: "Keyboard",
    7: "PDA",
    8: "Phone",
}
UPOWER_WARNING: dict[Any, str] = {
    0: "Unknown",
    1: "None",
    2: "Discharging",
    3: "Low",
    4: "Critical",
    5: "Action",
}
UPOWER_TECH: dict[Any, str] = {
    0: "Unknown",
    1: "Lithium ion",
    2: "Lithium polymer",
    3: "Lithium iron phosphate",
    4: "Lead acid",
    5: "Nickel cadmium",
    6: "Nickel metal hydride",
}
NM_STATE: dict[Any, str] = {
    0: "Unknown",
    10: "Asleep",
    20: "Disconnected",
    30: "Disconnecting",
    40: "Connecting",
    50: "Connected (local)",
    60: "Connected (site)",
    70: "Connected (global)",
}
NM_CONNECTIVITY: dict[Any, str] = {
    0: "Unknown",
    1: "None",
    2: "Portal",
    3: "Limited",
    4: "Full",
}
NM_DEVICE_TYPE: dict[Any, str] = {
    1: "Ethernet",
    2: "Wi-Fi",
    5: "Bluetooth",
    6: "OLPC mesh",
    7: "WiMAX",
    8: "Modem",
    9: "InfiniBand",
    10: "Bond",
    11: "VLAN",
    12: "ADSL",
    13: "Bridge",
    14: "Generic",
    15: "Team",
    16: "TUN",
    17: "IP tunnel",
    29: "Wireguard",
}
NM_DEVICE_STATE: dict[Any, str] = {
    0: "Unknown",
    10: "Unmanaged",
    20: "Unavailable",
    30: "Disconnected",
    40: "Prepare",
    50: "Config",
    60: "Need auth",
    70: "IP config",
    80: "IP check",
    90: "Secondaries",
    100: "Activated",
    110: "Deactivating",
    120: "Failed",
}


def fmt_seconds(secs: Any) -> str:
    try:
        secs = int(secs)
    except (TypeError, ValueError):
        return "—"
    if secs <= 0:
        return "—"
    h, rem = divmod(secs, 3600)
    m, _ = divmod(rem, 60)
    if h:
        return f"{h} h {m} min"
    return f"{m} min"


def fmt_bool(value: Any) -> str:
    if value is None:
        return "—"
    return "Yes" if value else "No"


def join_list(value: Any) -> str:
    if not value:
        return "—"
    if isinstance(value, (list, tuple)):
        return ", ".join(str(v) for v in value if v) or "—"
    return str(value)


def fmt_us(micros: Any) -> str:
    """Format an MPRIS microsecond duration as m:ss (or h:mm:ss)."""
    try:
        total = int(micros) // 1_000_000
    except (TypeError, ValueError):
        return "0:00"
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


COLOR_SCHEME = {0: "No preference", 1: "Prefer dark", 2: "Prefer light"}


# --------------------------------------------------------------------------- #
# Small widget builders
# --------------------------------------------------------------------------- #
def action_row(title: str, subtitle: str = "—") -> Adw.ActionRow:
    row = Adw.ActionRow(title=title, subtitle=subtitle)
    row.add_css_class("property")
    return row


def set_subtitle(row: Adw.ActionRow, value: Any) -> None:
    text = "—" if value in (None, "") else str(value)
    row.set_subtitle(text)


# --------------------------------------------------------------------------- #
# Page base
# --------------------------------------------------------------------------- #
class Page:
    """A sidebar entry: an icon, a title, a built widget, and an updater."""

    icon = "applications-system-symbolic"
    title = "Page"
    name = "page"
    bus_kind = "system bus"

    def __init__(self, bus: Bus, toast: Callable[[str], None]) -> None:
        self.bus = bus
        self.toast = toast
        self._updaters: list[Callable[[], None]] = []
        self.widget = self.build()
        self.subscribe()

    def build(self) -> Gtk.Widget:  # pragma: no cover - overridden
        raise NotImplementedError

    def subscribe(self) -> None:
        """Optionally register signal subscriptions for live updates."""

    def add_updater(self, fn: Callable[[], None]) -> None:
        self._updaters.append(fn)

    def refresh(self) -> None:
        for fn in self._updaters:
            try:
                fn()
            except GLib.Error as exc:
                self.toast(f"{self.title}: {exc.message}")
            except Exception as exc:
                self.toast(f"{self.title}: {exc}")


# --------------------------------------------------------------------------- #
# System page
# --------------------------------------------------------------------------- #
class SystemPage(Page):
    icon = "computer-symbolic"
    title = "System"
    name = "system"

    HOST = "org.freedesktop.hostname1"
    HOST_PATH = "/org/freedesktop/hostname1"
    SD = "org.freedesktop.systemd1"
    SD_PATH = "/org/freedesktop/systemd1"
    SD_MGR = "org.freedesktop.systemd1.Manager"

    def build(self) -> Gtk.Widget:
        page = Adw.PreferencesPage()

        idg = Adw.PreferencesGroup(title="Identity", description=self.HOST)
        self.r_host = action_row("Hostname")
        self.r_pretty = action_row("Pretty hostname")
        self.r_icon = action_row("Icon name")
        self.r_chassis = action_row("Chassis")
        for r in (self.r_host, self.r_pretty, self.r_icon, self.r_chassis):
            idg.add(r)
        page.add(idg)

        osg = Adw.PreferencesGroup(title="Operating system")
        self.r_os = action_row("Distribution")
        self.r_kernel = action_row("Kernel")
        self.r_arch = action_row("Architecture")
        self.r_virt = action_row("Virtualization")
        for r in (self.r_os, self.r_kernel, self.r_arch, self.r_virt):
            osg.add(r)
        page.add(osg)

        hwg = Adw.PreferencesGroup(title="Hardware and firmware")
        self.r_vendor = action_row("Vendor")
        self.r_model = action_row("Model")
        self.r_fw = action_row("Firmware")
        self.r_fwdate = action_row("Firmware date")
        for r in (self.r_vendor, self.r_model, self.r_fw, self.r_fwdate):
            hwg.add(r)
        page.add(hwg)

        idsg = Adw.PreferencesGroup(title="Identifiers")
        self.r_machine = action_row("Machine ID")
        self.r_boot = action_row("Boot ID")
        self.r_sd = action_row("systemd version")
        for r in (self.r_machine, self.r_boot, self.r_sd):
            idsg.add(r)
        page.add(idsg)

        self.add_updater(self._update)
        return page

    def _update(self) -> None:
        h = self.bus.get_all(self.HOST, self.HOST_PATH, self.HOST)
        set_subtitle(self.r_host, h.get("Hostname"))
        set_subtitle(self.r_pretty, h.get("PrettyHostname") or h.get("DefaultHostname"))
        set_subtitle(self.r_icon, h.get("IconName"))
        set_subtitle(self.r_chassis, h.get("Chassis"))
        set_subtitle(self.r_os, h.get("OperatingSystemPrettyName"))
        kernel = " ".join(
            str(h.get(k, "")) for k in ("KernelName", "KernelRelease")
        ).strip()
        set_subtitle(self.r_kernel, f"{kernel}  ({h.get('KernelVersion', '')})".strip())
        set_subtitle(self.r_vendor, h.get("HardwareVendor"))
        set_subtitle(self.r_model, h.get("HardwareModel"))
        set_subtitle(
            self.r_fw,
            " ".join(
                str(h.get(k, "")) for k in ("FirmwareVendor", "FirmwareVersion")
            ).strip(),
        )
        set_subtitle(self.r_fwdate, h.get("FirmwareDate"))
        set_subtitle(self.r_machine, h.get("MachineID"))
        set_subtitle(self.r_boot, h.get("BootID"))

        try:
            sd = self.bus.get_all(self.SD, self.SD_PATH, self.SD_MGR)
        except Exception:
            sd = {}
        set_subtitle(self.r_arch, sd.get("Architecture"))
        set_subtitle(self.r_virt, sd.get("Virtualization") or "bare metal")
        set_subtitle(self.r_sd, sd.get("Version"))


# --------------------------------------------------------------------------- #
# Power page
# --------------------------------------------------------------------------- #
class PowerPage(Page):
    icon = "battery-symbolic"
    title = "Power"
    name = "power"

    UP = "org.freedesktop.UPower"
    UP_PATH = "/org/freedesktop/UPower"
    UP_DEV = "org.freedesktop.UPower.Device"
    DISPLAY = "/org/freedesktop/UPower/devices/DisplayDevice"
    PP = "org.freedesktop.UPower.PowerProfiles"
    PP_PATH = "/org/freedesktop/UPower/PowerProfiles"

    def build(self) -> Gtk.Widget:
        page = Adw.PreferencesPage()

        dg = Adw.PreferencesGroup(title="UPower daemon", description=self.UP)
        self.r_onbat = action_row("On battery")
        self.r_lid = action_row("Lid")
        self.r_ver = action_row("Daemon version")
        for r in (self.r_onbat, self.r_lid, self.r_ver):
            dg.add(r)
        page.add(dg)

        bg = Adw.PreferencesGroup(
            title="Battery (DisplayDevice)", description=self.DISPLAY
        )
        self.r_present = action_row("Present")
        self.r_state = action_row("State")
        self.r_pct = action_row("Charge")
        self.r_time = action_row("Time remaining")
        self.r_rate = action_row("Energy rate")
        self.r_energy = action_row("Energy")
        self.r_tech = action_row("Technology")
        self.r_warn = action_row("Warning level")
        self.r_temp = action_row("Temperature")
        self.r_battvendor = action_row("Vendor / model")
        for r in (
            self.r_present,
            self.r_state,
            self.r_pct,
            self.r_time,
            self.r_rate,
            self.r_energy,
            self.r_tech,
            self.r_warn,
            self.r_temp,
            self.r_battvendor,
        ):
            bg.add(r)
        page.add(bg)

        self.profile_group = Adw.PreferencesGroup(
            title="Power profiles", description=self.PP
        )
        self.profile_model = Gtk.StringList()
        self.profile_combo = Adw.ComboRow(
            title="Active profile",
            model=cast("Gio.ListModel[GObject.Object]", self.profile_model),
        )
        self._profiles: list[str] = []
        self._suppress_combo = False
        self.profile_combo.notify("selected").connect(self._on_profile_selected)
        self.profile_group.add(self.profile_combo)
        self.r_degraded = action_row("Performance degraded", "no")
        self.profile_group.add(self.r_degraded)
        page.add(self.profile_group)

        self.devices_group = Adw.PreferencesGroup(title="Power devices")
        self._device_rows: list[Gtk.Widget] = []
        page.add(self.devices_group)

        self.add_updater(self._update_daemon)
        self.add_updater(self._update_battery)
        self.add_updater(self._update_profiles)
        self.add_updater(self._update_devices)
        return page

    def subscribe(self) -> None:
        self.bus.subscribe(
            self.UP,
            PROPS_IFACE,
            "PropertiesChanged",
            lambda *_: GLib.idle_add(self._on_signal, "battery"),
            path=self.DISPLAY,
        )
        self.bus.subscribe(
            self.PP,
            PROPS_IFACE,
            "PropertiesChanged",
            lambda *_: GLib.idle_add(self._on_signal, "profiles"),
            path=self.PP_PATH,
        )

    def _on_signal(self, what: str) -> bool:
        if what == "battery":
            self._safe(self._update_battery)
        else:
            self._safe(self._update_profiles)
        return False

    def _safe(self, fn: Callable[[], None]) -> None:
        try:
            fn()
        except Exception as exc:
            self.toast(f"Power: {exc}")

    def _update_daemon(self) -> None:
        d = self.bus.get_all(self.UP, self.UP_PATH, self.UP)
        set_subtitle(self.r_onbat, fmt_bool(d.get("OnBattery")))
        if d.get("LidIsPresent"):
            lid = "closed" if d.get("LidIsClosed") else "open"
        else:
            lid = "not present"
        set_subtitle(self.r_lid, lid)
        set_subtitle(self.r_ver, d.get("DaemonVersion"))

    def _update_battery(self) -> None:
        b = self.bus.get_all(self.UP, self.DISPLAY, self.UP_DEV)
        present = bool(b.get("IsPresent"))
        set_subtitle(self.r_present, fmt_bool(present))
        if not present:
            for r in (
                self.r_state,
                self.r_pct,
                self.r_time,
                self.r_rate,
                self.r_energy,
                self.r_tech,
                self.r_warn,
                self.r_temp,
                self.r_battvendor,
            ):
                set_subtitle(r, "no battery on this machine")
            return
        set_subtitle(self.r_state, UPOWER_STATE.get(b.get("State"), b.get("State")))
        set_subtitle(self.r_pct, f"{b.get('Percentage', 0):.0f}%")
        state = b.get("State")
        if state == 1:
            set_subtitle(self.r_time, f"{fmt_seconds(b.get('TimeToFull'))} to full")
        else:
            set_subtitle(self.r_time, f"{fmt_seconds(b.get('TimeToEmpty'))} remaining")
        set_subtitle(self.r_rate, f"{b.get('EnergyRate', 0):.1f} W")
        set_subtitle(
            self.r_energy,
            f"{b.get('Energy', 0):.1f} / {b.get('EnergyFull', 0):.1f} Wh "
            f"(design {b.get('EnergyFullDesign', 0):.1f})",
        )
        set_subtitle(self.r_tech, UPOWER_TECH.get(b.get("Technology"), "—"))
        set_subtitle(self.r_warn, UPOWER_WARNING.get(b.get("WarningLevel"), "—"))
        temp = b.get("Temperature") or 0
        set_subtitle(self.r_temp, f"{temp:.1f} °C" if temp else "—")
        set_subtitle(
            self.r_battvendor,
            " ".join(str(b.get(k, "")) for k in ("Vendor", "Model")).strip(),
        )

    def _update_profiles(self) -> None:
        try:
            profiles = self.bus.get(self.PP, self.PP_PATH, self.PP, "Profiles")
            active = self.bus.get(self.PP, self.PP_PATH, self.PP, "ActiveProfile")
            degraded = self.bus.get(
                self.PP, self.PP_PATH, self.PP, "PerformanceDegraded"
            )
        except Exception:
            self.profile_group.set_description("power-profiles-daemon unavailable")
            self.profile_combo.set_sensitive(False)
            return
        names = [str(p.get("Profile")) for p in profiles]
        if names != self._profiles:
            self._suppress_combo = True
            while self.profile_model.get_n_items():
                self.profile_model.remove(0)
            for n in names:
                self.profile_model.append(n)
            self._profiles = names
            self._suppress_combo = False
        if active in names:
            self._suppress_combo = True
            self.profile_combo.set_selected(names.index(active))
            self._suppress_combo = False
        set_subtitle(self.r_degraded, degraded or "no")

    def _on_profile_selected(self, combo: Adw.ComboRow, _pspec: Any) -> None:
        if self._suppress_combo:
            return
        idx = combo.get_selected()
        if idx < 0 or idx >= len(self._profiles):
            return
        target = self._profiles[idx]
        try:
            self.bus.set(
                self.PP,
                self.PP_PATH,
                self.PP,
                "ActiveProfile",
                GLib.Variant("s", target),
            )
            self.toast(f"Active power profile → {target}")
        except Exception as exc:
            self.toast(f"Could not set profile: {exc}")

    def _update_devices(self) -> None:
        for row in self._device_rows:
            self.devices_group.remove(row)
        self._device_rows.clear()
        try:
            paths = self.bus.call(self.UP, self.UP_PATH, self.UP, "EnumerateDevices")[0]
        except Exception:
            paths = []
        if not paths:
            row = action_row("Devices", "no line-power or battery devices enumerated")
            self.devices_group.add(row)
            self._device_rows.append(row)
            return
        for path in paths:
            try:
                d = self.bus.get_all(self.UP, path, self.UP_DEV)
            except Exception:
                continue
            kind = UPOWER_TYPE.get(d.get("Type"), "Device")
            exp = Adw.ExpanderRow(
                title=kind,
                subtitle=str(path).split("/")[-1],
            )
            detail = {
                "Native path": d.get("NativePath"),
                "Online": fmt_bool(d.get("Online")) if d.get("Type") == 1 else None,
                "State": UPOWER_STATE.get(d.get("State"))
                if d.get("Type") == 2
                else None,
                "Charge": f"{d.get('Percentage', 0):.0f}%"
                if d.get("Type") == 2
                else None,
                "Power supply": fmt_bool(d.get("PowerSupply")),
            }
            for k, v in detail.items():
                if v is None:
                    continue
                exp.add_row(action_row(k, str(v)))
            self.devices_group.add(exp)
            self._device_rows.append(exp)


# --------------------------------------------------------------------------- #
# Sessions page
# --------------------------------------------------------------------------- #
class SessionsPage(Page):
    icon = "system-users-symbolic"
    title = "Sessions"
    name = "sessions"

    L1 = "org.freedesktop.login1"
    L1_PATH = "/org/freedesktop/login1"
    L1_MGR = "org.freedesktop.login1.Manager"
    L1_SESSION = "org.freedesktop.login1.Session"

    def build(self) -> Gtk.Widget:
        page = Adw.PreferencesPage()

        mg = Adw.PreferencesGroup(title="Login manager", description=self.L1)
        self.r_idle = action_row("Idle hint")
        self.r_docked = action_row("Docked")
        self.r_block = action_row("Blocked inhibitors")
        self.r_delay = action_row("Delayed inhibitors")
        for r in (self.r_idle, self.r_docked, self.r_block, self.r_delay):
            mg.add(r)
        page.add(mg)

        cg = Adw.PreferencesGroup(
            title="Capabilities",
            description="login1 Can* method calls (polkit-gated)",
        )
        self.r_suspend = action_row("Can suspend")
        self.r_reboot = action_row("Can reboot")
        self.r_poweroff = action_row("Can power off")
        self.r_hibernate = action_row("Can hibernate")
        for r in (self.r_suspend, self.r_reboot, self.r_poweroff, self.r_hibernate):
            cg.add(r)
        page.add(cg)

        self.sessions_group = Adw.PreferencesGroup(title="Active sessions")
        self._session_rows: list[Gtk.Widget] = []
        page.add(self.sessions_group)

        self.users_group = Adw.PreferencesGroup(title="Logged-in users")
        self._user_rows: list[Gtk.Widget] = []
        page.add(self.users_group)

        self.add_updater(self._update_manager)
        self.add_updater(self._update_sessions)
        self.add_updater(self._update_users)
        return page

    def _can(self, method: str) -> str:
        try:
            return str(self.bus.call(self.L1, self.L1_PATH, self.L1_MGR, method)[0])
        except Exception:
            return "—"

    def _update_manager(self) -> None:
        try:
            m = self.bus.get_all(self.L1, self.L1_PATH, self.L1_MGR)
        except Exception:
            m = {}
        set_subtitle(self.r_idle, fmt_bool(m.get("IdleHint")))
        set_subtitle(self.r_docked, fmt_bool(m.get("Docked")))
        set_subtitle(self.r_block, m.get("BlockInhibited") or "none")
        set_subtitle(self.r_delay, m.get("DelayInhibited") or "none")
        set_subtitle(self.r_suspend, self._can("CanSuspend"))
        set_subtitle(self.r_reboot, self._can("CanReboot"))
        set_subtitle(self.r_poweroff, self._can("CanPowerOff"))
        set_subtitle(self.r_hibernate, self._can("CanHibernate"))

    def _update_sessions(self) -> None:
        for row in self._session_rows:
            self.sessions_group.remove(row)
        self._session_rows.clear()
        try:
            sessions = self.bus.call(
                self.L1, self.L1_PATH, self.L1_MGR, "ListSessions"
            )[0]
        except Exception as exc:
            self.sessions_group.set_description(str(exc))
            return
        self.sessions_group.set_description(f"{len(sessions)} session(s)")
        for sid, uid, user, seat, path in sessions:
            try:
                s = self.bus.get_all(self.L1, path, self.L1_SESSION)
            except Exception:
                s = {}
            exp = Adw.ExpanderRow(
                title=f"Session {sid} — {user}",
                subtitle=f"{s.get('Type', '?')} · {s.get('State', '?')}",
            )
            seat_name = s.get("Seat")
            if isinstance(seat_name, (list, tuple)):
                seat_name = seat_name[0]
            detail = {
                "User": f"{user} ({uid})",
                "Seat": seat_name or seat or "—",
                "Type": s.get("Type"),
                "State": s.get("State"),
                "Active": fmt_bool(s.get("Active")),
                "Remote": fmt_bool(s.get("Remote")),
                "Service": s.get("Service"),
                "TTY / display": s.get("TTY") or s.get("Display") or "—",
            }
            for k, v in detail.items():
                exp.add_row(action_row(k, str(v) if v not in (None, "") else "—"))
            self.sessions_group.add(exp)
            self._session_rows.append(exp)

    def _update_users(self) -> None:
        for row in self._user_rows:
            self.users_group.remove(row)
        self._user_rows.clear()
        try:
            users = self.bus.call(self.L1, self.L1_PATH, self.L1_MGR, "ListUsers")[0]
        except Exception:
            users = []
        self.users_group.set_description(f"{len(users)} user(s)")
        for uid, name, _path in users:
            self._user_rows.append(action_row(name, f"uid {uid}"))
        if not self._user_rows:
            self._user_rows.append(action_row("Users", "—"))
        for row in self._user_rows:
            self.users_group.add(row)


# --------------------------------------------------------------------------- #
# systemd page
# --------------------------------------------------------------------------- #
class SystemdPage(Page):
    icon = "emblem-system-symbolic"
    title = "systemd"
    name = "systemd"

    SD = "org.freedesktop.systemd1"
    SD_PATH = "/org/freedesktop/systemd1"
    SD_MGR = "org.freedesktop.systemd1.Manager"

    def build(self) -> Gtk.Widget:
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        root.set_margin_top(12)
        root.set_margin_bottom(12)
        root.set_margin_start(12)
        root.set_margin_end(12)

        # Stat tiles
        stat_clamp = Adw.Clamp(maximum_size=900)
        self.stats_flow = Gtk.FlowBox(
            selection_mode=Gtk.SelectionMode.NONE,
            max_children_per_line=6,
            min_children_per_line=2,
            row_spacing=8,
            column_spacing=8,
            homogeneous=True,
        )
        self._stat_labels: dict[str, Gtk.Label] = {}
        for key, caption in (
            ("units", "Loaded units"),
            ("running", "Running"),
            ("failed", "Failed"),
            ("jobs", "Queued jobs"),
            ("state", "System state"),
            ("names", "Bus names"),
        ):
            self.stats_flow.append(self._make_tile(key, caption))
        stat_clamp.set_child(self.stats_flow)
        root.append(stat_clamp)

        # Search + unit list
        self.search = Gtk.SearchEntry(placeholder_text="Filter units by name…")
        self.search.search_changed.connect(lambda *_: self._refilter())
        search_clamp = Adw.Clamp(maximum_size=900, child=self.search)
        root.append(search_clamp)

        self.unit_store = Gio.ListStore.new(_UnitObject)
        self.filter = Gtk.CustomFilter.new(self._filter_func)
        self.filter_model = Gtk.FilterListModel(
            model=self.unit_store, filter=self.filter
        )
        factory = Gtk.SignalListItemFactory.new()
        factory.setup.connect(self._row_setup)
        factory.bind.connect(self._row_bind)
        selection_model = cast(
            "Gtk.SelectionModel[GObject.Object]",
            Gtk.NoSelection.new(self.filter_model),
        )
        self.list_view = Gtk.ListView(
            model=selection_model, factory=factory
        )
        self.list_view.add_css_class("boxed-list")
        scroller = Gtk.ScrolledWindow(vexpand=True)
        scroller.set_child(self.list_view)
        list_clamp = Adw.Clamp(maximum_size=900, child=scroller, vexpand=True)
        root.append(list_clamp)

        self._units: list[tuple[str, str, str, str]] = []
        self.add_updater(self._update)
        return root

    def _make_tile(self, key: str, caption: str) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        box.add_css_class("card")
        box.set_margin_top(6)
        box.set_margin_bottom(6)
        value = Gtk.Label(label="—")
        value.add_css_class("title-1")
        value.set_margin_top(10)
        cap = Gtk.Label(label=caption)
        cap.add_css_class("dim-label")
        cap.set_margin_bottom(10)
        box.append(value)
        box.append(cap)
        self._stat_labels[key] = value
        return box

    # -- unit row factory --
    def _row_setup(self, _factory: Any, item: Gtk.ListItem) -> None:
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        row.set_margin_top(6)
        row.set_margin_bottom(6)
        row.set_margin_start(10)
        row.set_margin_end(10)
        dot = Gtk.Image(icon_name="media-record-symbolic")
        name = Gtk.Label(xalign=0, hexpand=True, ellipsize=3)
        state = Gtk.Label(xalign=1)
        state.add_css_class("dim-label")
        row.append(dot)
        row.append(name)
        row.append(state)
        item.set_child(row)

    def _row_bind(self, _factory: Any, item: Gtk.ListItem) -> None:
        obj = item.get_item()
        assert isinstance(obj, _UnitObject)
        name, active, sub = obj.uname, obj.active, obj.sub
        row = item.get_child()
        assert row is not None
        dot = row.get_first_child()
        assert isinstance(dot, Gtk.Image)
        label = dot.get_next_sibling()
        assert isinstance(label, Gtk.Label)
        state = label.get_next_sibling()
        assert isinstance(state, Gtk.Label)
        label.set_text(name)
        state.set_text(f"{active} · {sub}")
        for cls in ("success", "warning", "error", "dim-label"):
            dot.remove_css_class(cls)
        if active == "failed":
            dot.add_css_class("error")
        elif active == "active":
            dot.add_css_class("success")
        elif active == "activating":
            dot.add_css_class("warning")
        else:
            dot.add_css_class("dim-label")

    def _filter_func(self, obj: GObject.Object) -> bool:
        text = self.search.get_text().strip().lower()
        if not text:
            return True
        if not isinstance(obj, _UnitObject):
            return True
        return text in obj.uname.lower()

    def _refilter(self) -> None:
        self.filter.changed(Gtk.FilterChange.DIFFERENT)

    def _update(self) -> None:
        m = self.bus.get_all(self.SD, self.SD_PATH, self.SD_MGR)
        units = self.bus.call(self.SD, self.SD_PATH, self.SD_MGR, "ListUnits")[0]
        running = sum(1 for u in units if u[4] == "running")
        failed = sum(1 for u in units if u[3] == "failed")
        self._stat_labels["units"].set_text(str(len(units)))
        self._stat_labels["running"].set_text(str(running))
        self._stat_labels["failed"].set_text(str(failed))
        self._stat_labels["jobs"].set_text(str(m.get("NJobs", "—")))
        self._stat_labels["state"].set_text(str(m.get("SystemState", "—")))
        self._stat_labels["names"].set_text(str(m.get("NNames", "—")))
        if failed:
            self._stat_labels["failed"].add_css_class("error")
        else:
            self._stat_labels["failed"].remove_css_class("error")

        # rebuild the store, failed first then alphabetical
        rows = sorted(
            ((str(u[0]), str(u[3]), str(u[4])) for u in units),
            key=lambda r: (r[1] != "failed", r[0]),
        )
        self.unit_store.remove_all()
        for name, active, sub in rows:
            self.unit_store.append(_UnitObject(name, active, sub))


class _UnitObject(GObject.Object, type_name="DBusDashboardUnit"):
    # Stored as GObject properties (not plain attributes) so the values live on
    # the underlying GObject and survive the Python wrapper being recreated when
    # the ListStore hands an item back during list-view binding.
    uname = GObject.Property(type=str, default="")
    active = GObject.Property(type=str, default="")
    sub = GObject.Property(type=str, default="")

    def __init__(self, name: str, active: str, sub: str) -> None:
        super().__init__()
        self.uname = name
        self.active = active
        self.sub = sub


# --------------------------------------------------------------------------- #
# Network page
# --------------------------------------------------------------------------- #
class NetworkPage(Page):
    icon = "network-wired-symbolic"
    title = "Network"
    name = "network"

    NM = "org.freedesktop.NetworkManager"
    NM_PATH = "/org/freedesktop/NetworkManager"
    NM_DEV = "org.freedesktop.NetworkManager.Device"
    NM_AC = "org.freedesktop.NetworkManager.Connection.Active"

    def build(self) -> Gtk.Widget:
        page = Adw.PreferencesPage()

        sg = Adw.PreferencesGroup(title="NetworkManager", description=self.NM)
        self.r_state = action_row("State")
        self.r_conn = action_row("Connectivity")
        self.r_net = action_row("Networking enabled")
        self.r_wifi = action_row("Wi-Fi enabled")
        self.r_primary = action_row("Primary connection type")
        self.r_metered = action_row("Metered")
        self.r_ver = action_row("Version")
        for r in (
            self.r_state,
            self.r_conn,
            self.r_net,
            self.r_wifi,
            self.r_primary,
            self.r_metered,
            self.r_ver,
        ):
            sg.add(r)
        page.add(sg)

        self.dev_group = Adw.PreferencesGroup(title="Devices")
        self._dev_rows: list[Gtk.Widget] = []
        page.add(self.dev_group)

        self.ac_group = Adw.PreferencesGroup(title="Active connections")
        self._ac_rows: list[Gtk.Widget] = []
        page.add(self.ac_group)

        self.add_updater(self._update_manager)
        self.add_updater(self._update_devices)
        self.add_updater(self._update_connections)
        return page

    def subscribe(self) -> None:
        self.bus.subscribe(
            self.NM,
            PROPS_IFACE,
            "PropertiesChanged",
            lambda *_: GLib.idle_add(self._on_signal),
            path=self.NM_PATH,
        )

    def _on_signal(self) -> bool:
        try:
            self._update_manager()
        except Exception as exc:
            self.toast(f"Network: {exc}")
        return False

    def _update_manager(self) -> None:
        try:
            n = self.bus.get_all(self.NM, self.NM_PATH, self.NM)
        except Exception:
            for r in (
                self.r_state,
                self.r_conn,
                self.r_net,
                self.r_wifi,
                self.r_primary,
                self.r_metered,
                self.r_ver,
            ):
                set_subtitle(r, "NetworkManager unavailable")
            return
        set_subtitle(self.r_state, NM_STATE.get(n.get("State"), n.get("State")))
        set_subtitle(self.r_conn, NM_CONNECTIVITY.get(n.get("Connectivity"), "—"))
        set_subtitle(self.r_net, fmt_bool(n.get("NetworkingEnabled")))
        set_subtitle(self.r_wifi, fmt_bool(n.get("WirelessEnabled")))
        set_subtitle(self.r_primary, n.get("PrimaryConnectionType") or "—")
        set_subtitle(self.r_metered, str(n.get("Metered", "—")))
        set_subtitle(self.r_ver, n.get("Version"))

    def _update_devices(self) -> None:
        for row in self._dev_rows:
            self.dev_group.remove(row)
        self._dev_rows.clear()
        try:
            paths = self.bus.call(self.NM, self.NM_PATH, self.NM, "GetDevices")[0]
        except Exception:
            paths = []
        self.dev_group.set_description(f"{len(paths)} device(s)")
        for path in paths:
            try:
                d = self.bus.get_all(self.NM, path, self.NM_DEV)
            except Exception:
                continue
            exp = Adw.ExpanderRow(
                title=d.get("Interface", "device"),
                subtitle=NM_DEVICE_TYPE.get(d.get("DeviceType"), "—"),
            )
            detail = {
                "Type": NM_DEVICE_TYPE.get(d.get("DeviceType"), d.get("DeviceType")),
                "State": NM_DEVICE_STATE.get(d.get("State"), d.get("State")),
                "Driver": d.get("Driver"),
                "Managed": fmt_bool(d.get("Managed")),
                "MTU": d.get("Mtu"),
                "MAC": d.get("HwAddress"),
            }
            for k, v in detail.items():
                exp.add_row(action_row(k, str(v) if v not in (None, "") else "—"))
            self.dev_group.add(exp)
            self._dev_rows.append(exp)
        if not self._dev_rows:
            row = action_row("Devices", "none / unavailable")
            self.dev_group.add(row)
            self._dev_rows.append(row)

    def _update_connections(self) -> None:
        for row in self._ac_rows:
            self.ac_group.remove(row)
        self._ac_rows.clear()
        try:
            paths = self.bus.get(self.NM, self.NM_PATH, self.NM, "ActiveConnections")
        except Exception:
            paths = []
        self.ac_group.set_description(f"{len(paths)} active")
        for path in paths:
            try:
                a = self.bus.get_all(self.NM, path, self.NM_AC)
            except Exception:
                continue
            row = action_row(
                a.get("Id", "connection"),
                f"{a.get('Type', '?')}"
                + ("  ·  default route" if a.get("Default") else ""),
            )
            self.ac_group.add(row)
            self._ac_rows.append(row)
        if not self._ac_rows:
            row = action_row("Connections", "none / unavailable")
            self.ac_group.add(row)
            self._ac_rows.append(row)


# --------------------------------------------------------------------------- #
# Media page (MPRIS) — session bus
# --------------------------------------------------------------------------- #
class MediaPage(Page):
    icon = "multimedia-player-symbolic"
    title = "Media"
    name = "media"
    bus_kind = "session bus"

    PREFIX = "org.mpris.MediaPlayer2."
    PATH = "/org/mpris/MediaPlayer2"
    ROOT = "org.mpris.MediaPlayer2"
    PLAYER = "org.mpris.MediaPlayer2.Player"

    def build(self) -> Gtk.Widget:
        self.page = Adw.PreferencesPage()
        self._groups: list[Adw.PreferencesGroup] = []
        # player bus name -> (position row, track length in microseconds)
        self._pos_rows: dict[str, tuple[Adw.ActionRow, int]] = {}
        self.add_updater(self._rebuild)
        GLib.timeout_add(1000, self._tick)  # poll Position (MPRIS has no signal)
        return self.page

    def subscribe(self) -> None:
        # One subscription covers every player: same object path, no sender.
        self.bus.subscribe(
            None,
            PROPS_IFACE,
            "PropertiesChanged",
            self._on_props_changed,
            path=self.PATH,
        )
        self.bus.subscribe(
            "org.freedesktop.DBus",
            "org.freedesktop.DBus",
            "NameOwnerChanged",
            self._on_name_owner,
        )

    def _on_props_changed(self, *_a: Any) -> None:
        GLib.idle_add(self._delayed_rebuild)

    def _on_name_owner(self, *args: Any) -> None:
        params = args[-1]
        try:
            name = params.unpack()[0]
        except Exception:
            return
        if isinstance(name, str) and name.startswith(self.PREFIX):
            GLib.idle_add(self._delayed_rebuild)

    def _delayed_rebuild(self) -> bool:
        try:
            self._rebuild()
        except Exception as exc:
            self.toast(f"Media: {exc}")
        return False

    def _players(self) -> list[str]:
        try:
            return sorted(n for n in self.bus.list_names() if n.startswith(self.PREFIX))
        except Exception:
            return []

    def _rebuild(self) -> None:
        for g in self._groups:
            self.page.remove(g)
        self._groups.clear()
        self._pos_rows.clear()
        players = self._players()
        if not players:
            group = Adw.PreferencesGroup(
                title="No media players",
                description="org.mpris.MediaPlayer2.*",
            )
            group.add(
                action_row(
                    "MPRIS",
                    "Start a music app, video, or browser tab to control it here.",
                )
            )
            self.page.add(group)
            self._groups.append(group)
            return
        for name in players:
            self._add_player(name)

    def _add_player(self, name: str) -> None:
        try:
            root = self.bus.get_all(name, self.PATH, self.ROOT)
            player = self.bus.get_all(name, self.PATH, self.PLAYER)
        except Exception:
            return
        identity = root.get("Identity") or name[len(self.PREFIX) :]
        group = Adw.PreferencesGroup(title=str(identity), description=name)

        meta = player.get("Metadata") or {}
        title = meta.get("xesam:title")
        artist = join_list(meta.get("xesam:artist"))
        status = player.get("PlaybackStatus") or "Unknown"

        now = f"{title} — {artist}" if title else "Nothing playing"
        now_row = action_row("Now playing", now)
        album_row = action_row("Album", str(meta.get("xesam:album") or "—"))

        status_row = action_row("Status", str(status))
        status_row.add_suffix(self._controls(name, str(status), player))

        length = int(meta.get("mpris:length") or 0)
        pos = int(player.get("Position") or 0)
        pos_row = action_row("Position", f"{fmt_us(pos)} / {fmt_us(length)}")

        vol = player.get("Volume")
        vol_row = action_row(
            "Volume", f"{vol * 100:.0f}%" if isinstance(vol, (int, float)) else "—"
        )

        for r in (now_row, album_row, status_row, pos_row, vol_row):
            group.add(r)
        self.page.add(group)
        self._groups.append(group)
        self._pos_rows[name] = (pos_row, length)

    def _controls(self, name: str, status: str, player: dict[str, Any]) -> Gtk.Widget:
        box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=6,
            valign=Gtk.Align.CENTER,
        )
        playing = status == "Playing"
        specs = (
            (
                "media-skip-backward-symbolic",
                "Previous",
                bool(player.get("CanGoPrevious")),
            ),
            (
                "media-playback-pause-symbolic"
                if playing
                else "media-playback-start-symbolic",
                "PlayPause",
                bool(player.get("CanPlay") or player.get("CanPause")),
            ),
            ("media-skip-forward-symbolic", "Next", bool(player.get("CanGoNext"))),
        )
        for icon, method, sensitive in specs:
            btn = Gtk.Button(icon_name=icon)
            btn.add_css_class("flat")
            btn.set_sensitive(sensitive)
            btn.clicked.connect(self._make_control(name, method))
            box.append(btn)
        return box

    def _make_control(self, name: str, method: str) -> Callable[..., None]:
        def handler(*_a: Any) -> None:
            try:
                self.bus.call(name, self.PATH, self.PLAYER, method)
            except Exception as exc:
                self.toast(f"{method} failed: {exc}")
                return
            GLib.timeout_add(200, self._delayed_rebuild)

        return handler

    def _tick(self) -> bool:
        for name, (row, length) in list(self._pos_rows.items()):
            try:
                pos = self.bus.get(name, self.PATH, self.PLAYER, "Position")
            except Exception:
                continue
            row.set_subtitle(f"{fmt_us(pos)} / {fmt_us(length)}")
        return True


# --------------------------------------------------------------------------- #
# Desktop page (notifications, portals, idle) — session bus
# --------------------------------------------------------------------------- #
class DesktopPage(Page):
    icon = "preferences-desktop-symbolic"
    title = "Desktop"
    name = "desktop"
    bus_kind = "session bus"

    NOTIFY = "org.freedesktop.Notifications"
    NOTIFY_PATH = "/org/freedesktop/Notifications"
    PORTAL = "org.freedesktop.portal.Desktop"
    PORTAL_PATH = "/org/freedesktop/portal/desktop"
    SETTINGS = "org.freedesktop.portal.Settings"
    IDLE = "org.gnome.Mutter.IdleMonitor"
    IDLE_PATH = "/org/gnome/Mutter/IdleMonitor/Core"

    WATCH = [
        ("org.freedesktop.Notifications", "Notifications"),
        ("org.freedesktop.portal.Desktop", "XDG desktop portal"),
        ("org.freedesktop.secrets", "Secret Service (keyring)"),
        ("org.freedesktop.ScreenSaver", "Screen saver / inhibit"),
        ("org.gnome.Mutter.IdleMonitor", "Mutter idle monitor"),
        ("org.gnome.Shell", "GNOME Shell"),
        ("org.gtk.vfs.Daemon", "GVfs"),
    ]

    def build(self) -> Gtk.Widget:
        page = Adw.PreferencesPage()

        ng = Adw.PreferencesGroup(title="Notifications", description=self.NOTIFY)
        self.r_server = action_row("Server")
        self.r_vendor = action_row("Vendor")
        self.r_spec = action_row("Spec version")
        self.r_caps = action_row("Capabilities")
        send_row = Adw.ActionRow(
            title="Send a test notification",
            subtitle="org.freedesktop.Notifications.Notify",
        )
        send_btn = Gtk.Button(label="Send", valign=Gtk.Align.CENTER)
        send_btn.add_css_class("suggested-action")
        send_btn.clicked.connect(self._send_test)
        send_row.add_suffix(send_btn)
        for r in (self.r_server, self.r_vendor, self.r_spec, self.r_caps, send_row):
            ng.add(r)
        page.add(ng)

        ag = Adw.PreferencesGroup(
            title="Appearance", description="org.freedesktop.portal.Settings"
        )
        self.r_scheme = action_row("Color scheme")
        self.r_accent = action_row("Accent color")
        self.r_idle = action_row("Idle time")
        for r in (self.r_scheme, self.r_accent, self.r_idle):
            ag.add(r)
        page.add(ag)

        self.services_group = Adw.PreferencesGroup(
            title="Session services",
            description="well-known names GNOME apps rely on",
        )
        self._service_rows: list[Gtk.Widget] = []
        page.add(self.services_group)

        self.add_updater(self._update_notifications)
        self.add_updater(self._update_appearance)
        self.add_updater(self._update_services)
        return page

    def _update_notifications(self) -> None:
        try:
            info = self.bus.call(
                self.NOTIFY, self.NOTIFY_PATH, self.NOTIFY, "GetServerInformation"
            )
            caps = self.bus.call(
                self.NOTIFY, self.NOTIFY_PATH, self.NOTIFY, "GetCapabilities"
            )[0]
        except Exception as exc:
            set_subtitle(self.r_server, f"unavailable ({exc})")
            return
        set_subtitle(self.r_server, info[0])
        set_subtitle(self.r_vendor, info[1])
        set_subtitle(self.r_spec, f"{info[2]} (spec {info[3]})")
        set_subtitle(self.r_caps, join_list(caps))

    def _read_setting(self, namespace: str, key: str) -> Any:
        value = self.bus.call(
            self.PORTAL,
            self.PORTAL_PATH,
            self.SETTINGS,
            "Read",
            GLib.Variant("(ss)", (namespace, key)),
        )[0]
        # Read returns a 'v'; unpacking may leave one nesting level.
        while isinstance(value, GLib.Variant):
            value = value.unpack()
        return value

    def _update_appearance(self) -> None:
        try:
            scheme = self._read_setting("org.freedesktop.appearance", "color-scheme")
            set_subtitle(self.r_scheme, COLOR_SCHEME.get(scheme, scheme))
        except Exception as exc:
            set_subtitle(self.r_scheme, f"unavailable ({exc})")
        try:
            accent = self._read_setting("org.freedesktop.appearance", "accent-color")
            if isinstance(accent, (list, tuple)) and len(accent) == 3:
                r, g, b = (int(round(c * 255)) for c in accent)
                set_subtitle(self.r_accent, f"#{r:02x}{g:02x}{b:02x}")
            else:
                set_subtitle(self.r_accent, str(accent))
        except Exception as exc:
            set_subtitle(self.r_accent, f"unavailable ({exc})")
        try:
            idle_ms = self.bus.call(
                self.IDLE, self.IDLE_PATH, self.IDLE, "GetIdletime"
            )[0]
            set_subtitle(self.r_idle, f"{int(idle_ms) / 1000:.1f} s")
        except Exception:
            set_subtitle(self.r_idle, "—")

    def _update_services(self) -> None:
        for row in self._service_rows:
            self.services_group.remove(row)
        self._service_rows.clear()
        try:
            present = set(self.bus.list_names())
        except Exception:
            present = set()
        for bus_name, label in self.WATCH:
            row = action_row(label, bus_name)
            ok = bus_name in present
            row.add_suffix(
                Gtk.Image(
                    icon_name="emblem-ok-symbolic" if ok else "window-close-symbolic"
                )
            )
            self.services_group.add(row)
            self._service_rows.append(row)

    def _send_test(self, *_a: Any) -> None:
        try:
            self.bus.call(
                self.NOTIFY,
                self.NOTIFY_PATH,
                self.NOTIFY,
                "Notify",
                GLib.Variant(
                    "(susssasa{sv}i)",
                    (
                        "D-Bus Dashboard",
                        0,
                        "dialog-information-symbolic",
                        "ginext D-Bus Dashboard",
                        "This notification was sent over "
                        "org.freedesktop.Notifications.",
                        [],
                        {},
                        5000,
                    ),
                ),
            )
            self.toast("Notification sent")
        except Exception as exc:
            self.toast(f"Notify failed: {exc}")


# --------------------------------------------------------------------------- #
# Window
# --------------------------------------------------------------------------- #
class DashboardWindow(Adw.ApplicationWindow, type_name="DBusDashboardWindow"):
    def __init__(self, app: Adw.Application, system: Bus, session: Bus) -> None:
        super().__init__(application=app, title="GNOME D-Bus Dashboard")
        self.set_default_size(940, 760)

        self.toaster = Adw.ToastOverlay()
        self.set_content(self.toaster)
        self._row_pages: dict[Gtk.ListBoxRow, str] = {}

        # Session-bus pages (what GNOME apps actually speak) come first, then
        # the system-bus infrastructure pages.
        self.pages: list[Page] = [
            MediaPage(session, self.toast),
            DesktopPage(session, self.toast),
            SystemPage(system, self.toast),
            PowerPage(system, self.toast),
            SessionsPage(system, self.toast),
            SystemdPage(system, self.toast),
            NetworkPage(system, self.toast),
        ]

        self.stack = Adw.ViewStack()
        for page in self.pages:
            self.stack.add_titled(page.widget, page.name, page.title)

        split = Adw.NavigationSplitView()
        # Build content first: _build_sidebar() selects the first row, which
        # fires row-selected -> _on_sidebar_row, which needs content_page.
        content = self._build_content()
        split.set_sidebar(self._build_sidebar())
        split.set_content(content)
        self.split = split
        self.toaster.set_child(split)

        self.refresh_all()

    # -- sidebar --
    def _build_sidebar(self) -> Adw.NavigationPage:
        toolbar = Adw.ToolbarView()
        toolbar.add_top_bar(Adw.HeaderBar())

        self.sidebar_list = Gtk.ListBox()
        self.sidebar_list.add_css_class("navigation-sidebar")
        self.sidebar_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        for page in self.pages:
            row = Adw.ActionRow(title=page.title)
            row.add_prefix(Gtk.Image(icon_name=page.icon))
            row.set_activatable(True)
            self._row_pages[row] = page.name
            self.sidebar_list.append(row)
        self.sidebar_list.row_selected.connect(self._on_sidebar_row)
        self.sidebar_list.select_row(self.sidebar_list.get_row_at_index(0))

        scroller = Gtk.ScrolledWindow(vexpand=True, child=self.sidebar_list)
        toolbar.set_content(scroller)
        return Adw.NavigationPage(title="Services", child=toolbar, tag="sidebar")

    def _on_sidebar_row(
        self, _listbox: Gtk.ListBox, row: Gtk.ListBoxRow | None
    ) -> None:
        if row is None:
            return
        name = self._row_pages.get(row)
        if name:
            self.stack.set_visible_child_name(name)
            for page in self.pages:
                if page.name == name:
                    self.content_page.set_title(page.title)
                    self.bus_label.set_label(page.bus_kind)
                    break

    # -- content --
    def _build_content(self) -> Adw.NavigationPage:
        toolbar = Adw.ToolbarView()
        header = Adw.HeaderBar()

        refresh_btn = Gtk.Button(icon_name="view-refresh-symbolic")
        refresh_btn.set_tooltip_text("Re-read every service")
        refresh_btn.clicked.connect(lambda *_: self.refresh_all())
        header.pack_start(refresh_btn)

        self.bus_label = Gtk.Label(label="session bus")
        self.bus_label.add_css_class("dim-label")
        header.pack_end(self.bus_label)

        toolbar.add_top_bar(header)
        toolbar.set_content(self.stack)
        self.content_page = Adw.NavigationPage(
            title="Media", child=toolbar, tag="content"
        )
        return self.content_page

    def toast(self, message: str) -> None:
        self.toaster.add_toast(Adw.Toast(title=message, timeout=3))

    def refresh_all(self) -> None:
        for page in self.pages:
            page.refresh()


# --------------------------------------------------------------------------- #
# Application
# --------------------------------------------------------------------------- #
class DashboardApp(Adw.Application, type_name="DBusDashboardApp"):
    def __init__(self, self_test: bool = False) -> None:
        super().__init__(application_id="org.ginext.DBusDashboard")
        self.self_test = self_test
        self.window: DashboardWindow | None = None

    def do_activate(self) -> None:
        if self.window is None:
            try:
                system = Bus(Gio.BusType.SYSTEM)
                session = Bus(Gio.BusType.SESSION)
            except GLib.Error as exc:
                print(f"cannot reach a message bus: {exc.message}", file=sys.stderr)
                self.quit()
                return
            self.window = DashboardWindow(self, system, session)
        self.window.present()
        if self.self_test:
            # Land on the unit list so the ListView realizes and binds rows,
            # exercising the factory bind path.
            self.window.stack.set_visible_child_name("systemd")
            GLib.timeout_add(600, self._finish_self_test)

    def _finish_self_test(self) -> bool:
        print("self-test: window built and refreshed; quitting", flush=True)
        self.quit()
        return False


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv if argv is None else argv)
    self_test = "--self-test" in argv
    argv = [a for a in argv if a != "--self-test"]
    Adw.init()
    app = DashboardApp(self_test=self_test)
    return app.run(argv)


if __name__ == "__main__":
    raise SystemExit(main())
