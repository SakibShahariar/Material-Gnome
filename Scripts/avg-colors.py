#!/usr/bin/env python3
from pathlib import Path
import re

# ---------- Settings ----------
color_file = Path.home() / ".config/colors/fix.css"
targets = [
    "/home/sakib/.config/gtk-4.0/colors.css",
    "/home/sakib/.config/gtk-3.0/colors.css",
    "/home/sakib/.config/kitty/themes/colors.conf",
    "/home/sakib/.themes/Material-Gnome/gnome-shell/gnome-shell.css",
    "/home/sakib/.themes/Material-Gnome/gtk-3.0/colors.css",
    "/home/sakib/.themes/Material-Gnome/gtk-4.0/colors.css",
    "/home/sakib/.config/qt5ct/colors/colors.conf",
    "/home/sakib/.config/qt6ct/colors/colors.conf",
    "/home/sakib/.zen/czfvdv64.Default (release)/chrome/colors.css"
]

color_vars = ["color0"]  # add more if needed
# ------------------------------

def parse_hex(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0,2,4))

def avg_colors(c1,c2):
    return tuple(round((a+b)/2) for a,b in zip(c1,c2))

def to_hex(rgb):
    return "#{:02x}{:02x}{:02x}".format(*rgb)

# Read colors from fix.css
with open(color_file) as f:
    lines = [l.strip() for l in f if l.strip()]
    if len(lines) < 2:
        raise SystemExit("Need two colors in fix.css")
    old_hex = lines[0]
    new_hex = to_hex(avg_colors(parse_hex(lines[0]), parse_hex(lines[1])))
    new_r, new_g, new_b = [int(new_hex[i:i+2],16) for i in (1,3,5)]
    r, g, b = parse_hex(old_hex)

# regex patterns
hex_pat = re.compile(re.escape(old_hex), re.IGNORECASE)
rgba_pat = re.compile(
    r"rgba\(\s*{r}\s*,\s*{g}\s*,\s*{b}\s*,\s*([^)]+)\)".format(r=r,g=g,b=b),
    re.IGNORECASE,
)

def make_color_pat(var, channel):
    return re.compile(rf"(--{var}-{channel}\s*:\s*)(\d+)")

for path in targets:
    text = Path(path).read_text()

    # replace hex
    text = hex_pat.sub(new_hex, text)

    # replace rgba RGB values but keep alpha
    def rgba_repl(m):
        return f"rgba({new_r},{new_g},{new_b},{m.group(1)})"
    text = rgba_pat.sub(rgba_repl, text)

    # replace --colorX-r/g/b only if they exist
    for var in color_vars:
        for channel, val in zip(["r","g","b"], [new_r,new_g,new_b]):
            pat = make_color_pat(var, channel)
            if pat.search(text):
                text = pat.sub(lambda m, v=val: f"{m.group(1)}{v}", text)

    Path(path).write_text(text)
