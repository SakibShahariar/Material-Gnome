#!/usr/bin/env bash
# ~/Scripts/folder_icon.sh - Accurate color distance matching

colors_file="$HOME/.config/colors.json"
line_number=25

# Read the line and extract hex color
raw_line=$(sed -n "${line_number}p" "$colors_file")
hex_input=$(echo "$raw_line" | grep -oE '#[A-Fa-f0-9]{6}' | tr '[:upper:]' '[:lower:]')

if [[ -z "$hex_input" ]]; then
    echo "Error: No hex color found on line $line_number" >&2
    exit 1
fi

echo "Input color: $hex_input"

# Color distance matching with Python
nearest_color=$(python3 -c "
import colorsys
import sys
import math

def hex_to_rgb(hex_color):
    \"\"\"Convert hex to RGB values (0-255).\"\"\"
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

def hex_to_hsv(hex_color):
    \"\"\"Convert hex color to HSV values.\"\"\"
    hex_color = hex_color.lstrip('#')
    r = int(hex_color[0:2], 16) / 255.0
    g = int(hex_color[2:4], 16) / 255.0
    b = int(hex_color[4:6], 16) / 255.0
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    return h * 360, s * 100, v * 100

def color_distance_hsv(color1_hex, color2_hex):
    \"\"\"
    Calculate perceptual distance between two colors in HSV space.
    Uses weighted distance that considers hue, saturation, and value.
    \"\"\"
    h1, s1, v1 = hex_to_hsv(color1_hex)
    h2, s2, v2 = hex_to_hsv(color2_hex)

    # Handle hue wrapping (circular distance)
    dh = min(abs(h1 - h2), 360 - abs(h1 - h2))

    # Normalize hue difference to 0-180 range
    dh = dh / 180.0

    # Saturation and value differences (0-100 range)
    ds = abs(s1 - s2) / 100.0
    dv = abs(v1 - v2) / 100.0

    # Weighted Euclidean distance
    # Hue is most important, then saturation, then value
    distance = math.sqrt((dh * 2.0)**2 + (ds * 1.0)**2 + (dv * 0.5)**2)

    return distance

def color_distance_rgb(color1_hex, color2_hex):
    \"\"\"Calculate RGB Euclidean distance.\"\"\"
    r1, g1, b1 = hex_to_rgb(color1_hex)
    r2, g2, b2 = hex_to_rgb(color2_hex)

    # Euclidean distance in RGB space
    distance = math.sqrt((r1-r2)**2 + (g1-g2)**2 + (b1-b2)**2)
    return distance

def find_nearest_theme(input_hex):
    \"\"\"
    Find the nearest Tela theme by calculating color distance.
    Uses actual theme colors for accurate matching.
    \"\"\"
    # Official Tela theme colors (in order provided)
    theme_colors = {
        'Tela-blue':    '#5677fc',
        'Tela-brown':   '#795548',
        'Tela-dracula': '#44475a',
        'Tela-green':   '#66bb6a',
        'Tela-grey':    '#bdbdbd',
        'Tela-manjaro': '#16a085',
        'Tela-nord':    '#4d576a',
        'Tela-orange':  '#ff9800',
        'Tela-pink':    '#f06292',
        'Tela-purple':  '#7e57c2',
        'Tela-red':     '#ef5350',
        'Tela-ubuntu':  '#fb8441',
        'Tela-yellow':  '#ffca28',
    }

    input_h, input_s, input_v = hex_to_hsv(input_hex)

    # Special case: very low saturation = grey
    if input_s < 10:
        return 'Tela-grey'

    # Calculate distance to each theme color
    distances = {}
    for theme_name, theme_hex in theme_colors.items():
        # Use HSV distance for better perceptual matching
        dist = color_distance_hsv(input_hex, theme_hex)
        distances[theme_name] = dist

    # Find the theme with minimum distance
    nearest_theme = min(distances, key=distances.get)
    nearest_distance = distances[nearest_theme]

    # Debug output
    print(f'Debug: HSV({input_h:.1f}°, {input_s:.1f}%, {input_v:.1f}%)', file=sys.stderr)
    print(f'Debug: Nearest={nearest_theme} (distance={nearest_distance:.3f})', file=sys.stderr)

    return nearest_theme

# Main execution
input_hex = '$hex_input'
match = find_nearest_theme(input_hex)
print(match)
")

# Check if Python execution was successful
if [[ $? -ne 0 || -z "$nearest_color" ]]; then
    echo "Error: Failed to calculate theme color" >&2
    exit 1
fi

echo "Nearest Tela color: $nearest_color"

# Apply via gsettings
if command -v gsettings > /dev/null; then
    echo "Applying icon theme: $nearest_color"
    if gsettings set org.gnome.desktop.interface icon-theme "$nearest_color"; then
        current_theme=$(gsettings get org.gnome.desktop.interface icon-theme | tr -d "'")
        echo "✓ Icon theme changed to: $current_theme"
    else
        echo "✗ Failed to apply icon theme" >&2
        exit 1
    fi
else
    echo "Note: gsettings not available (GNOME not detected?)"
fi
