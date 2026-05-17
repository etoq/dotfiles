
# ~/.config/fish/config.fish
set -gx XDG_CURRENT_DESKTOP GNOME
set -gx XDG_SESSION_TYPE x11
# ── Greeting ──────────────────────────────────────────────────────────────────
set -U fish_greeting  # убрать стандартное приветствие

# ── Цвета Fish ────────────────────────────────────────────────────────────────
set fish_color_command        green
set fish_color_param          cyan
set fish_color_error          red
set fish_color_comment        brblack
set fish_color_keyword        purple
set fish_color_string         yellow
set fish_color_operator       magenta
set fish_color_autosuggestion brblack

# ── Переменные окружения ───────────────────────────────────────────────────────
set -gx EDITOR nvim
set -gx VISUAL nvim
set -gx BROWSER /usr/bin/librewolf
set -gx PATH $HOME/.local/bin $PATH
set -gx QT_QPA_PLATFORM xcb        # Telegram / Qt на X11
set -gx FM yazi

# Dracula цвета (для скриптов которые их используют)
set -gx DRACULA_BG        "#0D1117"
set -gx DRACULA_PURPLE    "#BD93F9"
set -gx DRACULA_PINK      "#FF79C6"
set -gx DRACULA_CYAN      "#8BE9FD"
set -gx DRACULA_GREEN     "#50FA7B"
set -gx DRACULA_YELLOW    "#F1FA8C"
set -gx DRACULA_RED       "#FF5555"
set -gx DRACULA_FG        "#F8F8F2"

# ── Замены команд ─────────────────────────────────────────────────────────────
alias ls='lsd'
alias ll='lsd -la'
alias lt='lsd --tree'
alias la='lsd -A'
alias cat='bat'
alias catp='bat -p'                 # bat без украшений
alias find='fd'
alias rm='rmtrash'                  # в корзину вместо удаления
alias rmf='/usr/bin/rm -rf'        # настоящее удаление — явно
alias df='duf'
alias top='btop'
alias htop='neohtop'
alias grep='grep --color=auto'
alias diff='diff --color=auto'
alias ip='ip --color=auto'
alias feh='feh --scale-down'

# ── Навигация ─────────────────────────────────────────────────────────────────
alias ..='cd ..'
alias ...='cd ../..'
alias ....='cd ../../..'
alias h='cd ~'

# ── Редакторы ─────────────────────────────────────────────────────────────────
alias n='nvim'
alias m='micro'
alias g='git'

# ── Система ───────────────────────────────────────────────────────────────────
alias update='xdg-open https://archlinux.org/news/ && sudo pacman -Syu'
alias install='sudo pacman -S'
alias search='pacman -Ss'
alias remove='sudo pacman -Rns'
alias orphans='pacman -Qqdt'
alias clean='sudo paccache -r && sudo pacman -Sc'

# ── Arch specific ─────────────────────────────────────────────────────────────
alias mirrors='sudo reflector --latest 20 --sort rate --save /etc/pacman.d/mirrorlist'
alias snaps='snapper -c root list'
alias dkms-check='dkms status'

# ── Логи и диагностика ────────────────────────────────────────────────────────
alias syslog_emerg='sudo dmesg --level=emerg,alert,crit'
alias syslog='sudo dmesg --level=err,warn'
alias xlog='grep "(EE)\|(WW)\|error\|failed" ~/.local/share/xorg/Xorg.0.log'
alias vacuum='journalctl --vacuum-size=100M'
alias vacuum_time='journalctl --vacuum-time=2weeks'

# ── Security tools ────────────────────────────────────────────────────────────
alias ports='ss -tulpn'
alias listening='ss -tlnp'
alias myip='curl -s https://ipinfo.io/ip'
alias localip="ip -4 addr | grep inet | grep -v 127 | awk '{print \$2}'"
alias scan='nmap -sV -sC'
alias scanfast='nmap -T4 -F'

# ── VM ────────────────────────────────────────────────────────────────────────
alias vms='virsh list --all'
alias vmstart='virsh start'
alias vmstop='virsh shutdown'
alias vmkill='virsh destroy'

# ── Git ───────────────────────────────────────────────────────────────────────
alias gs='git status'
alias ga='git add'
alias gc='git commit -m'
alias gp='git push'
alias gl='git log --oneline --graph --color'

# ── Misc ──────────────────────────────────────────────────────────────────────
alias cls='clear'
alias q='exit'
alias reload='source ~/.config/fish/config.fish'
# ── Интерактивный режим ───────────────────────────────────────────────────────
if status is-interactive

    # Starship prompt
    starship init fish | source

    # Zoxide (умный cd) вместо обычного cd
    zoxide init fish | source

    # fzf keybindings (Ctrl+R история, Ctrl+T файлы)
    fzf --fish | source

end
