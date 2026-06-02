#!/usr/bin/env fish

# ======================
# ⚙️ CONFIG
# ======================
set wallpaper_dir "/mnt/Storage/Wallpapers"
set spinner "globe"  # Valid options: line, dot, minidot, jump, pulse, points, globe, moon, monkey, meter, hamburger

# ======================
# 🧰 HELPERS
# ======================
function load_wallpapers
    find $wallpaper_dir -type f \( -iname '*.jpg' -o -iname '*.png' -o -iname '*.jpeg' \)
end

function apply_wallpaper -a wallpaper
    set filename (path basename $wallpaper)

    gum spin --spinner $spinner --title "Applying wallpaper to GNOME..." -- fish -c "
        gsettings set org.gnome.desktop.background picture-uri 'file://$wallpaper'
        gsettings set org.gnome.desktop.background picture-uri-dark 'file://$wallpaper'
    "

    echo "🖼️ Wallpaper set to: $filename"
end

function generate_theme -a wallpaper

    # Other available schemes (commented out by default)
    # matugen image $wallpaper -t scheme-content --show-colors
    # matugen image $wallpaper -t scheme-expressive --show-colors
    matugen image $wallpaper -t scheme-fidelity
    # matugen image $wallpaper -t scheme-fruit-salad --show-colors
    # matugen image $wallpaper -t scheme-monochrome --show-colors
    # matugen image $wallpaper -t scheme-neutral --show-colors
    # matugen image $wallpaper -t scheme-rainbow --show-colors
end

function set_folder_icons
    set script_dir (path dirname (status --current-filename))
    gum spin --spinner moon --title "Setting folder icon theme..." -- $script_dir/folder_icon.sh
end

# ======================
# 🎨 GNOME THEME ENGINE
# ======================

function apply_gnome_settings

    # --- theme reload ---
    # dconf write /org/gnome/shell/extensions/user-theme/name "'default'"
    # dconf write /org/gnome/shell/extensions/user-theme/name "'Material-Gnome'"

    # --- pop shell ---
    set pop_hint_color (cat ~/.config/colors/pop-shell.css | string trim)
    dconf write /org/gnome/shell/extensions/pop-shell/hint-color-rgba "'$pop_hint_color'"

    # --- O-Tiling ---
    dconf write /org/gnome/shell/extensions/o-tiling/hint-color-rgba "'$pop_hint_color'"

    # --- clock ---
    set clock_file ~/.config/colors/clock-color.css
    set time_rgba (sed -n '1p' $clock_file)
    set date_rgba (sed -n '2p' $clock_file)
    set cmd_rgba  (sed -n '3p' $clock_file)
    set hint_rgba (sed -n '4p' $clock_file)

    dconf write /org/gnome/shell/extensions/customize-clock-on-lockscreen/time-font-color "'$time_rgba'"
    dconf write /org/gnome/shell/extensions/customize-clock-on-lockscreen/date-font-color "'$date_rgba'"
    dconf write /org/gnome/shell/extensions/customize-clock-on-lockscreen/command-output-font-color "'$cmd_rgba'"
    dconf write /org/gnome/shell/extensions/customize-clock-on-lockscreen/hint-font-color "'$hint_rgba'"

    # ======================
    # 📦 SPACE BAR COLORS (FIXED)
    # ======================

    set space_file ~/.config/colors/space-bar.css

    while read -l line
        set line (string trim $line)

        string match -q "#*" $line; and continue
        test -z "$line"; and continue

        set parts (string split '=' $line)
        set key (string trim $parts[1])
        set value (string trim $parts[2])

        switch $key
            case active_bg
                set active_bg $value
            case active_fg
                set active_fg $value
            case inactive_fg
                set inactive_fg $value
        end
    end < $space_file

    dconf write /org/gnome/shell/extensions/space-bar/appearance/active-workspace-background-color $active_bg
    dconf write /org/gnome/shell/extensions/space-bar/appearance/active-workspace-text-color $active_fg
    dconf write /org/gnome/shell/extensions/space-bar/appearance/inactive-workspace-text-color $inactive_fg

    # --- search-light ---
    python ~/Scripts/normalize_rgb.py

    set search_file ~/.config/colors/search-light.css
    set foreground ""
    set background ""

    while read -l line
        set line (string trim $line)
        string match -q "#*" $line; and continue
        test -z "$line"; and continue

        set parts (string split '=' $line)
        set key (string trim $parts[1])
        set value (string trim $parts[2])

        switch $key
            case foreground; set foreground $value
            case background; set background $value
        end
    end < $search_file

    dconf write /org/gnome/shell/extensions/search-light/background-color "($background, 0.75)"
    dconf write /org/gnome/shell/extensions/search-light/text-color "($foreground, 1.0)"
    dconf write /org/gnome/shell/extensions/search-light/panel-icon-color "($foreground, 1.0)"
    dconf write /org/gnome/shell/extensions/search-light/border-color "($foreground, 1.0)"

    # ======================
    # 🎧 Dynamic Music Pill
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

# ======================
# 🎛️ MAIN MENU
# ======================

set choice (gum choose --cursor "👉" --header "Pick your vibe" \
    "📂 Pick Wallpaper" "🎲 Random Wallpaper")

set wallpaper_paths (load_wallpapers)

switch $choice
    case "📂 Pick Wallpaper"

        set wallpaper (env \
            MESA_DEBUG_OVERRIDE=0 \
            MESA_LOG_LEVEL=0 \
            GSK_RENDERER=gl \
            VK_INSTANCE_LAYERS= \
            VK_LAYER_PATH= \
            python3 ~/Scripts/wallpicker.py "$wallpaper_dir" 2>/dev/null | string trim)

        if test -z "$wallpaper"
            echo "No wallpaper selected, exiting."
            exit 1
        end

    case "🎲 Random Wallpaper"
        set wallpaper (random choice $wallpaper_paths)
end

# ======================
# 🌐 DARK READER SYNC
# ======================

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
# 🚀 EXECUTION PIPELINE
# ======================

if test -n "$wallpaper"
    # Apply all changes in sequence:
    # 1. Set the wallpaper
    # 2. Generate color scheme
    # 3. Update folder icons
    # 4. Apply GNOME settings
    apply_wallpaper $wallpaper
    generate_theme $wallpaper
    set_folder_icons
    apply_gnome_settings
    sync_darkreader
end
