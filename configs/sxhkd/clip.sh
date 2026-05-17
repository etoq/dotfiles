#!/usr/bin/env bash

# Удаляем старый временный файл, если он есть
rm -f /tmp/clip_result

# Открываем kitty с fzf и пишем результат выбора в файл
kitty --class clipboard-manager --override window_padding_width=15 --override background=#0D1117 \
  -e bash -c 'greenclip print | fzf --cycle --prompt "  Copy > " --color "bg:#0D1117,bg+:#1F2937,fg:#F8F8F2,hl:#8BE9FD,pointer:#8BE9FD" > /tmp/clip_result'

# Если файл существует и он НЕ пустой (выбрали текст, а не нажали Esc)
if [ -s /tmp/clip_result ]; then
    # Копируем текст в буфер обмена X11
    cat /tmp/clip_result | xclip -selection clipboard -in
    
    # Опционально: очищаем за собой
    rm -f /tmp/clip_result
fi
