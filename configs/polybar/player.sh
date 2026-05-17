#!/bin/bash

STATUS=$(playerctl status 2>/dev/null)

if [ "$STATUS" = "Playing" ]; then
    # Иконка паузы + название (только когда играет)
    echo " $(playerctl metadata title)"
    rm -f /tmp/player_pause_time
elif [ "$STATUS" = "Paused" ]; then
    if [ ! -f /tmp/player_pause_time ]; then
        date +%s > /tmp/player_pause_time
    fi
    
    PAUSE_START=$(cat /tmp/player_pause_time)
    NOW=$(date +%s)
    DIFF=$((NOW - PAUSE_START))

    if [ $DIFF -lt 600 ]; then
        # Иконка плея + название (если прошло меньше 5 минут)
        echo " $(playerctl metadata title)"
    else
        echo ""
    fi
else
    echo ""
    rm -f /tmp/player_pause_time
fi

