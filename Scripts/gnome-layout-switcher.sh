#!/usr/bin/env bash

T="$HOME/.themes/Material-Gnome/gnome-shell"
L="$T/layouts"
M_TEMPLATES="$HOME/.config/matugen/templates"
HOOK="/home/sakib/.config/matugen/post-hook-scripts/merge-layout.sh"

# 1. Gather choices from the theme layouts folder
layouts=$(find "$L" -maxdepth 1 -name "*.css" ! -name "active-layout.css" -exec basename {} .css \;)
SELECTED_LAYOUT=$(echo "$layouts" | gum choose)

[ -z "$SELECTED_LAYOUT" ] && exit 0

# 2. Handle Matugen Template folder internally
cp "$M_TEMPLATES/gnome-$SELECTED_LAYOUT.css" "$M_TEMPLATES/gnome-active-layout.css"

# 3. Handle Theme Layouts folder internally
cp "$L/$SELECTED_LAYOUT.css" "$L/active-layout.css"

# 4. Fire the merge script
bash "$HOOK"

echo "Layout shifted to $SELECTED_LAYOUT!"
