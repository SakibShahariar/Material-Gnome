#!/usr/bin/env fish

set wallpaper_dir "/mnt/data/Wallpapers"

# Show options immediately
set choice (gum choose --cursor "👉" --header "Pick your vibe" \
    "📂 Pick Wallpaper" "🎲 Random Wallpaper")

# Load wallpaper paths asynchronously
set wallpaper_paths (find $wallpaper_dir -type f \( -iname '*.jpg' -o -iname '*.png' -o -iname '*.jpeg' \)) &

# Wait for wallpaper paths to be ready (without blocking the menu)
wait

# Create a mapping of basename to full path
set -l wallpaper_map
for path in $wallpaper_paths
    set filename (basename $path)
    set wallpaper_map $wallpaper_map $filename $path
end

switch $choice
    case "📂 Pick Wallpaper"
        # Use Zenity to invoke the Nautilus file picker, open in the correct dir
        set wallpaper (zenity --file-selection --title="Select a Wallpaper" --file-filter="*.jpg *.jpeg *.png" --filename="$wallpaper_dir/")

        # Exit if no wallpaper is selected
        if test -z "$wallpaper"
            echo "No wallpaper selected, exiting."
            exit 1
        end

        set filename (basename $wallpaper)
        echo "You picked: $filename"
    case "🎲 Random Wallpaper"
        # Pick a random wallpaper from the list
        set wallpaper (printf "%s\n" $wallpaper_paths | shuf -n 1)
        set filename (basename $wallpaper)
        echo "Random pick: $filename"
end

# Apply wallpaper with GNOME gsettings
if test -n "$wallpaper"
    gum spin --spinner globe --title "Applying wallpaper to GNOME..." -- fish -c "
        gsettings set org.gnome.desktop.background picture-uri 'file://$wallpaper';
        gsettings set org.gnome.desktop.background picture-uri-dark 'file://$wallpaper'
    "
    echo "🖼️ Wallpaper set to: $filename"

    # 🌈 Generate theme with matugen
    matugen image $wallpaper -v
    # matugen image $wallpaper -t scheme-content --show-colors
    # matugen image $wallpaper -t scheme-expressive --show-colors
    # matugen image $wallpaper -t scheme-fidelity --show-colors
    # matugen image $wallpaper -t scheme-fruit-salad --show-colors
    # matugen image $wallpaper -t scheme-monochrome --show-colors
    # matugen image $wallpaper -t scheme-neutral --show-colors
    # matugen image $wallpaper -t scheme-rainbow --show-colors

    kitty @ set-colors --all ~/.config/kitty/colors.conf
    fish ~/Scripts/remove_hash.fish

        # ADDED: Call folder icon script after all other operations
    # Get directory of this script
    set script_dir (dirname (status --current-filename))

    # Execute folder_icon.fish from the same directory
    gum spin --spinner moon --title "Setting folder icon theme..." -- $script_dir/folder_icon.fish

end

dconf write /org/gnome/shell/extensions/user-theme/name "'default'"
dconf write /org/gnome/shell/extensions/user-theme/name "'Material-Gnome'"
