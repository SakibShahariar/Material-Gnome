#!/usr/bin/env python3

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, GdkPixbuf, Gdk, GLib, Adw, Gio
import os
import sys
import concurrent.futures
import subprocess
import time
import hashlib
import shutil
import json
from pathlib import Path
import humanize
import colorsys

THUMBNAIL_SIZE = 180
THUMBNAIL_CACHE_DIR = os.path.join(os.path.expanduser("~"), ".cache", "wallpicker-thumbs")
FAVORITES_FILE = os.path.join(os.path.expanduser("~"), ".config", "wallpicker-favorites.json")
COLOR_CACHE_FILE = os.path.join(os.path.expanduser("~"), ".cache", "wallpicker-color-cache.json")
GREYSCALE_THRESHOLD = 25
REFRESH_INTERVAL = 5000  # Check for new images every 5 seconds

COLOR_FAMILIES = {
    "Red": ["#F44336", "#E91E63", "#FF5252"],
    "Pink": ["#E91E63", "#EC407A", "#F06292"],
    "Purple": ["#9C27B0", "#8E24AA", "#AB47BC"],
    "Blue": ["#2196F3", "#1E88E5", "#42A5F5"],
    "Teal": ["#009688", "#00897B", "#26A69A"],
    "Green": ["#4CAF50", "#43A047", "#66BB6A"],
    "Yellow": ["#FFEB3B", "#FDD835", "#FFEE58"],
    "Orange": ["#FF9800", "#FB8C00", "#FFA726"],
    "Brown": ["#795548", "#6D4C41", "#8D6E63"],
    "Grey": ["#9E9E9E", "#757575", "#BDBDBD"]
}

class WallpaperPicker(Adw.Application):
    def __init__(self):
        super().__init__(application_id="org.sakib.wallpicker")
        self.connect("activate", self.on_activate)
        self.wallpaper_dir = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser("~/Pictures/Wallpapers")
        self.destroyed = False
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=8)
        self.search_text = ""
        self.favorites = self.load_favorites()
        self.color_family_filter = None
        self.preview_window = None
        self.current_preview = None
        self.color_cache = self.load_color_cache()
        self.analyzing_colors = False
        self.total_files = 0
        self.analyzed_files = 0
        self.last_mtime = 0

        os.makedirs(THUMBNAIL_CACHE_DIR, exist_ok=True)

    def hex_to_rgb(self, hex_color):
        """Convert hex color to RGB tuple"""
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

    def is_greyscale(self, rgb):
        """Check if color is effectively greyscale"""
        r, g, b = rgb
        return (abs(r - g) < GREYSCALE_THRESHOLD and
                abs(g - b) < GREYSCALE_THRESHOLD and
                abs(r - b) < GREYSCALE_THRESHOLD)

    def analyze_image_colors(self, file_path):
        """Get vibrant dominant colors using ImageMagick"""
        try:
            if file_path in self.color_cache:
                return self.color_cache[file_path]

            cmd = [
                'convert', file_path,
                '-resize', '100x100',
                '+dither',
                '-colors', '10',
                '-unique-colors',
                'txt:-'
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, check=True)

            colors = []
            for line in result.stdout.splitlines()[1:]:
                if '#' in line:
                    hex_color = '#' + line.split('#')[1].split(' ')[0]
                    rgb = self.hex_to_rgb(hex_color)
                    if not self.is_greyscale(rgb):
                        colors.append(hex_color)

            self.color_cache[file_path] = colors[:5]
            return colors[:5]

        except Exception as e:
            print(f"Error analyzing colors: {e}")
            return []

    def colors_are_similar(self, color1_hex, color2_hex, hue_threshold=30, sat_threshold=40):
        """Check if colors are similar in HSL space"""
        def hex_to_hsl(hex_color):
            hex_color = hex_color.lstrip('#')
            rgb = tuple(int(hex_color[i:i+2], 16)/255 for i in (0, 2, 4))
            return colorsys.rgb_to_hls(*rgb)

        h1, l1, s1 = hex_to_hsl(color1_hex)
        h2, l2, s2 = hex_to_hsl(color2_hex)

        hue_diff = min(abs(h1-h2), 1-abs(h1-h2)) * 360
        sat_diff = abs(s1-s2) * 100

        return hue_diff < hue_threshold and sat_diff < sat_threshold

    def filter_func(self, child, data):
        """Filter wallpapers based on search/favorites/color family"""
        button = child.get_child()

        if self.search_text and self.search_text not in button.filename.lower():
            return False

        if self.favorites_toggle.get_active() and button.full_path not in self.favorites:
            return False

        if self.color_family_filter:
            if button.full_path not in self.color_cache:
                return False

            family_colors = COLOR_FAMILIES.get(self.color_family_filter, [])
            wall_colors = self.color_cache[button.full_path]

            for wall_color in wall_colors:
                for family_color in family_colors:
                    if self.colors_are_similar(wall_color, family_color):
                        return True

            return False

        return True

    def on_activate(self, app):
        self.win = Adw.ApplicationWindow(application=app)
        self.win.set_title("Wallpaper Selector")
        self.win.set_default_size(1000, 700)
        self.win.set_size_request(800, 500)

        # Add CSS for tooltip styling
        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(b"""
        tooltip {
            padding: 0;
            border-radius: 5px;
        }
        tooltip * {
            background-color: transparent;
        }
        """)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        self.main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.win.set_content(self.main_box)

        self.header = Adw.HeaderBar()
        self.main_box.append(self.header)

        self.search_entry = Gtk.SearchEntry()
        self.search_entry.set_placeholder_text("Search wallpapers...")
        self.search_entry.set_size_request(300, -1)
        self.search_entry.connect("search-changed", self.on_search_changed)
        self.header.set_title_widget(self.search_entry)

        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        self.header.pack_start(button_box)

        # Home button to reset all filters
        self.home_button = Gtk.Button.new_from_icon_name("go-home-symbolic")
        self.home_button.set_tooltip_text("Reset all filters")
        self.home_button.connect("clicked", self.reset_all_filters)
        button_box.append(self.home_button)

        self.color_button = Gtk.Button.new_from_icon_name("color-select-symbolic")
        self.color_button.set_tooltip_text("Filter by Color Family")
        self.color_button.connect("clicked", self.show_color_palette)
        button_box.append(self.color_button)

        self.folder_button = Gtk.Button.new_from_icon_name("folder-open-symbolic")
        self.folder_button.set_tooltip_text("Open Wallpaper Folder")
        self.folder_button.connect("clicked", self.open_wallpaper_folder)
        button_box.append(self.folder_button)

        self.refresh_button = Gtk.Button.new_from_icon_name("view-refresh-symbolic")
        self.refresh_button.set_tooltip_text("Refresh")
        self.refresh_button.connect("clicked", self.refresh_wallpapers)
        button_box.append(self.refresh_button)

        self.clear_cache_button = Gtk.Button.new_from_icon_name("edit-clear-symbolic")
        self.clear_cache_button.set_tooltip_text("Clear Thumbnail Cache")
        self.clear_cache_button.connect("clicked", self.clear_thumbnail_cache)
        button_box.append(self.clear_cache_button)

        self.favorites_toggle = Gtk.ToggleButton()
        self.favorites_toggle.set_icon_name("starred-symbolic")
        self.favorites_toggle.set_tooltip_text("Show Favorites Only")
        self.favorites_toggle.connect("toggled", self.toggle_favorites)
        button_box.append(self.favorites_toggle)

        self.scrolled = Gtk.ScrolledWindow()
        self.scrolled.set_vexpand(True)
        self.main_box.append(self.scrolled)

        self.status_bar = Gtk.Statusbar()
        self.status_bar.set_vexpand(False)
        self.main_box.append(self.status_bar)

        self.flowbox = Gtk.FlowBox()
        self.flowbox.set_max_children_per_line(5)
        self.flowbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.flowbox.set_margin_top(10)
        self.flowbox.set_margin_bottom(10)
        self.flowbox.set_margin_start(10)
        self.flowbox.set_margin_end(10)
        self.flowbox.set_row_spacing(12)
        self.flowbox.set_column_spacing(12)
        self.flowbox.set_homogeneous(True)
        self.flowbox.set_filter_func(self.filter_func, None)
        self.flowbox.set_can_focus(True)

        flowbox_key_controller = Gtk.EventControllerKey.new()
        flowbox_key_controller.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        flowbox_key_controller.connect("key-pressed", self.on_flowbox_key_pressed)
        self.flowbox.add_controller(flowbox_key_controller)

        self.scrolled.set_child(self.flowbox)

        key_controller = Gtk.EventControllerKey.new()
        key_controller.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        key_controller.connect("key-pressed", self.on_key_pressed)
        self.win.add_controller(key_controller)

        self.win.connect("close-request", self.on_window_close_request)
        self.load_wallpaper_placeholders()

        # Start periodic check for new images
        GLib.timeout_add(REFRESH_INTERVAL, self.check_for_new_images)

        self.win.present()

    def check_for_new_images(self):
        """Check for new images in the wallpaper directory"""
        if self.destroyed:
            return False

        try:
            current_mtime = os.path.getmtime(self.wallpaper_dir)
            if current_mtime > self.last_mtime:
                self.last_mtime = current_mtime
                GLib.idle_add(self.refresh_wallpapers)
                self.update_status("New wallpapers detected - refreshing...")

        except Exception as e:
            print(f"Error checking for new images: {e}")

        return True  # Continue the timer

    def show_color_palette(self, button):
        dialog = Gtk.Dialog(title="Select Color Family")
        dialog.set_transient_for(self.win)
        dialog.set_modal(True)
        dialog.set_default_size(400, 300)

        content_area = dialog.get_content_area()
        content_area.set_margin_top(10)
        content_area.set_margin_bottom(10)
        content_area.set_margin_start(10)
        content_area.set_margin_end(10)

        def on_color_selected(family_name):
            self.color_family_filter = family_name
            dialog.response(Gtk.ResponseType.OK)
            self.update_status(f"Filter applied: {family_name}")
            self.update_filter_status()

        def on_clear_filter():
            self.color_family_filter = None
            dialog.response(Gtk.ResponseType.OK)
            self.update_status("Color filter cleared")
            self.update_filter_status()

        # Color family selection
        family_flow = Gtk.FlowBox()
        family_flow.set_max_children_per_line(4)
        family_flow.set_selection_mode(Gtk.SelectionMode.NONE)
        family_flow.set_margin_bottom(10)

        for family_name, family_colors in COLOR_FAMILIES.items():
            btn = Gtk.Button()
            btn.set_tooltip_text(family_name)

            grad_box = Gtk.Box()
            grad_box.set_size_request(80, 30)

            css = f"""
            box {{
                background: linear-gradient(to right, {', '.join(family_colors[:3])});
                border-radius: 5px;
                border: 1px solid #333;
            }}
            """
            provider = Gtk.CssProvider()
            provider.load_from_data(css.encode())
            grad_box.get_style_context().add_provider(
                provider,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
            )

            btn.set_child(grad_box)
            btn.connect("clicked", lambda _, fn=family_name: on_color_selected(fn))
            family_flow.append(btn)

        content_area.append(family_flow)

        # Controls
        controls = Gtk.Box(spacing=10)
        controls.set_halign(Gtk.Align.CENTER)
        controls.set_margin_top(10)

        clear_btn = Gtk.Button(label="Clear Filter")
        clear_btn.connect("clicked", lambda _: on_clear_filter())
        controls.append(clear_btn)

        close_btn = Gtk.Button(label="Close")
        close_btn.connect("clicked", lambda _: dialog.response(Gtk.ResponseType.CANCEL))
        controls.append(close_btn)

        content_area.append(controls)

        def on_dialog_response(dialog, response):
            dialog.destroy()
            if response == Gtk.ResponseType.OK:
                # Status already updated by button handlers
                pass

        dialog.connect("response", on_dialog_response)
        dialog.present()

    def update_filter_status(self):
        """Update status bar with current filter and count"""
        self.flowbox.invalidate_filter()
        visible_count = len([c for c in self.flowbox.get_children() if c.get_visible()])

        if self.color_family_filter:
            status = f"Showing {visible_count} {self.color_family_filter.lower()} wallpapers"
        elif self.search_text:
            status = f"Showing {visible_count} matching '{self.search_text}'"
        elif self.favorites_toggle.get_active():
            status = f"Showing {visible_count} favorites"
        else:
            status = f"Showing all {visible_count} wallpapers"

        self.update_status(status)

    def reset_all_filters(self, button):
        """Reset all filters to show all wallpapers"""
        self.search_entry.set_text("")
        self.search_text = ""
        self.color_family_filter = None
        self.favorites_toggle.set_active(False)
        self.update_status(f"Showing all {len(self.files)} wallpapers")
        self.flowbox.invalidate_filter()

    def on_window_close_request(self, widget):
        self.destroyed = True
        self.executor.shutdown(wait=False, cancel_futures=True)
        self.save_favorites()
        self.save_color_cache()
        return False

    def show_preview(self, button):
        # Destroy any existing preview window
        self.close_preview()

        # Create new preview window
        self.preview_window = Gtk.Window()
        self.preview_window.set_title(f"Preview - {button.filename}")
        self.preview_window.set_default_size(1000, 700)
        self.preview_window.fullscreen()
        self.preview_window.set_modal(True)
        self.preview_window.set_transient_for(self.win)

        # Main container
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.preview_window.set_child(box)

        # Image preview
        self.current_preview = Gtk.Picture()
        self.current_preview.set_size_request(900, 600)
        self.current_preview.set_can_shrink(True)
        self.current_preview.set_file(Gio.File.new_for_path(button.full_path))
        box.append(self.current_preview)

        # Button box
        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        btn_box.set_halign(Gtk.Align.CENTER)
        btn_box.set_margin_bottom(10)
        box.append(btn_box)

        # Set wallpaper button
        set_btn = Gtk.Button.new_with_label("Set as Wallpaper")
        set_btn.connect("clicked", lambda b: self.on_thumbnail_clicked(button))
        btn_box.append(set_btn)

        # Close button
        close_btn = Gtk.Button.new_with_label("Close Preview")
        close_btn.connect("clicked", lambda b: self.close_preview())
        btn_box.append(close_btn)

        # Key controller for keyboard shortcuts
        key_controller = Gtk.EventControllerKey.new()
        key_controller.connect("key-pressed", self.on_preview_key_pressed)
        self.preview_window.add_controller(key_controller)

        # Connect close handler
        self.preview_window.connect("close-request", lambda w: self.close_preview())

        self.preview_window.present()

    def close_preview(self):
        if hasattr(self, 'preview_window') and self.preview_window:
            self.preview_window.destroy()
            self.preview_window = None
        return True

    def on_preview_key_pressed(self, controller, keyval, keycode, state):
        if keyval == Gdk.KEY_Escape:
            self.close_preview()
            return True
        elif keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):
            selected = self.flowbox.get_selected_children()
            if selected:
                child = selected[0]
                button = child.get_child()
                self.on_thumbnail_clicked(button)
            return True
        return False

    def get_columns_count(self):
        allocation = self.flowbox.get_allocation()
        if allocation.width == 1:
            return 5
        child_width = 200 + 12
        return max(1, allocation.width // child_width)

    def on_flowbox_key_pressed(self, controller, keyval, keycode, state):
        if keyval == Gdk.KEY_Right:
            self.navigate_flowbox(1)
            return True
        elif keyval == Gdk.KEY_Left:
            self.navigate_flowbox(-1)
            return True
        elif keyval == Gdk.KEY_Down:
            n_columns = self.get_columns_count()
            self.navigate_flowbox(n_columns)
            return True
        elif keyval == Gdk.KEY_Up:
            n_columns = self.get_columns_count()
            self.navigate_flowbox(-n_columns)
            return True
        elif keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):
            selected = self.flowbox.get_selected_children()
            if selected:
                child = selected[0]
                button = child.get_child()
                self.on_thumbnail_clicked(button)
            return True
        return False

    def navigate_flowbox(self, step):
        n_columns = self.get_columns_count()
        current_index = self.flowbox.get_selected_index()
        num_children = len(self.flowbox.get_children())

        if current_index < 0:
            new_index = 0
        else:
            new_index = current_index + step
            if new_index < 0:
                new_index = num_children - 1
            elif new_index >= num_children:
                new_index = 0

        child = self.flowbox.get_child_at_index(new_index)
        if child:
            self.flowbox.select_child(child)
            child.grab_focus()
            self.scrolled.get_vadjustment().set_value(child.get_allocation().y - 100)

    def on_key_pressed(self, controller, keyval, keycode, state):
        if keyval == Gdk.KEY_Escape:
            self.win.close()
            return True
        elif keyval == Gdk.KEY_F5:
            self.refresh_wallpapers()
            return True
        elif keyval == Gdk.KEY_space:
            selected = self.flowbox.get_selected_children()
            if selected:
                child = selected[0]
                button = child.get_child()
                self.show_preview(button)
            return True

        modifiers = state & (Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.ALT_MASK)
        if keyval < 128 and chr(keyval).isprintable() and not modifiers:
            if not self.search_entry.is_focus():
                self.search_entry.grab_focus()
                current = self.search_entry.get_text()
                self.search_entry.set_text(current + chr(keyval))
                self.search_entry.set_position(-1)
                return True

        return False

    def refresh_wallpapers(self, button=None):
        while self.flowbox.get_first_child():
            self.flowbox.remove(self.flowbox.get_first_child())

        self.buttons = []
        self.load_wallpaper_placeholders()
        self.update_status(f"Refreshed: {len(self.files)} wallpapers")

    def open_wallpaper_folder(self, button):
        try:
            subprocess.Popen(['xdg-open', self.wallpaper_dir])
        except Exception as e:
            print(f"Error opening folder: {e}", file=sys.stderr)
            self.update_status(f"Error opening folder: {e}")

    def clear_thumbnail_cache(self, button=None):
        try:
            if os.path.exists(THUMBNAIL_CACHE_DIR):
                shutil.rmtree(THUMBNAIL_CACHE_DIR)
            os.makedirs(THUMBNAIL_CACHE_DIR, exist_ok=True)
            self.refresh_wallpapers()
            self.update_status("Thumbnail cache cleared")
        except Exception as e:
            print(f"Error clearing cache: {e}", file=sys.stderr)
            self.update_status(f"Error clearing cache: {e}")

    def on_search_changed(self, entry):
        self.search_text = entry.get_text().lower()
        self.update_filter_status()

    def update_status(self, message):
        self.status_bar.remove_all(0)
        self.status_bar.push(0, message)

    def load_wallpaper_placeholders(self):
        if not os.path.isdir(self.wallpaper_dir):
            self.update_status(f"Directory not found: {self.wallpaper_dir}")
            return

        self.files = []
        extensions = ('.jpg', '.jpeg', '.png', '.webp', '.bmp', '.tiff')

        file_info = []
        with os.scandir(self.wallpaper_dir) as entries:
            for entry in entries:
                if entry.is_file() and entry.name.lower().endswith(extensions):
                    stat = entry.stat()
                    file_info.append({
                        'name': entry.name,
                        'path': entry.path,
                        'size': stat.st_size,
                    })

        # Always sort by name
        file_info.sort(key=lambda x: x['name'].lower())
        self.files = [f['path'] for f in file_info]
        self.current_files = set(self.files)

        self.buttons = []
        for info in file_info:
            btn = Gtk.Button()
            btn.set_can_focus(True)
            btn.set_focusable(True)
            btn.set_hexpand(True)
            btn.set_vexpand(True)
            btn.set_size_request(200, 200)
            btn.set_css_classes(["thumbnail"])

            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
            box.set_margin_bottom(5)
            box.set_margin_top(5)
            box.set_margin_start(5)
            box.set_margin_end(5)

            spinner = Gtk.Spinner()
            spinner.set_size_request(THUMBNAIL_SIZE, THUMBNAIL_SIZE)
            spinner.start()
            box.append(spinner)

            label = Gtk.Label(label=info['name'])
            label.set_ellipsize(3)
            label.set_max_width_chars(20)
            label.set_wrap(True)
            label.set_wrap_mode(2)
            box.append(label)

            if info['path'] in self.favorites:
                fav_icon = Gtk.Image.new_from_icon_name("starred-symbolic")
                fav_icon.set_halign(Gtk.Align.END)
                fav_icon.set_valign(Gtk.Align.START)
                fav_icon.set_margin_top(5)
                fav_icon.set_margin_end(5)
                overlay = Gtk.Overlay()
                overlay.set_child(box)
                overlay.add_overlay(fav_icon)
                btn.set_child(overlay)
            else:
                btn.set_child(box)

            btn.full_path = info['path']
            btn.filename = info['name']
            btn.file_size = info['size']
            btn.connect("clicked", self.on_thumbnail_clicked)

            btn.set_has_tooltip(True)
            btn.connect("query-tooltip", self.on_query_tooltip)

            gesture = Gtk.GestureClick.new()
            gesture.set_button(3)
            gesture.connect("pressed", self.on_right_click, btn)
            btn.add_controller(gesture)

            self.flowbox.append(btn)
            self.buttons.append(btn)

        self.update_status(f"Loaded {len(self.files)} wallpapers")

        if self.files:
            self.flowbox.grab_focus()
            first_child = self.flowbox.get_child_at_index(0)
            if first_child:
                self.flowbox.select_child(first_child)

        future = self.executor.submit(self.load_thumbnails_thread)
        future = self.executor.submit(self.analyze_colors_thread)

    def load_thumbnails_thread(self):
        if self.destroyed:
            return

        for i, file_path in enumerate(self.files):
            if self.destroyed:
                return

            try:
                success, width, height = GdkPixbuf.Pixbuf.get_file_info(file_path)
                if not success:
                    width, height = 0, 0

                cache_filename = hashlib.md5(file_path.encode()).hexdigest() + ".png"
                cache_path = os.path.join(THUMBNAIL_CACHE_DIR, cache_filename)

                use_cache = False
                if os.path.exists(cache_path):
                    cache_mtime = os.path.getmtime(cache_path)
                    file_mtime = os.path.getmtime(file_path)
                    if cache_mtime >= file_mtime:
                        use_cache = True

                if use_cache:
                    pixbuf = GdkPixbuf.Pixbuf.new_from_file(cache_path)
                else:
                    pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(
                        file_path, THUMBNAIL_SIZE, THUMBNAIL_SIZE, preserve_aspect_ratio=True)
                    pixbuf.savev(cache_path, "png", [], [])

                texture = Gdk.Texture.new_for_pixbuf(pixbuf)
                GLib.idle_add(self.update_button_image, i, texture, width, height)
            except Exception as e:
                print(f"Error loading {file_path}: {e}", file=sys.stderr)
                GLib.idle_add(self.mark_thumbnail_error, i)

    def mark_thumbnail_error(self, index):
        if self.destroyed or index >= len(self.buttons):
            return

        btn = self.buttons[index]
        if isinstance(btn.get_child(), Gtk.Overlay):
            box = btn.get_child().get_child()
        else:
            box = btn.get_child()

        spinner = box.get_first_child()
        box.remove(spinner)

        error_icon = Gtk.Image.new_from_icon_name("image-missing")
        error_icon.set_pixel_size(THUMBNAIL_SIZE)
        box.prepend(error_icon)

    def update_button_image(self, index, texture, orig_width, orig_height):
        if self.destroyed or index >= len(self.buttons):
            return False

        btn = self.buttons[index]
        btn.orig_width = orig_width
        btn.orig_height = orig_height

        if isinstance(btn.get_child(), Gtk.Overlay):
            box = btn.get_child().get_child()
        else:
            box = btn.get_child()

        spinner = box.get_first_child()
        box.remove(spinner)

        img = Gtk.Image.new_from_paintable(texture)
        img.set_size_request(THUMBNAIL_SIZE, THUMBNAIL_SIZE)
        box.prepend(img)

        return False

    def on_query_tooltip(self, widget, x, y, keyboard_mode, tooltip):
        size_str = humanize.naturalsize(widget.file_size, binary=True)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        box.set_margin_top(5)
        box.set_margin_bottom(5)
        box.set_margin_start(5)
        box.set_margin_end(5)

        # Filename
        name_label = Gtk.Label()
        name_label.set_markup(f"<b>{widget.filename}</b>")
        name_label.set_xalign(0)
        box.append(name_label)

        # Dimensions and size
        info_label = Gtk.Label()
        info_label.set_xalign(0)

        info_text = []
        if hasattr(widget, 'orig_width') and hasattr(widget, 'orig_height'):
            if widget.orig_width > 0 and widget.orig_height > 0:
                info_text.append(f"Dimensions: {widget.orig_width}×{widget.orig_height}")
        info_text.append(f"Size: {size_str}")

        info_label.set_label("\n".join(info_text))
        box.append(info_label)

        # Dominant colors section
        colors = []
        if widget.full_path in self.color_cache:
            colors = self.color_cache[widget.full_path][:3]  # Show max 3 dominant colors

        if colors:
            colors_label = Gtk.Label(label="Dominant Colors:")
            colors_label.set_xalign(0)
            box.append(colors_label)

            colors_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
            for color in colors:
                color_box = Gtk.Box()
                color_box.set_size_request(24, 24)
                color_box.set_margin_top(2)
                color_box.set_margin_bottom(2)

                css = f"""
                box {{
                    background-color: {color};
                    border-radius: 3px;
                    border: 1px solid #333;
                }}
                """
                provider = Gtk.CssProvider()
                provider.load_from_data(css.encode())
                color_box.get_style_context().add_provider(
                    provider,
                    Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
                )
                colors_box.append(color_box)
            box.append(colors_box)

        tooltip.set_custom(box)
        return True

    def on_thumbnail_clicked(self, button):
        print(button.full_path)
        sys.stdout.flush()
        self.win.close()

    def toggle_favorites(self, button):
        if button.get_active():
            self.update_status("Showing favorites only")
        else:
            self.update_status("Showing all wallpapers")
        self.update_filter_status()

    def load_favorites(self):
        try:
            if os.path.exists(FAVORITES_FILE):
                with open(FAVORITES_FILE, 'r') as f:
                    return set(json.load(f))
        except:
            pass
        return set()

    def save_favorites(self):
        try:
            os.makedirs(os.path.dirname(FAVORITES_FILE), exist_ok=True)
            with open(FAVORITES_FILE, 'w') as f:
                json.dump(list(self.favorites), f)
        except Exception as e:
            print(f"Error saving favorites: {e}")

    def on_right_click(self, gesture, n_press, x, y, btn):
        menu = Gtk.PopoverMenu()
        menu_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        menu_box.set_margin_top(5)
        menu_box.set_margin_bottom(5)
        menu_box.set_margin_start(5)
        menu_box.set_margin_end(5)

        set_item = Gtk.Button.new_with_label("Set as Wallpaper")
        set_item.set_halign(Gtk.Align.FILL)
        set_item.connect("clicked", lambda *_: self.on_thumbnail_clicked(btn))
        menu_box.append(set_item)

        preview_item = Gtk.Button.new_with_label("Preview")
        preview_item.set_halign(Gtk.Align.FILL)
        preview_item.connect("clicked", lambda *_: self.show_preview(btn))
        menu_box.append(preview_item)

        open_item = Gtk.Button.new_with_label("Open in Viewer")
        open_item.set_halign(Gtk.Align.FILL)
        open_item.connect("clicked", lambda *_: self.open_in_viewer(btn))
        menu_box.append(open_item)

        show_item = Gtk.Button.new_with_label("Show in Folder")
        show_item.set_halign(Gtk.Align.FILL)
        show_item.connect("clicked", lambda *_: self.show_in_folder(btn.full_path))
        menu_box.append(show_item)

        is_fav = btn.full_path in self.favorites
        fav_text = "Remove from Favorites" if is_fav else "Add to Favorites"
        fav_icon = "starred-symbolic" if is_fav else "non-starred-symbolic"
        fav_item = Gtk.Button.new_with_label(fav_text)
        fav_item.set_icon_name(fav_icon)
        fav_item.set_halign(Gtk.Align.FILL)
        fav_item.connect("clicked", lambda *_: self.toggle_favorite_for(btn))
        menu_box.append(fav_item)

        menu.set_child(menu_box)
        menu.set_parent(btn)
        menu.set_autohide(True)
        menu.set_has_arrow(False)
        menu.set_position(Gtk.PositionType.BOTTOM)
        menu.popup()

    def toggle_favorite_for(self, button):
        if button.full_path in self.favorites:
            self.favorites.discard(button.full_path)
        else:
            self.favorites.add(button.full_path)
        self.save_favorites()
        self.refresh_wallpapers()

    def open_in_viewer(self, button):
        try:
            subprocess.Popen(['xdg-open', button.full_path])
        except Exception as e:
            print(f"Error opening viewer: {e}", file=sys.stderr)
            self.update_status(f"Error opening viewer: {e}")

    def show_in_folder(self, path):
        try:
            subprocess.Popen(['xdg-open', os.path.dirname(path)])
        except Exception as e:
            print(f"Error showing in folder: {e}", file=sys.stderr)
            self.update_status(f"Error showing folder: {e}")

    def load_color_cache(self):
        try:
            if os.path.exists(COLOR_CACHE_FILE):
                with open(COLOR_CACHE_FILE, 'r') as f:
                    return json.load(f)
        except:
            pass
        return {}

    def save_color_cache(self):
        try:
            os.makedirs(os.path.dirname(COLOR_CACHE_FILE), exist_ok=True)
            with open(COLOR_CACHE_FILE, 'w') as f:
                json.dump(self.color_cache, f)
        except Exception as e:
            print(f"Error saving color cache: {e}")

    def analyze_colors_thread(self):
        """Color analysis with progress reporting"""
        if self.destroyed:
            return

        self.analyzing_colors = True
        self.total_files = len(self.files)
        self.analyzed_files = 0

        for i, file_path in enumerate(self.files):
            if self.destroyed:
                return

            if file_path not in self.color_cache:
                colors = self.analyze_image_colors(file_path)
                self.analyzed_files += 1
                GLib.idle_add(self.update_color_cache, file_path, colors)

                # Update progress every 10 files or when done
                if i % 10 == 0 or i == len(self.files) - 1:
                    progress = (self.analyzed_files / self.total_files) * 100
                    GLib.idle_add(self.update_status,
                        f"Analyzing colors... {self.analyzed_files}/{self.total_files} ({progress:.1f}%)")

        self.analyzing_colors = False
        GLib.idle_add(self.save_color_cache)
        GLib.idle_add(self.update_status,
            f"Ready. {len([f for f in self.files if f in self.color_cache])}/{len(self.files)} images analyzed")

    def update_color_cache(self, file_path, colors):
        self.color_cache[file_path] = colors

app = WallpaperPicker()
app.run(None)
