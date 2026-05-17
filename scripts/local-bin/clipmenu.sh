#!/usr/bin/env bash

# Открываем kitty с fzf и сохраняем результат в переменную
# Важно: kitty должен вернуть stdout, поэтому используем подпроцесс
selected=$(kitty --class clipboard-manager --override window_padding_width=15 --override background=#0D1117 sh -c 'greenclip print | fzf --cycle --prompt "  Copy > " --color "bg:#0D1117,bg+:#1F2937,fg:#F8F8F2,hl:#8BE9FD,pointer:#8BE9FD"')

# Если выбор не пустой — копируем
if [ -n "$selected" ]; then
    printf "%s" "$selected" | xsel -b -i
fi
