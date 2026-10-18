#!/usr/bin/env bash
# Install the tested update safeguard and remove only the user-selected packages.
set -euo pipefail
repo_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
mode=${1:---check}
case "$mode" in --check|--apply) ;; *) echo 'Usage: maintain-system.sh [--check|--apply]'; exit 2 ;; esac
mapfile -t requested < "$repo_dir/docs/cleanup-packages.txt"
packages=()
for pkg in "${requested[@]}"; do
    [[ "$pkg" =~ ^[a-z0-9][a-z0-9+_.-]*$ ]] || { echo 'Invalid package name'; exit 1; }
    case "$pkg" in obsidian|throne|qemu*|libvirt|bluez*|neovim|snapper|linux*|nvidia*) echo "Protected: $pkg"; exit 1 ;; esac
    if pacman -Q "$pkg" >/dev/null 2>&1; then packages+=("$pkg"); fi
done
if (( ${#packages[@]} )); then
    echo 'Packages selected by the user (no recursive dependency removal):'
    pacman -R --print --print-format '%n' "${packages[@]}"
fi
if pgrep -x VirtualBoxVM >/dev/null || pgrep -x VBoxHeadless >/dev/null; then
    echo 'A VirtualBox guest is running. Shut it down before removal.'; exit 1
fi
if pgrep -x wineserver >/dev/null || pgrep -x wine >/dev/null || pgrep -x wine64 >/dev/null; then
    echo 'Wine is running. Close Windows applications before removal.'; exit 1
fi
test "$(cat /sys/class/dmi/id/product_name)" = 20EQS59J07
test -s "$repo_dir/scripts/system/nvidia470-sleep-policy"
test -s "$repo_dir/configs/etc/pacman.d/hooks/66-nvidia470-sleep-policy.hook"
test -s "$repo_dir/configs/etc/workstation/nvidia-sleep-mode"
python3 "$repo_dir/scripts/system/cleanup-portproton"
if [[ "$mode" == --check ]]; then
    echo 'Preflight passed. No packages or files changed.'
    exit 0
fi
(( EUID == 0 )) || { echo 'Run ~/.local/bin/finalize-workstation as your normal user.'; exit 1; }
backup_dir="/var/backups/workstation-maintenance-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$backup_dir"
pacman -Q > "$backup_dir/packages-before.txt"
pacman -Qqe > "$backup_dir/explicit-before.txt"
cp -a /etc/modprobe.d "$backup_dir/modprobe.d"
cp -a /usr/lib/systemd/system-sleep/nvidia "$backup_dir/nvidia-post-hook"
if [[ -f /etc/workstation/nvidia-sleep-mode ]]; then cp -a /etc/workstation/nvidia-sleep-mode "$backup_dir/previous-sleep-mode"; fi
if command -v snapper >/dev/null && [[ -f /etc/snapper/configs/root ]]; then
    snapper -c root create --type single --print-number --description 'Before selected app cleanup and NVIDIA sleep safeguard' > "$backup_dir/snapshot.txt"
fi
install -D -m 644 "$repo_dir/configs/etc/workstation/nvidia-sleep-mode" /etc/workstation/nvidia-sleep-mode
install -D -m 755 "$repo_dir/scripts/system/nvidia470-sleep-policy" /usr/local/libexec/nvidia470-sleep-policy
install -D -m 644 "$repo_dir/configs/etc/pacman.d/hooks/66-nvidia470-sleep-policy.hook" /etc/pacman.d/hooks/66-nvidia470-sleep-policy.hook
/usr/local/libexec/nvidia470-sleep-policy
if (( ${#packages[@]} )); then
    for service in happd.service v2raya.service; do
        if [[ "$(systemctl show "$service" -p LoadState --value)" == loaded ]]; then
            systemctl disable --now "$service"
        fi
    done
    pacman -R --noconfirm "${packages[@]}"
fi
# Keep two package versions for rollback; do not purge every cache or any snapshots.
paccache --remove --keep 2
python3 "$repo_dir/scripts/system/cleanup-stale-kernels" --apply
python3 "$repo_dir/scripts/system/cleanup-portproton" --apply
# Include the new canonical modprobe policy in both boot images.
mkinitcpio -P
pacman -Dk
pacman -Q > "$backup_dir/packages-after.txt"
pacman -Qdtq > "$backup_dir/orphans-after.txt" || true
echo "Completed. Backup: $backup_dir"
echo 'Obsidian, Hiddify, VM disks, personal profiles and shared dependencies were preserved.'
