#!/usr/bin/env bash

# Открываем kitty с fzf и сохраняем результат в переменную
# Важно: kitty должен вернуть stdout, поэтому используем подпроцесс
selected=$(kitty --class clipboard-manager --override window_padding_width=15 --override background=#080D10 sh -c 'greenclip print | fzf --cycle --prompt "  Copy > " --color "bg:#080D10,bg+:#183039,fg:#C5D6D8,hl:#4DDDD5,pointer:#4DDDD5"')

# Если выбор не пустой — копируем
if [ -n "$selected" ]; then
    printf "%s" "$selected" | xsel -b -i
fi
