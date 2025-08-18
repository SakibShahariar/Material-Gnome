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
set -l base_paths ~/Scripts /usr/bin /usr/local/bin /home/sakib/.local/bin /home/sakib/.cargo/bin /usr/local/sbin ~/sbin
set -l go_paths (go env GOPATH)/bin
set -l custom_paths /home/sakib/programms/hellwal /home/sakib/.npm-global/bin ~/.config/rofi/scripts

# Deduplicate and export
set -gx PATH (string match -r -v '^$' (string join \n $base_paths $go_paths $custom_paths | sort -u))

# ======================
# 🎛️ QT/THEME SETTINGS
# ======================
set -gx QT_SCALE_FACTOR 1.0
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
alias sudo="doas"
alias in='doas dnf install'
alias re='doas dnf remove'
alias remove="doas dnf autoremove"
alias grub_refresh="doas grub2-mkconfig -o /boot/grub2/grub.cfg"
alias grub_edit="doas micro /etc/default/grub"

alias weather='curl wttr.in'
alias starwars="telnet towel.blinkenlights.nl"

# ======================
# 📁 FILE MANAGEMENT
# ======================
alias ls='lsd -a $argv'
alias yy="yazi"
alias yys="doas yazi"
alias disk="dysk"

# ======================
# 🎨 CONFIGURATION
# ======================
alias fe="micro ~/.config/fish/config.fish"
alias fr="source ~/.config/fish/config.fish"
alias ke="micro ~/.config/kitty/kitty.conf"

# ======================
# 🧩 DEVELOPMENT
# ======================
alias dotgit="git --git-dir=$HOME/.dotfiles_repo/ --work-tree=$HOME"

# ======================
# 🎮 ENTERTAINMENT
# ======================
alias anime="fastanime --icons --fzf --preview anilist"
alias clock="tty-clock -c -C 2"
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

# ======================
# ✨ FUNCTIONS
# ======================
# Smart sudo that uses micro instead of nano
function sudo
    if test $argv[1] = 'nano'
        command sudo micro $argv[2..-1]
    else
        command sudo $argv
    end
end

# Typewriter effect for text
function typewrite
    for arg in $argv
        for i in (seq (string length $arg))
            echo -n (string sub -s $i -l 1 $arg)
            sleep 0.01
        end
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

# ======================
# 🖥️ INTERACTIVE SESSION
# ======================
if status is-interactive
    fastfetch --config ~/.config/fastfetch/pre.jsonc
end
