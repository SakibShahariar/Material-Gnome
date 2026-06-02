#!/usr/bin/env python3

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, GLib, Gio, Gdk, Adw, GObject
import cairo

import os
import subprocess
import random
import json
from pathlib import Path

# Custom GObject to hold theme data
class Theme(GObject.Object):
    __gtype_name__ = 'Theme'
    
    name = GObject.Property(type=str)
    primary_color = GObject.Property(type=str)
    surface_color = GObject.Property(type=str)

    def __init__(self, name, primary_color, surface_color):
        super().__init__()
        self.name = name
        self.primary_color = primary_color
        self.surface_color = surface_color

class ThemeSwitcher(Adw.Application):
    def __init__(self):
        super().__init__(application_id="com.example.ThemeSwitcher",
                         flags=Gio.ApplicationFlags.FLAGS_NONE)
        self.preview_popover = None
        self.current_hovered_box = None
        self.popover_timeout_id = None
        self.close_timeout_id = None
        self.is_showing_popover = False
        self.last_hover_time = 0
        
        # Store all themes for filtering
        self.all_themes = Gio.ListStore(item_type=Theme)
        self.filtered_themes = Gio.ListStore(item_type=Theme)
        
        # Buffer for type-to-search
        self.search_buffer = ""
        self.search_timeout_id = None

    def do_startup(self):
        Gtk.Application.do_startup(self)
        Adw.init()

        # Add CSS provider for styling
        css_provider = Gtk.CssProvider()
        css_provider.load_from_data("""
        .color-swatch {
            border-radius: 5px;
            border: 1px solid rgba(0,0,0,0.2);
        }
        .theme-preview {
            border-radius: 8px;
            border: 1px solid @borders;
            margin: 5px;
        }
        .theme-name-preview {
            font-weight: bold;
            font-size: 14px;
        }
        .color-label {
            font-size: 12px;
            opacity: 0.8;
        }
        .hover-row {
            background-color: alpha(@accent_bg_color, 0.2);
        }
        .no-results {
            opacity: 0.7;
            font-style: italic;
        }
        .bottom-search {
            margin-top: 5px;
            margin-bottom: 5px;
        }
        .search-indicator {
            font-size: 12px;
            opacity: 0.7;
            font-style: italic;
        }
        """)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def do_activate(self):
        # Create a new window
        self.window = Adw.ApplicationWindow(application=self, title="Theme Switcher")
        self.window.set_default_size(300, 400)

        # Create a toast overlay for notifications
        self.toast_overlay = Adw.ToastOverlay()
        self.window.set_content(self.toast_overlay)

        # Create the main content box
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.toast_overlay.set_child(main_box)

        header = Adw.HeaderBar()
        header.set_show_end_title_buttons(False)
        
        # Config button
        config_button = Gtk.Button.new_from_icon_name("preferences-system-symbolic")
        config_button.connect("clicked", self.on_config_clicked)
        config_button.set_tooltip_text("Edit configuration")
        header.pack_start(config_button)

        # Random button
        random_button = Gtk.Button.new_from_icon_name("media-playlist-shuffle-symbolic")
        random_button.connect("clicked", self.on_random_clicked)
        random_button.set_tooltip_text("Apply random theme")
        header.pack_end(random_button)

        # Add key controller to close on escape
        controller = Gtk.EventControllerKey()
        controller.connect("key-pressed", self.on_key_pressed)
        self.window.add_controller(controller)

        # --- Gtk.ListView Implementation ---

        # 1. Create a model (use filtered_themes as the main model)
        self.theme_store = self.filtered_themes  # This will show filtered results
        self.load_themes_to_model()

        # 2. Create a factory
        factory = Gtk.SignalListItemFactory()
        factory.connect("setup", self.on_factory_setup)
        factory.connect("bind", self.on_factory_bind)

        # 3. Create a selection model
        self.selection_model = Gtk.SingleSelection(model=self.theme_store)
        # Set the first item as selected if available
        if self.theme_store.get_n_items() > 0:
            self.selection_model.set_selected(0)

        # 4. Create the list view
        self.list_view = Gtk.ListView(model=self.selection_model, factory=factory)
        self.list_view.set_can_focus(True) # Make focusable for keyboard navigation
        self.list_view.connect("activate", self.on_list_activate) # Handle activation
        self.list_view.add_css_class("theme-list")

        self.window.set_default_widget(self.list_view)

        # 5. Put it in a ScrolledWindow
        scrolled_window = Gtk.ScrolledWindow()
        scrolled_window.set_child(self.list_view)
        scrolled_window.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled_window.set_vexpand(True)

        # Create the content layout
        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        content_box.set_margin_top(10)
        content_box.set_margin_bottom(5)
        content_box.set_margin_start(10)
        content_box.set_margin_end(10)
        
        # Theme label
        theme_label = Gtk.Label(label="Select a Theme:")
        theme_label.add_css_class("title-1")
        content_box.append(theme_label)
        
        # Add a label to show search status
        self.status_label = Gtk.Label(label="")
        self.status_label.add_css_class("no-results")
        self.status_label.set_visible(False)
        content_box.append(self.status_label)
        
        content_box.append(scrolled_window)

        # Create a box for the search entry at the bottom
        search_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        search_box.set_margin_top(5)
        search_box.set_margin_bottom(10)
        search_box.set_margin_start(10)
        search_box.set_margin_end(10)
        search_box.add_css_class("bottom-search")
        
        # Type-to-search indicator
        self.search_indicator = Gtk.Label(label="Type to search")
        self.search_indicator.add_css_class("search-indicator")
        self.search_indicator.set_visible(False)
        search_box.append(self.search_indicator)
        
        # Search entry
        self.search_entry = Gtk.SearchEntry()
        self.search_entry.set_placeholder_text("Search themes...")
        self.search_entry.connect("search-changed", self.on_search_changed)
        self.search_entry.connect("stop-search", self.on_search_stopped)
        self.search_entry.set_hexpand(True)
        self.search_entry.set_valign(Gtk.Align.CENTER)
        self.search_entry.set_visible(False)  # Hidden by default
        search_box.append(self.search_entry)

        # Clear search button
        self.clear_search_button = Gtk.Button.new_from_icon_name("edit-clear-symbolic")
        self.clear_search_button.connect("clicked", self.on_clear_search)
        self.clear_search_button.set_tooltip_text("Clear search")
        self.clear_search_button.set_visible(False)
        self.clear_search_button.set_valign(Gtk.Align.CENTER)
        search_box.append(self.clear_search_button)

        main_box.append(header)
        main_box.append(content_box)
        main_box.append(search_box)

        self.window.present()
        self.list_view.grab_focus()  # Focus the list view, not the search

    def on_config_clicked(self, button):
        script_path = Path.home() / "wallpaper-config-editor" / "target" / "debug" / "wallpaper-config-editor"
        if script_path.exists():
            subprocess.Popen([str(script_path)])
            self.show_notification("Config Editor", "Configuration editor launched")
        else:
            self.show_error_dialog(f"Wallpaper config editor not found at {script_path}")

    def on_random_clicked(self, button):
        n_themes = self.theme_store.get_n_items()
        if n_themes > 0:
            random_index = random.randint(0, n_themes - 1)
            theme_object = self.theme_store.get_item(random_index)
            self.apply_theme(theme_object.name)
        else:
            self.show_error_dialog("No themes available to select")

    def on_key_pressed(self, controller, keyval, keycode, state):
        if keyval == Gdk.KEY_Escape:
            # If showing search indicator or search entry, clear search
            if self.search_buffer or (self.search_entry and self.search_entry.get_text()):
                self.clear_search()
            else:
                self.window.close()
        elif keyval == Gdk.KEY_r and state & Gdk.ModifierType.CONTROL_MASK:
            self.on_random_clicked(None)
        elif keyval == Gdk.KEY_f and state & Gdk.ModifierType.CONTROL_MASK:
            # Ctrl+F to toggle search entry visibility
            self.toggle_search_entry()
            return True
        elif keyval == Gdk.KEY_BackSpace:
            # Handle backspace for type-to-search
            if not self.search_entry.get_visible() and self.search_buffer:
                self.search_buffer = self.search_buffer[:-1]
                self.update_type_to_search()
                return True
        elif (keyval >= Gdk.KEY_a and keyval <= Gdk.KEY_z) or \
             (keyval >= Gdk.KEY_A and keyval <= Gdk.KEY_Z) or \
             (keyval >= Gdk.KEY_0 and keyval <= Gdk.KEY_9) or \
             keyval in [Gdk.KEY_minus, Gdk.KEY_underscore, Gdk.KEY_period]:
            # Type-to-search: capture alphanumeric keys
            if not self.search_entry.get_visible():
                char = Gdk.keyval_name(keyval)
                if char:
                    # Convert to lowercase for letters
                    if len(char) == 1 and char.isalpha():
                        if state & Gdk.ModifierType.SHIFT_MASK:
                            self.search_buffer += char.upper()
                        else:
                            self.search_buffer += char.lower()
                    else:
                        self.search_buffer += char.lower() if char.isalpha() else char
                    self.update_type_to_search()
                    return True
        return False

    def toggle_search_entry(self):
        """Toggle search entry visibility"""
        if self.search_entry.get_visible():
            # Hide search entry
            self.search_entry.set_visible(False)
            self.search_indicator.set_visible(False)
            self.clear_search_button.set_visible(False)
            self.list_view.grab_focus()
        else:
            # Show search entry
            self.search_entry.set_visible(True)
            self.search_indicator.set_visible(False)
            self.search_entry.grab_focus()
            # If there's type-to-search buffer, copy it to the search entry
            if self.search_buffer:
                self.search_entry.set_text(self.search_buffer)
                self.clear_search_button.set_visible(True)

    def update_type_to_search(self):
        """Update type-to-search filtering and indicator"""
        if self.search_buffer:
            # Show search indicator
            self.search_indicator.set_label(f"Searching: {self.search_buffer}")
            self.search_indicator.set_visible(True)
            
            # Filter themes based on search buffer
            search_text = self.search_buffer.lower()
            filtered_items = []
            for i in range(self.all_themes.get_n_items()):
                theme = self.all_themes.get_item(i)
                if search_text in theme.name.lower():
                    filtered_items.append(theme)
            
            # Update filtered list
            self.filtered_themes.splice(0, self.filtered_themes.get_n_items(), filtered_items)
            
            # Update selection model
            self.selection_model.set_model(self.filtered_themes)
            
            # Select first item if available
            if self.filtered_themes.get_n_items() > 0:
                self.selection_model.set_selected(0)
            
            # Update status label
            self.update_status_label(search_text)
            
            # Clear search buffer after a delay
            if self.search_timeout_id:
                GLib.source_remove(self.search_timeout_id)
            self.search_timeout_id = GLib.timeout_add(2000, self.clear_search_buffer)
        else:
            # Clear search
            self.clear_search()

    def clear_search_buffer(self):
        """Clear the type-to-search buffer after timeout"""
        self.search_buffer = ""
        self.search_indicator.set_visible(False)
        self.search_timeout_id = None
        return False

    def clear_search(self):
        """Clear all search-related state"""
        self.search_buffer = ""
        self.search_indicator.set_visible(False)
        
        if self.search_entry.get_visible():
            self.search_entry.set_text("")
            self.clear_search_button.set_visible(False)
        
        # Show all themes
        all_items = []
        for i in range(self.all_themes.get_n_items()):
            all_items.append(self.all_themes.get_item(i))
        
        self.filtered_themes.splice(0, self.filtered_themes.get_n_items(), all_items)
        self.selection_model.set_model(self.filtered_themes)
        
        # Select first item if available
        if self.filtered_themes.get_n_items() > 0:
            self.selection_model.set_selected(0)
        
        # Update status label
        self.update_status_label("")
        
        # Cancel any pending timeout
        if self.search_timeout_id:
            GLib.source_remove(self.search_timeout_id)
            self.search_timeout_id = None

    def load_themes_to_model(self):
        try:
            theme_dir = Path.home() / ".config" / "matugen" / "themes"
            if not theme_dir.exists():
                self.show_error_dialog(f"Theme directory not found: {theme_dir}")
                return
            
            themes = []
            for theme_file in sorted(theme_dir.glob("*.json")):
                with open(theme_file, 'r') as f:
                    data = json.load(f)
                    primary_color = data.get("colors", {}).get("primary", {}).get("default", {}).get("color", "#FFFFFF")
                    surface_color = data.get("colors", {}).get("surface", {}).get("default", {}).get("color", "#000000")
                    themes.append(Theme(theme_file.stem, primary_color, surface_color))
            
            # Store in all_themes
            self.all_themes.splice(0, self.all_themes.get_n_items(), themes)
            
            # Initially show all themes in filtered list
            self.filtered_themes.splice(0, self.filtered_themes.get_n_items(), themes)
            
            # Show notification about loaded themes
            if themes:
                self.show_notification(f"Themes Loaded", f"Successfully loaded {len(themes)} themes")
                # Update status label
                self.update_status_label()

        except Exception as e:
            self.show_error_dialog(f"An error occurred while loading themes: {e}")

    def on_search_changed(self, entry):
        # Only process if search entry is visible
        if not entry.get_visible():
            return
            
        search_text = entry.get_text().strip().lower()
        
        # Show/hide clear button
        self.clear_search_button.set_visible(bool(search_text))
        
        # Filter themes
        filtered_items = []
        for i in range(self.all_themes.get_n_items()):
            theme = self.all_themes.get_item(i)
            if search_text in theme.name.lower():
                filtered_items.append(theme)
        
        # Update filtered list
        self.filtered_themes.splice(0, self.filtered_themes.get_n_items(), filtered_items)
        
        # Update selection model
        self.selection_model.set_model(self.filtered_themes)
        
        # Select first item if available
        if self.filtered_themes.get_n_items() > 0:
            self.selection_model.set_selected(0)
        
        # Update status label
        self.update_status_label(search_text)
        
        # Close any open popover
        self.cleanup_popover()

    def on_search_stopped(self, entry):
        # Clear search when stop button is clicked
        self.clear_search()

    def on_clear_search(self, button):
        self.clear_search()
        if self.search_entry.get_visible():
            self.search_entry.grab_focus()

    def update_status_label(self, search_text=""):
        # Make sure status_label exists
        if not hasattr(self, 'status_label') or self.status_label is None:
            return
            
        total_count = self.all_themes.get_n_items()
        filtered_count = self.filtered_themes.get_n_items()
        
        if search_text:
            if filtered_count == 0:
                self.status_label.set_label(f"No themes found matching '{search_text}'")
                self.status_label.set_visible(True)
            else:
                self.status_label.set_label(f"Found {filtered_count} of {total_count} themes")
                self.status_label.set_visible(True)
        else:
            if total_count > 0:
                self.status_label.set_label(f"Showing all {total_count} themes")
                self.status_label.set_visible(True)
            else:
                self.status_label.set_label("No themes available")
                self.status_label.set_visible(True)

    def draw_color_swatch(self, area, cr, width, height, color_str):
        rgba = Gdk.RGBA()
        rgba.parse(color_str)
        
        cr.set_source_rgba(rgba.red, rgba.green, rgba.blue, rgba.alpha)
        cr.paint()

    def draw_preview(self, area, cr, width, height, theme_data):
        # Draw a larger preview with both colors
        if not theme_data:
            return
            
        # Parse colors
        primary_rgba = Gdk.RGBA()
        surface_rgba = Gdk.RGBA()
        primary_rgba.parse(theme_data.primary_color)
        surface_rgba.parse(theme_data.surface_color)
        
        # Draw surface color (top 60% of the area)
        cr.set_source_rgba(surface_rgba.red, surface_rgba.green, surface_rgba.blue, surface_rgba.alpha)
        cr.rectangle(0, 0, width, height * 0.6)
        cr.fill()
        
        # Draw primary color (bottom 40% of the area)
        cr.set_source_rgba(primary_rgba.red, primary_rgba.green, primary_rgba.blue, primary_rgba.alpha)
        cr.rectangle(0, height * 0.6, width, height * 0.4)
        cr.fill()
        
        # Add a subtle border
        cr.set_source_rgb(0, 0, 0)
        cr.set_line_width(0.5)
        cr.rectangle(0, 0, width, height)
        cr.stroke()

    def on_factory_setup(self, factory, list_item):
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        box.set_margin_top(5)
        box.set_margin_bottom(5)
        box.set_margin_start(5)
        box.set_margin_end(5)
        
        primary_color_area = Gtk.DrawingArea()
        primary_color_area.set_content_width(20)
        primary_color_area.set_content_height(20)
        primary_color_area.add_css_class("color-swatch")
        
        surface_color_area = Gtk.DrawingArea()
        surface_color_area.set_content_width(20)
        surface_color_area.set_content_height(20)
        surface_color_area.add_css_class("color-swatch")

        label = Gtk.Label(xalign=0)
        label.set_hexpand(True)
        
        box.append(label)
        box.append(surface_color_area)
        box.append(primary_color_area)
        
        # Add motion controllers for hover preview
        motion_controller = Gtk.EventControllerMotion()
        motion_controller.connect("enter", self.on_row_enter)
        motion_controller.connect("leave", self.on_row_leave)
        box.add_controller(motion_controller)
        
        list_item.set_child(box)

    def on_factory_bind(self, factory, list_item):
        box = list_item.get_child()
        theme_object = list_item.get_item()
        
        label = box.get_first_child()
        surface_color_area = label.get_next_sibling()
        primary_color_area = surface_color_area.get_next_sibling()
        
        label.set_label(theme_object.name)
        
        primary_color_area.set_draw_func(self.draw_color_swatch, theme_object.primary_color)
        surface_color_area.set_draw_func(self.draw_color_swatch, theme_object.surface_color)
        
        # Store theme data on the box for hover preview
        box.theme_data = theme_object

    def on_row_enter(self, controller, x, y):
        current_time = GLib.get_monotonic_time()
        
        # Prevent rapid hover events (within 50ms)
        if current_time - self.last_hover_time < 50000:  # 50ms in microseconds
            return
            
        self.last_hover_time = current_time
        
        box = controller.get_widget()
        theme_data = getattr(box, 'theme_data', None)
        
        if not theme_data or box == self.current_hovered_box:
            return
            
        # Cancel any pending close timeout
        if self.close_timeout_id:
            GLib.source_remove(self.close_timeout_id)
            self.close_timeout_id = None
        
        # Remove hover effect from previous row
        if self.current_hovered_box:
            self.current_hovered_box.remove_css_class("hover-row")
        
        # Add hover effect to current row
        box.add_css_class("hover-row")
        self.current_hovered_box = box
        
        # Cancel any pending show timeout
        if self.popover_timeout_id:
            GLib.source_remove(self.popover_timeout_id)
            self.popover_timeout_id = None
        
        # Show popover with a delay to prevent rapid creation
        self.popover_timeout_id = GLib.timeout_add(100, self.show_popover_delayed, theme_data, box)

    def show_popover_delayed(self, theme_data, box):
        """Show popover with a delay to prevent rapid creation"""
        # Check if still on the same box
        if self.current_hovered_box != box:
            self.popover_timeout_id = None
            return False
            
        # Clean up existing popover first
        self.cleanup_popover()
        
        # Create and show new popover
        self.show_preview_popover(theme_data, box)
        self.popover_timeout_id = None
        return False

    def on_row_leave(self, controller, *args):
        box = controller.get_widget()
        
        # Only remove hover effect if this is the currently hovered box
        if box == self.current_hovered_box:
            box.remove_css_class("hover-row")
            self.current_hovered_box = None
            
            # Cancel any pending show timeout
            if self.popover_timeout_id:
                GLib.source_remove(self.popover_timeout_id)
                self.popover_timeout_id = None
            
            # Schedule popover to close after a delay
            if self.preview_popover and self.is_showing_popover:
                # Cancel any existing close timeout
                if self.close_timeout_id:
                    GLib.source_remove(self.close_timeout_id)
                    self.close_timeout_id = None
                
                # Set a timeout to close the popover
                self.close_timeout_id = GLib.timeout_add(300, self.close_popover_delayed)

    def close_popover_delayed(self):
        """Close popover with a small delay"""
        self.cleanup_popover()
        self.close_timeout_id = None
        return False

    def cleanup_popover(self):
        """Properly clean up the popover resources"""
        if self.preview_popover:
            # Disconnect signals to prevent memory leaks
            try:
                self.preview_popover.disconnect_by_func(self.on_popover_closed)
            except:
                pass
            
            # Remove popover from parent
            try:
                parent = self.preview_popover.get_parent()
                if parent:
                    # Try to remove motion controllers
                    controllers = parent.get_controllers()
                    for ctrl in controllers:
                        if isinstance(ctrl, Gtk.EventControllerMotion):
                            parent.remove_controller(ctrl)
            except:
                pass
            
            # Close the popover
            try:
                if self.preview_popover.get_visible():
                    self.preview_popover.popdown()
            except:
                pass
            
            # Set to None to allow garbage collection
            self.preview_popover = None
            self.is_showing_popover = False

    def show_preview_popover(self, theme_data, parent_widget):
        """Show a popover preview of the theme colors"""
        # Create new popover
        self.preview_popover = Gtk.Popover()
        self.preview_popover.set_parent(parent_widget)
        self.preview_popover.set_position(Gtk.PositionType.RIGHT)
        self.preview_popover.set_autohide(True)
        self.preview_popover.set_has_arrow(True)
        
        # Create preview content
        preview_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        preview_box.set_margin_top(12)
        preview_box.set_margin_bottom(12)
        preview_box.set_margin_start(12)
        preview_box.set_margin_end(12)
        
        # Theme name
        name_label = Gtk.Label(label=theme_data.name)
        name_label.add_css_class("theme-name-preview")
        name_label.set_xalign(0)
        preview_box.append(name_label)
        
        # Large color preview
        preview_area = Gtk.DrawingArea()
        preview_area.set_content_width(180)
        preview_area.set_content_height(100)
        preview_area.add_css_class("theme-preview")
        preview_area.set_draw_func(self.draw_preview, theme_data)
        preview_box.append(preview_area)
        
        # Color details
        details_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        
        # Primary color preview
        primary_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        primary_label = Gtk.Label(label="Primary")
        primary_label.add_css_class("color-label")
        primary_label.set_xalign(0)
        primary_swatch = Gtk.DrawingArea()
        primary_swatch.set_content_width(40)
        primary_swatch.set_content_height(20)
        primary_swatch.add_css_class("color-swatch")
        primary_swatch.set_draw_func(self.draw_color_swatch, theme_data.primary_color)
        primary_box.append(primary_label)
        primary_box.append(primary_swatch)
        
        # Surface color preview
        surface_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        surface_label = Gtk.Label(label="Surface")
        surface_label.add_css_class("color-label")
        surface_label.set_xalign(0)
        surface_swatch = Gtk.DrawingArea()
        surface_swatch.set_content_width(40)
        surface_swatch.set_content_height(20)
        surface_swatch.add_css_class("color-swatch")
        surface_swatch.set_draw_func(self.draw_color_swatch, theme_data.surface_color)
        surface_box.append(surface_label)
        surface_box.append(surface_swatch)
        
        details_box.append(primary_box)
        details_box.append(surface_box)
        preview_box.append(details_box)
        
        # Apply button
        apply_button = Gtk.Button(label="Apply Theme")
        apply_button.add_css_class("suggested-action")
        apply_button.connect("clicked", lambda btn: self.on_preview_apply(theme_data))
        preview_box.append(apply_button)
        
        self.preview_popover.set_child(preview_box)
        self.preview_popover.popup()
        self.is_showing_popover = True
        
        # Connect to popover closed signal
        self.preview_popover.connect("closed", self.on_popover_closed)

    def on_popover_closed(self, popover):
        """Handle popover being closed"""
        if self.current_hovered_box:
            self.current_hovered_box.remove_css_class("hover-row")
            self.current_hovered_box = None
        self.preview_popover = None
        self.is_showing_popover = False

    def on_preview_apply(self, theme_data):
        """Apply theme from preview popover"""
        self.cleanup_popover()
        self.apply_theme(theme_data.name)

    def on_list_activate(self, list_view, position):
        model = list_view.get_model()
        theme_object = model.get_item(position)
        if not theme_object:
            return
        self.apply_theme(theme_object.name)

    def apply_theme(self, theme_name):
        print(f"Selected theme: {theme_name}")

        # Execute the apply-theme.fish script
        script_path = Path.home() / "Scripts" / "apply-theme.fish"
        if not script_path.exists():
            self.show_error_dialog(f"Error: apply-theme.fish not found at {script_path}")
            return

        try:
            subprocess.run(["fish", "-c", f"{script_path} {theme_name}"], check=True)
            print(f"Successfully applied theme: {theme_name}")
            self.show_notification("Success", f"Theme '{theme_name}' applied!")
            self.window.close()
        except subprocess.CalledProcessError as e:
            self.show_error_dialog(f"Error applying theme {theme_name}: {e}")
        except FileNotFoundError:
            self.show_error_dialog(f"Error: 'fish' command not found. Is fish shell installed?")

    def show_error_dialog(self, message):
        dialog = Gtk.MessageDialog(
            transient_for=self.window,
            modal=True,
            message_type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.OK,
            text="Error",
            secondary_text=str(message)
        )
        dialog.connect("response", lambda d, r: d.destroy())
        dialog.present()

    def show_notification(self, title, message):
        """Show a simple notification toast"""
        toast = Adw.Toast.new(message)
        toast.set_title(title)
        toast.set_timeout(2)  # 2 seconds
        
        # Add toast to the toast overlay
        self.toast_overlay.add_toast(toast)
        
        # Also print to console for debugging
        print(f"[NOTIFICATION] {title}: {message}")

def main():
    app = ThemeSwitcher()
    app.run(None)

if __name__ == "__main__":
    main()
