#!/usr/bin/env python3
"""
Dual Color Picker v3.1
- Fixed alpha transparency in contrast calculations
- Precision decimal contrast ratings
- Logarithmic scaling for high contrast ratios
- Partial dot filling for visual accuracy
- Enhanced WCAG compliance descriptions
- MODERN UI/UX ENHANCEMENTS
"""

import gi
import cairo
import math
gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gtk, Gdk, GLib

class DualColorPicker(Gtk.Application):
    def __init__(self):
        super().__init__(application_id='com.example.DualColorPicker.v3_2_modern')
        self.text_color = Gdk.RGBA()
        self.text_color.parse("rgb(0,0,0)")
        self.bg_color = Gdk.RGBA()
        self.bg_color.parse("rgb(255,255,255)")
        self.updating = False

    def do_activate(self):
        self.win = Gtk.ApplicationWindow(application=self, title="Dual Color Picker v3.2 (Modern)")
        self.win.set_default_size(800, 600)
        self.win.set_resizable(True)

        # Apply global CSS
        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(b"""
            /* Global Styling */
            window {
                background-color: @theme_bg_color;
                font-family: sans-serif; /* Use system default modern sans-serif */
            }

            .main-container {
                padding: 24px;
            }

            .color-panel-box {
                background-color: @card_bg_color;
                border-radius: 12px; /* Rounded corners for panels */
                box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08); /* Subtle shadow */
                padding: 24px;
                min-width: 320px;
                flex-grow: 1; /* Allow panels to grow */
                flex-shrink: 1;
            }
            .panel-title {
                font-size: 1.4em;
                font-weight: bold;
                margin-bottom: 18px;
                color: @theme_text_color;
            }

            /* Color Preview */
            .color-preview {
                min-height: 80px;
                border-radius: 8px; /* Rounded corners for previews */
                margin-bottom: 24px;
                border: 1px solid rgba(0,0,0,0.1); /* Subtle border for definition */
            }

            /* Input Fields */
            .format-grid {
                margin-top: 12px;
                margin-bottom: 8px;
            }
            .format-label {
                font-weight: bold;
                color: @theme_text_color;
                opacity: 0.8;
            }
            entry {
                min-height: 38px;
                border-radius: 6px;
                border: 1px solid @borders;
                background-color: @theme_base_color;
                padding: 0 12px;
                transition: border-color 0.2s ease-in-out, box-shadow 0.2s ease-in-out;
            }
            entry:focus {
                border-color: @theme_selected_bg_color;
                box-shadow: 0 0 0 2px alpha(@theme_selected_bg_color, 0.4);
            }

            /* Combined Preview */
            .combined-preview-box {
                background-color: @card_bg_color;
                border-radius: 12px;
                box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
                padding: 24px;
                margin: 24px 0; /* Adjusted margin */
                width: 100%; /* Take full width */
                min-height: 120px;
            }
            .combined-preview-drawing {
                border-radius: 8px; /* Rounded corners for drawing area */
                min-height: 90px;
                border: 1px solid rgba(0,0,0,0.1);
            }


            /* Contrast Rating */
            .contrast-rating-box {
                background-color: @card_bg_color;
                border-radius: 12px;
                box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
                padding: 24px;
                margin-top: 24px;
            }
            .contrast-title {
                font-size: 1.2em;
                font-weight: bold;
                margin-bottom: 12px;
                color: @theme_text_color;
            }
            .rating-dots-box {
                margin-bottom: 12px;
            }
            .rating-label {
                font-weight: bold;
                font-size: 1.1em;
                color: @theme_text_color;
                margin-bottom: 6px;
            }
            .contrast-ratio-label {
                font-size: 1em;
                color: @theme_text_color;
                opacity: 0.9;
                margin-bottom: 8px;
            }
            .wcag-label {
                font-size: 0.9em;
                color: @theme_text_color;
                opacity: 0.7;
                line-height: 1.4;
            }

            /* Separator */
            .panel-separator {
                margin: 0 12px; /* Add some space around separator */
            }
        """)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.win.set_child(scrolled)

        main_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=24)
        main_container.set_css_classes(["main-container"])
        scrolled.set_child(main_container)

        self.main_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=24)
        main_container.append(self.main_box)

        self.text_panel_box, self.text_preview = self.create_color_panel("Text Color", self.text_color, "text")
        self.main_box.append(self.text_panel_box)

        separator = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        separator.set_css_classes(["panel-separator"])
        self.main_box.append(separator)

        self.bg_panel_box, self.bg_preview = self.create_color_panel("Background Color", self.bg_color, "bg")
        self.main_box.append(self.bg_panel_box)

        self.create_preview_box(main_container)
        self.create_contrast_rating_box(main_container)

        self.update_displays("text")
        self.update_displays("bg")
        self.update_contrast_rating()

        self.win.present()

    def blend_with_background(self, foreground, background):
        """Blend semi-transparent colors with their background"""
        if foreground.alpha >= 1.0:
            return foreground

        result = Gdk.RGBA()
        alpha = foreground.alpha
        result.red = foreground.red * alpha + background.red * (1 - alpha)
        result.green = foreground.green * alpha + background.green * (1 - alpha)
        result.blue = foreground.blue * alpha + background.blue * (1 - alpha)
        result.alpha = 1.0  # Result is now effectively opaque
        return result

    def create_contrast_rating_box(self, parent):
        contrast_box_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        contrast_box_container.set_css_classes(["contrast-rating-box"])
        parent.append(contrast_box_container)

        title = Gtk.Label(label="Contrast Rating (WCAG 2.1)")
        title.set_css_classes(["contrast-title"])
        title.set_halign(Gtk.Align.CENTER)
        contrast_box_container.append(title)

        center_box = Gtk.CenterBox()
        contrast_box_container.append(center_box)

        self.rating_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        self.rating_box.set_css_classes(["rating-dots-box"])
        center_box.set_center_widget(self.rating_box)

        self.rating_dots = []
        for i in range(10):
            dot = Gtk.DrawingArea()
            dot.set_size_request(24, 24)
            dot.set_draw_func(self.draw_rating_dot, i+1)
            self.rating_dots.append(dot)
            self.rating_box.append(dot)

        self.rating_label = Gtk.Label()
        self.rating_label.set_css_classes(["rating-label"])
        self.rating_label.set_halign(Gtk.Align.CENTER)
        contrast_box_container.append(self.rating_label)

        self.contrast_ratio_label = Gtk.Label()
        self.contrast_ratio_label.set_css_classes(["contrast-ratio-label"])
        self.contrast_ratio_label.set_halign(Gtk.Align.CENTER)
        contrast_box_container.append(self.contrast_ratio_label)

        self.wcag_label = Gtk.Label()
        self.wcag_label.set_css_classes(["wcag-label"])
        self.wcag_label.set_wrap(True)
        self.wcag_label.set_halign(Gtk.Align.CENTER)
        contrast_box_container.append(self.wcag_label)

    def draw_rating_dot(self, area, cr, width, height, rating_level):
        ratio = self.calculate_contrast_ratio()
        if ratio is None:
            return

        rating = self.contrast_ratio_to_rating(ratio)
        dot_diameter = min(width, height) - 4
        dot_radius = dot_diameter / 2
        x = (width - dot_diameter) / 2
        y = (height - dot_diameter) / 2

        # Draw outer ring
        cr.set_source_rgba(0.7, 0.7, 0.7, 0.7) # Lighter, semi-transparent gray
        cr.arc(x + dot_radius, y + dot_radius, dot_radius, 0, 2 * math.pi)
        cr.set_line_width(1.5)
        cr.stroke()

        # Fill calculation for partial dots
        if rating_level <= math.floor(rating):
            fill_level = 1.0
        elif rating_level <= rating:
            fill_level = rating - math.floor(rating)
        else:
            fill_level = 0.0

        if fill_level > 0:
            # Color based on rating level (slightly adjusted colors for modern feel)
            if rating >= 9:
                cr.set_source_rgb(0.1, 0.55, 0.1)  # Darker, richer green for very high scores
            elif rating >= 8:
                cr.set_source_rgb(0.2, 0.7, 0.2)   # Good green
            elif rating >= 7:
                cr.set_source_rgb(0.5, 0.8, 0.2)   # Lime-green
            elif rating >= 4.5: # WCAG AA
                cr.set_source_rgb(0.9, 0.7, 0.1)   # Warm yellow for AA
            elif rating >= 3: # WCAG AA Large Text
                cr.set_source_rgb(0.9, 0.5, 0.1)   # Orange for large text only
            else:
                cr.set_source_rgb(0.85, 0.25, 0.2) # Soft red for failing

            # Draw filled circle (potentially partial)
            cr.arc(x + dot_radius, y + dot_radius, dot_radius * fill_level, 0, 2 * math.pi)
            cr.fill()


    def calculate_relative_luminance(self, color):
        def srgb_to_linear(channel):
            if channel <= 0.03928:
                return channel / 12.92
            else:
                return ((channel + 0.055) / 1.055) ** 2.4

        r = srgb_to_linear(color.red)
        g = srgb_to_linear(color.green)
        b = srgb_to_linear(color.blue)
        return 0.2126 * r + 0.7152 * g + 0.0722 * b

    def calculate_contrast_ratio(self):
        # Blend colors if they have transparency
        effective_text = self.blend_with_background(self.text_color, self.bg_color)
        effective_bg = self.blend_with_background(self.bg_color, self.text_color)

        l1 = self.calculate_relative_luminance(effective_text)
        l2 = self.calculate_relative_luminance(effective_bg)

        if l1 < l2:
            l1, l2 = l2, l1
        return (l1 + 0.05) / (l2 + 0.05)

    def contrast_ratio_to_rating(self, ratio):
        # Slightly adjusted logarithmic scale for better distribution visually
        if ratio >= 21: return 10.0
        elif ratio >= 7: # WCAG AAA threshold
            return 7 + (math.log10(ratio) - math.log10(7)) * (3 / (math.log10(21) - math.log10(7))) # Scale 7-21 to 7-10
        elif ratio >= 4.5: # WCAG AA threshold
            return 4 + (math.log10(ratio) - math.log10(4.5)) * (3 / (math.log10(7) - math.log10(4.5))) # Scale 4.5-7 to 4-7
        elif ratio >= 3: # WCAG AA Large Text threshold
            return 2 + (math.log10(ratio) - math.log10(3)) * (2 / (math.log10(4.5) - math.log10(3))) # Scale 3-4.5 to 2-4
        else: return max(0.5, ratio / 3 * 2) # Below 3:1, scale to 0.5-2

    def update_contrast_rating(self):
        ratio = self.calculate_contrast_ratio()
        if ratio is None:
            return

        for dot in self.rating_dots:
            dot.queue_draw()

        self.contrast_ratio_label.set_label(f"Contrast Ratio: {ratio:.2f}:1")

        rating = self.contrast_ratio_to_rating(ratio)
        rating_display = f"{rating:.1f}".replace(".0", "")

        # Enhanced WCAG descriptions for clarity
        if ratio >= 7:
            rating_text = f"Excellent ({rating_display}/10)"
            wcag_text = "Meets WCAG AAA (normal text) & AAA (large text)."
        elif ratio >= 4.5:
            rating_text = f"Good ({rating_display}/10)"
            wcag_text = "Meets WCAG AA (normal text) & AAA (large text)."
        elif ratio >= 3:
            rating_text = f"Fair ({rating_display}/10)"
            wcag_text = "Meets WCAG AA (large text only). Fails for normal text."
        else:
            rating_text = f"Poor ({rating_display}/10)"
            wcag_text = "Fails WCAG requirements for all text sizes."

        self.rating_label.set_label(f"Rating: {rating_text}")
        self.wcag_label.set_label(f"Accessibility: {wcag_text}")


    def create_preview_box(self, parent):
        combined_preview_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        combined_preview_container.set_css_classes(["combined-preview-box"])
        parent.append(combined_preview_container)

        self.combined_preview = Gtk.DrawingArea()
        self.combined_preview.set_size_request(-1, 90) # Height fixed, width adapts
        self.combined_preview.set_draw_func(self.draw_combined_preview, None)
        self.combined_preview.set_css_classes(["combined-preview-drawing"])
        combined_preview_container.append(self.combined_preview)


    def draw_combined_preview(self, area, cr, width, height, data):
        # Draw background (with potential transparency)
        bg = self.blend_with_background(self.bg_color, self.text_color)
        Gdk.cairo_set_source_rgba(cr, bg)
        cr.rectangle(0, 0, width, height)
        cr.fill()

        # Draw text (with potential transparency)
        text_color_blended = self.blend_with_background(self.text_color, self.bg_color)
        Gdk.cairo_set_source_rgba(cr, text_color_blended)
        cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)

        # Using a slightly different approach for vertical centering and padding
        padding_y = 10
        total_text_height = (20 + 16 + 12) * 1.2 # Rough estimate of text heights with line spacing
        start_y = (height - total_text_height) / 2 + padding_y # Center vertically within the box

        # Define text styles and positions
        texts = [
            ("Body Text", 12),
            ("Heading", 16),
            ("Display Title", 20)
        ]

        current_y = start_y
        for text_str, font_size in texts:
            cr.set_font_size(font_size)
            extents = cr.text_extents(text_str)
            text_x = (width - extents.width) / 2
            cr.move_to(text_x, current_y + extents.height / 2) # Center text vertically on its line
            cr.show_text(text_str)
            current_y += extents.height + 8 # Add line spacing

    def create_color_panel(self, title, color, prefix):
        panel_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        panel_box.set_css_classes(["color-panel-box"])

        title_label = Gtk.Label(label=title)
        title_label.set_css_classes(["panel-title"])
        title_label.set_halign(Gtk.Align.CENTER)
        panel_box.append(title_label)

        preview = Gtk.DrawingArea()
        preview.set_size_request(-1, 80)
        preview.set_draw_func(self.draw_color_preview, color)
        preview.set_css_classes(["color-preview"])
        panel_box.append(preview)

        formats = [
            ("HEX", self.get_hex_color, "hex"),
            ("HEX+Alpha", self.get_hex_alpha_color, "hex_alpha"),
            ("RGB", self.get_rgb_color, "rgb"),
            ("RGBA", self.get_rgba_color, "rgba")
        ]

        format_grid = Gtk.Grid()
        format_grid.set_column_spacing(12)
        format_grid.set_row_spacing(10)
        format_grid.set_css_classes(["format-grid"])
        panel_box.append(format_grid)

        for i, (name, formatter, prop) in enumerate(formats):
            label = Gtk.Label(label=name)
            label.set_css_classes(["format-label"])
            label.set_xalign(0)
            format_grid.attach(label, 0, i, 1, 1)

            entry = Gtk.Entry()
            entry.set_text(formatter(color))
            entry.set_hexpand(True)
            format_grid.attach(entry, 1, i, 1, 1)

            setattr(self, f"{prefix}_{prop}_entry", entry)

            if prop == "rgba":
                entry.connect("notify::has-focus", self.on_rgba_focus_change, prefix)
                entry.connect("activate", self.on_rgba_activate, prefix)
            else:
                entry.connect("changed", getattr(self, f"on_{prop}_changed"), prefix)

        return panel_box, preview

    def on_rgba_focus_change(self, entry, param, prefix):
        if not entry.has_focus():
            self.validate_rgba(entry, prefix)

    def on_rgba_activate(self, entry, prefix):
        self.validate_rgba(entry, prefix)

    def validate_rgba(self, entry, prefix):
        if self.updating:
            return

        text = entry.get_text()

        try:
            parts = [p.strip() for p in text.split(",")]
            if len(parts) == 4:
                color = getattr(self, f"{prefix}_color")
                color.red = min(max(int(parts[0]), 0), 255)/255
                color.green = min(max(int(parts[1]), 0), 255)/255
                color.blue = min(max(int(parts[2]), 0), 255)/255
                alpha_str = parts[3]
                if alpha_str:
                    alpha = min(max(float(alpha_str), 0.0), 1.0)
                    color.alpha = alpha
                self.update_displays(prefix)

        except (ValueError, IndexError):
            # If invalid, revert to current color representation
            color = getattr(self, f"{prefix}_color")
            self.updating = True
            entry.set_text(f"{int(color.red*255)}, {int(color.green*255)}, {int(color.blue*255)}, {round(color.alpha, 2)}")
            self.updating = False

    def get_hex_color(self, color):
        return f"#{int(color.red*255):02X}{int(color.green*255):02X}{int(color.blue*255):02X}"

    def get_hex_alpha_color(self, color):
        return f"#{int(color.red*255):02X}{int(color.green*255):02X}{int(color.blue*255):02X}{int(color.alpha*255):02X}"

    def get_rgb_color(self, color):
        return f"{int(color.red*255)}, {int(color.green*255)}, {int(color.blue*255)}"

    def get_rgba_color(self, color):
        # Format alpha to two decimal places, avoiding trailing zeros if .00
        alpha_val = round(color.alpha, 2)
        if alpha_val == int(alpha_val):
            alpha_str = str(int(alpha_val)) # e.g., 1.0 becomes 1
        else:
            alpha_str = str(alpha_val) # e.g., 0.5 becomes 0.5

        return f"{int(color.red*255)}, {int(color.green*255)}, {int(color.blue*255)}, {alpha_str}"


    def draw_color_preview(self, area, cr, width, height, color):
        Gdk.cairo_set_source_rgba(cr, color)
        cr.rectangle(0, 0, width, height)
        cr.fill()

    def update_displays(self, color_var):
        if self.updating:
            return

        self.updating = True

        color = getattr(self, f"{color_var}_color")

        # Store cursor positions to restore them after updating text
        cursor_positions = {
            'hex': getattr(self, f"{color_var}_hex_entry").get_position(),
            'hex_alpha': getattr(self, f"{color_var}_hex_alpha_entry").get_position(),
            'rgb': getattr(self, f"{color_var}_rgb_entry").get_position(),
            'rgba': getattr(self, f"{color_var}_rgba_entry").get_position()
        }

        # Update text in entries
        getattr(self, f"{color_var}_hex_entry").set_text(self.get_hex_color(color))
        getattr(self, f"{color_var}_hex_alpha_entry").set_text(self.get_hex_alpha_color(color))
        getattr(self, f"{color_var}_rgb_entry").set_text(self.get_rgb_color(color))
        getattr(self, f"{color_var}_rgba_entry").set_text(self.get_rgba_color(color))

        # Restore cursor positions
        # Only restore if the entry has focus to avoid interfering with user typing
        if getattr(self, f"{color_var}_hex_entry").has_focus():
            getattr(self, f"{color_var}_hex_entry").set_position(cursor_positions['hex'])
        if getattr(self, f"{color_var}_hex_alpha_entry").has_focus():
            getattr(self, f"{color_var}_hex_alpha_entry").set_position(cursor_positions['hex_alpha'])
        if getattr(self, f"{color_var}_rgb_entry").has_focus():
            getattr(self, f"{color_var}_rgb_entry").set_position(cursor_positions['rgb'])
        if getattr(self, f"{color_var}_rgba_entry").has_focus():
            getattr(self, f"{color_var}_rgba_entry").set_position(cursor_positions['rgba'])


        if color_var == "text":
            self.text_preview.queue_draw()
        else:
            self.bg_preview.queue_draw()

        self.combined_preview.queue_draw()
        self.update_contrast_rating()

        self.updating = False

    def on_hex_changed(self, entry, prefix):
        if self.updating:
            return

        text = entry.get_text().lstrip('#')
        if len(text) == 6: # Only update if complete HEX6
            try:
                color = getattr(self, f"{prefix}_color")
                color.red = int(text[0:2], 16) / 255
                color.green = int(text[2:4], 16) / 255
                color.blue = int(text[4:6], 16) / 255
                self.update_displays(prefix)
            except ValueError:
                pass # Ignore incomplete/invalid hex for live update, wait for full 6 chars

    def on_hex_alpha_changed(self, entry, prefix):
        if self.updating:
            return

        text = entry.get_text().lstrip('#')
        if len(text) == 8: # Only update if complete HEX8
            try:
                color = getattr(self, f"{prefix}_color")
                color.red = int(text[0:2], 16) / 255
                color.green = int(text[2:4], 16) / 255
                color.blue = int(text[4:6], 16) / 255
                color.alpha = int(text[6:8], 16) / 255
                self.update_displays(prefix)
            except ValueError:
                pass # Ignore incomplete/invalid hex for live update

    def on_rgb_changed(self, entry, prefix):
        if self.updating:
            return

        try:
            parts_str = [p.strip() for p in entry.get_text().split(",")]
            # Only update if exactly 3 parts and all are numeric
            if len(parts_str) == 3 and all(p.isdigit() for p in parts_str):
                parts = [int(p) for p in parts_str]
                color = getattr(self, f"{prefix}_color")
                color.red = min(max(parts[0], 0), 255)/255
                color.green = min(max(parts[1], 0), 255)/255
                color.blue = min(max(parts[2], 0), 255)/255
                self.update_displays(prefix)
        except ValueError:
            pass # Ignore invalid input for live update

if __name__ == "__main__":
    app = DualColorPicker()
    app.run()
