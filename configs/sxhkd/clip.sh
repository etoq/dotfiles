#!/usr/bin/env bash
# Private per-invocation result; cancellation preserves the current clipboard.
set -euo pipefail
result_file=$(mktemp "${XDG_RUNTIME_DIR:-/tmp}/clip-result.XXXXXX")
trap 'rm -f -- "$result_file"' EXIT
if kitty --class clipboard-manager --override window_padding_width=15 --override background=#080D10 \
    -e bash -c 'greenclip print | fzf --cycle --prompt "  Copy > " --color "bg:#080D10,bg+:#183039,fg:#C5D6D8,hl:#4DDDD5,pointer:#4DDDD5" > "$1"' _ "$result_file"; then
    if [[ -s "$result_file" ]]; then
        xclip -selection clipboard -in < "$result_file"
    fi
fi
