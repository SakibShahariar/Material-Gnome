# ======================
# 🖥️ CORE SHELL SETTINGS
# ======================
set -g fish_greeting ""           # Disable Fish's default welcome message
set -gx EDITOR micro              # Set micro as default editor for all programs
export MICRO_TRUECOLOR=1          # Enable truecolor support in micro editor
alias nano='micro'                # Replace nano calls with micro system-wide

# ======================
# 📁 PATH CONFIGURATION
# ======================
set -e PATH                       # Clear existing PATH completely
set -Ux PATH $PATH ~/Scripts /usr/bin /usr/local/bin /home/sakib/.local/bin /home/sakib/.cargo/bin /usr/local/sbin ~/sbin

# Go language environment setup
set -x GOPATH (go env GOPATH)     # Set Go workspace location
set -x GOBIN $GOPATH/bin          # Set Go binaries directory
set -x PATH $PATH $GOBIN          # Add Go binaries to PATH

# Custom project path addition
set -gx PATH /home/sakib/programms/hellwal $PATH  # Add hellwal project to PATH
set -U fish_user_paths $fish_user_paths ~/.config/rofi/scripts
set -Ux PATH $PATH /home/sakib/.npm-global/bin

# ======================
# 🎛️ QT/THEME SETTINGS
# ======================
# QT application scaling and theming configuration
set -Ux QT_SCALE_FACTOR 1.0       # Set 80% scaling for all QT applications
set -Ux QT_QPA_PLATFORM wayland    # Prefer Wayland display protocol for QT
set -Ux QT_QPA_PLATFORMTHEME qt5ct # Use qt5ct for QT5 application theming
set -Ux QT_QPA_PLATFORMTHEME_QT6 qt6ct  # Use qt6ct for QT6 application theming

# ======================
# 🚀 TOOL INTEGRATION
# ======================
# Modern shell prompt with starship
starship init fish | source       # Initialize starship prompt

# Smarter directory navigation with zoxide
zoxide init fish | source         # Initialize zoxide (replaces 'cd')

# Uncomment if you need direct cargo environment sourcing
# source $HOME/.cargo/env         # Rust cargo environment (usually not needed)

# ======================
# ⌨️ KEY BINDINGS
# ======================
bind \cf 'fzf_files'              # Ctrl+F for fuzzy file search

# ======================
# 🛠️ SYSTEM ALIASES
# ======================
# Package management with doas
alias sudo="doas"                 # Replace sudo with doas
alias in='doas dnf install'       # Install packages
alias re='doas dnf remove'        # Remove packages
alias remove="doas dnf autoremove" # Remove unused packages
alias grub_refresh="doas grub2-mkconfig -o /boot/grub2/grub.cfg" # Update GRUB
alias grub_edit="doas nano /etc/default/grub"  # Edit GRUB config

# Network utilities
alias weather='curl wttr.in'                   # Get weather forecast
alias starwars="telnet towel.blinkenlights.nl" # Watch Star Wars ASCII animation

# ======================
# 📁 FILE MANAGEMENT
# ======================
# Modern ls replacement
alias ls='lsd -a $argv'           # Colorized ls with icons
alias yy="yazi"                   # Modern file manager
alias yys="doas yazi"             # Yazi with root privileges
alias disk="dysk"                 # Disk usage analyzer

# ======================
# 🎨 CONFIGURATION
# ======================
# Quick config editing
alias fe="micro ~/.config/fish/config.fish"  # Edit fish config
alias fr="source ~/.config/fish/config.fish" # Reload fish config
alias ke="micro ~/.config/kitty/kitty.conf"  # Edit kitty config

# ======================
# 🧩 DEVELOPMENT
# ======================
alias dotgit="git --git-dir=$HOME/.dotfiles_repo/ --work-tree=$HOME" # Dotfiles git repo

# ======================
# 🎮 ENTERTAINMENT
# ======================
alias anime="fastanime --icons --fzf --preview anilist" # Anime search tool
alias clock="tty-clock -c -C 2"   # Terminal clock
alias ask="lumo"                  # Lumo tool (purpose?)

# ======================
# 🖼️ DESKTOP
# ======================
alias rr="random-wallpaper-matugen.fish" # Random wallpaper
alias rw="matugen-picker.fish"           # Wallpaper color picker
alias ss="hellwal.fish"
alias mm="matugen.fish"

# ======================
# 🧰 UTILITIES
# ======================
alias ff="fastfetch"                     # System information tool

# ======================
# ✨ FUNCTIONS
# ======================
# Smart sudo that uses micro instead of nano
function sudo
    if test $argv[1] = 'nano'
        command sudo micro $argv[2..-1] # Replace 'sudo nano' with 'sudo micro'
    else
        command sudo $argv              # Normal sudo for other commands
    end
end

# Typewriter effect for text
function typewrite
    for arg in $argv
        for i in (seq (string length $arg))
            echo -n (string sub -s $i -l 1 $arg) # Print one character at a time
            sleep 0.01                           # Delay between characters
        end
    end
    echo ""                         # Newline at end
end

# Yazi file manager with directory tracking
function y
    set tmp (mktemp -t "yazi-cwd.XXXXXX") # Create temp file
    yazi $argv --cwd-file="$tmp"    # Launch yazi
    if set cwd (command cat -- "$tmp"); and [ -n "$cwd" ]; and [ "$cwd" != "$PWD" ]
        builtin cd -- "$cwd"        # Change directory if yazi reported one
    end
    rm -f -- "$tmp"                 # Clean up temp file
end

# Fuzzy file search and edit
function fzf_files
    set file (fzf)                  # Find file with fzf
    if test -n "$file"
        micro $file                 # Open selected file in micro
    end
end

# ======================
# 🖥️ INTERACTIVE SESSION
# ======================
if status is-interactive
    # Display system information on startup
    fastfetch --config ~/.config/fastfetch/pre.jsonc
end
