#!/usr/bin/env bash
# ~/Scripts/choose-accent.sh - No dependencies version

if [[ $# -lt 1 ]]; then
    echo "Usage: choose-accent.sh '#rrggbb'"
    exit 1
fi

hex="$1"

if [[ ! "$hex" =~ ^#[0-9A-Fa-f]{6}$ ]]; then
    echo "Error: Invalid hex color format. Use '#rrggbb'" >&2
    exit 1
fi

# Pure Python implementation with no external dependencies
chosen=$(python3 -c "
import sys
import math

def hex_to_rgb(hex_color):
    '''Convert hex to RGB'''
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

def rgb_to_hsv(r, g, b):
    '''Convert RGB to HSV'''
    r, g, b = r/255.0, g/255.0, b/255.0
    cmax = max(r, g, b)
    cmin = min(r, g, b)
    delta = cmax - cmin

    # Hue calculation
    if delta == 0:
        hue = 0
    elif cmax == r:
        hue = 60 * (((g - b) / delta) % 6)
    elif cmax == g:
        hue = 60 * (((b - r) / delta) + 2)
    else:  # cmax == b
        hue = 60 * (((r - g) / delta) + 4)

    # Saturation calculation
    saturation = 0 if cmax == 0 else delta / cmax

    # Value
    value = cmax

    return hue, saturation, value

def find_nearest_accent(input_hex):
    '''Find nearest accent color using HSV similarity'''
    input_hsv = rgb_to_hsv(*hex_to_rgb(input_hex))
    input_hue = input_hsv[0]

    # Accent color palette with their typical hue ranges
    accents = {
        'red': (0, 15),
        'orange': (15, 45),
        'yellow': (45, 75),
        'green': (75, 165),
        'teal': (165, 195),
        'blue': (195, 255),
        'purple': (255, 285),
        'pink': (285, 330),
        'slate': None  # Special case for neutrals
    }

    # For very low saturation, return slate (neutral)
    if input_hsv[1] < 0.2:
        return 'slate'

    # Find closest hue match
    best_match = 'slate'
    best_distance = float('inf')

    for name, hue_range in accents.items():
        if hue_range is None:  # Skip slate for hue matching
            continue

        low, high = hue_range
        # Handle hue wrap-around (red at 0° and 360°)
        if low <= input_hue <= high:
            distance = 0  # Exact match within range
        else:
            # Calculate minimal circular distance
            dist1 = min(abs(input_hue - low), 360 - abs(input_hue - low))
            dist2 = min(abs(input_hue - high), 360 - abs(input_hue - high))
            distance = min(dist1, dist2)

        if distance < best_distance:
            best_distance = distance
            best_match = name

    return best_match

input_hex = '$hex'
print(find_nearest_accent(input_hex))
")

if [[ $? -ne 0 || -z "$chosen" ]]; then
    echo "Error: Failed to calculate accent color" >&2
    exit 1
fi

echo "Nearest accent: $chosen"

# Apply via gsettings
if command -v gsettings > /dev/null; then
    echo "Applying accent color: $chosen"
    if gsettings set org.gnome.desktop.interface accent-color "'$chosen'"; then
        current_accent=$(gsettings get org.gnome.desktop.interface accent-color | tr -d "'")
        echo "✓ Accent color changed to: $current_accent"
    else
        echo "✗ Failed to apply accent color via gsettings" >&2
        exit 1
    fi
else
    echo "Note: gsettings not available (GNOME not detected?)"
    echo "Would apply accent: $chosen"
fi
