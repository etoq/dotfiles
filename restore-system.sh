#!/usr/bin/env bash
# Restore this workstation's non-secret system configuration. Default: check only.
set -euo pipefail
repo_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
mode=${1:---check}
case "$mode" in --check|--apply) ;; *) echo 'Usage: restore-system.sh [--check|--apply]'; exit 2 ;; esac
files=(
    default/grub mkinitcpio.conf nftables.conf apparmor/parser.conf sddm.conf smartd.conf
    systemd/system/workstation-storage-warning.service
    systemd/system/btrfs-scrub@-.service.d/maintenance.conf
    tlp.conf thinkfan.conf thinkfan-normal.conf thinkfan-silent.conf keyd/default.conf
    modprobe.d/nvidia.conf modprobe.d/nvidia-power-management.conf modprobe.d/notpm.conf
    modprobe.d/90-intel-kvm-only.conf sysctl.d/90-sysrq-recovery.conf
    systemd/network/10-networkmanager-ethernet.network
    systemd/system/nftables.service.d/libvirt-dep.conf
    systemd/logind.conf.d/99-lid-lock.conf
    workstation/nvidia-sleep-mode
    pacman.d/hooks/65-nvidia470-compat.hook
    pacman.d/hooks/66-nvidia470-sleep-policy.hook
    pacman.d/hooks/99-copy-kernel-to-efi.hook
    initcpio/post/95-sync-efi
)
for rel in "${files[@]}"; do test -s "$repo_dir/configs/etc/$rel"; done
for name in nvidia470-compat sync-efi-kernels nvidia470-sleep-policy workstation-health-notify; do
    test -s "$repo_dir/scripts/system/$name"
done
for part in 1 2 3; do test -s "$repo_dir/patches/nvidia470/part$part.patch"; done
test -s "$repo_dir/themes/sddm/black-tiffany/Main.qml"
test "$(cat /sys/class/dmi/id/product_name)" = 20EQS59J07 || {
    echo 'This payload is for the ThinkPad P50. Adapt hardware-specific settings first.'; exit 1;
}
test "$(findmnt -n -o UUID /)" = c6838094-6e77-4446-bbb1-0a4acfd72b25 || {
    echo 'Root filesystem UUID differs. Adapt GRUB/EFI settings before restoring.'; exit 1;
}
if [[ "$mode" == --check ]]; then
    printf 'Payload present: %s configs, 4 helpers, 3 NVIDIA patches and SDDM theme.\n' "${#files[@]}"
    echo 'Machine identity matches. No files or services changed.'
    exit 0
fi
if pacman -Q nvidia-580xx-utils >/dev/null 2>&1; then
    echo 'NVIDIA 580 is installed. This restore payload is for tested 470; adapt it before applying.'; exit 1
fi
(( EUID == 0 )) || { echo 'Run sudo bash restore-system.sh --apply'; exit 1; }
for tool in mkinitcpio grub-mkconfig nft systemctl modprobe unshare dkms; do command -v "$tool" >/dev/null; done
for unit in NetworkManager iwd bluetooth apparmor thinkfan tlp virtqemud virtnetworkd virtstoraged; do
    systemctl cat "$unit.service" >/dev/null
done
if systemctl is-active --quiet libvirtd.service; then
    echo 'Legacy libvirtd is active; review migration before restoring modular units.'; exit 1
fi
# Validate firewall in a separate network namespace, without changing host rules.
unshare --net nft --check --file "$repo_dir/configs/etc/nftables.conf"
bash -n "$repo_dir/configs/etc/default/grub"
backup_dir="/var/backups/dotfiles-system-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$backup_dir/files"
backup() {
    local path=$1
    if [[ -e "$path" || -L "$path" ]]; then
        cp -a --parents -- "$path" "$backup_dir/files"
    else
        printf '%s\n' "$path" >> "$backup_dir/created-paths.txt"
    fi
}
systemctl list-unit-files --no-pager > "$backup_dir/units-before.txt"
for rel in "${files[@]}"; do backup "/etc/$rel"; done
for name in nvidia470-compat sync-efi-kernels nvidia470-sleep-policy workstation-health-notify; do backup "/usr/local/libexec/$name"; done
backup /etc/pacman.d/hooks/dkms-cleanup.hook
backup /usr/lib/systemd/system-sleep/nvidia
backup /usr/share/sddm/themes/black-tiffany
backup /boot/grub/grub.cfg
for rel in "${files[@]}"; do
    install -D -o root -g root -m 644 "$repo_dir/configs/etc/$rel" "/etc/$rel"
done
chmod 755 /etc/initcpio/post/95-sync-efi
for name in nvidia470-compat sync-efi-kernels nvidia470-sleep-policy workstation-health-notify; do
    install -D -o root -g root -m 755 "$repo_dir/scripts/system/$name" "/usr/local/libexec/$name"
done
for part in 1 2 3; do
    install -D -o root -g root -m 644 "$repo_dir/patches/nvidia470/part$part.patch" "/usr/local/share/workstation-repair/nvidia470/part$part.patch"
done
mkdir -p /usr/share/sddm/themes/black-tiffany
cp -a "$repo_dir/themes/sddm/black-tiffany/." /usr/share/sddm/themes/black-tiffany/
chown -R root:root /usr/share/sddm/themes/black-tiffany
chmod -R a+rX /usr/share/sddm/themes/black-tiffany
ln -sfn /dev/null /etc/pacman.d/hooks/dkms-cleanup.hook
/usr/local/libexec/nvidia470-compat
/usr/local/libexec/nvidia470-sleep-policy
systemctl disable libvirtd.service libvirtd.socket libvirtd-ro.socket libvirtd-admin.socket
systemctl enable NetworkManager iwd bluetooth apparmor thinkfan tlp nftables
systemctl enable virtqemud.service virtnetworkd.service virtstoraged.service
systemctl enable virtqemud.socket virtnetworkd.socket virtstoraged.socket
systemctl enable virtnodedevd.socket virtsecretd.socket virtproxyd.socket virtlogd.socket virtlockd.socket
systemctl daemon-reload
systemctl enable smartd.service btrfs-scrub@-.timer
sysctl -p /etc/sysctl.d/90-sysrq-recovery.conf
for pkgbase_file in /usr/lib/modules/*/pkgbase; do
    [[ -f "$pkgbase_file" ]] || continue
    case "$(cat "$pkgbase_file")" in
        linux|linux-lts) kernel_dir=${pkgbase_file%/pkgbase}; dkms autoinstall -k "${kernel_dir##*/}" ;;
    esac
done
mkinitcpio -P
grub-mkconfig -o "$backup_dir/grub-new.cfg"
grub-script-check "$backup_dir/grub-new.cfg"
install -m 600 "$backup_dir/grub-new.cfg" /boot/grub/grub.cfg
printf 'Completed. Backup: %s\n' "$backup_dir"
echo 'No VM, firewall, network connection, login session, sleep or reboot was restarted.'
