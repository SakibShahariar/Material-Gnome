#!/usr/bin/env python3

import os
import sys
import pwd
import socket
import getpass
import shutil
import subprocess
from datetime import datetime

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Gtk, Adw, GLib, Gdk


CSS = """
.logout-box {
    padding: 28px 24px 20px 24px;
}

.header-row {
    padding: 12px 16px;
    border-radius: 14px;
    background-color: alpha(currentColor, 0.05);
}

.user-name {
    font-size: 1.3rem;
    font-weight: 700;
}

.user-meta {
    opacity: 0.6;
    font-size: 0.85rem;
}

.clock-label {
    font-size: 1.3rem;
    font-weight: 800;
}

.section-label {
    opacity: 0.55;
    font-size: 0.78rem;
    font-weight: 600;
    letter-spacing: 0.08em;
    margin-bottom: 2px;
}

.action-btn {
    min-width: 140px;
    min-height: 54px;
    border-radius: 14px;
    font-size: 0.95rem;
    font-weight: 600;
    transition: box-shadow 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.action-btn:focus {
    box-shadow: 0 0 0 3px alpha(currentColor, 0.15),
                0 0 0 6px alpha(currentColor, 0.08);
    animation: pulse 2s ease-in-out infinite;
}

@keyframes pulse {
    0%, 100% {
        box-shadow: 0 0 0 3px alpha(currentColor, 0.15),
                    0 0 0 6px alpha(currentColor, 0.08);
    }
    50% {
        box-shadow: 0 0 0 3px alpha(currentColor, 0.25),
                    0 0 0 10px alpha(currentColor, 0.04);
    }
}

.cancel-btn {
    min-width: 200px;
    min-height: 42px;
    border-radius: 99px;
    font-size: 0.9rem;
    margin-top: 4px;
}

.logout-box.fading {
    opacity: 0;
    transition: opacity 0.3s ease-out;
}
"""


class LogoutWindow(Adw.ApplicationWindow):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.set_title("System Actions")
        self.set_default_size(480, -1)
        self.set_resizable(False)
        self.set_modal(True)

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        root.add_css_class("logout-box")
        self.set_content(root)

        root.append(self._make_header())

        title = Gtk.Label(label="System Actions")
        title.add_css_class("title-2")
        title.set_xalign(0.5)
        root.append(title)

        session, power = self._get_actions()
        first = None

        if session:
            box, first = self._make_section("SESSION", session)
            root.append(box)

        if power:
            box, pfirst = self._make_section("POWER", power)
            root.append(box)
            if first is None:
                first = pfirst

        cancel = Gtk.Button(label="Cancel")
        cancel.add_css_class("cancel-btn")
        cancel.set_halign(Gtk.Align.CENTER)
        cancel.connect("clicked", lambda *_: self.close())
        root.append(cancel)

        if first:
            first.grab_focus()

        key = Gtk.EventControllerKey()
        key.connect("key-pressed", self.on_key)
        self.add_controller(key)

        self._tick()
        GLib.timeout_add_seconds(1, self._tick)

    def _make_header(self):
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        header.add_css_class("header-row")

        user = getpass.getuser()
        avatar = Gtk.Image()
        avatar.set_pixel_size(52)

        for p in [f"/var/lib/AccountsService/icons/{user}", os.path.expanduser("~/.face")]:
            if os.path.exists(p):
                avatar.set_from_file(p)
                break
        else:
            avatar.set_from_icon_name("avatar-default-symbolic")

        self.name_label = Gtk.Label(label=self._display_name())
        self.name_label.add_css_class("user-name")
        self.name_label.set_xalign(0)

        self.meta = Gtk.Label()
        self.meta.add_css_class("user-meta")
        self.meta.set_xalign(0)

        info = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
        info.set_valign(Gtk.Align.CENTER)
        info.append(self.name_label)
        info.append(self.meta)

        left = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        left.set_valign(Gtk.Align.CENTER)
        left.append(avatar)
        left.append(info)

        spacer = Gtk.Box()
        spacer.set_hexpand(True)

        self.clock = Gtk.Label()
        self.clock.add_css_class("clock-label")
        self.clock.set_xalign(1)

        self.date_label = Gtk.Label()
        self.date_label.add_css_class("user-meta")
        self.date_label.set_xalign(1)

        right = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
        right.set_valign(Gtk.Align.CENTER)
        right.set_halign(Gtk.Align.END)
        right.append(self.clock)
        right.append(self.date_label)

        header.append(left)
        header.append(spacer)
        header.append(right)
        return header

    def _display_name(self):
        user = getpass.getuser()
        try:
            return pwd.getpwnam(user).pw_gecos.split(",")[0] or user
        except Exception:
            return user

    def _get_uptime(self):
        """Parse /proc/uptime and return human-readable format."""
        try:
            with open("/proc/uptime", "r") as f:
                uptime_seconds = int(float(f.read().split()[0]))
            
            days = uptime_seconds // 86400
            hours = (uptime_seconds % 86400) // 3600
            minutes = (uptime_seconds % 3600) // 60
            
            if days > 0:
                return f"{days}d {hours}h"
            elif hours > 0:
                return f"{hours}h {minutes}m"
            else:
                return f"{minutes}m"
        except Exception:
            return "unknown"

    def _tick(self):
        now = datetime.now()
        self.clock.set_text(now.strftime("%H:%M"))
        self.date_label.set_text(now.strftime("%a %d %b"))
        uptime = self._get_uptime()
        self.meta.set_text(
            f"{getpass.getuser()} · {socket.gethostname()} · "
            f"up {uptime}"
        )
        return True

    def _make_section(self, title, actions):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)

        sec_label = Gtk.Label(label=title)
        sec_label.add_css_class("section-label")
        sec_label.set_xalign(0.5)
        box.append(sec_label)

        btn_row = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=10,
            halign=Gtk.Align.CENTER,
        )

        first = None
        for label, icon, cmd, destructive, _key in actions:
            btn = Gtk.Button()
            btn.set_child(Adw.ButtonContent(label=label, icon_name=icon))
            btn.add_css_class("action-btn")
            btn.connect("clicked", self.run, (label, cmd))
            if destructive:
                btn.add_css_class("destructive-action")
            btn_row.append(btn)
            if first is None:
                first = btn

        box.append(btn_row)
        return box, first

    def _get_actions(self):
        session = []
        power = []

        if shutil.which("loginctl"):
            session.append(("Lock", "system-lock-screen-symbolic",
                            ["loginctl", "lock-session"], False, Gdk.KEY_l))

        if shutil.which("gnome-session-quit"):
            session.append(("Log Out", "system-log-out-symbolic",
                            ["gnome-session-quit", "--logout", "--no-prompt"],
                            False, Gdk.KEY_o))

        if shutil.which("systemctl"):
            power.append(("Suspend", "weather-clear-night-symbolic",
                          ["systemctl", "suspend"], False, Gdk.KEY_s))
            power.append(("Reboot", "system-reboot-symbolic",
                          ["systemctl", "reboot"], True, Gdk.KEY_r))
            power.append(("Shutdown", "system-shutdown-symbolic",
                          ["systemctl", "poweroff"], True, Gdk.KEY_p))

        return session, power

    def on_key(self, controller, keyval, keycode, state):
        if keyval == Gdk.KEY_Escape:
            self.close()
            return True
        return False

    def run(self, btn, data):
        _label, cmd = data
        
        # Trigger fade animation
        root = self.get_content()
        root.add_css_class("fading")
        
        def execute_and_close():
            try:
                subprocess.run(cmd, check=True)
            except Exception:
                pass
            finally:
                self.close()
        
        # Execute after fade starts (300ms)
        GLib.timeout_add(300, execute_and_close)
        return False


class App(Adw.Application):
    def __init__(self):
        super().__init__(application_id="dev.sak.SystemActions")
        GLib.set_application_name("System Actions")

    def do_startup(self):
        Adw.Application.do_startup(self)
        css = Gtk.CssProvider()
        css.load_from_string(CSS)
        display = Gdk.Display.get_default()
        if display:
            Gtk.StyleContext.add_provider_for_display(
                display, css,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
            )

    def do_activate(self):
        win = self.props.active_window
        if not win:
            win = LogoutWindow(application=self)
        win.present()


if __name__ == "__main__":
    app = App()
    sys.exit(app.run(sys.argv))
