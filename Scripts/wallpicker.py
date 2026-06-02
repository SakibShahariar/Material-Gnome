#!/usr/bin/env python3

import sys
import os
import json
import humanize
import threading
import hashlib
from pathlib import Path
import subprocess
import logging
from concurrent.futures import ThreadPoolExecutor

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
gi.require_version('Gdk', '4.0')
gi.require_version('GdkPixbuf', '2.0')

from gi.repository import Gtk, Gio, Gdk, GdkPixbuf, Adw, GLib, Pango
from PIL import Image

# ---------------------------
# Helper: Enhanced CSS with animations
# ---------------------------
def install_css():
    css = b"""
    .thumbnail {
        border-radius: 12px;
        transition: all 200ms cubic-bezier(0.25, 0.46, 0.45, 0.94);
        background-color: transparent;
        border: 1px solid transparent;
        opacity: 0;
    }

    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(10px); }
        to { opacity: 1; transform: translateY(0); }
    }

    .thumbnail.loaded {
        animation: fadeIn 300ms ease-in forwards;
    }

    .thumbnail:hover {
        transform: translateY(-4px) scale(1.02);
        box-shadow: 0 12px 35px rgba(0, 0, 0, 0.2);
    }
    .thumbnail:focus {
        outline: 3px solid rgba(130,211,227,0.95);
        outline-offset: 2px;
    }
    .thumbnail-label {
        font-size: 11px;
        font-weight: 500;
    }

    .favorite-badge {
        background: rgba(255, 193, 7, 0.9);
        border-radius: 50%;
        padding: 4px;
    }

    .stat-badge {
        font-size: 10px;
        padding: 2px 6px;
        border-radius: 4px;
        background: alpha(@accent_bg_color, 0.15);
        font-weight: 500;
    }

    .count-label {
        font-size: 11px;
        opacity: 0.7;
    }

    .skeleton {
        background: linear-gradient(90deg,
            rgba(255,255,255,0.05) 25%,
            rgba(255,255,255,0.1) 50%,
            rgba(255,255,255,0.05) 75%);
        background-size: 200% 100%;
        animation: shimmer 1.5s infinite;
    }

    @keyframes shimmer {
        0% { background-position: 200% 0; }
        100% { background-position: -200% 0; }
    }
    """
    provider = Gtk.CssProvider()
    provider.load_from_data(css)
    display = Gdk.Display.get_default()
    Gtk.StyleContext.add_provider_for_display(display, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)


class SettingsDialog(Adw.Window):
    """Dialog for editing application settings."""
    def __init__(self, parent_app, config, **kwargs):
        super().__init__(**kwargs)
        self.set_transient_for(parent_app.window)
        self.set_modal(True)
        self.set_default_size(400, 400)

        self.config = config
        self.parent_app = parent_app

        self.main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_content(self.main_box)

        header_bar = Adw.HeaderBar()
        header_bar.set_title_widget(Adw.WindowTitle(title="Wallpaper Picker Settings"))
        self.main_box.append(header_bar)

        scrolled_window = Gtk.ScrolledWindow()
        scrolled_window.set_vexpand(True)
        self.main_box.append(scrolled_window)

        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        content_box.set_margin_top(12)
        content_box.set_margin_bottom(12)
        content_box.set_margin_start(12)
        content_box.set_margin_end(12)
        scrolled_window.set_child(content_box)

        settings_group = Adw.PreferencesGroup(title="General Settings")
        content_box.append(settings_group)

        # Wallpaper Directory
        dir_row = Adw.ActionRow(title="Wallpaper Directory")
        dir_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.dir_entry = Gtk.Entry()
        self.dir_entry.set_text(self.config.get('wallpaper_dir', GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_PICTURES)))
        self.dir_entry.set_hexpand(True)
        dir_box.append(self.dir_entry)

        dir_button = Gtk.Button(label="Browse")
        dir_button.connect("clicked", self.on_browse_dir_clicked)
        dir_box.append(dir_button)

        dir_row.add_suffix(dir_box)
        settings_group.add(dir_row)

        # Thumbnail Width
        width_row = Adw.ActionRow(title="Thumbnail Width")
        self.width_spin = Gtk.SpinButton(adjustment=Gtk.Adjustment.new(self.config.get('thumbnail_width', 200), 50, 500, 10, 0, 0), numeric=True)
        width_row.add_suffix(self.width_spin)
        settings_group.add(width_row)

        # Thumbnail Height
        height_row = Adw.ActionRow(title="Thumbnail Height")
        self.height_spin = Gtk.SpinButton(adjustment=Gtk.Adjustment.new(self.config.get('thumbnail_height', 150), 50, 500, 10, 0, 0), numeric=True)
        height_row.add_suffix(self.height_spin)
        settings_group.add(height_row)

        # Columns
        columns_row = Adw.ActionRow(title="Columns")
        self.columns_spin = Gtk.SpinButton(adjustment=Gtk.Adjustment.new(self.config.get('columns', 4), 1, 10, 1, 0, 0), numeric=True)
        columns_row.add_suffix(self.columns_spin)
        settings_group.add(columns_row)

        # Extensions
        extensions_row = Adw.ActionRow(title="Extensions (comma-separated)")
        self.extensions_entry = Gtk.Entry()
        self.extensions_entry.set_text(self.config.get('extensions', 'jpg,jpeg,png'))
        extensions_row.add_suffix(self.extensions_entry)
        settings_group.add(extensions_row)

        # Thumbnail Quality
        quality_row = Adw.ActionRow(title="Thumbnail Quality")
        self.quality_spin = Gtk.SpinButton(adjustment=Gtk.Adjustment.new(self.config.get('thumbnail_quality', 95), 1, 100, 1, 0, 0), numeric=True)
        quality_row.add_suffix(self.quality_spin)
        settings_group.add(quality_row)

        # Lazy load batch size
        batch_row = Adw.ActionRow(title="Initial Load Batch Size", subtitle="Number of thumbnails to load initially")
        self.batch_spin = Gtk.SpinButton(adjustment=Gtk.Adjustment.new(self.config.get('lazy_load_batch', 20), 10, 100, 5, 0, 0), numeric=True)
        batch_row.add_suffix(self.batch_spin)
        settings_group.add(batch_row)

        # Buttons
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        button_box.set_halign(Gtk.Align.END)
        button_box.set_margin_top(12)
        button_box.set_margin_bottom(12)
        button_box.set_margin_start(12)
        button_box.set_margin_end(12)

        cancel_btn = Gtk.Button(label="Cancel")
        cancel_btn.connect("clicked", lambda btn: self.close())
        button_box.append(cancel_btn)

        save_btn = Gtk.Button(label="Save")
        save_btn.add_css_class('suggested-action')
        save_btn.connect("clicked", self.on_save_clicked)
        button_box.append(save_btn)

        self.main_box.append(button_box)

    def on_save_clicked(self, button):
        self.save_settings()
        self.close()

    def on_browse_dir_clicked(self, button):
        dialog = Gtk.FileDialog.new()
        dialog.set_title("Select Wallpaper Directory")
        dialog.set_modal(True)
        dialog.set_initial_folder(Gio.File.new_for_path(self.dir_entry.get_text()))

        def on_folder_selected(dialog, result):
            try:
                folder = dialog.select_folder_finish(result)
                if folder:
                    self.dir_entry.set_text(folder.get_path())
            except GLib.Error as e:
                print(f"Error selecting folder: {e}", file=sys.stderr)

        dialog.select_folder(self.parent_app.window, None, on_folder_selected)

    def save_settings(self):
        new_config = {
            'wallpaper_dir': self.dir_entry.get_text(),
            'thumbnail_width': self.width_spin.get_value_as_int(),
            'thumbnail_height': self.height_spin.get_value_as_int(),
            'columns': self.columns_spin.get_value_as_int(),
            'extensions': self.extensions_entry.get_text(),
            'thumbnail_quality': self.quality_spin.get_value_as_int(),
            'lazy_load_batch': self.batch_spin.get_value_as_int()
        }

        self.parent_app.config.update(new_config)

        config_dir = Path(GLib.get_user_config_dir()) / 'wallpicker'
        config_file = config_dir / 'config.json'
        try:
            with open(config_file, 'w') as f:
                json.dump(self.parent_app.config, f, indent=4)
        except OSError as e:
            print(f"Error writing config file: {e}", file=sys.stderr)

        self.parent_app.reload_ui_after_settings_change()


# FIX 1: Replaced deprecated Gtk.AboutDialog with Adw.AboutDialog.
# Adw.AboutDialog is the modern libadwaita equivalent with a richer,
# responsive design. The API differs: use set_application_name(),
# set_application_icon(), set_developer_name(), set_version(),
# set_comments(), set_license_type(), and present(parent) instead of
# set_transient_for() + present().
class AboutDialog:
    """Factory for the About dialog using the modern Adw.AboutDialog."""
    @staticmethod
    def show(parent_window):
        dialog = Adw.AboutDialog()
        dialog.set_application_name("Wallpaper Picker")
        dialog.set_version("2.1.0")
        dialog.set_comments("A modern wallpaper picker for GNOME with lazy loading, favorites, sorting, and smooth animations.")
        dialog.set_license_type(Gtk.License.GPL_3_0_ONLY)
        dialog.present(parent_window)


# ---------------------------
# Main Application
# ---------------------------
class WallpaperPicker(Adw.Application):
    def __init__(self, **kwargs):
        super().__init__(application_id="com.github.WallpaperPicker",
                         flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE,
                         **kwargs)
        self.selected_wallpaper = None
        self.wallpapers = []
        self.file_info = {}
        self.thumbnail_widgets = []
        self.selected_index = -1
        self.config = self.load_config()
        cache_dir_str = GLib.get_user_cache_dir()
        self.cache_dir = Path(cache_dir_str) / "wallpicker" / "thumbs"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.preview_window = None
        self.search_text = ""
        self.search_timeout = None
        self.executor = ThreadPoolExecutor(max_workers=os.cpu_count())

        # Favorites and sorting
        self.favorites = self.load_favorites()
        self.show_favorites_only = False
        self.sort_mode = "name"
        self.view_mode = "grid"

        # Lazy loading state
        self.loaded_count = 0
        self.is_loading = False
        self.load_lock = threading.Lock()
        self.pending_loads = set()
        self.scroll_timeout = None

        install_css()
        self.connect('activate', self.on_activate)

    def do_command_line(self, command_line):
        args = command_line.get_arguments()[1:]

        if len(args) > 0:
            path = args[0]
            if os.path.isdir(path):
                self.config['wallpaper_dir'] = path
            else:
                print(f"Warning: Provided path is not a valid directory: {path}", file=sys.stderr)

        self.activate()
        return 0

    def load_favorites(self):
        config_dir = Path(GLib.get_user_config_dir()) / 'wallpicker'
        fav_file = config_dir / 'favorites.json'
        if fav_file.exists():
            try:
                with open(fav_file, 'r') as f:
                    return set(json.load(f))
            except:
                return set()
        return set()

    def save_favorites(self):
        config_dir = Path(GLib.get_user_config_dir()) / 'wallpicker'
        config_dir.mkdir(parents=True, exist_ok=True)
        fav_file = config_dir / 'favorites.json'
        try:
            with open(fav_file, 'w') as f:
                json.dump(list(self.favorites), f, indent=4)
        except Exception as e:
            logging.error(f"Could not save favorites: {e}")

    def toggle_favorite(self, wallpaper_path):
        if wallpaper_path in self.favorites:
            self.favorites.remove(wallpaper_path)
        else:
            self.favorites.add(wallpaper_path)
        self.save_favorites()
        self.refresh_thumbnail(wallpaper_path)

    def refresh_thumbnail(self, wallpaper_path):
        for btn in self.thumbnail_widgets:
            if btn.wallpaper_path == wallpaper_path:
                overlay = btn.get_child()
                child = overlay.get_first_child()
                while child:
                    next_child = child.get_next_sibling()
                    if hasattr(child, 'is_fav_badge'):
                        overlay.remove_overlay(child)
                    child = next_child

                if wallpaper_path in self.favorites:
                    fav_badge = Gtk.Image.new_from_icon_name("starred-symbolic")
                    fav_badge.add_css_class('favorite-badge')
                    fav_badge.set_halign(Gtk.Align.END)
                    fav_badge.set_valign(Gtk.Align.START)
                    fav_badge.set_margin_top(8)
                    fav_badge.set_margin_end(8)
                    fav_badge.is_fav_badge = True
                    overlay.add_overlay(fav_badge)
                break

    def load_config(self):
        config_dir = Path(GLib.get_user_config_dir()) / 'wallpicker'
        config_file = config_dir / 'config.json'
        config_dir.mkdir(parents=True, exist_ok=True)

        default_config = {
            'wallpaper_dir': '/mnt/Storage/Wallpapers',
            'thumbnail_width': 200,
            'thumbnail_height': 150,
            'columns': 4,
            'extensions': 'jpg,jpeg,png',
            'thumbnail_quality': 95,
            'lazy_load_batch': 20
        }

        if config_file.exists():
            try:
                with open(config_file, 'r') as f:
                    config = json.load(f)
                    return {**default_config, **config}
            except (json.JSONDecodeError, TypeError) as e:
                print(f"Error reading config file, falling back to defaults: {e}", file=sys.stderr)
                return default_config
        else:
            try:
                with open(config_file, 'w') as f:
                    json.dump(default_config, f, indent=4)
            except OSError as e:
                print(f"Error writing default config file: {e}", file=sys.stderr)
            return default_config

    def on_activate(self, app):
        self.window = Adw.ApplicationWindow(application=app)
        self.window.set_title('Wallpaper Picker')
        self.window.set_default_size(1000, 700)

        header_bar = Adw.HeaderBar()

        view_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        view_box.add_css_class('linked')

        self.grid_btn = Gtk.ToggleButton(icon_name="view-grid-symbolic")
        self.grid_btn.set_active(True)
        self.grid_btn.set_tooltip_text("Grid View")
        view_box.append(self.grid_btn)

        self.list_btn = Gtk.ToggleButton(icon_name="view-list-symbolic")
        self.list_btn.set_tooltip_text("List View (Coming Soon)")
        self.list_btn.set_sensitive(False)
        self.list_btn.set_group(self.grid_btn)
        view_box.append(self.list_btn)

        header_bar.pack_start(view_box)

        sort_action_group = Gio.SimpleActionGroup()
        self.window.insert_action_group("sort", sort_action_group)

        sort_name_action = Gio.SimpleAction.new("name", None)
        sort_name_action.connect("activate", lambda a, p: self.set_sort_mode("name"))
        sort_action_group.add_action(sort_name_action)

        sort_date_action = Gio.SimpleAction.new("date", None)
        sort_date_action.connect("activate", lambda a, p: self.set_sort_mode("date"))
        sort_action_group.add_action(sort_date_action)

        sort_size_action = Gio.SimpleAction.new("size", None)
        sort_size_action.connect("activate", lambda a, p: self.set_sort_mode("size"))
        sort_action_group.add_action(sort_size_action)

        sort_menu = Gio.Menu()
        sort_menu.append("Name", "sort.name")
        sort_menu.append("Date Modified", "sort.date")
        sort_menu.append("File Size", "sort.size")

        sort_button = Gtk.MenuButton(
            icon_name="view-sort-ascending-symbolic",
            menu_model=sort_menu,
            tooltip_text="Sort By"
        )
        header_bar.pack_start(sort_button)

        search_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        search_box.set_halign(Gtk.Align.CENTER)

        self.search_entry = Gtk.SearchEntry()
        self.search_entry.set_placeholder_text("Search wallpapers...")
        self.search_entry.connect("search-changed", self.on_search_changed)
        search_box.append(self.search_entry)

        self.count_label = Gtk.Label()
        self.count_label.add_css_class('count-label')
        self.count_label.add_css_class('dim-label')
        search_box.append(self.count_label)

        header_bar.set_title_widget(search_box)

        self.fav_toggle = Gtk.ToggleButton(icon_name="starred-symbolic")
        self.fav_toggle.set_tooltip_text("Show Favorites Only")
        self.fav_toggle.connect("toggled", self.on_favorites_filter_toggled)
        header_bar.pack_end(self.fav_toggle)

        self.select_btn = Gtk.Button(label="Select")
        self.select_btn.add_css_class('suggested-action')
        self.select_btn.set_sensitive(False)
        self.select_btn.connect("clicked", self.on_select)
        header_bar.pack_end(self.select_btn)

        menu = Gio.Menu()
        menu.append("Settings", "app.settings")
        menu.append("About", "app.about")

        menu_button = Gtk.MenuButton(icon_name="open-menu-symbolic", menu_model=menu)
        header_bar.pack_end(menu_button)

        settings_action = Gio.SimpleAction.new("settings", None)
        settings_action.connect("activate", self.on_settings_clicked)
        self.add_action(settings_action)

        about_action = Gio.SimpleAction.new("about", None)
        about_action.connect("activate", self.on_about_clicked)
        self.add_action(about_action)

        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        main_box.append(header_bar)

        self.progress_bar = Gtk.ProgressBar()
        self.progress_bar.set_show_text(True)
        self.progress_bar.set_margin_start(12)
        self.progress_bar.set_margin_end(12)
        self.progress_bar.set_margin_top(6)
        self.progress_bar.set_margin_bottom(6)
        self.progress_bar.set_visible(False)
        main_box.append(self.progress_bar)

        self.view_stack = Adw.ViewStack()
        main_box.append(self.view_stack)

        self.scrolled = Gtk.ScrolledWindow()
        self.scrolled.set_hexpand(True)
        self.scrolled.set_vexpand(True)
        self.scrolled.get_vadjustment().connect("value-changed", self.on_scroll)

        self.flow_box = Gtk.FlowBox()
        self.flow_box.set_selection_mode(Gtk.SelectionMode.NONE)
        columns = self.config.get('columns', 4)
        self.flow_box.set_max_children_per_line(columns)
        self.flow_box.set_homogeneous(False)
        self.flow_box.set_margin_start(16)
        self.flow_box.set_margin_end(16)
        self.flow_box.set_filter_func(self.filter_func)

        self.scrolled.set_child(self.flow_box)
        self.view_stack.add_named(self.scrolled, "wallpapers")

        status_page = Adw.StatusPage.new()
        status_page.set_icon_name("folder-pictures-symbolic")
        status_page.set_title("No Wallpapers Found")
        status_page.set_description("Check the configured wallpaper directory or add images to it.")
        status_page.set_vexpand(True)

        settings_button = Gtk.Button.new_with_label("Open Settings")
        settings_button.connect("clicked", lambda _: self.on_settings_clicked(None, None))
        status_page.set_child(settings_button)
        self.view_stack.add_named(status_page, "empty")

        self.window.set_content(main_box)
        self.window.present()

        nav_key_controller = Gtk.EventControllerKey.new()
        nav_key_controller.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        nav_key_controller.connect("key-pressed", self.on_key_pressed)
        self.flow_box.add_controller(nav_key_controller)

        window_key_controller = Gtk.EventControllerKey.new()
        window_key_controller.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        window_key_controller.connect("key-pressed", self.on_window_key_pressed)
        self.window.add_controller(window_key_controller)

        self.start_loading()

    def on_scroll(self, adjustment):
        if self.scroll_timeout:
            GLib.source_remove(self.scroll_timeout)
        self.scroll_timeout = GLib.timeout_add(150, self.check_and_load_more)

    def check_and_load_more(self):
        self.scroll_timeout = None

        if self.is_loading or self.loaded_count >= len(self.wallpapers):
            return False

        vadj = self.scrolled.get_vadjustment()
        value = vadj.get_value()
        page_size = vadj.get_page_size()
        upper = vadj.get_upper()

        if value + page_size >= upper * 0.8:
            self.load_next_batch()

        return False

    def load_next_batch(self):
        with self.load_lock:
            if self.is_loading:
                return
            self.is_loading = True

        batch_size = self.config.get('lazy_load_batch', 20)
        start = self.loaded_count
        end = min(start + batch_size, len(self.wallpapers))

        if start >= end:
            self.is_loading = False
            return

        GLib.idle_add(self.update_progress, end, len(self.wallpapers))

        for i in range(start, end):
            wall_info = self.wallpapers[i]
            wallpaper_path = wall_info['path']

            if wallpaper_path not in self.pending_loads:
                self.pending_loads.add(wallpaper_path)
                for btn in self.thumbnail_widgets:
                    if btn.wallpaper_path == wallpaper_path and not btn.thumbnail_loaded:
                        self.load_thumbnail(btn, wallpaper_path)
                        break

        self.loaded_count = end
        self.is_loading = False
        GLib.idle_add(self.check_and_load_more)

    def set_sort_mode(self, mode):
        self.sort_mode = mode
        self.resort_wallpapers()

    def resort_wallpapers(self):
        if self.sort_mode == "name":
            self.wallpapers.sort(key=lambda x: os.path.basename(x['path']).lower())
        elif self.sort_mode == "date":
            self.wallpapers.sort(key=lambda x: x.get('mtime', 0), reverse=True)
        elif self.sort_mode == "size":
            self.wallpapers.sort(key=lambda x: x.get('size', 0), reverse=True)
        self.reload_ui_after_settings_change()

    def on_favorites_filter_toggled(self, toggle):
        self.show_favorites_only = toggle.get_active()
        self.flow_box.invalidate_filter()
        self.update_count_label()

    def update_count_label(self):
        visible = len(self._get_visible_flowbox_children())
        total = len(self.wallpapers)

        if self.show_favorites_only:
            self.count_label.set_text(f"{visible} favorites")
        elif visible == total:
            self.count_label.set_text(f"{total} wallpapers")
        else:
            self.count_label.set_text(f"{visible} of {total} wallpapers")

    def on_search_changed(self, entry):
        self.search_text = entry.get_text().lower()
        if self.search_timeout:
            GLib.source_remove(self.search_timeout)
        self.search_timeout = GLib.timeout_add(300, self._perform_search)

    def _perform_search(self):
        self.flow_box.invalidate_filter()
        self.update_count_label()
        self.search_timeout = None
        return False

    def filter_func(self, child, data=None):
        button = child.get_child()
        if not hasattr(button, 'wallpaper_path'):
            return False

        wallpaper_path = button.wallpaper_path

        if self.show_favorites_only and wallpaper_path not in self.favorites:
            return False

        if self.search_text:
            return self.search_text in os.path.basename(wallpaper_path).lower()

        return True

    def on_settings_clicked(self, action, state):
        self.settings_dialog = SettingsDialog(self, self.config)
        self.settings_dialog.present()

    def on_about_clicked(self, action, state):
        # FIX 1 (usage): Call the static factory method instead of
        # instantiating the old Gtk.AboutDialog subclass.
        AboutDialog.show(self.window)

    def start_loading(self):
        self.view_stack.set_visible_child_name("wallpapers")
        self.progress_bar.set_visible(True)
        self.progress_bar.set_text("Scanning directory...")
        thread = threading.Thread(target=self.load_wallpapers_thread, daemon=True)
        thread.start()

    def find_wallpapers_fast(self):
        wallpaper_dir = self.config.get('wallpaper_dir')
        if not os.path.isdir(wallpaper_dir):
            return []
        extensions = tuple(f".{e.strip().lower()}" for e in self.config.get('extensions', 'jpg,jpeg,png').split(','))
        wallpapers_with_info = []
        try:
            for root, _, files in os.walk(wallpaper_dir):
                for name in files:
                    if name.lower().endswith(extensions):
                        path = os.path.join(root, name)
                        try:
                            stat = os.stat(path)
                            wallpapers_with_info.append({
                                'path': path,
                                'size': stat.st_size,
                                'mtime': stat.st_mtime
                            })
                        except OSError:
                            continue
        except (PermissionError, OSError) as e:
            logging.warning(f"Permission or OS error during wallpaper search: {e}")
        return sorted(wallpapers_with_info, key=lambda x: x['path'])

    def _get_visible_flowbox_children(self):
        visible_children = []
        child = self.flow_box.get_first_child()
        while child:
            if self.filter_func(child):
                visible_children.append(child)
            child = child.get_next_sibling()
        return visible_children

    def load_wallpapers_thread(self):
        self.wallpapers = self.find_wallpapers_fast()
        if not self.wallpapers:
            GLib.idle_add(self.show_error_dialog, "No wallpapers found!")
            return

        total = len(self.wallpapers)
        GLib.idle_add(self.progress_bar.set_text, f"Found {total} wallpapers")

        for wall_info in self.wallpapers:
            self.file_info[wall_info['path']] = {
                'size': wall_info['size'],
                'mtime': wall_info.get('mtime', 0)
            }
            GLib.idle_add(self.add_wallpaper_skeleton, wall_info['path'])

        GLib.idle_add(self.placeholders_complete)
        GLib.idle_add(self.load_next_batch)

    def placeholders_complete(self):
        self.update_count_label()
        self.progress_bar.set_text("Loading thumbnails...")
        return False

    def update_progress(self, current, total):
        fraction = current / total if total > 0 else 0
        self.progress_bar.set_fraction(fraction)
        self.progress_bar.set_text(f"Loaded {current}/{total} thumbnails")

        if current >= total:
            GLib.timeout_add(500, lambda: self.progress_bar.set_visible(False))

        return False

    def add_wallpaper_skeleton(self, wallpaper):
        btn = Gtk.Button()
        btn.add_css_class('thumbnail')
        btn.connect('clicked', self.on_thumbnail_button_clicked)

        overlay = Gtk.Overlay()
        btn.set_child(overlay)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box.set_margin_top(6)
        box.set_margin_bottom(6)
        box.set_margin_start(6)
        box.set_margin_end(6)
        overlay.set_child(box)

        if wallpaper in self.favorites:
            fav_badge = Gtk.Image.new_from_icon_name("starred-symbolic")
            fav_badge.add_css_class('favorite-badge')
            fav_badge.set_halign(Gtk.Align.END)
            fav_badge.set_valign(Gtk.Align.START)
            fav_badge.set_margin_top(8)
            fav_badge.set_margin_end(8)
            fav_badge.is_fav_badge = True
            overlay.add_overlay(fav_badge)

        skeleton = Gtk.Box()
        skeleton.add_css_class('skeleton')
        skeleton.set_size_request(
            self.config.get('thumbnail_width', 200),
            self.config.get('thumbnail_height', 150)
        )
        box.append(skeleton)
        btn.skeleton = skeleton

        label = Gtk.Label(label=os.path.basename(wallpaper))
        label.add_css_class('thumbnail-label')
        label.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
        label.set_max_width_chars(22)
        box.append(label)

        btn.wallpaper_path = wallpaper
        btn.set_focusable(True)
        btn.set_has_tooltip(True)
        btn.connect("query-tooltip", self.on_query_tooltip)

        gesture = Gtk.GestureClick.new()
        gesture.set_button(3)
        gesture.connect("pressed", self.on_thumbnail_right_click, wallpaper)
        btn.add_controller(gesture)

        self.flow_box.append(btn)
        self.thumbnail_widgets.append(btn)
        btn.thumbnail_loaded = False

        return False

    def on_thumbnail_right_click(self, gesture, n_press, x, y, wallpaper_path):
        menu = Gio.Menu()

        is_fav = wallpaper_path in self.favorites
        fav_label = "★ Remove from Favorites" if is_fav else "☆ Add to Favorites"
        menu.append(fav_label, f"win.toggle-favorite")
        menu.append("Preview", f"win.preview-wallpaper")
        menu.append("Show in Files", f"win.show-in-files")

        action_group = Gio.SimpleActionGroup()

        toggle_fav = Gio.SimpleAction.new("toggle-favorite", None)
        toggle_fav.connect("activate", lambda a, p: self.toggle_favorite(wallpaper_path))
        action_group.add_action(toggle_fav)

        preview_action = Gio.SimpleAction.new("preview-wallpaper", None)
        preview_action.connect("activate", lambda a, p: self.open_preview(wallpaper_path))
        action_group.add_action(preview_action)

        show_files = Gio.SimpleAction.new("show-in-files", None)
        show_files.connect("activate", lambda a, p: subprocess.Popen(['xdg-open', os.path.dirname(wallpaper_path)]))
        action_group.add_action(show_files)

        widget = gesture.get_widget()
        widget.insert_action_group("win", action_group)

        popover = Gtk.PopoverMenu.new_from_model(menu)
        popover.set_parent(widget)
        popover.set_position(Gtk.PositionType.BOTTOM)
        popover.popup()

    def load_thumbnail(self, btn, wallpaper):
        if hasattr(btn, 'thumbnail_loaded') and btn.thumbnail_loaded:
            return

        btn.thumbnail_loaded = True
        self.executor.submit(self._load_thumbnail_thread, btn, wallpaper)

    # FIX 2 & 3: Replaced the fragile GdkPixbuf.Pixbuf.new_from_data() +
    # Gdk.Texture.new_for_pixbuf() pipeline with a cache-first approach:
    #
    #   - Always write the resized thumbnail to the PNG cache file (same as
    #     before), then load the texture directly from the file path using
    #     Gdk.Texture.new_from_filename(). This is the idiomatic GTK4 path
    #     and completely avoids the deprecated Pixbuf→Texture conversion.
    #
    #   - The manual Pixbuf construction from raw PIL bytes
    #     (GdkPixbuf.Pixbuf.new_from_data) is gone. Saving to a file and
    #     reloading is both safer and avoids the rowstride/alpha-channel
    #     pitfalls of the manual approach.
    #
    #   - The `warnings` import has been removed since we no longer need to
    #     suppress DeprecationWarning around Texture.new_for_pixbuf().
    #
    #   - We still read orig_width/height via PIL for the tooltip/stat badge.
    def _load_thumbnail_thread(self, btn, wallpaper):
        thumb_width = self.config.get('thumbnail_width', 200)
        thumb_height = self.config.get('thumbnail_height', 150)
        h = hashlib.sha1(wallpaper.encode()).hexdigest()
        cache_file = self.cache_dir / f"{h}.png"

        try:
            # Always read original dimensions for the stat/tooltip overlay.
            try:
                with Image.open(wallpaper) as img:
                    orig_width, orig_height = img.size
                    if self.file_info.get(wallpaper):
                        self.file_info[wallpaper]['width'] = orig_width
                        self.file_info[wallpaper]['height'] = orig_height
            except Exception:
                pass

            # Build / validate cache file, then load texture from it.
            cache_valid = (
                cache_file.exists()
                and os.path.getmtime(cache_file) >= os.path.getmtime(wallpaper)
            )

            if not cache_valid:
                with Image.open(wallpaper) as pil_image:
                    pil_image.thumbnail((thumb_width, thumb_height))
                    pil_image.save(cache_file, "PNG")

            # Gdk.Texture.new_from_filename() is the modern, deprecation-free
            # way to create a texture for display in a Gtk.Picture widget.
            texture = Gdk.Texture.new_from_filename(str(cache_file))

            GLib.idle_add(self._update_thumbnail_ui, btn, texture)

        except Exception as e:
            error_message = str(e)
            logging.error(f"Error loading {wallpaper}: {error_message}")
            GLib.idle_add(self._update_thumbnail_ui_with_error, btn, error_message)
        finally:
            if wallpaper in self.pending_loads:
                self.pending_loads.remove(wallpaper)

    # FIX 2 (cont.): _update_thumbnail_ui now receives a ready-to-use
    # Gdk.Texture instead of a GdkPixbuf, removing the deprecated
    # Gdk.Texture.new_for_pixbuf() call that was previously here.
    def _update_thumbnail_ui(self, btn, texture):
        thumb_width = self.config.get('thumbnail_width', 200)
        thumb_height = self.config.get('thumbnail_height', 150)

        picture = Gtk.Picture.new_for_paintable(texture)
        picture.set_size_request(thumb_width, thumb_height)

        overlay = btn.get_child()
        box = overlay.get_child()

        if hasattr(btn, "skeleton") and btn.skeleton is not None:
            try:
                box.remove(btn.skeleton)
            except Exception as e:
                logging.warning(f"Could not remove skeleton: {e}")
            del btn.skeleton

        box.prepend(picture)

        if btn.wallpaper_path in self.file_info and 'width' in self.file_info[btn.wallpaper_path]:
            info = self.file_info[btn.wallpaper_path]
            stats_text = f"{info['width']}×{info['height']}"
            stats_label = Gtk.Label(label=stats_text)
            stats_label.add_css_class('stat-badge')
            box.append(stats_label)

        btn.add_css_class('loaded')
        return False

    def _update_thumbnail_ui_with_error(self, btn, error_message):
        thumb_width = self.config.get('thumbnail_width', 200)
        thumb_height = self.config.get('thumbnail_height', 150)

        error_icon = Gtk.Image.new_from_icon_name("image-missing")
        error_icon.set_pixel_size(64)
        error_icon.set_size_request(thumb_width, thumb_height)
        error_icon.set_valign(Gtk.Align.CENTER)
        error_icon.set_halign(Gtk.Align.CENTER)

        overlay = btn.get_child()
        box = overlay.get_child()

        if hasattr(btn, "skeleton") and btn.skeleton is not None:
            try:
                box.remove(btn.skeleton)
            except Exception:
                pass
            del btn.skeleton

        box.prepend(error_icon)
        btn.error_message = error_message
        btn.add_css_class('loaded')
        return False

    def reload_ui_after_settings_change(self):
        child = self.flow_box.get_first_child()
        while child:
            next_child = child.get_next_sibling()
            self.flow_box.remove(child)
            child = next_child

        self.thumbnail_widgets = []
        self.selected_index = -1
        self.selected_wallpaper = None
        self.select_btn.set_sensitive(False)
        self.loaded_count = 0
        self.pending_loads.clear()
        self.progress_bar.set_visible(True)

        self.flow_box.set_max_children_per_line(self.config.get('columns', 4))
        self.start_loading()

    # FIX 4: Replaced deprecated Adw.MessageDialog with Adw.AlertDialog.
    # Adw.MessageDialog was deprecated in libadwaita 1.5 (GNOME 45).
    # Adw.AlertDialog is the current API. A try/except fallback is included
    # so the code still works on older libadwaita (< 1.5) installations.
    def show_error_dialog(self, message):
        try:
            # Adw.AlertDialog — available since libadwaita 1.5
            dialog = Adw.AlertDialog(
                heading="Error",
                body=message
            )
            dialog.add_response("ok", "OK")
            dialog.connect("response", lambda d, r: self.window.close())
            dialog.present(self.window)
        except AttributeError:
            # Fallback for libadwaita < 1.5 (Adw.MessageDialog still works there)
            dialog = Adw.MessageDialog(
                transient_for=self.window,
                heading="Error",
                body=message
            )
            dialog.add_response("ok", "OK")
            dialog.connect("response", lambda d, r: self.window.close())
            dialog.present()

    def on_query_tooltip(self, widget, x, y, keyboard_mode, tooltip):
        path = widget.wallpaper_path

        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        main_box.set_margin_top(8)
        main_box.set_margin_bottom(8)
        main_box.set_margin_start(8)
        main_box.set_margin_end(8)

        name_label = Gtk.Label()
        name_label.set_markup(f"<b>{GLib.markup_escape_text(os.path.basename(path))}</b>")
        name_label.set_xalign(0)
        main_box.append(name_label)

        if hasattr(widget, 'error_message'):
            error_label = Gtk.Label(label=f"Error: {widget.error_message}")
            error_label.set_xalign(0)
            error_label.set_wrap(True)
            error_label.set_max_width_chars(40)
            main_box.append(error_label)
            tooltip.set_custom(main_box)
            return True

        info = self.file_info.get(path)
        if not info:
            return False

        if 'size' in info:
            size_str = humanize.naturalsize(info['size'], binary=True)
            size_label = Gtk.Label(label=f"Size: {size_str}")
            size_label.set_xalign(0)
            main_box.append(size_label)

        if 'width' in info and 'height' in info:
            dim_label = Gtk.Label(label=f"Dimensions: {info['width']} × {info['height']}")
            dim_label.set_xalign(0)
            main_box.append(dim_label)

        if path in self.favorites:
            fav_label = Gtk.Label(label="⭐ Favorite")
            fav_label.set_xalign(0)
            main_box.append(fav_label)

        tooltip.set_custom(main_box)
        return True

    def _select_item_by_index(self, visible_index):
        visible_children = self._get_visible_flowbox_children()
        if not (0 <= visible_index < len(visible_children)):
            return

        self.selected_index = visible_index
        flowbox_child = visible_children[visible_index]
        widget = flowbox_child.get_child()

        widget.grab_focus()

        if not hasattr(widget, 'thumbnail_loaded') or not widget.thumbnail_loaded:
            self.load_thumbnail(widget, widget.wallpaper_path)

        coords = widget.translate_coordinates(self.flow_box, 0, 0)
        if coords:
            x, y = coords
            widget_height = widget.get_height()

            vadj = self.scrolled.get_vadjustment()
            viewport_top = vadj.get_value()
            viewport_height = vadj.get_page_size()
            viewport_bottom = viewport_top + viewport_height

            if not (y >= viewport_top and (y + widget_height) <= viewport_bottom):
                if y < viewport_top:
                    vadj.set_value(y - 20)
                else:
                    vadj.set_value(y + widget_height - viewport_height + 20)

        self.selected_wallpaper = widget.wallpaper_path
        self.select_btn.set_sensitive(True)

    def on_thumbnail_button_clicked(self, btn):
        if not hasattr(btn, 'thumbnail_loaded') or not btn.thumbnail_loaded:
            self.load_thumbnail(btn, btn.wallpaper_path)
        self.open_preview(btn.wallpaper_path)

    def on_window_key_pressed(self, controller, keyval, keycode, state):
        if keyval == Gdk.KEY_Escape:
            if self.search_entry.has_focus() and self.search_entry.get_text():
                self.search_entry.set_text("")
                if self.search_timeout:
                    GLib.source_remove(self.search_timeout)
                    self.search_timeout = None
                self.flow_box.invalidate_filter()
                self.update_count_label()
                return True
            else:
                self.window.close()
                return True

        if keyval == Gdk.KEY_f and self.selected_wallpaper:
            self.toggle_favorite(self.selected_wallpaper)
            return True

        if not self.search_entry.has_focus():
            unicode_char = Gdk.keyval_to_unicode(keyval)
            if unicode_char and chr(unicode_char).isprintable():
                self.search_entry.grab_focus()
                current_text = self.search_entry.get_text()
                self.search_entry.set_text(current_text + chr(unicode_char))
                self.search_entry.set_position(-1)
                self.on_search_changed(self.search_entry)
                return True

        return False

    def on_key_pressed(self, controller, keyval, keycode, state):
        if not self.thumbnail_widgets:
            return False

        visible_children = self._get_visible_flowbox_children()
        visible_count = len(visible_children)

        if visible_count == 0:
            self.selected_index = -1
            self.select_btn.set_sensitive(False)
            return False

        if self.selected_index == -1 or self.selected_index >= visible_count:
            self._select_item_by_index(0)
            return True

        current_visible_index = self.selected_index
        new_visible_index = current_visible_index

        columns = self.flow_box.get_max_children_per_line()

        if keyval == Gdk.KEY_Right:
            new_visible_index = (current_visible_index + 1) % visible_count
        elif keyval == Gdk.KEY_Left:
            new_visible_index = (current_visible_index - 1 + visible_count) % visible_count
        elif keyval == Gdk.KEY_Down:
            new_visible_index = min(current_visible_index + columns, visible_count - 1)
        elif keyval == Gdk.KEY_Up:
            new_visible_index = max(current_visible_index - columns, 0)
        elif keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):
            self.open_preview(visible_children[current_visible_index].get_child().wallpaper_path)
            return True
        else:
            return False

        if new_visible_index != current_visible_index:
            self._select_item_by_index(new_visible_index)
            return True

        return False

    def _handle_preview_apply(self, wallpaper_path):
        if self.preview_window:
            self.preview_window.destroy()
            self.preview_window = None

        print(wallpaper_path)
        self.window.close()

    def open_preview(self, wallpaper_path):
        if self.preview_window:
            self.preview_window.destroy()

        self.preview_window = Adw.Window(transient_for=self.window, modal=True)
        self.preview_window.set_title("Preview")
        self.preview_window.set_default_size(900, 600)

        def on_key_press(controller, keyval, keycode, state):
            if keyval == Gdk.KEY_Escape:
                if self.preview_window:
                    self.preview_window.destroy()
                    self.preview_window = None
                return True
            elif keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):
                self._handle_preview_apply(wallpaper_path)
                return True
            elif keyval == Gdk.KEY_f:
                self.toggle_favorite(wallpaper_path)
                return True
            return False

        key_controller = Gtk.EventControllerKey.new()
        key_controller.connect("key-pressed", on_key_press)
        self.preview_window.add_controller(key_controller)

        dialog_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.preview_window.set_content(dialog_box)

        # FIX 5: Preview window: replaced GdkPixbuf.Pixbuf.new_from_file_at_size()
        # + Gdk.Texture.new_for_pixbuf() with Gdk.Texture.new_from_filename().
        # For the preview we still want to cap the display size, which
        # Gtk.Picture handles automatically via content-fit; no manual
        # scaling is needed. GdkPixbuf is no longer used here at all.
        try:
            texture = Gdk.Texture.new_from_filename(wallpaper_path)
            picture = Gtk.Picture.new_for_paintable(texture)
            picture.set_content_fit(Gtk.ContentFit.CONTAIN)
            picture.set_hexpand(True)
            picture.set_vexpand(True)
            content = Gtk.ScrolledWindow()
            content.set_child(picture)
            dialog_box.append(content)
        except Exception as e:
            lbl = Gtk.Label(label=f"Could not load preview:\n{e}")
            dialog_box.append(lbl)

        action_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        action_bar.set_halign(Gtk.Align.CENTER)
        action_bar.set_margin_top(6)
        action_bar.set_margin_bottom(6)
        dialog_box.append(action_bar)

        is_fav = wallpaper_path in self.favorites
        fav_btn = Gtk.Button(icon_name="starred-symbolic" if is_fav else "non-starred-symbolic")
        fav_btn.set_tooltip_text("Toggle Favorite (F)")
        fav_btn.connect("clicked", lambda btn: self.toggle_favorite(wallpaper_path))
        action_bar.append(fav_btn)

        apply_btn = Gtk.Button(label="Apply")
        apply_btn.add_css_class("suggested-action")
        action_bar.append(apply_btn)

        close_btn = Gtk.Button(label="Close")
        action_bar.append(close_btn)

        apply_btn.connect("clicked", lambda btn: self._handle_preview_apply(wallpaper_path))
        close_btn.connect("clicked", lambda btn: self.preview_window.destroy())

        self.preview_window.present()

    def on_select(self, button):
        if self.selected_wallpaper:
            print(self.selected_wallpaper)
        else:
            print("No wallpaper selected", file=sys.stderr)
        self.window.close()


if __name__ == "__main__":
    app = WallpaperPicker()
    sys.exit(app.run(sys.argv))
