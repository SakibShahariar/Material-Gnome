#!/usr/bin/env python3

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GdkPixbuf, Gdk, GLib
import os
import threading
import sys

class WallpaperPicker(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="org.sakib.wallpicker")
        self.connect("activate", self.on_activate)

        # Get wallpaper dir from command-line argument or default
        if len(sys.argv) > 1:
            self.wallpaper_dir = sys.argv[1]
        else:
            self.wallpaper_dir = "/mnt/data/Wallpapers"

    def on_activate(self, app):
        self.win = Gtk.ApplicationWindow(application=app)
        self.win.set_title("Pick Your Vibe")
        self.win.set_default_size(900, 600)
        self.win.set_resizable(True)

        # Keyboard controller: ESC to close, ENTER to select
        key_controller = Gtk.EventControllerKey.new()
        key_controller.connect("key-pressed", self.on_key_pressed)
        self.win.add_controller(key_controller)

        self.scrolled = Gtk.ScrolledWindow()
        self.win.set_child(self.scrolled)

        self.flowbox = Gtk.FlowBox()
        self.flowbox.set_max_children_per_line(4)
        self.flowbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.scrolled.set_child(self.flowbox)

        self.load_wallpaper_placeholders()
        threading.Thread(target=self.load_thumbnails_thread, daemon=True).start()

        self.win.present()

    def on_key_pressed(self, controller, keyval, keycode, state):
        # ESC closes window
        if keyval == 65307:
            self.win.close()
            return True
        # ENTER or KP_Enter triggers selection of the focused wallpaper
        elif keyval in (65293, 65421):
            selected = self.flowbox.get_selected_children()
            if selected:
                child = selected[0]
                button = child.get_child()
                self.on_thumbnail_clicked(button)
            return True
        return False

    def load_wallpaper_placeholders(self):
        # Clear existing children
        while self.flowbox.get_child_at_index(0) is not None:
            child = self.flowbox.get_child_at_index(0)
            self.flowbox.remove(child)

        if not os.path.isdir(self.wallpaper_dir):
            print(f"Wallpaper directory not found: {self.wallpaper_dir}", file=sys.stderr)
            self.win.close()
            return

        self.files = [f for f in os.listdir(self.wallpaper_dir)
                      if f.lower().endswith(('.jpg', '.jpeg', '.png'))]

        self.buttons = []

        for filename in self.files:
            btn = Gtk.Button()
            btn.set_can_focus(True)
            btn.set_focusable(True)
            btn.set_receives_default(True)
            btn.set_size_request(270, 300)

            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)

            img = Gtk.Image.new()
            label = Gtk.Label(label=filename)
            label.set_max_width_chars(20)
            label.set_ellipsize(3)

            box.append(img)
            box.append(label)
            btn.set_child(box)

            btn.full_path = os.path.join(self.wallpaper_dir, filename)
            btn.connect("clicked", self.on_thumbnail_clicked)

            self.flowbox.append(btn)
            self.buttons.append(btn)

        # Select first by default
        if self.flowbox.get_first_child():
            self.flowbox.select_child(self.flowbox.get_first_child())

    def load_thumbnails_thread(self):
        for i, filename in enumerate(self.files):
            full_path = os.path.join(self.wallpaper_dir, filename)
            try:
                pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(
                    full_path, 256, 256, preserve_aspect_ratio=True)
                texture = Gdk.Texture.new_for_pixbuf(pixbuf)
            except Exception as e:
                print(f"Failed to load thumbnail for {filename}: {e}", file=sys.stderr)
                continue

            GLib.idle_add(self.update_button_image, i, texture)

    def update_button_image(self, index, texture):
        btn = self.buttons[index]
        img = Gtk.Image()
        img.set_from_paintable(texture)
        img.set_hexpand(True)
        img.set_vexpand(True)
        img.set_halign(Gtk.Align.CENTER)
        img.set_valign(Gtk.Align.CENTER)
        img.set_size_request(256, 256)

        box = btn.get_child()
        old_img = box.get_first_child()
        box.remove(old_img)
        box.insert_child_after(img, None)

        return False

    def on_thumbnail_clicked(self, button):
        path = button.full_path
        print(path)   # Output selected wallpaper path to stdout
        sys.stdout.flush()
        self.win.close()

app = WallpaperPicker()
app.run()
