#!/bin/sh
# Configure both layouts once; XKB handles Alt+Shift without a hotkey daemon.
exec setxkbmap -layout us,ru -option grp:alt_shift_toggle
