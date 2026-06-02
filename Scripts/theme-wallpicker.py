#!/usr/bin/env python3

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, GLib, Gio, Gdk, GdkPixbuf, Adw, Pango
import subprocess
import json
import os
import sys
from pathlib import Path
import shlex
import time

class WallpaperPicker(Adw.Application):
    def __init__(self):
        super().__init__(application_id="com.example.WallpaperPicker",
                         flags=Gio.ApplicationFlags.FLAGS_NONE)

        self.WALLPAPER_MAP = Path.home() / ".config" / "matugen" / "wallpaper_map.json"
        self.STATE_FILE = Path.home() / ".config" / "theme-switcher" / "state.json"
        self.current_theme = None
        self.current_wallpapers = []
        self.selected_index = -1
        self.thumbnails = []

    def do_activate(self):
        if not self.load_current_theme():
            self.show_error_dialog("No theme selected", "Please select a theme first using apply-theme.fish")
            return

        if not self.load_wallpapers():
            self.show_error_dialog("No wallpapers found", f"No wallpapers found for theme '{self.current_theme}'")
            return

        self.window = Adw.ApplicationWindow(application=self, title="Select Wallpaper")

        # Set window size
        num_wallpapers = len(self.current_wallpapers)
        thumbnail_width = 140
        spacing = 10
        window_width = min(1200, (num_wallpapers * thumbnail_width) + ((num_wallpapers - 1) * spacing) + 40)
        height = 140  # Reduced height since we don't show labels

        self.window.set_default_size(window_width, height)
        self.window.set_resizable(True)

        # Add CSS styling
        self.add_css_styles()

        # Create main box
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.window.set_content(main_box)

        # Create scrolled container
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)
        scrolled.set_vexpand(True)
        scrolled.set_hexpand(True)
        scrolled.set_margin_top(10)
        scrolled.set_margin_bottom(10)
        scrolled.set_margin_start(10)
        scrolled.set_margin_end(10)

        # Create a grid for horizontal layout
        grid = Gtk.Grid()
        grid.set_row_homogeneous(True)
        grid.set_column_homogeneous(False)
        grid.set_column_spacing(10)
        grid.set_row_spacing(0)
        grid.set_halign(Gtk.Align.START)
        grid.set_valign(Gtk.Align.CENTER)

        # Clear thumbnails list
        self.thumbnails = []

        # Load current selection
        self.load_current_selection()

        # Create thumbnails and add to grid
        for idx, wallpaper_path in enumerate(self.current_wallpapers):
            polaroid = self.create_polaroid_thumbnail(wallpaper_path, idx)
            grid.attach(polaroid, idx, 0, 1, 1)
            self.thumbnails.append(polaroid)

        # Create a container to hold the grid
        container = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        container.append(grid)

        scrolled.set_child(container)
        main_box.append(scrolled)

        # Setup keyboard shortcuts
        self.setup_keyboard_shortcuts()

        # Connect window close event
        self.window.connect("close-request", self.on_window_close)

        self.window.present()

    def on_window_close(self, window):
        """Handle window close"""
        print("Window closing")
        return False

    def setup_keyboard_shortcuts(self):
        """Setup keyboard shortcuts properly"""
        key_controller = Gtk.EventControllerKey()
        key_controller.connect("key-pressed", self.on_key_pressed)
        self.window.add_controller(key_controller)

    def on_key_pressed(self, controller, keyval, keycode, state):
        """Handle key presses"""
        if keyval == Gdk.KEY_Escape or keyval == Gdk.KEY_q:
            self.window.close()
            return True
        elif keyval == Gdk.KEY_Return or keyval == Gdk.KEY_KP_Enter:
            self.apply_selected_wallpaper()
            return True
        elif keyval == Gdk.KEY_Left:
            self.select_previous_wallpaper()
            return True
        elif keyval == Gdk.KEY_Right:
            self.select_next_wallpaper()
            return True

        return False

    def select_previous_wallpaper(self):
        """Select previous wallpaper"""
        if len(self.current_wallpapers) == 0:
            return

        if self.selected_index < 0:
            self.selected_index = 0
        else:
            self.selected_index = (self.selected_index - 1) % len(self.current_wallpapers)

        self.update_selection_visual()

    def select_next_wallpaper(self):
        """Select next wallpaper"""
        if len(self.current_wallpapers) == 0:
            return

        if self.selected_index < 0:
            self.selected_index = 0
        else:
            self.selected_index = (self.selected_index + 1) % len(self.current_wallpapers)

        self.update_selection_visual()

    def update_selection_visual(self):
        """Update visual selection"""
        for idx, thumbnail in enumerate(self.thumbnails):
            if idx == self.selected_index:
                thumbnail.add_css_class("selected")
            else:
                thumbnail.remove_css_class("selected")

    def apply_selected_wallpaper(self):
        """Apply the currently selected wallpaper"""
        if self.selected_index >= 0 and self.selected_index < len(self.current_wallpapers):
            wallpaper = self.current_wallpapers[self.selected_index]
            self.apply_wallpaper(wallpaper, self.selected_index)

    def add_css_styles(self):
        """Add CSS styling"""
        css = """
        .polaroid-frame {
            border: 2px solid alpha(@borders, 0.5);
            border-radius: 8px;
            background-color: @theme_bg_color;
            box-shadow: 0 2px 6px alpha(black, 0.1);
            transition: all 150ms ease-in-out;
        }

        .polaroid-frame:hover {
            border-color: @theme_selected_bg_color;
            box-shadow: 0 4px 10px alpha(black, 0.15);
        }

        .polaroid-frame.selected {
            border-color: @theme_selected_bg_color;
            border-width: 3px;
            background-color: alpha(@theme_selected_bg_color, 0.1);
            box-shadow: 0 0 0 2px alpha(@theme_selected_bg_color, 0.3);
        }

        .wallpaper-image {
            border-radius: 6px;
        }
        """

        provider = Gtk.CssProvider()
        provider.load_from_data(css.encode())
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def create_polaroid_thumbnail(self, wallpaper_path, index):
        """Create a thumbnail without labels"""
        container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        container.set_size_request(140, 120)  # Square-ish size

        # Add CSS classes
        container.add_css_class("polaroid-frame")
        if index == self.selected_index:
            container.add_css_class("selected")

        # Image area - full thumbnail
        try:
            if os.path.exists(wallpaper_path):
                picture = Gtk.Picture.new_for_filename(wallpaper_path)
                picture.set_content_fit(Gtk.ContentFit.COVER)
                picture.add_css_class("wallpaper-image")
                picture.set_size_request(136, 116)
                picture.set_hexpand(True)
                picture.set_vexpand(True)
                container.append(picture)
            else:
                # Fallback for missing images
                label = Gtk.Label(label="❌")
                label.set_hexpand(True)
                label.set_vexpand(True)
                label.set_halign(Gtk.Align.CENTER)
                label.set_valign(Gtk.Align.CENTER)
                container.append(label)
        except Exception as e:
            print(f"Error loading image {wallpaper_path}: {e}")
            label = Gtk.Label(label="Error")
            label.set_hexpand(True)
            label.set_vexpand(True)
            container.append(label)

        # Make clickable
        click = Gtk.GestureClick()
        click.connect("released", self.on_wallpaper_clicked, wallpaper_path, index, container)
        container.add_controller(click)

        return container

    def load_current_theme(self):
        """Load current theme from state file"""
        if not self.STATE_FILE.exists():
            print(f"State file not found: {self.STATE_FILE}")
            return False

        try:
            with open(self.STATE_FILE, 'r') as f:
                state = json.load(f)
                self.current_theme = state.get("current_theme")
                if not self.current_theme:
                    print("No current theme in state file")
                    return False
                return True
        except Exception as e:
            print(f"Error loading current theme: {e}")
            return False

    def load_current_selection(self):
        """Load current wallpaper selection"""
        if not self.STATE_FILE.exists():
            return

        try:
            with open(self.STATE_FILE, 'r') as f:
                state = json.load(f)
                self.selected_index = state.get("wallpaper_index", 1) - 1
                if self.selected_index >= len(self.current_wallpapers):
                    self.selected_index = 0
        except Exception as e:
            print(f"Error loading selection: {e}")
            self.selected_index = -1

    def load_wallpapers(self):
        """Load wallpapers for current theme - READ ONLY (doesn't modify wallpaper_map.json)"""
        if not self.WALLPAPER_MAP.exists():
            print(f"Wallpaper map not found: {self.WALLPAPER_MAP}")
            return False

        try:
            with open(self.WALLPAPER_MAP, 'r') as f:
                data = json.load(f)

            theme_data = data.get(self.current_theme)
            if not theme_data:
                print(f"Theme '{self.current_theme}' not found in wallpaper_map.json")
                return False

            # Handle different data structures
            wallpapers = []
            if isinstance(theme_data, dict):
                # Check for 'wallpapers' key
                if "wallpapers" in theme_data and isinstance(theme_data["wallpapers"], list):
                    wallpapers = theme_data["wallpapers"]
                else:
                    # Try to find list values
                    for key, value in theme_data.items():
                        if isinstance(value, list):
                            wallpapers = value
                            break
                    else:
                        # If no list found, collect all string values
                        wallpapers = [v for v in theme_data.values() if isinstance(v, str)]
            elif isinstance(theme_data, list):
                wallpapers = theme_data
            elif isinstance(theme_data, str):
                wallpapers = [theme_data]
            else:
                print(f"Unexpected data type for theme in wallpaper_map.json: {type(theme_data)}")
                return False

            # Filter valid files
            valid_wallpapers = []
            for wp in wallpapers:
                if os.path.exists(wp):
                    valid_wallpapers.append(wp)
                else:
                    print(f"Warning: Wallpaper not found: {wp}")

            self.current_wallpapers = valid_wallpapers

            if len(self.current_wallpapers) == 0:
                print("No valid wallpapers found")
                return False

            print(f"Loaded {len(self.current_wallpapers)} wallpapers for theme '{self.current_theme}'")
            return True

        except json.JSONDecodeError as e:
            print(f"JSON error reading wallpaper_map.json: {e}")
            return False
        except Exception as e:
            print(f"Error loading wallpapers: {e}")
            return False

    def on_wallpaper_clicked(self, gesture, n_press, x, y, wallpaper_path, index, container):
        """Handle wallpaper click"""
        self.selected_index = index
        self.update_selection_visual()
        self.apply_wallpaper(wallpaper_path, index)

    def apply_wallpaper(self, wallpaper_path, index):
        """Apply wallpaper - Only updates state.json, doesn't modify wallpaper_map.json"""
        print(f"Applying wallpaper: {wallpaper_path}")

        # Update state file only
        self.update_state_file(wallpaper_path, index)

        # Apply with dconf
        success = self.apply_with_dconf(wallpaper_path)

        if success:
            self.show_success_message(wallpaper_path)
            GLib.timeout_add(1000, self.close_window)
        else:
            self.show_error_dialog("Failed", "Could not set wallpaper")

    def update_state_file(self, wallpaper_path, index):
        """Update state file ONLY - doesn't touch wallpaper_map.json"""
        try:
            state = {}
            if self.STATE_FILE.exists():
                with open(self.STATE_FILE, 'r') as f:
                    state = json.load(f)

            state.update({
                "current_theme": self.current_theme,
                "wallpaper_index": index + 1,
                "wallpaper_path": wallpaper_path,
                "last_modified": time.time()  # Optional: add timestamp
            })

            self.STATE_FILE.parent.mkdir(parents=True, exist_ok=True)

            with open(self.STATE_FILE, 'w') as f:
                json.dump(state, f, indent=2, ensure_ascii=False)

            print(f"Updated state file: {self.STATE_FILE}")

        except Exception as e:
            print(f"Error updating state file: {e}")

    def apply_with_dconf(self, wallpaper_path):
        """Apply wallpaper using dconf"""
        try:
            wallpaper_uri = f"file://{wallpaper_path}"

            commands = [
                ["dconf", "write", "/org/gnome/desktop/background/picture-uri", f"'{wallpaper_uri}'"],
                ["dconf", "write", "/org/gnome/desktop/background/picture-uri-dark", f"'{wallpaper_uri}'"],
            ]

            for cmd in commands:
                result = subprocess.run(cmd, capture_output=True, text=True)
                if result.returncode != 0:
                    print(f"dconf error: {result.stderr}")

            print(f"Wallpaper applied via dconf: {wallpaper_path}")
            return True

        except Exception as e:
            print(f"Error applying wallpaper with dconf: {e}")
            return False

    def show_error_dialog(self, title, message):
        """Show error dialog"""
        dialog = Adw.MessageDialog(
            transient_for=self.window,
            heading=title,
            body=message
        )
        dialog.add_response("ok", "OK")
        dialog.present()

    def show_success_message(self, wallpaper_path):
        """Show success toast"""
        toast = Adw.Toast.new(f"✓ Wallpaper set")
        toast.set_timeout(1)

        current_content = self.window.get_content()
        if isinstance(current_content, Adw.ToastOverlay):
            current_content.add_toast(toast)
        else:
            toast_overlay = Adw.ToastOverlay()
            toast_overlay.set_child(current_content)
            self.window.set_content(toast_overlay)
            toast_overlay.add_toast(toast)

    def close_window(self):
        """Close window"""
        self.window.close()
        return False

def main():
    app = WallpaperPicker()
    return app.run(sys.argv)

if __name__ == "__main__":
    main()
