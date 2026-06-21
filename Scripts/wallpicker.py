#!/usr/bin/env python3

import sys
import os
import json
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

try:
    import humanize
    HAVE_HUMANIZE = True
except ImportError:
    HAVE_HUMANIZE = False


def format_size(num_bytes):
    if HAVE_HUMANIZE:
        return humanize.naturalsize(num_bytes, binary=True)
    size = float(num_bytes)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if size < 1024 or unit == "TiB":
            return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} {unit}"
        size /= 1024


def install_css():
    css = b"""
    .thumbnail {
        border-radius: 4px;
        background-color: transparent;
        border: 1px solid transparent;
        opacity: 0;
        transition: background-color 100ms ease;
    }

    @keyframes fadeIn {
        from { opacity: 0; }
        to { opacity: 1; }
    }

    .thumbnail.loaded {
        animation: fadeIn 150ms ease-in forwards;
    }

    .thumbnail:hover {
        background-color: alpha(@shade_color, 0.08);
    }

    .thumbnail:focus {
        background-color: alpha(@accent_bg_color, 0.1);
        outline: 2px solid @window_bg_color;
        outline-offset: 0px;
        box-shadow: 0 0 0 4px @accent_color;
    }

    .thumbnail-label {
        font-size: 11px;
        font-weight: 500;
    }

    .floating-search {
        background-color: alpha(@window_bg_color, 0.92);
        border: 1px solid alpha(@shade_color, 0.15);
        border-radius: 999px;
        padding: 6px 14px;
        box-shadow: 0 2px 12px alpha(black, 0.16);
    }

    .floating-search entry {
        background: none;
        border: none;
        box-shadow: none;
        min-width: 220px;
    }

    .hover-action {
        opacity: 0;
        transition: opacity 100ms ease;
        background-color: alpha(@window_bg_color, 0.55);
        border-radius: 50%;
        min-width: 28px;
        min-height: 28px;
        padding: 4px;
    }

    .thumbnail:hover .hover-action,
    .thumbnail:focus .hover-action,
    .hover-action:focus {
        opacity: 1;
    }

    .hover-action.is-favorited {
        opacity: 1;
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
            alpha(@shade_color, 0.08) 25%,
            alpha(@shade_color, 0.16) 50%,
            alpha(@shade_color, 0.08) 75%);
        background-size: 200% 100%;
        animation: shimmer 1.5s infinite;
        border-radius: 4px;
    }

    @keyframes shimmer {
        0% { background-position: 200% 0; }
        100% { background-position: -200% 0; }
    }

    .empty-results-label {
        opacity: 0.6;
        font-size: 14px;
    }
    """
    provider = Gtk.CssProvider()
    provider.load_from_data(css)
    display = Gdk.Display.get_default()
    Gtk.StyleContext.add_provider_for_display(display, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)


class SettingsDialog(Adw.PreferencesDialog):
    def __init__(self, parent_app, config, **kwargs):
        super().__init__(**kwargs)
        self.set_title("Wallpaper Picker Settings")
        self.set_search_enabled(False)

        self.config = config
        self.parent_app = parent_app
        self._dimension_reload_timeout = None

        self.connect("closed", self._on_closed)

        page = Adw.PreferencesPage()
        self.add(page)

        library_group = Adw.PreferencesGroup(
            title="Library",
            description="Where to find wallpapers and which files to show"
        )
        page.add(library_group)

        dir_row = Adw.ActionRow(
            title="Wallpaper Directory",
            subtitle=self.config.get('wallpaper_dir', '')
        )
        self.dir_row = dir_row

        dir_button = Gtk.Button(icon_name="folder-open-symbolic", valign=Gtk.Align.CENTER)
        dir_button.add_css_class("flat")
        dir_button.set_tooltip_text("Browse…")
        dir_button.connect("clicked", self.on_browse_dir_clicked)
        dir_row.add_suffix(dir_button)
        dir_row.set_activatable_widget(dir_button)
        library_group.add(dir_row)

        extensions_row = Adw.EntryRow(title="Extensions (comma-separated)")
        extensions_row.set_text(self.config.get('extensions', 'jpg,jpeg,png'))
        extensions_row.set_show_apply_button(True)
        extensions_row.connect("apply", self.on_extensions_applied)
        extensions_row.connect("notify::has-focus", self.on_extensions_focus_changed)
        self.extensions_row = extensions_row
        library_group.add(extensions_row)

        appearance_group = Adw.PreferencesGroup(title="Appearance")
        page.add(appearance_group)

        self.width_row = Adw.SpinRow.new_with_range(50, 500, 10)
        self.width_row.set_title("Thumbnail Width")
        self.width_row.set_value(self.config.get('thumbnail_width', 200))
        self.width_row.connect("notify::value", self.on_dimension_changed)
        appearance_group.add(self.width_row)

        self.height_row = Adw.SpinRow.new_with_range(50, 500, 10)
        self.height_row.set_title("Thumbnail Height")
        self.height_row.set_value(self.config.get('thumbnail_height', 150))
        self.height_row.connect("notify::value", self.on_dimension_changed)
        appearance_group.add(self.height_row)

        self.columns_row = Adw.SpinRow.new_with_range(1, 10, 1)
        self.columns_row.set_title("Columns")
        self.columns_row.set_value(self.config.get('columns', 4))
        self.columns_row.connect("notify::value", self.on_columns_changed)
        appearance_group.add(self.columns_row)

        perf_group = Adw.PreferencesGroup(
            title="Performance",
            description="How many thumbnails to decode at once while scrolling"
        )
        page.add(perf_group)

        self.batch_row = Adw.SpinRow.new_with_range(10, 100, 5)
        self.batch_row.set_title("Load Batch Size")
        self.batch_row.set_subtitle("Thumbnails decoded per batch as you scroll")
        self.batch_row.set_value(self.config.get('lazy_load_batch', 20))
        self.batch_row.connect("notify::value", self.on_batch_changed)
        perf_group.add(self.batch_row)


    def _on_closed(self, dialog):
        if self._dimension_reload_timeout:
            GLib.source_remove(self._dimension_reload_timeout)
            self._dimension_reload_timeout = None

    def _persist(self):
        config_dir = Path(GLib.get_user_config_dir()) / 'wallpicker'
        config_file = config_dir / 'config.json'
        try:
            with open(config_file, 'w') as f:
                json.dump(self.parent_app.config, f, indent=4)
            return True
        except OSError as e:
            print(f"Error writing config file: {e}", file=sys.stderr)
            self.add_toast(Adw.Toast.new("Could not write config file"))
            return False

    def on_browse_dir_clicked(self, button):
        dialog = Gtk.FileDialog.new()
        dialog.set_title("Select Wallpaper Directory")
        dialog.set_modal(True)
        current = self.config.get('wallpaper_dir', '')
        if current and os.path.isdir(current):
            dialog.set_initial_folder(Gio.File.new_for_path(current))

        def on_folder_selected(dlg, result):
            try:
                folder = dlg.select_folder_finish(result)
            except GLib.Error as e:
                print(f"Error selecting folder: {e}", file=sys.stderr)
                return
            if not folder:
                return
            new_dir = folder.get_path()
            self.dir_row.set_subtitle(new_dir)
            self.config['wallpaper_dir'] = new_dir
            if self._persist():
                self.add_toast(Adw.Toast.new("Wallpaper directory updated"))
                self.parent_app.reload_ui_after_settings_change()

        dialog.select_folder(self.parent_app.window, None, on_folder_selected)

    def on_extensions_focus_changed(self, row, pspec):
        if not row.get_has_focus():
            self.on_extensions_applied(row)

    def on_extensions_applied(self, row):
        new_value = row.get_text().strip()
        if not new_value or new_value == self.config.get('extensions', ''):
            return
        self.config['extensions'] = new_value
        if self._persist():
            self.parent_app.reload_ui_after_settings_change()

    def on_dimension_changed(self, row, pspec):
        self.config['thumbnail_width'] = self.width_row.get_value_as_int()
        self.config['thumbnail_height'] = self.height_row.get_value_as_int()
        self._persist()
        if self._dimension_reload_timeout:
            GLib.source_remove(self._dimension_reload_timeout)
        self._dimension_reload_timeout = GLib.timeout_add(400, self._do_dimension_reload)

    def _do_dimension_reload(self):
        self._dimension_reload_timeout = None
        self.parent_app.reload_ui_after_settings_change()
        return False

    def on_columns_changed(self, row, pspec):
        self.config['columns'] = self.columns_row.get_value_as_int()
        if self._persist():
            self.parent_app.apply_column_count()

    def on_batch_changed(self, row, pspec):
        self.config['lazy_load_batch'] = self.batch_row.get_value_as_int()
        self._persist()


class AboutDialog:
    @staticmethod
    def show(parent_window):
        dialog = Adw.AboutDialog()
        dialog.set_application_name("Wallpaper Picker")
        dialog.set_version("2.3.0")
        dialog.set_comments("A modern wallpaper picker for GNOME with lazy loading, favorites, sorting, and smooth animations.")
        dialog.set_license_type(Gtk.License.GPL_3_0_ONLY)
        dialog.present(parent_window)


class WallpaperPicker(Adw.Application):
    def __init__(self, **kwargs):
        super().__init__(application_id="com.github.WallpaperPicker",
                         flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE,
                         **kwargs)
        self.window = None
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
        self.preview_fav_btn = None
        self.preview_wallpaper_path = None
        self.search_text = ""
        self.search_timeout = None
        self.executor = ThreadPoolExecutor(max_workers=os.cpu_count())

        self.favorites = self.load_favorites()
        self.show_favorites_only = False
        self.sort_mode = "name"

        self.loaded_count = 0
        self.is_loading = False
        self.load_lock = threading.Lock()
        self.scroll_timeout = None

        self._visible_cache = []

        self.load_generation = 0

        install_css()
        self.connect('activate', self.on_activate)

    def do_command_line(self, command_line):
        args = command_line.get_arguments()[1:]

        new_dir = None
        if len(args) > 0:
            path = args[0]
            abs_path = os.path.abspath(path)
            if os.path.isdir(abs_path):
                new_dir = abs_path
            else:
                print(f"Warning: Provided path is not a valid directory: {path}", file=sys.stderr)

        if self.window is not None:
            if new_dir and new_dir != self.config.get('wallpaper_dir'):
                self.config['wallpaper_dir'] = new_dir
                self.reload_ui_after_settings_change()
            self.window.present()
        else:
            if new_dir:
                self.config['wallpaper_dir'] = new_dir
            self.activate()

        return 0

    def do_shutdown(self):
        self.executor.shutdown(wait=False, cancel_futures=True)
        Adw.Application.do_shutdown(self)

    def load_favorites(self):
        config_dir = Path(GLib.get_user_config_dir()) / 'wallpicker'
        fav_file = config_dir / 'favorites.json'
        if fav_file.exists():
            try:
                with open(fav_file, 'r') as f:
                    return set(json.load(f))
            except Exception:
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
        self._sync_preview_favorite_icon(wallpaper_path)
        if self.show_favorites_only:
            self.flow_box.invalidate_filter()
            self._refresh_visible_cache()
            self.update_count_label()

    def _sync_preview_favorite_icon(self, wallpaper_path):
        if (self.preview_fav_btn is not None
                and self.preview_wallpaper_path == wallpaper_path):
            is_fav = wallpaper_path in self.favorites
            self.preview_fav_btn.set_icon_name(
                "starred-symbolic" if is_fav else "non-starred-symbolic"
            )

    def refresh_thumbnail(self, wallpaper_path):
        for card in self.thumbnail_widgets:
            if card.wallpaper_path == wallpaper_path:
                is_fav = wallpaper_path in self.favorites
                fav_btn = getattr(card, 'fav_btn', None)
                if fav_btn is not None:
                    fav_btn.set_icon_name("starred-symbolic" if is_fav else "non-starred-symbolic")
                    if is_fav:
                        fav_btn.add_css_class('is-favorited')
                    else:
                        fav_btn.remove_css_class('is-favorited')

                accessible_name = os.path.basename(wallpaper_path)
                if is_fav:
                    accessible_name += ", favorite"
                card.update_property(
                    [Gtk.AccessibleProperty.LABEL],
                    [GLib.Variant.new_string(accessible_name)]
                )
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
        if self.window is not None:
            self.window.present()
            return

        self.window = Adw.ApplicationWindow(application=app)
        self.window.set_title('Wallpaper Picker')
        self.window.set_default_size(1000, 700)
        self.window.set_size_request(360, 480)

        header_bar = Adw.HeaderBar()

        sort_action_group = Gio.SimpleActionGroup()
        self.window.insert_action_group("sort", sort_action_group)

        self.sort_action = Gio.SimpleAction.new_stateful(
            "mode", GLib.VariantType.new("s"), GLib.Variant.new_string(self.sort_mode)
        )
        self.sort_action.connect("activate", self.on_sort_action_activated)
        sort_action_group.add_action(self.sort_action)

        sort_menu = Gio.Menu()
        sort_menu.append("Name", "sort.mode::name")
        sort_menu.append("Date Modified", "sort.mode::date")
        sort_menu.append("File Size", "sort.mode::size")

        sort_button = Gtk.MenuButton(
            icon_name="view-sort-ascending-symbolic",
            menu_model=sort_menu,
            tooltip_text="Sort By"
        )
        sort_button.add_css_class("flat")
        header_bar.pack_start(sort_button)

        self.search_entry = Gtk.SearchEntry()
        self.search_entry.set_placeholder_text("Search wallpapers...")
        self.search_entry.connect("search-changed", self.on_search_changed)

        self.count_label = Gtk.Label()
        self.count_label.add_css_class('count-label')
        self.count_label.add_css_class('dim-label')

        self.fav_toggle = Gtk.ToggleButton(icon_name="starred-symbolic")
        self.fav_toggle.add_css_class("flat")
        self.fav_toggle.set_tooltip_text("Show Favorites Only")
        self.fav_toggle.connect("toggled", self.on_favorites_filter_toggled)
        header_bar.pack_end(self.fav_toggle)

        self.select_btn = Gtk.Button(label="Select")
        self.select_btn.add_css_class('suggested-action')
        self.select_btn.set_sensitive(False)
        self.select_btn.connect("clicked", self.on_select)
        header_bar.pack_end(self.select_btn)

        menu = Gio.Menu()
        menu.append("Keyboard Shortcuts", "app.shortcuts")
        menu.append("Settings", "app.settings")
        menu.append("About", "app.about")

        menu_button = Gtk.MenuButton(icon_name="open-menu-symbolic", menu_model=menu)
        menu_button.add_css_class("flat")
        header_bar.pack_end(menu_button)

        settings_action = Gio.SimpleAction.new("settings", None)
        settings_action.connect("activate", self.on_settings_clicked)
        self.add_action(settings_action)

        about_action = Gio.SimpleAction.new("about", None)
        about_action.connect("activate", self.on_about_clicked)
        self.add_action(about_action)

        shortcuts_action = Gio.SimpleAction.new("shortcuts", None)
        shortcuts_action.connect("activate", self.on_shortcuts_clicked)
        self.add_action(shortcuts_action)
        self.set_accels_for_action("app.shortcuts", ["<Control>question"])

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

        self.content_overlay = Gtk.Overlay()

        self.flow_box = Gtk.FlowBox()
        self.flow_box.set_selection_mode(Gtk.SelectionMode.NONE)
        columns = self.config.get('columns', 4)
        self.flow_box.set_max_children_per_line(columns)
        self.flow_box.set_homogeneous(False)
        self.flow_box.set_margin_start(16)
        self.flow_box.set_margin_end(16)
        self.flow_box.set_margin_top(84)
        self.flow_box.set_margin_bottom(16)
        self.flow_box.set_row_spacing(12)
        self.flow_box.set_column_spacing(12)
        self.flow_box.set_filter_func(self.filter_func)

        self.content_overlay.set_child(self.flow_box)

        self.no_results_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.no_results_box.set_halign(Gtk.Align.CENTER)
        self.no_results_box.set_valign(Gtk.Align.START)
        self.no_results_box.set_margin_top(64)
        self.no_results_box.set_visible(False)
        no_results_icon = Gtk.Image.new_from_icon_name("edit-find-symbolic")
        no_results_icon.set_pixel_size(48)
        no_results_icon.add_css_class('empty-results-label')
        self.no_results_box.append(no_results_icon)
        no_results_label = Gtk.Label(label="No matching wallpapers")
        no_results_label.add_css_class('empty-results-label')
        self.no_results_box.append(no_results_label)
        self.content_overlay.add_overlay(self.no_results_box)

        self.scrolled.set_child(self.content_overlay)

        search_pill = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        search_pill.add_css_class('floating-search')
        search_pill.set_halign(Gtk.Align.CENTER)
        search_pill.set_valign(Gtk.Align.START)
        search_pill.set_margin_top(16)
        search_pill.append(self.search_entry)
        search_pill.append(self.count_label)

        self.page_overlay = Gtk.Overlay()
        self.page_overlay.set_child(self.scrolled)
        self.page_overlay.add_overlay(search_pill)

        self.view_stack.add_named(self.page_overlay, "wallpapers")

        status_page = Adw.StatusPage.new()
        status_page.set_icon_name("folder-pictures-symbolic")
        status_page.set_title("No Wallpapers Found")
        status_page.set_description("Check the configured wallpaper directory or add images to it.")
        status_page.set_vexpand(True)

        settings_button = Gtk.Button.new_with_label("Open Settings")
        settings_button.connect("clicked", lambda _: self.on_settings_clicked(None, None))
        status_page.set_child(settings_button)
        self.view_stack.add_named(status_page, "empty")

        self.toast_overlay = Adw.ToastOverlay()
        self.toast_overlay.set_child(main_box)
        self.window.set_content(self.toast_overlay)

        narrow_breakpoint = Adw.Breakpoint.new(
            Adw.BreakpointCondition.parse("max-width: 700px")
        )
        narrow_breakpoint.add_setter(self.count_label, "visible", False)
        narrow_breakpoint.add_setter(self.flow_box, "margin-start", 6)
        narrow_breakpoint.add_setter(self.flow_box, "margin-end", 6)
        narrow_breakpoint.add_setter(self.select_btn, "icon-name", "object-select-symbolic")
        self.window.add_breakpoint(narrow_breakpoint)

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

    def on_shortcuts_clicked(self, action, state):
        builder = Gtk.Builder()
        builder.set_translation_domain(None)
        ui = """
        <interface>
          <object class="GtkShortcutsWindow" id="shortcuts">
            <property name="modal">1</property>
            <child>
              <object class="GtkShortcutsSection">
                <property name="section-name">main</property>
                <child>
                  <object class="GtkShortcutsGroup">
                    <property name="title">Browsing</property>
                    <child>
                      <object class="GtkShortcutsShortcut">
                        <property name="title">Navigate wallpapers</property>
                        <property name="accelerator">Left Right Up Down</property>
                      </object>
                    </child>
                    <child>
                      <object class="GtkShortcutsShortcut">
                        <property name="title">Open preview</property>
                        <property name="accelerator">Return</property>
                      </object>
                    </child>
                    <child>
                      <object class="GtkShortcutsShortcut">
                        <property name="title">Start typing to search</property>
                        <property name="accelerator">A</property>
                      </object>
                    </child>
                    <child>
                      <object class="GtkShortcutsShortcut">
                        <property name="title">Clear search / close window</property>
                        <property name="accelerator">Escape</property>
                      </object>
                    </child>
                    <child>
                      <object class="GtkShortcutsShortcut">
                        <property name="title">Toggle favorite</property>
                        <property name="accelerator">F</property>
                      </object>
                    </child>
                  </object>
                </child>
                <child>
                  <object class="GtkShortcutsGroup">
                    <property name="title">Preview window</property>
                    <child>
                      <object class="GtkShortcutsShortcut">
                        <property name="title">Apply wallpaper</property>
                        <property name="accelerator">Return</property>
                      </object>
                    </child>
                    <child>
                      <object class="GtkShortcutsShortcut">
                        <property name="title">Close preview</property>
                        <property name="accelerator">Escape</property>
                      </object>
                    </child>
                  </object>
                </child>
              </object>
            </child>
          </object>
        </interface>
        """
        builder.add_from_string(ui)
        shortcuts_window = builder.get_object("shortcuts")
        shortcuts_window.set_transient_for(self.window)
        shortcuts_window.present()

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

        if upper <= page_size or value + page_size >= upper * 0.8:
            self.load_next_batch()

        return False

    def load_next_batch(self):
        with self.load_lock:
            if self.is_loading:
                return
            self.is_loading = True

        generation = self.load_generation
        batch_size = self.config.get('lazy_load_batch', 20)
        start = self.loaded_count
        end = min(start + batch_size, len(self.wallpapers))

        if start >= end:
            self.is_loading = False
            return

        GLib.idle_add(self.update_progress, end, len(self.wallpapers))

        for i in range(start, end):
            wall_info = self.wallpapers[i]
            GLib.idle_add(self.add_and_load_wallpaper, wall_info['path'], generation)

        self.loaded_count = end
        self.is_loading = False
        GLib.idle_add(self._after_batch_added, generation)
        GLib.idle_add(self.check_and_load_more)

    def _after_batch_added(self, generation):
        if generation != self.load_generation:
            return False
        self._refresh_visible_cache()
        self.update_count_label()
        return False

    def add_and_load_wallpaper(self, wallpaper_path, generation):
        if generation != self.load_generation:
            return False
        btn = self.add_wallpaper_skeleton(wallpaper_path, generation)
        if btn is not None:
            self.load_thumbnail(btn, wallpaper_path)
        return False

    def on_sort_action_activated(self, action, parameter):
        mode = parameter.get_string()
        action.set_state(parameter)
        self.set_sort_mode(mode)

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
        self._refresh_visible_cache()
        self.update_count_label()

    def _refresh_visible_cache(self):
        visible = []
        child = self.flow_box.get_first_child()
        while child:
            if self.filter_func(child):
                visible.append(child)
            child = child.get_next_sibling()
        self._visible_cache = visible
        self.no_results_box.set_visible(
            len(visible) == 0 and (self.search_text or self.show_favorites_only)
        )
        return visible

    def _get_visible_flowbox_children(self):
        return self._visible_cache

    def update_count_label(self):
        visible = len(self._visible_cache)
        total = len(self.wallpapers)

        if self.show_favorites_only:
            self.count_label.set_text(f"{visible} favorites")
        elif self.loaded_count < total:
            self.count_label.set_text(f"{visible} of {total} wallpapers (scroll for more)")
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
        self._refresh_visible_cache()
        self.update_count_label()
        self.search_timeout = None
        if self.search_text:
            self._ensure_search_results_loaded()
        return False

    def _ensure_search_results_loaded(self):
        max_extra_batches = 10
        batches = 0
        while (
            self.search_text
            and self.loaded_count < len(self.wallpapers)
            and batches < max_extra_batches
        ):
            visible_matches = sum(
                1 for w in self.wallpapers[:self.loaded_count]
                if self.search_text in os.path.basename(w['path']).lower()
            )
            if visible_matches >= 1 and batches > 0:
                break
            self.load_next_batch()
            batches += 1

        if batches > 0:
            GLib.idle_add(self._finish_search_load)
        else:
            self.flow_box.invalidate_filter()
            self._refresh_visible_cache()
            self.update_count_label()

    def _finish_search_load(self):
        self.flow_box.invalidate_filter()
        self._refresh_visible_cache()
        self.update_count_label()
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
        self.settings_dialog.present(self.window)

    def apply_column_count(self):
        self.flow_box.set_max_children_per_line(self.config.get('columns', 4))

    def on_about_clicked(self, action, state):
        AboutDialog.show(self.window)

    def start_loading(self):
        self.view_stack.set_visible_child_name("wallpapers")
        self.progress_bar.set_visible(True)
        self.progress_bar.set_fraction(0.0)
        self.progress_bar.set_text("Scanning directory...")
        generation = self.load_generation
        thread = threading.Thread(target=self.load_wallpapers_thread, args=(generation,), daemon=True)
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
        return sorted(wallpapers_with_info, key=lambda x: os.path.basename(x['path']).lower())

    def load_wallpapers_thread(self, generation):
        wallpapers = self.find_wallpapers_fast()

        if generation != self.load_generation:
            return

        self.wallpapers = wallpapers
        if not self.wallpapers:
            GLib.idle_add(self.show_empty_state)
            return

        total = len(self.wallpapers)
        for wall_info in self.wallpapers:
            self.file_info[wall_info['path']] = {
                'size': wall_info['size'],
                'mtime': wall_info.get('mtime', 0)
            }

        GLib.idle_add(self.scan_complete, total, generation)

    def scan_complete(self, total, generation):
        if generation != self.load_generation:
            return False
        self.progress_bar.set_text(f"Found {total} wallpapers")
        self._refresh_visible_cache()
        self.update_count_label()
        self.load_next_batch()
        return False

    def show_empty_state(self):
        self.progress_bar.set_visible(False)
        self.view_stack.set_visible_child_name("empty")
        return False

    def update_progress(self, current, total):
        fraction = current / total if total > 0 else 0
        self.progress_bar.set_fraction(fraction)
        self.progress_bar.set_text(f"Loaded {current}/{total} thumbnails")

        if current >= total:
            GLib.timeout_add(500, lambda: self.progress_bar.set_visible(False))

        return False

    def add_wallpaper_skeleton(self, wallpaper, generation):
        if generation != self.load_generation:
            return None

        card = Gtk.Overlay()
        card.add_css_class('thumbnail')
        card.set_focusable(True)
        try:
            card.set_accessible_role(Gtk.AccessibleRole.BUTTON)
        except AttributeError:
            pass

        accessible_name = os.path.basename(wallpaper)
        if wallpaper in self.favorites:
            accessible_name += ", favorite"
        card.update_property(
            [Gtk.AccessibleProperty.LABEL],
            [GLib.Variant.new_string(accessible_name)]
        )

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        box.set_margin_top(4)
        box.set_margin_bottom(4)
        box.set_margin_start(4)
        box.set_margin_end(4)
        card.set_child(box)

        skeleton = Gtk.Box()
        skeleton.add_css_class('skeleton')
        skeleton.set_size_request(
            self.config.get('thumbnail_width', 200),
            self.config.get('thumbnail_height', 150)
        )
        box.append(skeleton)
        card.skeleton = skeleton

        label = Gtk.Label(label=os.path.basename(wallpaper))
        label.add_css_class('thumbnail-label')
        label.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
        label.set_max_width_chars(22)
        box.append(label)

        is_fav = wallpaper in self.favorites
        fav_btn = Gtk.Button(icon_name="starred-symbolic" if is_fav else "non-starred-symbolic")
        fav_btn.add_css_class('flat')
        fav_btn.add_css_class('hover-action')
        if is_fav:
            fav_btn.add_css_class('is-favorited')
        fav_btn.set_tooltip_text("Toggle Favorite")
        fav_btn.set_halign(Gtk.Align.END)
        fav_btn.set_valign(Gtk.Align.START)
        fav_btn.set_margin_top(8)
        fav_btn.set_margin_end(8)
        fav_btn.connect("clicked", lambda b: self.toggle_favorite(wallpaper))
        card.add_overlay(fav_btn)
        card.fav_btn = fav_btn

        show_files_btn = Gtk.Button(icon_name="folder-open-symbolic")
        show_files_btn.add_css_class('flat')
        show_files_btn.add_css_class('hover-action')
        show_files_btn.set_tooltip_text("Show in Files")
        show_files_btn.set_halign(Gtk.Align.START)
        show_files_btn.set_valign(Gtk.Align.START)
        show_files_btn.set_margin_top(8)
        show_files_btn.set_margin_start(8)
        show_files_btn.connect("clicked", lambda b: self._show_in_files(wallpaper))
        card.add_overlay(show_files_btn)

        card.wallpaper_path = wallpaper
        card.generation = generation
        card.set_has_tooltip(True)
        card.connect("query-tooltip", self.on_query_tooltip)

        click_gesture = Gtk.GestureClick.new()
        click_gesture.set_button(1)
        click_gesture.connect("released", self.on_thumbnail_left_click, wallpaper)
        card.add_controller(click_gesture)

        right_click_gesture = Gtk.GestureClick.new()
        right_click_gesture.set_button(3)
        right_click_gesture.connect("pressed", self.on_thumbnail_right_click, wallpaper)
        card.add_controller(right_click_gesture)

        self.flow_box.append(card)
        self.thumbnail_widgets.append(card)
        card.thumbnail_loaded = False

        return card

    def on_thumbnail_right_click(self, gesture, n_press, x, y, wallpaper_path):
        menu = Gio.Menu()

        is_fav = wallpaper_path in self.favorites
        fav_label = "★ Remove from Favorites" if is_fav else "☆ Add to Favorites"
        menu.append(fav_label, "win.toggle-favorite")
        menu.append("Preview", "win.preview-wallpaper")
        menu.append("Show in Files", "win.show-in-files")

        action_group = Gio.SimpleActionGroup()

        toggle_fav = Gio.SimpleAction.new("toggle-favorite", None)
        toggle_fav.connect("activate", lambda a, p: self.toggle_favorite(wallpaper_path))
        action_group.add_action(toggle_fav)

        preview_action = Gio.SimpleAction.new("preview-wallpaper", None)
        preview_action.connect("activate", lambda a, p: self.open_preview(wallpaper_path))
        action_group.add_action(preview_action)

        show_files = Gio.SimpleAction.new("show-in-files", None)
        show_files.connect("activate", lambda a, p: self._show_in_files(wallpaper_path))
        action_group.add_action(show_files)

        widget = gesture.get_widget()
        widget.insert_action_group("win", action_group)

        popover = Gtk.PopoverMenu.new_from_model(menu)
        popover.set_parent(widget)
        popover.set_position(Gtk.PositionType.BOTTOM)
        popover.popup()

    def _show_in_files(self, wallpaper_path):
        launcher = Gtk.FileLauncher.new(Gio.File.new_for_path(wallpaper_path))

        def on_done(source, result):
            try:
                launcher.open_containing_folder_finish(result)
            except GLib.Error as e:
                logging.warning(f"Could not show file in files app: {e}")
                self.toast_overlay.add_toast(Adw.Toast.new("Could not open file manager"))

        launcher.open_containing_folder(self.window, None, on_done)

    def load_thumbnail(self, btn, wallpaper):
        if hasattr(btn, 'thumbnail_loaded') and btn.thumbnail_loaded:
            return

        btn.thumbnail_loaded = True
        generation = getattr(btn, 'generation', self.load_generation)
        self.executor.submit(self._load_thumbnail_thread, btn, wallpaper, generation)

    def _load_thumbnail_thread(self, btn, wallpaper, generation):
        thumb_width = self.config.get('thumbnail_width', 200)
        thumb_height = self.config.get('thumbnail_height', 150)
        h = hashlib.sha1(wallpaper.encode()).hexdigest()
        cache_file = self.cache_dir / f"{h}.png"

        try:
            try:
                with Image.open(wallpaper) as img:
                    orig_width, orig_height = img.size
                    if self.file_info.get(wallpaper):
                        self.file_info[wallpaper]['width'] = orig_width
                        self.file_info[wallpaper]['height'] = orig_height
            except Exception:
                pass

            cache_valid = (
                cache_file.exists()
                and os.path.getmtime(cache_file) >= os.path.getmtime(wallpaper)
            )

            if not cache_valid:
                with Image.open(wallpaper) as pil_image:
                    pil_image.thumbnail((thumb_width, thumb_height))
                    pil_image.save(cache_file, "PNG")

            texture = Gdk.Texture.new_from_filename(str(cache_file))

            GLib.idle_add(self._update_thumbnail_ui, btn, texture, generation)

        except Exception as e:
            error_message = str(e)
            logging.error(f"Error loading {wallpaper}: {error_message}")
            GLib.idle_add(self._update_thumbnail_ui_with_error, btn, error_message, generation)

    def _update_thumbnail_ui(self, card, texture, generation):
        if generation != self.load_generation:
            return False

        thumb_width = self.config.get('thumbnail_width', 200)
        thumb_height = self.config.get('thumbnail_height', 150)

        picture = Gtk.Picture.new_for_paintable(texture)
        picture.set_size_request(thumb_width, thumb_height)
        picture.set_content_fit(Gtk.ContentFit.CONTAIN)

        box = card.get_child()

        if hasattr(card, "skeleton") and card.skeleton is not None:
            try:
                box.remove(card.skeleton)
            except Exception as e:
                logging.warning(f"Could not remove skeleton: {e}")
            del card.skeleton

        box.prepend(picture)

        if card.wallpaper_path in self.file_info and 'width' in self.file_info[card.wallpaper_path]:
            info = self.file_info[card.wallpaper_path]
            stats_text = f"{info['width']}×{info['height']}"
            stats_label = Gtk.Label(label=stats_text)
            stats_label.add_css_class('stat-badge')
            box.append(stats_label)

        card.add_css_class('loaded')
        return False

    def _update_thumbnail_ui_with_error(self, card, error_message, generation):
        if generation != self.load_generation:
            return False

        thumb_width = self.config.get('thumbnail_width', 200)
        thumb_height = self.config.get('thumbnail_height', 150)

        error_icon = Gtk.Image.new_from_icon_name("image-missing")
        error_icon.set_pixel_size(64)
        error_icon.set_size_request(thumb_width, thumb_height)
        error_icon.set_valign(Gtk.Align.CENTER)
        error_icon.set_halign(Gtk.Align.CENTER)

        box = card.get_child()

        if hasattr(card, "skeleton") and card.skeleton is not None:
            try:
                box.remove(card.skeleton)
            except Exception:
                pass
            del card.skeleton

        box.prepend(error_icon)
        card.error_message = error_message
        card.add_css_class('loaded')
        return False

    def reload_ui_after_settings_change(self):
        self.load_generation += 1

        child = self.flow_box.get_first_child()
        while child:
            next_child = child.get_next_sibling()
            self.flow_box.remove(child)
            child = next_child

        self.thumbnail_widgets = []
        self._visible_cache = []
        self.selected_index = -1
        self.selected_wallpaper = None
        self.select_btn.set_sensitive(False)
        self.loaded_count = 0
        self.progress_bar.set_visible(True)
        self.no_results_box.set_visible(False)

        self.flow_box.set_max_children_per_line(self.config.get('columns', 4))
        self.start_loading()

    def show_error_dialog(self, message):
        dialog = Adw.AlertDialog(
            heading="Error",
            body=message
        )
        dialog.add_response("ok", "OK")
        dialog.connect("response", lambda d, r: self.window.close())
        dialog.present(self.window)

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
            size_str = format_size(info['size'])
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

    def on_thumbnail_left_click(self, gesture, n_press, x, y, wallpaper):
        card = gesture.get_widget()
        card.grab_focus()
        if not getattr(card, 'thumbnail_loaded', False):
            self.load_thumbnail(card, wallpaper)
        self.open_preview(wallpaper)

    def on_window_key_pressed(self, controller, keyval, keycode, state):
        if keyval == Gdk.KEY_Escape:
            if self.search_entry.has_focus() and self.search_entry.get_text():
                self.search_entry.set_text("")
                if self.search_timeout:
                    GLib.source_remove(self.search_timeout)
                    self.search_timeout = None
                self.flow_box.invalidate_filter()
                self._refresh_visible_cache()
                self.update_count_label()
                return True
            else:
                self.window.close()
                return True

        if keyval == Gdk.KEY_f and self.selected_wallpaper:
            self.toggle_favorite(self.selected_wallpaper)
            return True

        modifier_mask = (
            Gdk.ModifierType.CONTROL_MASK
            | Gdk.ModifierType.ALT_MASK
            | Gdk.ModifierType.SUPER_MASK
        )
        if (not self.search_entry.has_focus()
                and not (state & modifier_mask)
                and self.search_entry.get_text() == ""):
            event = controller.get_current_event()
            if event is not None and self.search_entry.handle_event(event):
                self.search_entry.grab_focus_without_selecting()
                self.search_entry.set_position(-1)
                return True

        return False

    def _get_actual_column_count(self, visible_children):
        if len(visible_children) < 2:
            return 1

        first_y = visible_children[0].get_allocation().y
        count = 1
        for child in visible_children[1:]:
            if child.get_allocation().y == first_y:
                count += 1
            else:
                break
        return max(count, 1)

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

        columns = self._get_actual_column_count(visible_children)

        at_realized_edge = (
            (keyval in (Gdk.KEY_Right, Gdk.KEY_Down) and current_visible_index == visible_count - 1)
        )
        if at_realized_edge and self.loaded_count < len(self.wallpapers) and not self.is_loading:
            self.load_next_batch()
            return True

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
            self.preview_window.close()

        print(wallpaper_path)
        self.window.close()

    def open_preview(self, wallpaper_path):
        if self.preview_window:
            self.preview_window.destroy()

        self.preview_wallpaper_path = wallpaper_path

        self.preview_window = Adw.Window(transient_for=self.window, modal=True)
        self.preview_window.set_title(os.path.basename(wallpaper_path))
        self.preview_window.set_default_size(900, 600)

        def on_key_press(controller, keyval, keycode, state):
            if keyval == Gdk.KEY_Escape:
                if self.preview_window:
                    self.preview_window.close()
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

        def on_preview_close(window):
            self.preview_window = None
            self.preview_fav_btn = None
            self.preview_wallpaper_path = None
            return False

        self.preview_window.connect("close-request", on_preview_close)

        toolbar_view = Adw.ToolbarView()
        self.preview_window.set_content(toolbar_view)

        preview_header = Adw.HeaderBar()
        preview_header.set_show_title(True)
        toolbar_view.add_top_bar(preview_header)

        try:
            texture = Gdk.Texture.new_from_filename(wallpaper_path)
            picture = Gtk.Picture.new_for_paintable(texture)
            picture.set_content_fit(Gtk.ContentFit.CONTAIN)
            picture.set_hexpand(True)
            picture.set_vexpand(True)
            content = Gtk.ScrolledWindow()
            content.set_child(picture)
            toolbar_view.set_content(content)
        except GLib.Error as e:
            status_page = Adw.StatusPage.new()
            status_page.set_icon_name("image-missing")
            status_page.set_title("Could Not Load Preview")
            status_page.set_description(str(e))
            status_page.set_vexpand(True)
            toolbar_view.set_content(status_page)

        action_bar = Gtk.ActionBar()

        is_fav = wallpaper_path in self.favorites
        fav_btn = Gtk.Button(icon_name="starred-symbolic" if is_fav else "non-starred-symbolic")
        fav_btn.add_css_class("flat")
        fav_btn.set_tooltip_text("Toggle Favorite (F)")
        fav_btn.connect("clicked", lambda btn: self.toggle_favorite(wallpaper_path))
        self.preview_fav_btn = fav_btn
        action_bar.pack_start(fav_btn)

        show_files_btn = Gtk.Button(icon_name="folder-open-symbolic")
        show_files_btn.add_css_class("flat")
        show_files_btn.set_tooltip_text("Show in Files")
        show_files_btn.connect("clicked", lambda btn: self._show_in_files(wallpaper_path))
        action_bar.pack_start(show_files_btn)

        apply_btn = Gtk.Button(label="Apply")
        apply_btn.add_css_class("suggested-action")
        apply_btn.connect("clicked", lambda btn: self._handle_preview_apply(wallpaper_path))
        action_bar.pack_end(apply_btn)

        toolbar_view.add_bottom_bar(action_bar)

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
