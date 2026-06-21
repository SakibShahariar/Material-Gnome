# Import dynamic Matugen color theme
if test -f ~/.config/fish/matugen_colors.fish
    source ~/.config/fish/matugen_colors.fish
end

# ======================
# 🖥️ CORE SHELL SETTINGS
# ======================
set -g fish_greeting ""                # Disable Fish's default welcome message
set -gx EDITOR micro                   # Default editor
set -gx MICRO_TRUECOLOR 1              # Truecolor for micro
alias nano='micro'                     # Replace nano calls with micro

# ======================
# 📁 PATH CONFIGURATION
# ======================
fish_add_path ~/Scripts
fish_add_path /usr/bin
fish_add_path /usr/local/bin
fish_add_path /home/sakib/.local/bin
fish_add_path /home/sakib/.cargo/bin
fish_add_path /usr/local/sbin
fish_add_path ~/sbin
fish_add_path /home/sakib/programms/hellwal
fish_add_path /home/sakib/.npm-global/bin
fish_add_path ~/.config/rofi/scripts

# Only add Go path if Go exists
if type -q go
    fish_add_path (go env GOPATH)/bin
end

# ======================
# 🎛️ QT/THEME SETTINGS
# ======================
set -gx QT_SCALE_FACTOR 0.80
set -gx QT_QPA_PLATFORM wayland
set -gx QT_QPA_PLATFORMTHEME qt5ct
set -gx QT_QPA_PLATFORMTHEME_QT6 qt6ct

# ======================
# 🚀 TOOL INTEGRATION
# ======================
starship init fish | source
zoxide init fish | source

# ======================
# ⌨️ KEY BINDINGS
# ======================
bind \cf 'fzf_files'

# ======================
# 🛠️ SYSTEM ALIASES
# ======================

alias in='doas dnf install'
alias re='doas dnf remove'
alias grub_refresh="doas grub2-mkconfig -o /boot/grub2/grub.cfg"
alias grub_edit="doas micro /etc/default/grub"

alias weather='curl wttr.in'
alias starwars="telnet towel.blinkenlights.nl"

# ======================
# 📁 FILE MANAGEMENT
# ======================
# alias ls='lsd -a $argv'
alias yy="yazi"
alias yys="doas yazi"
alias disk="dysk"

# ======================
# 🎨 CONFIGURATION
# ======================
alias fe="micro ~/.config/fish/config.fish"
alias fr="set -g _fish_reloading 1; source ~/.config/fish/config.fish; set -e _fish_reloading"
alias ke="micro ~/.config/kitty/kitty.conf"

# ======================
# 🧩 DEVELOPMENT
# ======================
alias dotgit="git --git-dir=$HOME/.dotfiles_repo/ --work-tree=$HOME"

# ======================
# 🎮 ENTERTAINMENT
# ======================
alias anime="fastanime --icons --fzf --preview anilist"
alias clock="clock-rs"
alias ask="lumo"

# ======================
# 🖼️ DESKTOP
# ======================
alias rr="random-wallpaper-matugen.fish"
alias rw="matugen-picker.fish"
alias ss="hellwal.fish"
alias mm="matugen.fish"

# ======================
# 🧰 UTILITIES
# ======================
alias ff="fastfetch"
alias kotofetch="distrobox enter arch -- kotofetch"

# ======================
# 📦 DISTROBOX 2.x+ PATH & HELPERS
# ======================
# Make sure the new Distrobox binary in /usr/local/sbin is used
set -U fish_user_paths /usr/local/sbin $fish_user_paths

# Helper function to launch GUI apps from 'arch' Distrobox container
function dbx-app
    if test (count $argv) -eq 0
        echo "Usage: dbx-app <app> [additional args]"
        return 1
    end
    set app $argv[1]
    set args $argv[2..-1]
    distrobox-enter --name arch --bind /run/media:/run/media --gui $app $args
end

# Example alias for Media Writer
alias mediawriter='dbx-app mediawriter'

# ======================
# ✨ FUNCTIONS
# ======================
# Smart sudo that uses doas and replaces nano with micro


# Typewriter effect for text
function typewrite
    # Join arguments with spaces to form a single string
    set full_text (string join ' ' $argv)
    # Print character by character
    for char in (string split '' -- $full_text)
        echo -n $char
        sleep 0.01
    end
    echo ""
end

# Yazi file manager with directory tracking
function y
    set tmp (mktemp -t "yazi-cwd.XXXXXX")
    yazi $argv --cwd-file="$tmp"
    if set cwd (command cat -- "$tmp"); and [ -n "$cwd" ]; and [ "$cwd" != "$PWD" ]
        builtin cd -- "$cwd"
    end
    rm -f -- "$tmp"
end

# Fuzzy file search and edit
function fzf_files
    set file (fzf)
    if test -n "$file"
        micro $file
    end
end

# sudo → doas
function sudo
    doas $argv
end

# Watch for Matugen wallpaper/theme changes universally
function on_matugen_change --on-variable MATUGEN_RELOAD_TRIGGER
    set -g _fish_reloading 1
    if test -f ~/.config/fish/matugen_colors.fish
        source ~/.config/fish/matugen_colors.fish
    end
    set -e _fish_reloading
end

# ======================
# 🖥️ INTERACTIVE SESSION
# ======================
if status is-interactive
    # Only run fastfetch if we aren't actively reloading the shell
    if not set -q _fish_reloading
        fastfetch --config ~/.config/fastfetch/pre.jsonc
    end
end

# uv
fish_add_path "/home/sakib/.local/bin"

# opencode
fish_add_path /home/sakib/.opencode/bin
umask 007
