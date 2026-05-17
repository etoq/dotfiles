#!/bin/bash

# Получаем процент громкости и статус (Mute) из wpctl (PipeWire)
VOLUME_INFO=$(wpctl get-volume @DEFAULT_AUDIO_SINK@)

if echo "$VOLUME_INFO" | grep -q "MUTED"; then
    echo "%{F#d35f5e}  %{F-}"
    exit 0
fi

VOLUME=$(echo "$VOLUME_INFO" | awk '{print int($2 * 100)}')

# Проверяем, подключено ли Bluetooth аудио устройство через pactl
if pactl list sinks | grep -A 15 "State: RUNNING" | grep -q "bluez"; then
    # Иконка наушников, если активен Bluetooth профиль
    ICON="%{F#d35f5e} %{F-}"
else
    # Обычные иконки громкости в зависимости от уровня
    if [ "$VOLUME" -le 30 ]; then
        ICON="%{F#d35f5e}   %{F-}"
    else
        ICON="%{F#d35f5e}   %{F-}"
    fi
fi

echo "${ICON}${VOLUME}%"

