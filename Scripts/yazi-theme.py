#!/usr/bin/env python3

palette_file = "/home/sakib/.config/yazi/colors.txt"
template_file = "/home/sakib/.config/yazi/themes.toml"
output_file = "/home/sakib/.config/yazi/theme.toml"

# Load palette
palette = {line.split()[0]: line.split()[1].rstrip(';') 
           for line in open(palette_file) if ' ' in line.strip()}

# Process template
with open(template_file) as f_in, open(output_file, 'w') as f_out:
    for line in f_in:
        for key, val in palette.items():
            line = line.replace(f'"{key}"', f'"{val}"')
        f_out.write(line)

print(f"✅ theme.toml compiled from {len(palette)} colors")
