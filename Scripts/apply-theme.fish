#!/usr/bin/env fish

# This script applies a matugen theme based on a provided theme name.

# ======================
# Configuration
# ======================

set spinner "globe"

# ======================
# Helper Functions
# ======================

function generate_theme -a theme_name
    set theme_json_path (string join "" ~/.config/matugen/themes/ $theme_name ".json")

    if not test -f "$theme_json_path"
        echo "Error: Theme JSON file not found: $theme_json_path"
        exit 1
    end

    gum spin --spinner $spinner --title "Generating theme from $theme_name..." -- fish -c "
        matugen json $theme_json_path --show-colors
    "
end

function set_wallpaper -a theme_name
    set config_file ~/.config/matugen/wallpaper_map.json

    if not test -f "$config_file"
        echo "Warning: Wallpaper mapping file not found at $config_file"
        return
    end

    if not command -v jq >/dev/null
        echo "Error: jq is not installed"
        return
    end

    # Get wallpapers array for selected theme
    set wallpapers (jq -r ".\"$theme_name\".wallpapers[]" "$config_file" 2>/dev/null)

    if test (count $wallpapers) -eq 0
        echo "Warning: Wallpaper for theme '$theme_name' not found in $config_file"
        return
    end

    # Pick random wallpaper
    set wallpaper_path $wallpapers[(random 1 (count $wallpapers))]

    if not test -f "$wallpaper_path"
        echo "Warning: Wallpaper file not found at '$wallpaper_path'"
        return
    end

    gum spin --spinner moon --title "Setting wallpaper..." -- fish -c "
        dconf write /org/gnome/desktop/background/picture-uri \"'file://$wallpaper_path'\"
        dconf write /org/gnome/desktop/background/picture-uri-dark \"'file://$wallpaper_path'\"
    "
end

function set_folder_icons
    set icon_script_path (string join "" ~/Scripts/folder_icon.sh)

    if not test -f "$icon_script_path"
        echo "Warning: Folder icon script not found at $icon_script_path"
        return
    end

    gum spin --spinner moon --title "Setting folder icon theme..." -- $icon_script_path
end

function apply_gnome_settings
    # dconf write /org/gnome/shell/extensions/user-theme/name "'default'"
    # dconf write /org/gnome/shell/extensions/user-theme/name "'Material-Gnome'"

    set pop_hint_color (cat ~/.config/colors/pop-shell.css | string trim)
    dconf write /org/gnome/shell/extensions/pop-shell/hint-color-rgba "'$pop_hint_color'"

    set time_rgba (sed -n '1p' ~/.config/colors/clock-color.css)
    set date_rgba (sed -n '2p' ~/.config/colors/clock-color.css)
    set hint_rgba (sed -n '4p' ~/.config/colors/clock-color.css)
    set cmd_rgba (sed -n '3p' ~/.config/colors/clock-color.css)

    dconf write /org/gnome/shell/extensions/customize-clock-on-lockscreen/time-font-color "'$time_rgba'"
    dconf write /org/gnome/shell/extensions/customize-clock-on-lockscreen/date-font-color "'$date_rgba'"
    dconf write /org/gnome/shell/extensions/customize-clock-on-lockscreen/hint-font-color "'$hint_rgba'"
    dconf write /org/gnome/shell/extensions/customize-clock-on-lockscreen/command-output-font-color "'$cmd_rgba'"

    set color_file ~/.config/colors/space-bar.css

    for line in (cat $color_file | string trim | grep -v '^#')
        set parts (echo $line | string split '=')
        set key (string trim $parts[1])
        set value (string trim $parts[2])

        switch $key
            case 'active_bg'
                set active_bg $value
            case 'active_fg'
                set active_fg $value
            case 'inactive_fg'
                set inactive_fg $value
        end
    end

    dconf write /org/gnome/shell/extensions/space-bar/appearance/active-workspace-background-color $active_bg
    dconf write /org/gnome/shell/extensions/space-bar/appearance/active-workspace-text-color $active_fg
    dconf write /org/gnome/shell/extensions/space-bar/appearance/inactive-workspace-text-color $inactive_fg

    python ~/Scripts/normalize_rgb.py

    set color_file ~/.config/colors/search-light.css

    for line in (cat $color_file | string trim | grep -v '^#')
        set parts (echo $line | string split '=')
        set key (string trim $parts[1])
        set value (string trim $parts[2])

        switch $key
            case 'foreground'
                set foreground $value
            case 'background'
                set background $value
        end
    end

    dconf write /org/gnome/shell/extensions/search-light/background-color "($background, 0.75)"
    dconf write /org/gnome/shell/extensions/search-light/text-color "($foreground, 1.0)"
    dconf write /org/gnome/shell/extensions/search-light/panel-icon-color "($foreground, 1.0)"
    dconf write /org/gnome/shell/extensions/search-light/border-color "($foreground, 1.0)"

    # ======================
    # 🎧 Dynamic Music Pill FIX ONLY
    # ======================

    set color_file ~/.config/colors/search-light.css

    set fg_line (sed -n '1p' $color_file)
    set bg_line (sed -n '2p' $color_file)

    set fg_vals (string split ", " (string replace "foreground = " "" $fg_line))
    set bg_vals (string split ", " (string replace "background = " "" $bg_line))

    # convert 0–1 → 0–255 (ONLY for this feature)
    set fg_rgb (math "round($fg_vals[1] * 255)")","(math "round($fg_vals[2] * 255)")","(math "round($fg_vals[3] * 255)")
    set bg_rgb (math "round($bg_vals[1] * 255)")","(math "round($bg_vals[2] * 255)")","(math "round($bg_vals[3] * 255)")

    dconf write /org/gnome/shell/extensions/dynamic-music-pill/custom-text-color "'$fg_rgb'"
    dconf write /org/gnome/shell/extensions/dynamic-music-pill/custom-bg-color "'$bg_rgb'"

    # remove quotes around hex if present
    set clean_bg (string replace -a "'" "" $active_bg)
    bash ~/Scripts/choose-accent.sh "$clean_bg"

    # set yazi color
    # python3 ~/Scripts/yazi-theme.py
end

function sync_darkreader
    set DB "/home/sakib/.zen/oup922t1.Default (release)/storage-sync-v2.sqlite"

    set BG (jq -r '.colors.color0' ~/.config/colors.json)
    set FG (jq -r '.colors.color13' ~/.config/colors.json)

    sqlite3 $DB "
    UPDATE storage_sync_data
    SET data = json_set(
        data,
        '\$.theme.darkSchemeBackgroundColor', '$BG',
        '\$.theme.darkSchemeTextColor', '$FG',
        '\$.theme.scrollbarColor', '$FG'
    )
    WHERE ext_id = 'addon@darkreader.org';
    "

    echo \"🌙 Dark Reader synced → BG:$BG FG:$FG\"
end

# ======================
# Main Script
# ======================

if test -z "$argv[1]"
    echo "Usage: apply-theme.fish <theme_name>"
    exit 1
end

set selected_theme_name "$argv[1]"

generate_theme $selected_theme_name
set_wallpaper $selected_theme_name
set_folder_icons
apply_gnome_settings
sync_darkreader
