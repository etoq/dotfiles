#!/usr/bin/env bash
set -euo pipefail
mapfile -t connected < <(xrandr --query | awk '$2 == "connected" {print $1}')
(( ${#connected[@]} )) || exit 0
primary=$(xrandr --query | awk '$2 == "connected" && $3 == "primary" {print $1; exit}')
if [[ -z "$primary" ]]; then
    for output in "${connected[@]}"; do
        if [[ "$output" == eDP* || "$output" == LVDS* ]]; then primary="$output"; break; fi
    done
fi
primary=${primary:-${connected[0]}}
is_enabled() {
    xrandr --query | awk -v output="$1" '
      $1 == output && $2 == "connected" {
        for (i=3; i<=NF; i++) if ($i ~ /^[0-9]+x[0-9]+[+-][0-9]+[+-][0-9]+$/) active=1
      }
      END { exit !active }'
}
if is_enabled "$primary"; then
    xrandr --output "$primary" --primary
else
    xrandr --output "$primary" --auto --primary
fi
previous="$primary"
for output in "${connected[@]}"; do
    [[ "$output" == "$primary" ]] && continue
    if ! is_enabled "$output"; then
        xrandr --output "$output" --auto --right-of "$previous"
    fi
    previous="$output"
done
# Keep existing desktops and their windows; initialize only untouched defaults.
for output in "${connected[@]}"; do
    mapfile -t desktops < <(bspc query -D --names -m "$output")
    if (( ${#desktops[@]} == 1 )) && [[ "${desktops[0]}" == Desktop ]]; then
        if [[ "$output" == "$primary" ]]; then
            bspc monitor "$output" -d 1 2 3 4 5 6 7
        else
            bspc monitor "$output" -d "$output:1" "$output:2" "$output:3"
        fi
    fi
done
