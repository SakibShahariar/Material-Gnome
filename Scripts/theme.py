#!/usr/bin/env python3
import gi, subprocess, os
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk

THEME_DIR = os.path.expanduser("~/.config/matugen/themes")

FILES_MAP = [
    ("kitty.conf", "~/.config/kitty/themes/colors.conf", "kitty +kitten themes --reload-in=all colors"),
    ("clock-rs-conf.toml", "~/.config/clock-rs/conf.toml", None),
    ("sherlock.css", "~/.config/sherlock/main.css", None),
    ("starship.toml", "~/.config/starship.toml", None),
    ("accent-color.css", "~/.config/accent-color.css", None),
    ("gtk3-colors.css", "~/.config/gtk-3.0/colors.css", None),
    ("gtk4-colors.css", "~/.config/gtk-4.0/colors.css", None),
    ("micro-colors.micro", "~/.config/micro/colorschemes/colors.micro", None),
    ("qtct-colors.conf", "~/.config/qt5ct/colors/colors.conf", None),
    ("qtct-colors.conf", "~/.config/qt6ct/colors/colors.conf", None),
    ("mpv-uosc.conf", "~/.config/mpv/script-opts/uosc.conf", None),
    ("mpv-config.conf", "~/.config/colors.json", None),
    ("gnome-shell.css", "~/.themes/Material-Gnome/gnome-shell/gnome-shell.css", None),
    ("btop.theme", "~/.config/btop/themes/matugen.theme", None),
    ("cava-colors.ini", "~/.config/cava/themes/cava", "pkill -USR1 cava"),
    ("yazi.toml", "~/.config/yazi/theme.toml", None),
    ("zen_colors.css", "~/.zen/czfvdv64.Default (release)/chrome/colors.css", None),
    ("zen-accent.js", "~/.zen/czfvdv64.Default (release)/user.js", None),
]

def apply_pop_colors():
    accent_file = os.path.expanduser("~/.config/accent-color.css")
    if os.path.exists(accent_file):
        with open(accent_file, "r") as f:
            pop_hint_color = f.read().strip()

        # Pop Shell hint color
        subprocess.run([
            "dconf", "write",
            "/org/gnome/shell/extensions/pop-shell/hint-color-rgba",
            f"'{pop_hint_color}'"
        ], check=True)

        # Clock extension keys
        clock_keys = [
            "time-font-color",
            "date-font-color",
            "hint-font-color",
            "command-output-font-color"
        ]
        for key in clock_keys:
            subprocess.run([
                "dconf", "write",
                f"/org/gnome/shell/extensions/customize-clock-on-lockscreen/{key}",
                f"'{pop_hint_color}'"
            ], check=True)

def apply_theme(theme_name):
    theme_path = os.path.join(THEME_DIR, theme_name)
    for file_name, dest, hook in FILES_MAP:
        src = os.path.join(theme_path, file_name)
        dest = os.path.expanduser(dest)

        if os.path.exists(src):
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            subprocess.run(["cp", "--remove-destination", src, dest])
            if hook:
                subprocess.run(hook, shell=True)
        else:
            print(f"Skipping {file_name}: not found in theme folder.")

    # Reset GNOME Shell theme, then set Material-Gnome
    subprocess.run([
        "dconf", "write",
        "/org/gnome/shell/extensions/user-theme/name",
        "'default'"
    ])
    subprocess.run([
        "dconf", "write",
        "/org/gnome/shell/extensions/user-theme/name",
        "'Material-Gnome'"
    ])

    # Apply Pop Shell and Clock colors
    apply_pop_colors()

    print(f"Theme '{theme_name}' applied successfully!")

class ThemeApp(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="org.matugen.themepicker")

    def do_activate(self):
        win = Gtk.ApplicationWindow(application=self)
        win.set_title("Select Theme")
        win.set_default_size(300, 400)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        win.set_child(scrolled)

        listbox = Gtk.ListBox()
        listbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        scrolled.set_child(listbox)

        themes = sorted([d for d in os.listdir(THEME_DIR) if os.path.isdir(os.path.join(THEME_DIR, d))])
        for theme in themes:
            row = Gtk.ListBoxRow()
            label = Gtk.Label(label=theme, xalign=0)
            row.set_child(label)
            listbox.append(row)

        def on_theme_selected(lb, row):
            theme_name = row.get_child().get_text()
            apply_theme(theme_name)
            self.quit()

        listbox.connect("row-activated", on_theme_selected)

        win.present()

if __name__ == "__main__":
    app = ThemeApp()
    app.run()
