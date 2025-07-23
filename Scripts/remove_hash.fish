#!/usr/bin/env fish

set file ~/.config/mpv/script-opts/uosc.conf
set line_num 154

# Read file into an array of lines
set lines (cat $file)

# Check if the line exists
if test (count $lines) -ge $line_num
    # Nuke all '#' symbols from that specific line
    set lines[$line_num] (string replace -a '#' '' -- $lines[$line_num])

    # Write it back to the file
    printf "%s\n" $lines > $file
    # echo "Line $line_num is now hashless. No trace of # remains 🧼"
else
    # echo "Bro, line $line_num doesn’t exist. Your file’s playing games."
end
