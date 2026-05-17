#!/bin/bash
# Compositor с прозрачностью:
picom --daemon &
# Панель eww:
eww daemon && eww open bar &
# Обои (случайные из папки):
~/.local/bin/set-wallpaper &
# Notification daemon:
dunst &
# NetworkManager апплет (без иконки — только backend):
nm-applet --no-agent &
# Bluetooth:
blueman-applet &
# XDG autostart:
dex --autostart --environment bspwm &

xsettingsd &
