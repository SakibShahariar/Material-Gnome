#!/bin/bash
LOCK=/tmp/.dark-mode-self-toggle.lock

gsettings monitor org.gnome.desktop.interface color-scheme | while read -r line; do
    if [[ -f "$LOCK" ]]; then
        echo "Ignored — change came from wallpaper script"
    else
        echo "External toggle detected (Quick Settings): $line"
        # put whatever action you want here
    fi
done