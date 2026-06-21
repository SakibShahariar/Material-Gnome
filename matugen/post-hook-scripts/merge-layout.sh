#!/usr/bin/env bash
T="$HOME/.themes/Material-Gnome/gnome-shell"

# 1. Component Verification
if [ ! -f "$T/gnome-shell-stub.css" ]; then
    echo "❌ CRITICAL ERROR: Base stub missing at $T/gnome-shell-stub.css"
    exit 1
fi

if [ ! -f "$T/layouts/active-layout.css" ]; then
    echo "❌ CRITICAL ERROR: Active layout missing at $T/layouts/active-layout.css"
    exit 1
fi

# 2. Compile GNOME Shell Theme
cat "$T/gnome-shell-stub.css" "$T/layouts/active-layout.css" > "$T/gnome-shell.css"

# 3. Reload Shell Theme via dconf toggling
dconf write /org/gnome/shell/extensions/user-theme/name "'default'"

dconf write /org/gnome/shell/extensions/user-theme/name "'Material-Gnome'"
