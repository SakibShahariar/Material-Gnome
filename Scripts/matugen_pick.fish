#!/usr/bin/env fish

# --- Helper function to parse color files ---
# Reads a file with `key=value` pairs and outputs `set` commands
function parse_color_file
    set color_file $argv[1]
    while read -l line
        # Skip comments and empty lines
        if string match -q -r '^#' "$line" || test -z "$line"
            continue
        end
        # Split into key and value
        set parts (string split -m 1 '=' "$line")
        if test (count $parts) -eq 2
            # Output a command like: set -l key 'value'
            echo "set -l " (string trim $parts[1]) "'" (string trim --right $parts[2]) "'"
        end
    end < $color_file
end


set wallpaper_dir "/mnt/Storage/Wallpapers"

# Call the Python picker silently and trim the result
set wallpaper (env MESA_DEBUG_OVERRIDE=0 MESA_LOG_LEVEL=0 MESA_DEBUG_DISABLE=vulkan VK_INSTANCE_LAYERS= VK_LAYER_PATH= python3 ~/Scripts/wallpicker.py "$wallpaper_dir" 2>/dev/null | string trim)

# Exit silently if no wallpaper is selected
if test -z "$wallpaper"
    exit 0
end

# Apply the selected wallpaper
gsettings set org.gnome.desktop.background picture-uri "file://$wallpaper"
gsettings set org.gnome.desktop.background picture-uri-dark "file://$wallpaper"

# Generate theme using matugen silently
if command -v matugen >/dev/null
    matugen image $wallpaper -v > /dev/null 2>&1
end

if test -f ~/Scripts/avg-colors.py
    python ~/Scripts/avg-colors.py
end

# Reload kitty colors silently
if command -v kitty >/dev/null
    kitty +kitten themes --reload-in=all colors
    kitty @ set-colors --all ~/.config/kitty/themes/colors.conf > /dev/null 2>&1
end

# Set folder icons
set script_dir (dirname (status --current-filename))
if test -f "$script_dir/folder_icon.sh"
    bash "$script_dir/folder_icon.sh" > /dev/null 2>&1
end

# Reset and reapply GNOME Shell theme
dconf write /org/gnome/shell/extensions/user-theme/name "'default'"
dconf write /org/gnome/shell/extensions/user-theme/name "'Material-Gnome'"

# Apply it to Pop Shell
if test -f ~/.config/colors/pop-shell.css
    set pop_hint_color (cat ~/.config/colors/pop-shell.css | string trim)
    dconf write /org/gnome/shell/extensions/pop-shell/hint-color-rgba "'$pop_hint_color'"
end

# color to clock extension elements
if test -f ~/.config/colors/accent-color.css
    set rgba (cat ~/.config/colors/accent-color.css | string trim)
    for key in time-font-color date-font-color hint-font-color command-output-font-color
        dconf write /org/gnome/shell/extensions/customize-clock-on-lockscreen/$key "'$rgba'"
    end
end

# space-bar extension
if test -f ~/.config/colors/space-bar.css
    eval (parse_color_file ~/.config/colors/space-bar.css)
    if set -q active_bg
        dconf write /org/gnome/shell/extensions/space-bar/appearance/active-workspace-background-color $active_bg
    end
    if set -q active_fg
        dconf write /org/gnome/shell/extensions/space-bar/appearance/active-workspace-text-color $active_fg
    end
    if set -q inactive_fg
        dconf write /org/gnome/shell/extensions/space-bar/appearance/inactive-workspace-text-color $inactive_fg
    end
end

# Search-light Extension
if test -f ~/.config/colors/search-light.css
    # normalized the colors
    # python ~/Scripts/normalize_rgb.py
    eval (parse_color_file ~/.config/colors/search-light.css)
    if set -q background
        dconf write /org/gnome/shell/extensions/search-light/background-color "($background, 0.75)"
    end
    if set -q foreground
        dconf write /org/gnome/shell/extensions/search-light/text-color "($foreground, 1.0)"
        dconf write /org/gnome/shell/extensions/search-light/panel-icon-color "($foreground, 1.0)"
        dconf write /org/gnome/shell/extensions/search-light/border-color "($foreground, 1.0)"
    end
end

# Set final accent color from active workspace background
if set -q active_bg
    # remove quotes around hex if present
    set clean_bg (string replace -a "'" "" $active_bg)
    if test -f ~/Scripts/choose-accent.sh
        bash ~/Scripts/choose-accent.sh "$clean_bg"
    end
end

