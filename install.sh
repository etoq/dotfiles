#!/usr/bin/env bash
# ╔══════════════════════════════════════════════════════════════════╗
# ║  zer0 dotfiles installer · Arch Linux · BSPWM · Dracula          ║
# ║  ThinkPad P50 · nvidia-470xx                                     ║
# ╚══════════════════════════════════════════════════════════════════╝
# Usage:
#   git clone https://github.com/etoq/dotfiles ~/dotfiles
#   cd ~/dotfiles && bash install.sh

set -e

# ── Цвета ──────────────────────────────────────────────────────────
R='\033[0m'; BOLD='\033[1m'
PUR='\033[38;2;189;147;249m'; PNK='\033[38;2;255;121;198m'
CYN='\033[38;2;139;233;253m'; GRN='\033[38;2;80;250;123m'
YLW='\033[38;2;241;250;140m'; RED='\033[38;2;255;85;85m'
DIM='\033[38;2;98;114;164m'

ok()   { echo -e "${GRN}[✓]${R} $1"; }
warn() { echo -e "${YLW}[!]${R} $1"; }
err()  { echo -e "${RED}[✗]${R} $1"; }
info() { echo -e "${PUR}[*]${R} $1"; }
step() { echo -e "\n${PUR}${BOLD}══ $1 ══${R}"; }
ask()  { echo -e "${CYN}[?]${R} $1 [y/N] "; read -r ans; [[ "$ans" =~ ^[Yy]$ ]]; }

DOTFILES_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKUP_DIR="$HOME/.dotfiles-backup-$(date +%Y%m%d-%H%M%S)"

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
echo -e "${DIM}  zer0@p50 · Arch Linux · BSPWM · Dracula${R}"
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

if ! ping -c1 archlinux.org &>/dev/null; then
    err "Нет интернета. Проверь подключение"
    exit 1
fi
ok "Интернет есть"

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
step "АВТОРИЗАЦИЯ SUDO"
info "Введи пароль sudo"
# Запрашиваем пароль заранее
sudo -v
# Фоновый процесс: обновляет таймер sudo каждую минуту, пока жив основной скрипт
while true; do sudo -n true; sleep 60; kill -0 "$$" || exit; done 2>/dev/null &
ok "Пароль принят!"

# ── Функция симлинка с бэкапом ─────────────────────────────────────
link() {
    local src="$DOTFILES_DIR/$1"
    local dst="$2"
    local dir
    dir="$(dirname "$dst")"

    [ ! -d "$dir" ] && mkdir -p "$dir"

    if [ -e "$dst" ] && [ ! -L "$dst" ]; then
        mkdir -p "$BACKUP_DIR"
        mv "$dst" "$BACKUP_DIR/"
        warn "Бэкап: $dst → $BACKUP_DIR/"
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
    
    # 1. Добавление BlackArch (Критично сделать ДО установки пакетов)
    if ! grep -q "blackarch" /etc/pacman.conf; then
        info "Подключаю репозиторий BlackArch..."
        curl -O https://blackarch.org/strap.sh
        chmod +x strap.sh
        sudo ./strap.sh
        rm strap.sh
        sudo pacman -Sy --noconfirm
        ok "BlackArch добавлен"
    else
        ok "BlackArch уже подключен"
    fi

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
        btrfs-progs cryptsetup snap-pac snapper
        xorg-server xorg-xinit xorg-xrandr xorg-xsetroot xdotool
        xdg-desktop-portal xdg-desktop-portal-gtk xdg-user-dirs
        bspwm sxhkd picom polybar feh flameshot dunst libnotify playerctl
        kitty fish zoxide fzf bat lsd fd duf rmtrash
        ttf-jetbrains-mono ttf-jetbrains-mono-nerd ttf-fira-code ttf-iosevka-nerd ttf-dejavu
        noto-fonts noto-fonts-cjk noto-fonts-emoji terminus-font
        nvidia-prime vulkan-intel lib32-vulkan-intel mesa-utils
        pipewire-alsa pipewire-jack pipewire-pulse wireplumber pamixer pavucontrol pulsemixer
        networkmanager network-manager-applet networkmanager-openvpn openvpn bluez bluez-utils blueman bolt
        dnsmasq bridge-utils openresolv
        htop btop s-tui fastfetch cpufetch tlp tlp-rdw thinkfan brightnessctl acpilight
        apparmor chrony nftables reflector
        qemu-full libvirt virt-manager virt-viewer swtpm
        nmap masscan rustscan wireshark-qt tcpdump metasploit sqlmap hydra john hashcat
        nikto feroxbuster ffuf nuclei subfinder amass netexec impacket evil-winrm
        aircrack-ng radare2 ghidra gdb pwndbg binwalk foremost volatility3 autopsy
        exploitdb bloodhound proxychains-ng python-pwntools python-scapy
        neovim python-pip python-pipx python-pynvim git lazygit tmux shellcheck jq clang gdb luarocks
        keepassxc obsidian rofi librewolf-bin chromium torbrowser-launcher
        qbittorrent mpv kdenlive libreoffice-fresh evince zathura zathura-pdf-mupdf
        signal-desktop calcurse veracrypt mat2 bleachbit
        yazi ffmpegthumbnailer poppler unzip zip wimlib 7zip imagemagick gparted gnome-disk-utility
        xclip xsel xcolor gpick chafa screenkey scrot yt-dlp tldr tree perl-image-exiftool
        pacman-contrib snapd kernel-modules-hook zram-generator
    )

    info "Устанавливаю pacman пакеты..."
    sudo pacman -S --needed --noconfirm "${PACMAN_PKGS[@]}" 2>/dev/null || \
        warn "Некоторые пакеты не найдены — продолжаем"
    ok "Pacman пакеты установлены"

    step "ПАКЕТЫ AUR"
    AUR_PKGS=(
        nvidia-470xx-dkms nvidia-470xx-utils nvidia-470xx-settings
        lib32-nvidia-470xx-utils lib32-opencl-nvidia-470xx opencl-nvidia-470xx
        optimus-manager
        happ bluetuith impala neohtop rmtrash ptpython hyx snapper-rollback btrfs-assistant
        dracula-gtk-theme dracula-icons-git ttf-material-symbols-variable-git ttf-symbola
        i3lock-color rofi-greenclip apparmor.d-git
        ayugram-desktop librewolf-bin simplex-desktop otter-launcher lazydocker termdown light
        woff2-font-awesome
    )

    info "Устанавливаю AUR пакеты..."
    for pkg in "${AUR_PKGS[@]}"; do
        if ! pacman -Q "$pkg" &>/dev/null; then
            yay -S --needed --noconfirm "$pkg" && ok "$pkg" || warn "Ошибка при установке: $pkg"
        else
            ok "$pkg (уже установлен)"
        fi
    done

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
    step "СИМЛИНКИ КОНФИГОВ"

    link "configs/bspwm/bspwmrc"          "$HOME/.config/bspwm/bspwmrc"
    link "configs/bspwm/autostart.sh"     "$HOME/.config/bspwm/autostart.sh"
    chmod +x "$HOME/.config/bspwm/bspwmrc" 2>/dev/null
    chmod +x "$HOME/.config/bspwm/autostart.sh" 2>/dev/null

    link "configs/sxhkd/sxhkdrc"          "$HOME/.config/sxhkd/sxhkdrc"
    link "configs/polybar/config.ini"     "$HOME/.config/polybar/config.ini"
    link "configs/polybar/modules.ini"    "$HOME/.config/polybar/modules.ini"
    link "configs/polybar/launch.sh"      "$HOME/.config/polybar/launch.sh"
    link "configs/polybar/colors.ini"     "$HOME/.config/polybar/colors.ini"
    chmod +x "$HOME/.config/polybar/launch.sh" 2>/dev/null

    link "configs/kitty/kitty.conf"       "$HOME/.config/kitty/kitty.conf"
    link "configs/nvim"                   "$HOME/.config/nvim"
    link "configs/yazi/yazi.toml"         "$HOME/.config/yazi/yazi.toml"
    link "configs/yazi/keymap.toml"       "$HOME/.config/yazi/keymap.toml"
    link "configs/yazi/theme.toml"        "$HOME/.config/yazi/theme.toml"
    link "configs/otter-launcher/config.toml" "$HOME/.config/otter-launcher/config.toml"
    link "configs/rofi/config.rasi"       "$HOME/.config/rofi/config.rasi"
    link "configs/rofi/dracula.rasi"      "$HOME/.config/rofi/dracula.rasi"
    link "configs/picom/picom.conf"       "$HOME/.config/picom/picom.conf"
    link "configs/dunst/dunstrc"          "$HOME/.config/dunst/dunstrc"
    link "configs/fish/config.fish"       "$HOME/.config/fish/config.fish"
    link "configs/colors/dracula.sh"      "$HOME/.config/colors/dracula.sh"
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
    link "Images"                         "$HOME/Images"
    link "configs/.gtkrc-2.0"             "$HOME/.gtkrc-2.0"
    # Snapper
    if [ -d "$DOTFILES_DIR/configs/snapper" ]; then
        sudo cp "$DOTFILES_DIR/configs/snapper/root" /etc/snapper/configs/root
        ok "Snapper конфиг"
    fi

    ok "Все конфиги подключены"
fi

# ══════════════════════════════════════════════════════════════════
# СКРИПТЫ
# ══════════════════════════════════════════════════════════════════
if [ "$DO_SCRIPTS" = "1" ]; then
    step "СКРИПТЫ"

    mkdir -p "$HOME/.local/bin" "$HOME/bin"

    LOCAL_SCRIPTS=(syshealth clean-meta lock battery-status power-menu vm-menu layout-switch brightness weather wifi-menu weekly-clean cheat-sxhkd cheat-fish cheat-yazi cheat-nvim cheat-aliases otter-exec otter-run greet-wrapper)
    for s in "${LOCAL_SCRIPTS[@]}"; do
        if [ -f "$DOTFILES_DIR/scripts/local-bin/$s" ]; then
            link "scripts/local-bin/$s" "$HOME/.local/bin/$s"
            chmod +x "$HOME/.local/bin/$s"
        fi
    done

    BIN_SCRIPTS=(battery-alert random_wallpaper powermenu brightness volume weather weather2 screen-lock change_language.sh wifimenu toggle-polybar timer xcolor-pick)
    for s in "${BIN_SCRIPTS[@]}"; do
        if [ -f "$DOTFILES_DIR/scripts/bin/$s" ]; then
            link "scripts/bin/$s" "$HOME/bin/$s"
            chmod +x "$HOME/bin/$s"
        fi
    done
    ok "Скрипты установлены"

    # Starship
    if ! command -v starship &>/dev/null; then
        info "Устанавливаю Starship..."
        curl -sS https://starship.rs/install.sh | sh -s -- --yes
        ok "Starship установлен"
    else
        ok "Starship уже установлен"
    fi
fi

# ══════════════════════════════════════════════════════════════════
# СЕРВИСЫ И СИСТЕМНЫЕ НАСТРОЙКИ
# ══════════════════════════════════════════════════════════════════
if [ "$DO_SERVICES" = "1" ]; then
    step "СИСТЕМНЫЕ НАСТРОЙКИ И БЕЗОПАСНОСТЬ"

    # 1. Настройка пользователя (Группы)
    info "Добавляю $USER в нужные группы..."
    sudo usermod -aG wheel,audio,video,storage,optical,libvirt,kvm "$USER"
    ok "Права пользователя обновлены"

    # 2. Настройка сети для Виртуалок (NAT)
    info "Настройка сети KVM/libvirt..."
    sudo virsh net-autostart default 2>/dev/null || true
    sudo virsh net-start default 2>/dev/null || true
    ok "Сеть default (NAT) для VM включена"

    # 3. Изолированный DNS (DoT)
    info "Настройка защищенного DNS (systemd-resolved)..."
    sudo systemctl enable --now systemd-resolved 2>/dev/null
    sudo ln -sf /run/systemd/resolve/stub-resolv.conf /etc/resolv.conf
    ok "DNS-over-TLS включен"

    # 4. Инициализация Snapper (если еще не создан)
    if [ ! -d "/.snapshots" ]; then
        info "Инициализация Snapper..."
        sudo snapper -c root create-config / 2>/dev/null || true
        sudo chmod 750 /.snapshots
        ok "Snapper структура создана"
    fi

    # 6. Создание Pacman хука для копирования ядра в EFI
    info "Создание Pacman hooks (Kernel to EFI)..."
    sudo mkdir -p /etc/pacman.d/hooks/
    sudo mkdir -p /boot/efi/EFI/ARCH/
    
    sudo tee /etc/pacman.d/hooks/99-copy-kernel-to-efi.hook > /dev/null << 'EOF'
[Trigger]
Operation = Install
Operation = Upgrade
Type = Package
Target = linux
Target = linux-lts

[Action]
Description = Copying kernel to EFI...
When = PostTransaction
Exec = /bin/sh -c 'cp /boot/vmlinuz-linux* /boot/efi/EFI/ARCH/ 2>/dev/null; cp /boot/initramfs-linux* /boot/efi/EFI/ARCH/ 2>/dev/null; echo "Kernel copied to EFI"'
EOF
    ok "Pacman hook для EFI успешно создан"

    # 5. Копирование системных конфигов в /etc/
    info "Копирование системных конфигураций (grub, nftables, mkinitcpio)..."
    if [ -d "$DOTFILES_DIR/configs/etc" ]; then
        sudo cp "$DOTFILES_DIR/configs/etc/nftables.conf" /etc/nftables.conf 2>/dev/null || true
        sudo cp "$DOTFILES_DIR/configs/etc/mkinitcpio.conf" /etc/mkinitcpio.conf 2>/dev/null || true
        if [ -f "$DOTFILES_DIR/configs/etc/default/grub" ]; then
            sudo cp "$DOTFILES_DIR/configs/etc/default/grub" /etc/default/grub 2>/dev/null || true
        fi
        
        # Права root для системных конфигов
        sudo chown root:root /etc/nftables.conf /etc/mkinitcpio.conf /etc/default/grub 2>/dev/null || true
        sudo chmod 644 /etc/nftables.conf /etc/mkinitcpio.conf /etc/default/grub 2>/dev/null || true
        
        ok "Системные конфиги применены и защищены"
    else
        warn "Папка configs/etc не найдена в репозитории (пропущено)"
    fi

    step "SYSTEMD СЕРВИСЫ"
    SYSTEM_SERVICES=(
        NetworkManager bluetooth apparmor auditd chronyd nftables libvirtd
        virtnetworkd thinkfan tlp grub-btrfsd optimus-manager
        nvidia-suspend nvidia-resume nvidia-hibernate
    )

    for svc in "${SYSTEM_SERVICES[@]}"; do
        if systemctl list-unit-files "$svc.service" &>/dev/null; then
            sudo systemctl enable "$svc" 2>/dev/null && ok "$svc" || warn "$svc — пропущен"
        fi
    done

    USER_SERVICES=(wireplumber pipewire pipewire-pulse)
    for svc in "${USER_SERVICES[@]}"; do
        systemctl --user enable "$svc" 2>/dev/null && ok "$svc (user)" || warn "$svc — пропущен"
    done

    # GRUB
    if ask "Обновить GRUB конфиг?"; then
        sudo grub-mkconfig -o /boot/grub/grub.cfg
        ok "GRUB обновлён"
    fi

    # mkinitcpio
    if ask "Пересобрать initramfs?"; then
        sudo mkinitcpio -P
        ok "initramfs пересобран"
    fi
fi

# ══════════════════════════════════════════════════════════════════
# GTK ТЕМА
# ══════════════════════════════════════════════════════════════════
if [ "$DO_CONFIGS" = "1" ]; then
    step "GTK ТЕМА"
    gsettings set org.gnome.desktop.interface gtk-theme "Dracula" 2>/dev/null || true
    gsettings set org.gnome.desktop.interface icon-theme "Papirus-Dark" 2>/dev/null || true
    gsettings set org.gnome.desktop.interface font-name "JetBrainsMono Nerd Font 11" 2>/dev/null || true
    gsettings set org.gnome.desktop.interface color-scheme "prefer-dark" 2>/dev/null || true
    ok "GTK: Dracula + Papirus-Dark"

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
echo -e "  ${CYN}1.${R} Скопировать картинку: cp image.png ~/.config/otter-launcher/image.png"
echo -e "  ${CYN}2.${R} Перезапустить BSPWM: bspc wm -r"
echo -e "  ${CYN}3.${R} Перезагрузиться: sudo reboot"
echo -e "  ${RED}4. СДЕЛАТЬ БЭКАП LUKS: sudo cryptsetup luksHeaderBackup /dev/nvme0n1p2 --header-backup-file ~/luks-header.img${R}"
echo ""

# Очистка: убиваем фоновый процесс sudo и сбрасываем кэш пароля
kill $(jobs -p) 2>/dev/null || true
sudo -k
