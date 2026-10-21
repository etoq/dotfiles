#!/usr/bin/env bash
# ╔══════════════════════════════════════════════════════════════════╗
# ║  zer0 dotfiles installer · Arch Linux · BSPWM · Black Tiffany          ║
# ║  ThinkPad P50 · AwesomeWM · NVIDIA managed separately             ║
# ╚══════════════════════════════════════════════════════════════════╝
# Usage:
#   git clone https://github.com/etoq/dotfiles ~/dotfiles
#   cd ~/dotfiles && bash install.sh

set -e

# ── Цвета ──────────────────────────────────────────────────────────
R='\033[0m'; BOLD='\033[1m'
PUR='\033[38;2;10;186;181m'; PNK='\033[38;2;77;221;213m'
CYN='\033[38;2;77;221;213m'; GRN='\033[38;2;80;250;123m'
YLW='\033[38;2;241;250;140m'; RED='\033[38;2;255;85;85m'
DIM='\033[38;2;126;153;159m'

ok()   { echo -e "${GRN}[✓]${R} $1"; }
warn() { echo -e "${YLW}[!]${R} $1"; }
err()  { echo -e "${RED}[✗]${R} $1"; }
info() { echo -e "${PUR}[*]${R} $1"; }
step() { echo -e "\n${PUR}${BOLD}══ $1 ══${R}"; }
ask()  { echo -e "${CYN}[?]${R} $1 [y/N] "; read -r ans; [[ "$ans" =~ ^[Yy]$ ]]; }

DOTFILES_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKUP_DIR="$HOME/.dotfiles-backup-$(date +%Y%m%d-%H%M%S)"
if [[ ${1:-} == --check ]]; then
    exec python "$DOTFILES_DIR/scripts/maintenance/audit-dotfiles.py"
fi
[[ $# == 0 ]] || { echo 'Usage: install.sh [--check]'; exit 2; }

# ── Баннер ─────────────────────────────────────────────────────────
clear
echo -e "${PUR}${BOLD}"
cat << 'BANNER'
 ██████╗  ██████╗ ████████╗███████╗██╗██╗     ███████╗███████╗
 ██╔══██╗██╔═══██╗╚══██╔══╝██╔════╝██║██║     ██╔════╝██╔════╝
 ██║  ██║██║   ██║   ██║   █████╗  ██║██║     █████╗  ███████╗
 ██║  ██║██║   ██║   ██║   ██╔══╝  ██║██║     ██╔══╝  ╚════██║
 ██████╔╝╚██████╔╝   ██║   ██║     ██║███████╗███████╗███████║
 ╚═════╝  ╚═════╝    ╚═╝   ╚═╝     ╚═╝╚══════╝╚══════╝╚══════╝
BANNER
echo -e "${R}"
echo -e "${DIM}  zer0@p50 · Arch Linux · AwesomeWM + Polybar · Black Tiffany${R}"
echo -e "${DIM}  ────────────────────────────────────────────${R}\n"

# ── Проверки ───────────────────────────────────────────────────────
step "ПРОВЕРКИ"

if [ "$(id -u)" = "0" ]; then
    err "Не запускай от root. Запусти от обычного пользователя"
    exit 1
fi
ok "Пользователь: $(whoami)"

if ! command -v pacman &>/dev/null; then
    err "Это не Arch Linux. Скрипт только для Arch"
    exit 1
fi
ok "Arch Linux обнаружен"

# ── Меню установки ─────────────────────────────────────────────────
step "ЧТО УСТАНОВИТЬ"
echo -e "  ${PUR}1${R}) Полная установка (пакеты + конфиги + сервисы)"
echo -e "  ${CYN}2${R}) Только конфиги (симлинки)"
echo -e "  ${GRN}3${R}) Только пакеты"
echo -e "  ${YLW}4${R}) Только скрипты (~/.local/bin и ~/bin)"
echo -e "  ${DIM}5${R}) Выход\n"
read -rp "  Выбор [1-5]: " CHOICE

case "$CHOICE" in
    1) DO_PKGS=1; DO_CONFIGS=1; DO_SCRIPTS=1; DO_SERVICES=1 ;;
    2) DO_PKGS=0; DO_CONFIGS=1; DO_SCRIPTS=1; DO_SERVICES=0 ;;
    3) DO_PKGS=1; DO_CONFIGS=0; DO_SCRIPTS=0; DO_SERVICES=0 ;;
    4) DO_PKGS=0; DO_CONFIGS=0; DO_SCRIPTS=1; DO_SERVICES=0 ;;
    5) exit 0 ;;
    *) err "Неверный выбор"; exit 1 ;;
esac

# ── Авторизация sudo ───────────────────────────────────────────────
sudo_keepalive=
cleanup() { if [[ -n "$sudo_keepalive" ]]; then kill "$sudo_keepalive" 2>/dev/null || true; fi; }
trap cleanup EXIT
if [[ "$DO_PKGS" == 1 || "$DO_SERVICES" == 1 ]]; then
    step "АВТОРИЗАЦИЯ SUDO"
    sudo -v
    while kill -0 "$$" 2>/dev/null; do sudo -n true || exit; sleep 45; done 2>/dev/null &
    sudo_keepalive=$!
fi

# ── Функция симлинка с бэкапом ─────────────────────────────────────
link() {
    local src="$DOTFILES_DIR/$1"
    local dst="$2"
    local dir
    dir="$(dirname "$dst")"

    if [[ ! -e "$src" ]]; then
        warn "Исходник не найден, существующий файл сохранён: $src"
        return
    fi
    if [[ -L "$dst" && "$(readlink "$dst")" == "$src" ]]; then
        return
    fi

    [ ! -d "$dir" ] && mkdir -p "$dir"

    if [ -e "$dst" ] && [ ! -L "$dst" ]; then
        mkdir -p "$BACKUP_DIR"
        local backup_path="$BACKUP_DIR/${dst#"$HOME"/}"
        mkdir -p "$(dirname "$backup_path")"
        mv "$dst" "$backup_path"
        warn "Бэкап: $dst → $backup_path"
    fi

    if [ -L "$dst" ]; then
        rm "$dst"
    fi

    if [ -e "$src" ]; then
        ln -sf "$src" "$dst"
        ok "Симлинк: $dst"
    else
        warn "Исходник не найден: $src"
    fi
}

# ══════════════════════════════════════════════════════════════════
# ПАКЕТЫ
# ══════════════════════════════════════════════════════════════════
if [ "$DO_PKGS" = "1" ]; then
    step "ПОДГОТОВКА РЕПОЗИТОРИЕВ"

    # RE/malware workstation: use official Arch + reviewed AUR packages.
    # Existing third-party repositories are preserved; none is added automatically.
    info "Профиль: reverse engineering / malware analysis"
    sudo pacman -Syu --noconfirm

    step "УСТАНОВКА YAY (AUR helper)"
    if ! command -v yay &>/dev/null; then
        info "Устанавливаю yay..."
        sudo pacman -S --needed git base-devel --noconfirm
        rm -rf /tmp/yay-install # Очистка перед загрузкой
        git clone https://aur.archlinux.org/yay.git /tmp/yay-install
        cd /tmp/yay-install && makepkg -si --noconfirm
        cd "$DOTFILES_DIR"
        ok "yay установлен"
    else
        ok "yay уже установлен"
    fi

    step "ПАКЕТЫ PACMAN"
    PACMAN_PKGS=(
        base base-devel git curl wget sudo nano vim
        man-db man-pages linux linux-headers linux-lts linux-lts-headers
        linux-firmware intel-ucode grub efibootmgr grub-btrfs
        btrfs-progs smartmontools cryptsetup snap-pac snapper
        xorg-server xorg-xinit xorg-xrandr xorg-xsetroot xdotool
        xdg-desktop-portal xdg-desktop-portal-gtk xdg-user-dirs
        bspwm awesome xsettingsd lua53-dkjson xorg-server-xephyr sxhkd picom polybar gjs gtk3 feh flameshot dunst libnotify playerctl
        kitty fish zoxide fzf bat lsd fd duf
        ttf-jetbrains-mono ttf-jetbrains-mono-nerd ttf-fira-code ttf-iosevka-nerd ttf-dejavu
        noto-fonts noto-fonts-cjk noto-fonts-emoji terminus-font
        nvidia-prime vulkan-intel lib32-vulkan-intel mesa-utils
        pipewire-alsa pipewire-jack pipewire-pulse wireplumber pamixer pavucontrol pulsemixer easyeffects python-gobject python-yaml
        networkmanager network-manager-applet networkmanager-openvpn openvpn bluez bluez-utils bolt udiskie
        dnsmasq openresolv
        htop btop s-tui fastfetch cpufetch tlp tlp-rdw brightnessctl
        apparmor chrony nftables reflector xss-lock
        qemu-full libvirt virt-manager virt-viewer swtpm
        wireshark-qt tcpdump python-scapy
        radare2 gdb pwndbg binwalk foremost volatility3
        python-pefile python-capstone python-unicorn python-pycryptodome
        strace ltrace elfutils file binutils ripgrep hexyl python-pwntools bpftrace
        neovim python-pip python-pipx python-pynvim git lazygit tmux shellcheck jq clang gdb luarocks
        keepassxc obsidian rofi libqalculate tesseract vim
        qbittorrent mpv libreoffice-fresh zathura zathura-pdf-mupdf
        calcurse veracrypt mat2 bleachbit
        yazi ffmpegthumbnailer poppler unzip zip wimlib 7zip imagemagick gparted gnome-disk-utility
        xclip xsel gpick chafa yt-dlp tldr tree perl-image-exiftool
        pacman-contrib kernel-modules-hook zram-generator
    )

    info "Устанавливаю pacman пакеты..."
        sudo pacman -S --needed --noconfirm "${PACMAN_PKGS[@]}" || { err "ОШИБКА: Пакеты не найдены! Установка прервана."; exit 1; }
    ok "Pacman пакеты установлены"

    # Keep the existing working Ghidra development build on this machine.
    if [[ ! -x "$HOME/ghidra/build/dist/ghidra_12.2_DEV/ghidraRun" ]] && ! command -v ghidra >/dev/null; then
        sudo pacman -S --needed --noconfirm ghidra
    fi

    step "ПАКЕТЫ AUR"
    AUR_PKGS=(
        thinkfan
        bluetuith impala rmtrash ptpython hyx snapper-rollback btrfs-assistant
        papirus-icon-theme ttf-material-symbols-variable-git ttf-symbola
        i3lock-color rofi-greenclip apparmor.d-git
        ayugram-desktop-bin otter-launcher termdown light
        woff2-font-awesome betterlockscreen
        cutter-bin detect-it-easy-bin capa-bin
    )

    python "$DOTFILES_DIR/scripts/maintenance/install-desktop-assets.py" --apply

    info "Драйвер NVIDIA сохраняется установленный. Переход ветки — отдельной проверенной процедурой."

    info "Устанавливаю AUR пакеты..."
    for pkg in "${AUR_PKGS[@]}"; do
        if ! pacman -Q "$pkg" &>/dev/null; then
            yay -S --needed --noconfirm "$pkg" && ok "$pkg" || warn "Ошибка при установке: $pkg"
        else
            ok "$pkg (уже установлен)"
        fi
    done

    # Optional CTF toolkit; never add a third-party repository automatically.
    if ask "Добавить инструменты CTF (сканеры, Burp, Metasploit и другие)?"; then
        CTF_AVAILABLE=()
        while IFS= read -r pkg; do
            if pacman -Si "$pkg" >/dev/null 2>&1; then
                CTF_AVAILABLE+=("$pkg")
            else
                warn "CTF: $pkg отсутствует в подключённых репозиториях; пропускаю"
            fi
        done < "$DOTFILES_DIR/docs/packages-ctf.txt"
        if (( ${#CTF_AVAILABLE[@]} )); then
            sudo pacman -S --needed --noconfirm "${CTF_AVAILABLE[@]}"
        fi
    fi

    step "УСТАНОВКА ДОПОЛНИТЕЛЬНЫХ УТИЛИТ"

    # Установка Rednotes
    if ! command -v rednotes &>/dev/null; then
        info "Устанавливаю rednotes..."
        mkdir -p /tmp/rednotes-install
        git clone https://github.com/lilaf-sec/rednotes.git /tmp/rednotes-install
        cd /tmp/rednotes-install
        chmod +x rednotes
        mkdir -p "$HOME/.local/bin"
        cp rednotes "$HOME/.local/bin/"
        cd "$DOTFILES_DIR"
        rm -rf /tmp/rednotes-install
        ok "rednotes установлен"
    else
        ok "rednotes уже установлен"
    fi
fi

# ══════════════════════════════════════════════════════════════════
# КОНФИГИ — симлинки
# ══════════════════════════════════════════════════════════════════
if [ "$DO_CONFIGS" = "1" ]; then
    link "configs/applications/imhex.desktop" "$HOME/.local/share/applications/imhex.desktop"
    link "configs/udiskie/config.yml" "$HOME/.config/udiskie/config.yml"
    link "configs/systemd/user/idle-screen-lock.service" "$HOME/.config/systemd/user/idle-screen-lock.service"
    link "configs/systemd/user/wallpaper-rotate.service" "$HOME/.config/systemd/user/wallpaper-rotate.service"
    link "configs/systemd/user/wallpaper-rotate.timer" "$HOME/.config/systemd/user/wallpaper-rotate.timer"
    link "configs/systemd/user/udiskie.service" "$HOME/.config/systemd/user/udiskie.service"
    link "configs/systemd/user/proton-quota.service" "$HOME/.config/systemd/user/proton-quota.service"
    link "configs/systemd/user/proton-quota.timer" "$HOME/.config/systemd/user/proton-quota.timer"
    link "configs/autostart/udiskie.desktop" "$HOME/.config/autostart/udiskie.desktop"
    step "СИМЛИНКИ КОНФИГОВ"
    link "configs/applications/tiffany-image.desktop" "$HOME/.local/share/applications/tiffany-image.desktop"
    link "configs/applications/com.ayugram.desktop.desktop" "$HOME/.local/share/applications/com.ayugram.desktop.desktop"
    link "configs/xdg-desktop-portal/portals.conf" "$HOME/.config/xdg-desktop-portal/portals.conf"

    link "configs/bspwm/dual_monitors.sh" "$HOME/.config/bspwm/dual_monitors.sh"
    link "configs/bspwm/picom_configurations" "$HOME/.config/bspwm/picom_configurations"
    link "configs/panel-lab" "$HOME/.config/panel-lab"
    link "configs/awesome" "$HOME/.config/awesome"
    link "configs/kitty/otter.conf" "$HOME/.config/kitty/otter.conf"
    link "configs/otter-launcher/commands.json" "$HOME/.config/otter-launcher/commands.json"
    link "configs/otter-launcher/image.png" "$HOME/.config/otter-launcher/image.png"
    link "configs/gammastep" "$HOME/.config/gammastep"
    link "configs/systemd/user/clean-screenshots.timer" "$HOME/.config/systemd/user/clean-screenshots.timer"
    link "configs/systemd/user/throne.service" "$HOME/.config/systemd/user/throne.service"
    link "configs/systemd/user/easyeffects.service" "$HOME/.config/systemd/user/easyeffects.service"
    link "configs/systemd/user/wispr-a11y-guard.service" "$HOME/.config/systemd/user/wispr-a11y-guard.service"
    link "configs/systemd/user/wispr-a11y-guard.timer" "$HOME/.config/systemd/user/wispr-a11y-guard.timer"
    for unit in workstation-backup@.service workstation-backup-full.timer workstation-backup-keepass.timer workstation-backup-warning.service; do
        link "configs/systemd/user/$unit" "$HOME/.config/systemd/user/$unit"
    done
    # Retire only our former KeePass workaround; preserve unrelated user files.
    for old in "$HOME/.local/bin/keepassxc" "$HOME/.local/share/applications/org.keepassxc.KeePassXC.desktop"; do
        case "$(readlink "$old" 2>/dev/null || true)" in
            "$DOTFILES_DIR/scripts/local-bin/keepassxc"|"$DOTFILES_DIR/configs/applications/org.keepassxc.KeePassXC.desktop") rm "$old" ;;
        esac
    done
    link "configs/autostart/throne.desktop" "$HOME/.config/autostart/throne.desktop"
    link "configs/tiffany" "$HOME/.config/tiffany"
    mkdir -p "$HOME/.config/workstation-backup"
    chmod 700 "$HOME/.config/workstation-backup"
    link "configs/workstation-backup/proton-cli.json" "$HOME/.config/workstation-backup/proton-cli.json"
    link "configs/environment.d/60-black-tiffany.conf" "$HOME/.config/environment.d/60-black-tiffany.conf"
    link "configs/autostart/easyeffects.desktop" "$HOME/.config/autostart/easyeffects.desktop"
    link "configs/autostart/wispr-flow.desktop" "$HOME/.config/autostart/wispr-flow.desktop"
    link "themes/Ghidra/BlackTiffany.theme" "$HOME/.local/share/ghidra/BlackTiffany.theme"

    mkdir -p "$HOME/.themes"
    cp -a "$DOTFILES_DIR/themes/Black-Tiffany" "$HOME/.themes/"
    link "configs/systemd/user/clean-screenshots.service" "$HOME/.config/systemd/user/clean-screenshots.service"
    link "configs/xsettingsd" "$HOME/.config/xsettingsd"
    link "configs/fish/tiffany.fish" "$HOME/.config/fish/tiffany.fish"
    link "configs/btop/themes" "$HOME/.config/btop/themes"
    link "configs/gtk-3.0/gtk.css" "$HOME/.config/gtk-3.0/gtk.css"
    link "configs/lsd" "$HOME/.config/lsd"

    link "configs/bspwm/bspwmrc"          "$HOME/.config/bspwm/bspwmrc"
    link "configs/bspwm/autostart.sh"     "$HOME/.config/bspwm/autostart.sh"
    chmod +x "$HOME/.config/bspwm/bspwmrc" 2>/dev/null
    chmod +x "$HOME/.config/bspwm/autostart.sh" 2>/dev/null

    link "configs/sxhkd/sxhkdrc"          "$HOME/.config/sxhkd/sxhkdrc"
    link "configs/polybar/config.ini"     "$HOME/.config/polybar/config.ini"
    link "configs/polybar/launch.sh"      "$HOME/.config/polybar/launch.sh"
    chmod +x "$HOME/.config/polybar/launch.sh" 2>/dev/null

    link "configs/kitty/kitty.conf"       "$HOME/.config/kitty/kitty.conf"
    link "configs/nvim"                   "$HOME/.config/nvim"
    link "configs/yazi/yazi.toml"         "$HOME/.config/yazi/yazi.toml"
    link "configs/yazi/keymap.toml"       "$HOME/.config/yazi/keymap.toml"
    link "configs/yazi/theme.toml"        "$HOME/.config/yazi/theme.toml"
    link "configs/otter-launcher/config.toml" "$HOME/.config/otter-launcher/config.toml"
    link "configs/rofi/config.rasi"       "$HOME/.config/rofi/config.rasi"
    link "configs/rofi/tiffany.rasi"      "$HOME/.config/rofi/tiffany.rasi"
    link "configs/picom/picom.conf"       "$HOME/.config/picom/picom.conf"
    link "configs/betterlockscreen/betterlockscreenrc" "$HOME/.config/betterlockscreen/betterlockscreenrc"
    link "configs/dunst/dunstrc"          "$HOME/.config/dunst/dunstrc"
    link "configs/fish/config.fish"       "$HOME/.config/fish/config.fish"
    link "configs/colors/tiffany.sh"      "$HOME/.config/colors/tiffany.sh"
    link "configs/gtk-3.0/settings.ini"   "$HOME/.config/gtk-3.0/settings.ini"
    link "configs/zathura/zathurarc"      "$HOME/.config/zathura/zathurarc"
    link "configs/btop/btop.conf"         "$HOME/.config/btop/btop.conf"
    link "configs/Xresources"             "$HOME/.Xresources"
    link "configs/xinitrc"                "$HOME/.xinitrc"
    link "configs/mimeapps.list"          "$HOME/.config/mimeapps.list"
    link "configs/gtk-4.0"                "$HOME/.config/gtk-4.0"
    link "configs/greenclip.toml"         "$HOME/.config/greenclip.toml"
    link "configs/flameshot"              "$HOME/.config/flameshot"
    link "configs/calcurse"               "$HOME/.config/calcurse"
    # Preserve the personal wallpaper collection; install only the selected default.
    link "Images/system/lockscreen.png" "$HOME/Images/system/lockscreen.png"
    link "Images/tiffany-re-37-ghidra-neon-emblem.png" "$HOME/Images/tiffany-re-37-ghidra-neon-emblem.png"
    link "configs/gtkrc-2.0"             "$HOME/.gtkrc-2.0"
    if [[ -n ${DISPLAY:-} ]] && command -v betterlockscreen >/dev/null; then
        betterlockscreen -u "$HOME/Images/system/lockscreen.png" --fx dim,dimblur || warn "Не удалось собрать кэш блокировки; повторите betterlockscreen -u ~/Images/system/lockscreen.png --fx dim,dimblur"
    fi
    ok "Все конфиги подключены"
fi

# ══════════════════════════════════════════════════════════════════
# СКРИПТЫ
# ══════════════════════════════════════════════════════════════════
if [ "$DO_SCRIPTS" = "1" ]; then
    step "СКРИПТЫ"

    mkdir -p "$HOME/.local/bin" "$HOME/bin"

    LOCAL_SCRIPTS=(fan-toggle wallpaper-rotate workstation-away idle-screen-lock imhex proton-quota workstation-status workstation-backup wispr-flow wispr-a11y-guard proton-drive proton-drive-install workstation-root-audit deck-system tiffany-theme verify-kernel-stack polybar-workspaces disable-middle-click awesome-session-start awesome-preview panel-action panel-data panel-switch panel-dashboard panel-autostart reverse-ghidra AyuGram cheat-fish cheat-sxhkd check-sleep-callback check-nvidia-sleep clean-meta clipmenu.sh fix-ethernet-autoconnect tiffany-calendar otter-apps otter-exec otter-launcher otter-new-note otter-tools otter-install-assets otter-run polybar-temperature sys-update syshealth tiffany-reload tiffany-reload-polybar weekly-clean)
    for s in "${LOCAL_SCRIPTS[@]}"; do
        if [ -f "$DOTFILES_DIR/scripts/local-bin/$s" ]; then
            link "scripts/local-bin/$s" "$HOME/.local/bin/$s"
            chmod +x "$HOME/.local/bin/$s"
        fi
    done

    BIN_SCRIPTS=(calculator temps.sh battery-alert random_wallpaper powermenu brightness volume weather weather2 screen-lock change_language.sh wifimenu toggle-polybar timer xcolor-pick)
    for s in "${BIN_SCRIPTS[@]}"; do
        if [ -f "$DOTFILES_DIR/scripts/bin/$s" ]; then
            link "scripts/bin/$s" "$HOME/bin/$s"
            chmod +x "$HOME/bin/$s"
        fi
    done
    if [[ "$DO_PKGS" == 1 ]]; then
        "$HOME/.local/bin/otter-install-assets" || warn "Ресурсы Otter: повтори otter-install-assets при доступном интернете"
    fi
    ok "Скрипты установлены"


fi

# ══════════════════════════════════════════════════════════════════
# СЕРВИСЫ И СИСТЕМНЫЕ НАСТРОЙКИ
# ══════════════════════════════════════════════════════════════════
if [ "$DO_SERVICES" = "1" ]; then
    step "ПРОВЕРЕННЫЕ СИСТЕМНЫЕ НАСТРОЙКИ"
    # This payload is machine-specific. It preserves the tested 580 full-VRAM sleep,
    # modular libvirt and EFI hooks and does not replace DNS configuration.
    sudo bash "$DOTFILES_DIR/restore-system.sh" --apply

    for g in wheel audio video storage optical libvirt kvm; do
        sudo groupadd -f "$g"
    done
    sudo usermod -aG wheel,audio,video,storage,optical,libvirt,kvm "$USER"
    systemctl --user daemon-reload
    systemctl --user enable --now proton-quota.timer
    systemctl --user enable clean-screenshots.timer
    systemctl --user enable --now wispr-a11y-guard.timer
    if python3 -c 'import json,sys; from pathlib import Path; p=Path(sys.argv[1]); sys.exit(0 if p.exists() and json.loads(p.read_text()).get("enabled") is True else 1)' "$HOME/.config/workstation-backup/plan.json"; then
        systemctl --user enable --now workstation-backup-full.timer workstation-backup-keepass.timer
    fi
    ok "Системные настройки восстановлены; сеть и графический сеанс не перезапускались"
fi

# ══════════════════════════════════════════════════════════════════
# GTK ТЕМА
# ══════════════════════════════════════════════════════════════════
if [ "$DO_CONFIGS" = "1" ]; then
    step "GTK ТЕМА"
    gsettings set org.gnome.desktop.interface gtk-theme "Black-Tiffany" 2>/dev/null || true
    gsettings set org.gnome.desktop.interface icon-theme "Papirus-Dark" 2>/dev/null || true
    gsettings set org.gnome.desktop.interface font-name "JetBrainsMono Nerd Font 11" 2>/dev/null || true
    gsettings set org.gnome.desktop.interface cursor-theme "Bibata-Modern-Classic" 2>/dev/null || true
    gsettings set org.gnome.desktop.interface cursor-size 24 2>/dev/null || true
    gsettings set org.gnome.desktop.interface color-scheme "prefer-dark" 2>/dev/null || true
    ok "GTK: Black Tiffany + Papirus-Dark"

    [ -f "$HOME/.Xresources" ] && xrdb -merge "$HOME/.Xresources" 2>/dev/null && ok "Xresources загружены"
    fc-cache -fv &>/dev/null && ok "Шрифты обновлены"
fi

# ══════════════════════════════════════════════════════════════════
# ФИНАЛ
# ══════════════════════════════════════════════════════════════════
echo ""
echo -e "${PUR}${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${R}"
echo -e "${GRN}${BOLD}  Установка завершена!${R}"
echo -e "${PUR}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${R}"
echo ""

if [ -d "$BACKUP_DIR" ]; then
    echo -e "${YLW}  Бэкап старых файлов:${R} $BACKUP_DIR"
fi

echo -e "${DIM}  Следующие шаги:${R}"
echo -e "  ${CYN}1.${R} Проверить соответствие: bash install.sh --check"
echo -e "  ${CYN}2.${R} Восстановление и приватные данные: docs/RECOVERY.md"
echo -e "  ${CYN}3.${R} Если применялась системная часть — сохранить работу и перезагрузиться вручную в LTS"
echo ""

# The EXIT trap stops only this installer's sudo keepalive.
