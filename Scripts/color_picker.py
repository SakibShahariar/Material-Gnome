#!/usr/bin/env python3
"""
Dual Color Picker v4.0 - Modern Libadwaita Edition
"""

import gi
import cairo
import math
import sys

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")

try:
    gi.require_version("Adw", "1")
    from gi.repository import Gtk, Gdk, GLib, Adw
    HAS_ADWAITA = True
    print("Using Libadwaita")
except (ValueError, ImportError):
    from gi.repository import Gtk, Gdk, GLib
    HAS_ADWAITA = False
    print("Using pure GTK4")

class DualColorPicker:
    def __init__(self):
        self.text_color = Gdk.RGBA()
        self.text_color.parse("rgb(0,0,0)")
        self.bg_color = Gdk.RGBA()
        self.bg_color.parse("rgb(255,255,255)")
        self.updating = False
        self.debounce_timeout = None
        
        if HAS_ADWAITA:
            self.app = Adw.Application(application_id='com.example.DualColorPicker.v4')
        else:
            self.app = Gtk.Application(application_id='com.example.DualColorPicker.v4')
        
        self.app.connect('activate', self.on_activate)
        print("Application created")

    def on_activate(self, app):
        print("Building window...")
        
        if hasattr(self, 'win') and self.win:
            self.win.present()
            return
        
        if HAS_ADWAITA:
            self.win = Adw.ApplicationWindow(application=app)
        else:
            self.win = Gtk.ApplicationWindow(application=app)
            
        self.win.set_default_size(900, 600)
        self.win.set_title("Dual Color Picker v4.0")

        if HAS_ADWAITA:
            toolbar_view = Adw.ToolbarView()
            self.win.set_content(toolbar_view)
            
            header = Adw.HeaderBar()
            header.set_title_widget(Adw.WindowTitle(title="Dual Color Picker", subtitle="v4.0"))
            toolbar_view.add_top_bar(header)

            self.toast_overlay = Adw.ToastOverlay()
            toolbar_view.set_content(self.toast_overlay)
        else:
            main_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
            self.win.set_child(main_vbox)
            header = Gtk.HeaderBar()
            header.set_title_widget(Gtk.Label(label="Dual Color Picker v4.0"))
            main_vbox.append(header)
            self.toast_overlay = Gtk.Box()
            main_vbox.append(self.toast_overlay)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        
        if HAS_ADWAITA:
            self.toast_overlay.set_child(scrolled)
        else:
            self.toast_overlay.append(scrolled)

        if HAS_ADWAITA:
            clamp = Adw.Clamp()
            clamp.set_maximum_size(1200)
            clamp.set_margin_top(24)
            clamp.set_margin_bottom(24)
            clamp.set_margin_start(12)
            clamp.set_margin_end(12)
            scrolled.set_child(clamp)
            main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=24)
            clamp.set_child(main_box)
        else:
            main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=24)
            main_box.set_margin_top(24)
            main_box.set_margin_bottom(24)
            main_box.set_margin_start(24)
            main_box.set_margin_end(24)
            scrolled.set_child(main_box)

        panels_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        panels_box.set_homogeneous(True)
        main_box.append(panels_box)

        self.text_panel = self.create_color_panel("Text Color", self.text_color, "text")
        panels_box.append(self.text_panel)

        swap_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        swap_box.set_valign(Gtk.Align.CENTER)
        swap_button = Gtk.Button()
        swap_button.set_icon_name("object-flip-horizontal-symbolic")
        swap_button.set_tooltip_text("Swap Colors")
        swap_button.add_css_class("circular")
        swap_button.connect("clicked", self.on_swap_colors)
        swap_box.append(swap_button)
        panels_box.append(swap_box)

        self.bg_panel = self.create_color_panel("Background Color", self.bg_color, "bg")
        panels_box.append(self.bg_panel)

        self.create_preview_section(main_box)
        self.create_contrast_section(main_box)
        self.update_all_displays()
        
        controller = Gtk.EventControllerKey()
        controller.connect("key-pressed", self.on_key_pressed)
        self.win.add_controller(controller)

        print("Presenting window...")
        self.win.present()
        print("Window shown!")

    def on_key_pressed(self, controller, keyval, keycode, state):
        if keyval == Gdk.KEY_Escape:
            self.win.close()
            return True
        return False

    def create_color_panel(self, title, color, prefix):
        if HAS_ADWAITA:
            group = Adw.PreferencesGroup()
            group.set_title(title)
            group.set_margin_start(12)
            group.set_margin_end(12)
        else:
            group = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
            title_label = Gtk.Label(label=title)
            title_label.add_css_class("title-2")
            title_label.set_halign(Gtk.Align.START)
            group.append(title_label)

        preview_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        preview_box.set_margin_top(12)
        preview_box.set_margin_bottom(12)
        preview_box.set_margin_start(12)
        preview_box.set_margin_end(12)

        dialog = Gtk.ColorDialog(title=f"Select {title}")
        color_button = Gtk.ColorDialogButton(dialog=dialog)
        color_button.set_rgba(color)
        color_button.set_valign(Gtk.Align.CENTER)
        color_button.connect("notify::rgba", self.on_color_button_changed, prefix)
        preview_box.append(color_button)

        if HAS_ADWAITA:
            group.add(preview_box)
        else:
            group.append(preview_box)

        setattr(self, f"{prefix}_color_button", color_button)

        formats = [
            ("HEX", "hex"),
            ("HEX+A", "hex_alpha"),
            ("RGB", "rgb"),
            ("RGBA", "rgba")
        ]

        for label, prop in formats:
            if HAS_ADWAITA:
                row = Adw.EntryRow()
                row.set_title(label)
                row.set_show_apply_button(False)
                entry = row
                entry.connect("changed", self.on_entry_changed, prefix, prop)
                
                copy_btn = Gtk.Button()
                copy_btn.set_icon_name("edit-copy-symbolic")
                copy_btn.set_valign(Gtk.Align.CENTER)
                copy_btn.set_tooltip_text(f"Copy {label}")
                copy_btn.add_css_class("flat")
                copy_btn.connect("clicked", self.on_copy_clicked, entry)
                row.add_suffix(copy_btn)
                group.add(row)
            else:
                row_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
                row_label = Gtk.Label(label=label)
                row_label.set_width_chars(8)
                row_label.set_xalign(0)
                row_box.append(row_label)
                
                entry = Gtk.Entry()
                entry.set_hexpand(True)
                entry.connect("changed", self.on_entry_changed, prefix, prop)
                row_box.append(entry)
                
                copy_btn = Gtk.Button()
                copy_btn.set_icon_name("edit-copy-symbolic")
                copy_btn.set_tooltip_text(f"Copy {label}")
                copy_btn.connect("clicked", self.on_copy_clicked, entry)
                row_box.append(copy_btn)
                group.append(row_box)
            
            setattr(self, f"{prefix}_{prop}_entry", entry)

        return group

    def on_color_button_changed(self, color_button, pspec, prefix):
        new_color = color_button.get_rgba()
        old_color = getattr(self, f"{prefix}_color")
        if new_color.to_string() != old_color.to_string():
            setattr(self, f"{prefix}_color", new_color)
            self.update_all_displays()

    def on_copy_clicked(self, button, entry):
        text = entry.get_text()
            
        clipboard = Gdk.Display.get_default().get_clipboard()
        clipboard.set(text)
        
        if HAS_ADWAITA:
            toast = Adw.Toast(title=f"Copied: {text}")
            toast.set_timeout(2)
            self.toast_overlay.add_toast(toast)

    def on_entry_changed(self, entry, prefix, format_type):
        if self.updating:
            return

        if self.debounce_timeout:
            GLib.source_remove(self.debounce_timeout)

        self.debounce_timeout = GLib.timeout_add(300, self.update_from_entry, entry, prefix, format_type)

    def update_from_entry(self, entry, prefix, format_type):
        self.debounce_timeout = None
        text = entry.get_text().strip()
        color = getattr(self, f"{prefix}_color")

        try:
            if format_type == "hex":
                text = text.lstrip('#')
                if len(text) == 6:
                    color.red = int(text[0:2], 16) / 255
                    color.green = int(text[2:4], 16) / 255
                    color.blue = int(text[4:6], 16) / 255
                    self.update_all_displays()
            elif format_type == "hex_alpha":
                text = text.lstrip('#')
                if len(text) == 8:
                    color.red = int(text[0:2], 16) / 255
                    color.green = int(text[2:4], 16) / 255
                    color.blue = int(text[4:6], 16) / 255
                    color.alpha = int(text[6:8], 16) / 255
                    self.update_all_displays()
            elif format_type == "rgb":
                parts = [int(p.strip()) for p in text.split(",")]
                if len(parts) == 3:
                    color.red = max(0, min(255, parts[0])) / 255
                    color.green = max(0, min(255, parts[1])) / 255
                    color.blue = max(0, min(255, parts[2])) / 255
                    self.update_all_displays()
            elif format_type == "rgba":
                parts = text.split(",")
                if len(parts) == 4:
                    color.red = max(0, min(255, int(parts[0].strip()))) / 255
                    color.green = max(0, min(255, int(parts[1].strip()))) / 255
                    color.blue = max(0, min(255, int(parts[2].strip()))) / 255
                    color.alpha = max(0.0, min(1.0, float(parts[3].strip())))
                    self.update_all_displays()
        except (ValueError, IndexError):
            pass

        return False

    def on_swap_colors(self, button):
        tr, tg, tb, ta = self.text_color.red, self.text_color.green, self.text_color.blue, self.text_color.alpha
        br, bg, bb, ba = self.bg_color.red, self.bg_color.green, self.bg_color.blue, self.bg_color.alpha
        self.text_color.red, self.text_color.green, self.text_color.blue, self.text_color.alpha = br, bg, bb, ba
        self.bg_color.red, self.bg_color.green, self.bg_color.blue, self.bg_color.alpha = tr, tg, tb, ta
        self.update_all_displays()
        
        if HAS_ADWAITA:
            toast = Adw.Toast(title="Colors swapped")
            toast.set_timeout(1)
            self.toast_overlay.add_toast(toast)

    def create_preview_section(self, parent):
        if HAS_ADWAITA:
            group = Adw.PreferencesGroup()
            group.set_title("Preview")
            group.set_margin_start(12)
            group.set_margin_end(12)
        else:
            group = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
            title_label = Gtk.Label(label="Preview")
            title_label.add_css_class("title-2")
            title_label.set_halign(Gtk.Align.START)
            group.append(title_label)

        preview_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        preview_box.set_margin_top(12)
        preview_box.set_margin_bottom(12)
        preview_box.set_margin_start(12)
        preview_box.set_margin_end(12)

        self.combined_preview = Gtk.DrawingArea()
        self.combined_preview.set_size_request(-1, 120)
        self.combined_preview.set_draw_func(self.draw_combined_preview, None)
        self.combined_preview.add_css_class("card")
        preview_box.append(self.combined_preview)

        if HAS_ADWAITA:
            group.add(preview_box)
        else:
            group.append(preview_box)
        parent.append(group)

    def create_contrast_section(self, parent):
        if HAS_ADWAITA:
            group = Adw.PreferencesGroup()
            group.set_title("Contrast Rating (WCAG 2.1)")
            group.set_margin_start(12)
            group.set_margin_end(12)
        else:
            group = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
            title_label = Gtk.Label(label="Contrast Rating (WCAG 2.1)")
            title_label.add_css_class("title-2")
            title_label.set_halign(Gtk.Align.START)
            group.append(title_label)

        contrast_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        contrast_box.set_margin_top(12)
        contrast_box.set_margin_bottom(12)
        contrast_box.set_margin_start(12)
        contrast_box.set_margin_end(12)

        dots_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        dots_box.set_halign(Gtk.Align.CENTER)
        self.rating_dots = []
        for i in range(10):
            dot = Gtk.DrawingArea()
            dot.set_size_request(28, 28)
            dot.set_draw_func(self.draw_rating_dot, i + 1)
            self.rating_dots.append(dot)
            dots_box.append(dot)
        contrast_box.append(dots_box)

        self.rating_label = Gtk.Label()
        self.rating_label.set_markup("<big><b>Rating: Excellent (10/10)</b></big>")
        self.rating_label.set_halign(Gtk.Align.CENTER)
        contrast_box.append(self.rating_label)

        self.contrast_ratio_label = Gtk.Label()
        self.contrast_ratio_label.set_markup("Contrast Ratio: <b>21.00:1</b>")
        self.contrast_ratio_label.set_halign(Gtk.Align.CENTER)
        contrast_box.append(self.contrast_ratio_label)

        self.wcag_label = Gtk.Label()
        self.wcag_label.set_wrap(True)
        self.wcag_label.set_halign(Gtk.Align.CENTER)
        self.wcag_label.set_justify(Gtk.Justification.CENTER)
        self.wcag_label.add_css_class("dim-label")
        contrast_box.append(self.wcag_label)

        if HAS_ADWAITA:
            group.add(contrast_box)
        else:
            group.append(contrast_box)
        parent.append(group)



    def draw_combined_preview(self, area, cr, width, height, data):
        checker_size = 10
        for i in range(math.ceil(width / checker_size)):
            for j in range(math.ceil(height / checker_size)):
                if (i + j) % 2 == 0:
                    cr.set_source_rgb(0.9, 0.9, 0.9)
                else:
                    cr.set_source_rgb(1.0, 1.0, 1.0)
                cr.rectangle(i * checker_size, j * checker_size, checker_size, checker_size)
                cr.fill()

        Gdk.cairo_set_source_rgba(cr, self.bg_color)
        cr.rectangle(0, 0, width, height)
        cr.fill()

        Gdk.cairo_set_source_rgba(cr, self.text_color)
        cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)

        texts = [
            ("Display Title", 24, cairo.FONT_WEIGHT_BOLD),
            ("Heading Text", 18, cairo.FONT_WEIGHT_BOLD),
            ("Body text for reading", 14, cairo.FONT_WEIGHT_NORMAL)
        ]

        y = height / 4
        for text, size, weight in texts:
            cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, weight)
            cr.set_font_size(size)
            extents = cr.text_extents(text)
            x = (width - extents.width) / 2
            cr.move_to(x, y)
            cr.show_text(text)
            y += size + 12

    def draw_rating_dot(self, area, cr, width, height, level):
        ratio = self.calculate_contrast_ratio()
        if ratio is None:
            return

        rating = self.contrast_ratio_to_rating(ratio)
        radius = min(width, height) / 2 - 2
        cx, cy = width / 2, height / 2

        cr.set_source_rgba(0.5, 0.5, 0.5, 0.3)
        cr.arc(cx, cy, radius, 0, 2 * math.pi)
        cr.set_line_width(1.5)
        cr.stroke()

        if level <= math.floor(rating):
            fill = 1.0
        elif level <= rating:
            fill = rating - math.floor(rating)
        else:
            fill = 0.0

        if fill > 0:
            if rating >= 9:
                cr.set_source_rgb(0.18, 0.80, 0.44)
            elif rating >= 7:
                cr.set_source_rgb(0.52, 0.93, 0.18)
            elif rating >= 4.5:
                cr.set_source_rgb(0.95, 0.77, 0.06)
            elif rating >= 3:
                cr.set_source_rgb(0.96, 0.49, 0.00)
            else:
                cr.set_source_rgb(0.91, 0.22, 0.22)

            cr.arc(cx, cy, radius * fill, 0, 2 * math.pi)
            cr.fill()

    def blend_with_background(self, foreground, background):
        if foreground.alpha >= 1.0:
            return foreground
        result = Gdk.RGBA()
        alpha = foreground.alpha
        result.red = foreground.red * alpha + background.red * (1 - alpha)
        result.green = foreground.green * alpha + background.green * (1 - alpha)
        result.blue = foreground.blue * alpha + background.blue * (1 - alpha)
        result.alpha = 1.0
        return result

    def calculate_relative_luminance(self, color):
        def srgb_to_linear(c):
            return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
        r = srgb_to_linear(color.red)
        g = srgb_to_linear(color.green)
        b = srgb_to_linear(color.blue)
        return 0.2126 * r + 0.7152 * g + 0.0722 * b

    def calculate_contrast_ratio(self):
        text = self.blend_with_background(self.text_color, self.bg_color)
        bg = self.blend_with_background(self.bg_color, self.text_color)
        l1 = self.calculate_relative_luminance(text)
        l2 = self.calculate_relative_luminance(bg)
        if l1 < l2:
            l1, l2 = l2, l1
        return (l1 + 0.05) / (l2 + 0.05)

    def contrast_ratio_to_rating(self, ratio):
        if ratio >= 21:
            return 10.0
        elif ratio >= 7:
            return 7 + (math.log10(ratio) - math.log10(7)) * (3 / (math.log10(21) - math.log10(7)))
        elif ratio >= 4.5:
            return 4 + (math.log10(ratio) - math.log10(4.5)) * (3 / (math.log10(7) - math.log10(4.5)))
        elif ratio >= 3:
            return 2 + (math.log10(ratio) - math.log10(3)) * (2 / (math.log10(4.5) - math.log10(3)))
        else:
            return max(0.5, ratio / 3 * 2)

    def update_contrast_display(self):
        ratio = self.calculate_contrast_ratio()
        if ratio is None:
            return

        rating = self.contrast_ratio_to_rating(ratio)
        rating_str = f"{rating:.1f}".rstrip('0').rstrip('.')

        for dot in self.rating_dots:
            dot.queue_draw()

        if ratio >= 7:
            quality = "Excellent"
            wcag = "✓ Meets WCAG AAA (normal & large text)"
        elif ratio >= 4.5:
            quality = "Good"
            wcag = "✓ Meets WCAG AA (normal text) & AAA (large text)"
        elif ratio >= 3:
            quality = "Fair"
            wcag = "✓ Meets WCAG AA (large text only)\n✗ Fails for normal text"
        else:
            quality = "Poor"
            wcag = "✗ Fails WCAG requirements for all text sizes"

        self.rating_label.set_markup(f"<big><b>Rating: {quality} ({rating_str}/10)</b></big>")
        self.contrast_ratio_label.set_markup(f"Contrast Ratio: <b>{ratio:.2f}:1</b>")
        self.wcag_label.set_text(wcag)

    def format_color(self, color, format_type):
        if format_type == "hex":
            return f"#{int(color.red*255):02X}{int(color.green*255):02X}{int(color.blue*255):02X}"
        elif format_type == "hex_alpha":
            return f"#{int(color.red*255):02X}{int(color.green*255):02X}{int(color.blue*255):02X}{int(color.alpha*255):02X}"
        elif format_type == "rgb":
            return f"{int(color.red*255)}, {int(color.green*255)}, {int(color.blue*255)}"
        elif format_type == "rgba":
            alpha = round(color.alpha, 2)
            alpha_str = str(int(alpha)) if alpha == int(alpha) else str(alpha)
            return f"{int(color.red*255)}, {int(color.green*255)}, {int(color.blue*255)}, {alpha_str}"

    def update_all_displays(self):
        if self.updating:
            return
        self.updating = True

        focused_widget = self.win.get_focus()

        for prefix in ["text", "bg"]:
            color = getattr(self, f"{prefix}_color")

            # Update the Gtk.ColorDialogButton's color
            color_button = getattr(self, f"{prefix}_color_button", None)
            if color_button and color_button.get_rgba().to_string() != color.to_string():
                color_button.set_rgba(color)

            for format_type in ["hex", "hex_alpha", "rgb", "rgba"]:
                entry_widget = getattr(self, f"{prefix}_{format_type}_entry")

                has_focus = False
                if focused_widget:
                    # For Adw.EntryRow, the focus is on an internal Gtk.Entry.
                    # We check if the stored widget is an ancestor of the focused widget.
                    if HAS_ADWAITA and isinstance(entry_widget, Adw.EntryRow):
                        if focused_widget == entry_widget or (hasattr(focused_widget, 'get_ancestor') and focused_widget.get_ancestor(Adw.EntryRow) == entry_widget):
                            has_focus = True
                    # For Gtk.Entry, we do a direct comparison.
                    elif focused_widget == entry_widget:
                        has_focus = True
                
                if not has_focus:
                    entry_widget.set_text(self.format_color(color, format_type))

        self.combined_preview.queue_draw()
        self.update_contrast_display()
        self.updating = False

    def run(self):
        print("Starting...")
        # Don't manually call on_activate, let the signal do it
        return self.app.run(sys.argv)

def main():
    picker = DualColorPicker()
    return picker.run()

if __name__ == "__main__":
    sys.exit(main())
