<h1 align="center"> Material-Gnome (Dotfiles) </h3>

<p align="center">
  <a href="https://github.com/SakibShahariar/Material-Gnome/stargazers">
    <img src="https://img.shields.io/github/stars/SakibShahariar/Material-Gnome?style=for-the-badge&logo=starship&color=4285F4&logoColor=white&labelColor=1F1F1F">
  </a>
  <a href="https://github.com/SakibShahariar/Material-Gnome/issues">
    <img src="https://img.shields.io/github/issues/SakibShahariar/Material-Gnome?style=for-the-badge&logo=gitbook&color=AA66CC&logoColor=white&labelColor=1F1F1F">
  </a>
  <a href="https://github.com/SakibShahariar/Material-Gnome/graphs/contributors">
    <img src="https://img.shields.io/github/contributors/SakibShahariar/Material-Gnome?style=for-the-badge&logo=github&color=00BFA5&logoColor=white&labelColor=1F1F1F">
  </a>
</p>

A full Matugen-powered, wallpaper-driven theming pipeline for GNOME — generates a consistent Material color palette from your wallpaper and pushes it across the desktop, terminal apps, media players, Qt apps, the file manager, and the browser.

This repo is built on top of the [Material-Gnome theme](https://github.com/SakibShahariar/material-gnome-theme) (GTK3/GTK4/Shell theme) — **that theme is a required dependency**, not optional.

---

## 📸 Screenshots

### 🔲 Without Blur
![Material-Gnome](https://github.com/user-attachments/assets/2033fb23-3fcc-4a13-94a2-32127f342c13)

### 🌀 With Blur
![Material-Gnome-blur](https://github.com/user-attachments/assets/d19b7e54-d1ad-48a0-8d92-b30d977187c1)

### 🌀 Wallpicker
https://github.com/user-attachments/assets/6cff0cf5-478b-481b-842e-4e49608963d0

---

## ✨ What it does

Run one script, pick a wallpaper, and the whole system re-themes itself:

- Sets the wallpaper (dark mode only)
- Generates a Material color palette from the wallpaper via [`matugen`](https://github.com/InioX/matugen)
- Applies the palette to GTK3/GTK4/GNOME Shell (via Material-Gnome)
- Recolors folder icons to match
- Pushes the palette into GNOME Shell extensions (O-Tiling, Space Bar, Search Light, etc.)
- Syncs the palette into Dark Reader (browser extension) and Zen Browser
- Themes terminal/CLI tools, media players, and Qt apps to match

---

## 📂 Repository Structure

```text
Material-Gnome/
├── matugen/            # Matugen config, color templates, and premade theme JSONs
├── Scripts/             # Orchestration scripts (matugen.fish is the main entry point)
├── gtk-3.0/             # GTK3 theme files (from material-gnome-theme)
├── gtk-4.0/             # GTK4/Libadwaita theme files (from material-gnome-theme)
├── colors/              # Generated CSS color files for GNOME extensions
├── colors.json          # Generated raw color palette
├── kitty/                # Kitty terminal theme
├── btop/                 # btop theme
├── cava/                 # cava (audio visualizer) theme + shaders
├── mpv/                  # mpv media player theme/config
├── qt5ct/ qt6ct/         # Qt app theming
├── Kvantum/              # Kvantum Qt theme engine config
├── yazi/                 # yazi file manager theme + plugins
├── micro/                # micro text editor theme
├── fish/                  # fish shell config
├── starship.toml          # Starship prompt config
├── clock-rs/               # clock-rs config
└── zen.css                  # Zen Browser theme
```

---

## ✅ Requirements

> ⚠️ **Tested only on Fedora.** Other distros may need adjustments (package names, paths, etc.) — not yet verified.

### CLI dependencies
- [`matugen`](https://github.com/InioX/matugen) — palette generation
- [`gum`](https://github.com/charmbracelet/gum) — terminal UI prompts used by the script
- `jq` — JSON parsing
- `sqlite3` — used to sync colors into Dark Reader's local storage
- `python3` — wallpaper picker and color normalization scripts
- `fish` shell — scripts are written in fish

### GNOME Shell Extensions
- [**O-Tiling**](https://github.com/oliwebd/o-tiling)
- [**Space Bar**](https://extensions.gnome.org/extension/5090/space-bar/)
- [**Vitals**](https://extensions.gnome.org/extension/1460/vitals/)
- [**Search Light**](https://extensions.gnome.org/extension/5489/search-light/)
- [**Logo Menu**](https://extensions.gnome.org/extension/4451/logo-menu/)

> The script also includes support for Pop Shell, Dynamic Music Pill, and Clock on Lockscreen — these are optional and not part of the current core rice, but the hooks are there if you use them.

### Theme dependency
- [Material-Gnome theme](https://github.com/SakibShahariar/material-gnome-theme) — required, provides the base GTK3/GTK4/Shell stylesheets this pipeline themes.

---

## 🚀 Installation

This repo is managed with [GNU Stow](https://www.gnu.org/software/stow/).

```bash
git clone https://github.com/SakibShahariar/Material-Gnome.git ~/.dotfiles
cd ~/.dotfiles
stow .
```

This symlinks each top-level folder into your `~/.config` (and home directory, for things like `fish`) following Stow's standard layout.

Make sure you've also installed the [Material-Gnome theme](https://github.com/SakibShahariar/material-gnome-theme) separately first, since this repo depends on it.

---

## 📦 Flatpak Application Support

Flatpak applications run in isolated sandboxes and cannot access your local theme/config directories by default. To make them follow your theme, run:

1. **Grant filesystem permission:**
```bash
flatpak override --user --filesystem=$HOME/.themes:ro
```

2. **Force the theme environment variable:**
```bash
flatpak override --user --env=GTK_THEME=Material-Gnome
```

---

## 🎨 Usage

There are two independent things you can change: the **color theme** and the **top bar layout**. Mix and match either.

### Color theme

Two ways to set the palette — pick one:

**Generate from a wallpaper:**

```bash
fish ~/Scripts/matugen.fish
```

You'll be prompted to:
1. **Pick Wallpaper** — browse wallpapers from your configured wallpaper directory
2. **Random Wallpaper** — let it choose one for you

From there, it automatically:
- Sets the wallpaper (dark mode background)
- Generates the palette with Matugen
- Applies folder icon colors
- Pushes the new colors into GNOME Shell, your required extensions, terminal apps, Qt apps, and the browser

**Or apply a premade theme:**

```bash
python3 ~/Scripts/theme-switcher.py
```

Lets you pick from the premade palettes in `matugen/themes/` (via `theme-wallpicker.py`), then calls `apply-theme.fish` internally to apply the chosen theme across the system.

### Top bar layout

Independent of the color theme — switch the GNOME Shell top bar style:

```bash
bash ~/Scripts/gnome-layout-switcher.sh
```

---

## 📜 Scripts Reference

| Script | Purpose |
|---|---|
| `matugen.fish` | Main entry point — wallpaper-based theme generation |
| `theme-switcher.py` | Main entry point — applies a premade theme |
| `gnome-layout-switcher.sh` | Switches the GNOME Shell top bar layout |
| `apply-theme.fish` | Called internally by `theme-switcher.py` to apply the selected theme |
| `theme-wallpicker.py` | Picker UI for choosing a premade theme |
| `wallpicker.py` | Picker UI for choosing a wallpaper |
| `gnome_logout.py` | Simple logout menu |
| `update-boost.js` | Syncs the generated theme into Zen Browser (called by `matugen.fish`) |
| `matugen_pick.fish` | Reserved for future use |
| `update.fish` | Auto-update helper for Fedora — superseded by [topgrade](https://github.com/topgrade-rs/topgrade), which is recommended instead |

---

## ⚙️ Configuration

- **Wallpaper directory:** set at the top of `Scripts/matugen.fish` (`$wallpaper_dir`)
- **Matugen scheme:** also configurable in `matugen.fish` (`generate_theme` function) — defaults to `scheme-fidelity`, with other schemes available commented out (`scheme-content`, `scheme-expressive`, `scheme-monochrome`, etc.)
- **Premade themes:** browse `matugen/themes/` for a large set of ready-made palettes you can apply without generating from a wallpaper

---

## 📜 License

This project is licensed under the **GPL-3.0 License** — see the [LICENSE](LICENSE) file for details.

This repo also bundles a few third-party components under their own licenses — see [THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md) for details.
