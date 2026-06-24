#!/usr/bin/env bash

set -euo pipefail # Fail early if commands or variables fail

T="$HOME/.themes/Material-Gnome/gnome-shell"
L="$T/layouts"
M_TEMPLATES="$HOME/.config/matugen/templates"
HOOK="$HOME/.config/matugen/post-hook-scripts/merge-layout.sh"

# 1. Gather choices from the theme layouts folder
if [ ! -d "$L" ]; then
    echo "❌ Layouts directory does not exist: $L"
    exit 1
fi

layouts=$(find "$L" -maxdepth 1 -name "*.css" ! -name "active-layout.css" -exec basename {} .css \;)

if [ -z "$layouts" ]; then
    echo "❌ No layouts found in $L"
    exit 1
fi

# Select layout using gum
if ! SELECTED_LAYOUT=$(echo "$layouts" | gum choose); then
    echo "Selection cancelled."
    exit 0
fi

# 2. Handle Matugen Template folder internally
MATUGEN_SRC="$M_TEMPLATES/gnome-$SELECTED_LAYOUT.css"
if [ ! -f "$MATUGEN_SRC" ]; then
    echo "⚠️ Warning: Matugen template missing at $MATUGEN_SRC. Skipping Matugen copy."
else
    cp "$MATUGEN_SRC" "$M_TEMPLATES/gnome-active-layout.css"
fi

# 3. Handle Theme Layouts folder internally
cp "$L/$SELECTED_LAYOUT.css" "$L/active-layout.css"

# 4. Fire the merge script
if [ -f "$HOOK" ]; then
    bash "$HOOK"
else
    echo "❌ CRITICAL: Hook script missing at $HOOK"
    exit 1
fi

echo "✅ Layout shifted to $SELECTED_LAYOUT!"
