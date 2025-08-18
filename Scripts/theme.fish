#!/usr/bin/env fish

# ------------------------
# Theme switcher for Matugen
# ------------------------

# Base theme directory
set theme_dir ~/.config/matugen/themes

# Pick a theme interactively with gum
set themes (for t in $theme_dir/*/; echo (basename $t); end)
set selected_theme (gum choose $themes)

if test -z "$selected_theme"
    echo "No theme selected. Exiting."
    exit 1
end

set theme_path $theme_dir/$selected_theme
echo "Applying theme: $selected_theme"

# Map actual filenames in theme folder to destination paths and optional post_hook
set -l files_map \
"kitty.conf|~/.config/kitty/themes/colors.conf|kitty +kitten themes --reload-in=all colors" \
"clock-rs-conf.toml|~/.config/clock-rs/conf.toml" \
"sherlock.css|~/.config/sherlock/main.css" \
"starship.toml|~/.config/starship.toml" \
"accent-color.css|~/.config/accent-color.css" \
"gtk3-colors.css|~/.config/gtk-3.0/colors.css" \
"gtk4-colors.css|~/.config/gtk-4.0/colors.css" \
"micro-colors.micro|~/.config/micro/colorschemes/colors.micro" \
"qtct-colors.conf|~/.config/qt5ct/colors/colors.conf" \
"qtct-colors.conf|~/.config/qt6ct/colors/colors.conf" \
"mpv-uosc.conf|~/.config/mpv/script-opts/uosc.conf" \
"mpv-config.conf|~/.config/colors.json" \
"colors.json|~/.config/mpv/mpv.conf" \
"gnome-shell.css|~/.themes/Material-Gnome/gnome-shell/gnome-shell.css" \
"btop.theme|~/.config/btop/themes/matugen.theme" \
"cava-colors.ini|~/.config/cava/themes/cava|pkill -USR1 cava" \
"yazi.toml|~/.config/yazi/theme.toml" \
"zen_colors.css|~/.zen/czfvdv64.Default (release)/chrome/colors.css" \
"zen-accent.js|~/.zen/czfvdv64.Default (release)/user.js"

# Loop through each file and copy it safely
for entry in $files_map
    set fields (string split "|" $entry)
    set file_name $fields[1]
    set dest $fields[2]
    set hook ""
    if count $fields > 2
        set hook $fields[3]
    end

    set src "$theme_path/$file_name"

    if test -f $src
        # Expand ~ in destination
        set dest (string replace -r "^~" $HOME $dest)
        # Ensure destination directory exists
        mkdir -p (dirname $dest)
        # Replace file content safely (works with symlinks)
        cp --remove-destination $src $dest
        echo "Copied $file_name -> $dest"

        # Run post_hook if defined
        if test -n "$hook"
            eval $hook
            echo "Ran post_hook for $file_name"
        end
    else
        echo "Skipping $file_name: not found in theme folder."
    end
end

echo "Theme '$selected_theme' applied successfully!"
