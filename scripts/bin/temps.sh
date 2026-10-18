#!/usr/bin/env bash
# Resolve sensor names on each pass: hwmon numbers are not stable across boots.
show_temperatures() {
    local sensor name input label value found=0
    for sensor in /sys/class/hwmon/hwmon*; do
        [[ -r "$sensor/name" ]] || continue
        read -r name < "$sensor/name"
        case "$name" in coretemp|thinkpad|nvme|acpitz) ;; *) continue ;; esac
        printf '\n=== %s ===\n' "$name"
        for input in "$sensor"/temp*_input; do
            [[ -r "$input" ]] || continue
            read -r value < "$input"
            [[ "$value" =~ ^-?[0-9]+$ ]] || continue
            (( value > 0 )) || continue
            label=${input%_input}; label=${label##*/}
            [[ ! -r "${input%_input}_label" ]] || read -r label < "${input%_input}_label"
            awk -v label="$label" -v value="$value" 'BEGIN {printf "  %s: %.1f°C\n", label,value/1000}'
            found=1
        done
    done
    (( found )) || printf 'No readable temperature sensors.\n'
    if [[ -r /proc/acpi/ibm/fan ]]; then
        printf '\n=== Fan ===\n'
        awk '/^(status|speed|level):/' /proc/acpi/ibm/fan
    fi
}
if [[ "${1:-}" == --once ]]; then show_temperatures; exit; fi
while :; do clear; show_temperatures; sleep 2; done
