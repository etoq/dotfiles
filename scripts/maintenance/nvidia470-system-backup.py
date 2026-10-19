#!/usr/bin/python
"""Validate the local 470 recovery kit; with system-backup save boot/driver state.

No package installation, module loading, service changes or reboot is performed.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import pwd
import shutil
import stat
import subprocess as sp
import time

PACKAGES = ['nvidia-470xx-dkms', 'nvidia-470xx-utils', 'opencl-nvidia-470xx',
            'lib32-nvidia-470xx-utils', 'lib32-opencl-nvidia-470xx',
            'nvidia-470xx-settings', 'libxnvctrl-470xx']
RELATIVE = 'Documents/Workstation/2026-10-18/system-repair/nvidia470-rollback'


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def installed():
    return {name: sp.check_output(['pacman', '-Q', name], text=True).split()[1] for name in PACKAGES}


def inspect(home):
    base = home / RELATIVE
    if base.is_symlink():
        raise RuntimeError('Recovery directory must not be a symlink')
    data = json.loads((base / 'manifest.json').read_text())
    proof = json.loads((base / 'isolated-verification.json').read_text())
    if not data.get('verified_isolated_install') or not proof.get('verified') or proof.get('packages') != 7:
        raise RuntimeError('Isolated installation has not been verified')
    if set(data['packages']) != set(PACKAGES) or data['versions'] != installed():
        raise RuntimeError('Installed driver cohort changed; rebuild the recovery packages')
    for name in PACKAGES:
        item = data['packages'][name]
        expected = name + '-' + data['versions'][name] + '-x86_64.pkg.tar.zst'
        archive = base / 'packages' / expected
        if item['file'] != expected or archive.is_symlink() or sha(archive) != item['sha256']:
            raise RuntimeError('Recovery package identity/hash differs: ' + name)
        for relative, info in item['files'].items():
            path = Path('/') / relative
            relpath = Path(relative)
            if relpath.is_absolute() or not relpath.parts or relpath.parts[0] not in ('usr', 'etc') or '..' in relpath.parts:
                raise RuntimeError('Unsafe recorded path')
            status = path.lstat()
            if stat.S_IMODE(status.st_mode) != info['mode']:
                raise RuntimeError('Live permissions changed: ' + relative)
            if info['type'] == 'file' and (not stat.S_ISREG(status.st_mode) or sha(path) != info['sha256']):
                raise RuntimeError('Live file changed: ' + relative)
            if info['type'] == 'symlink' and (not stat.S_ISLNK(status.st_mode) or os.readlink(path) != info['target']):
                raise RuntimeError('Live link changed: ' + relative)
            if info['type'] == 'directory' and not stat.S_ISDIR(status.st_mode):
                raise RuntimeError('Live directory changed: ' + relative)
    return base, data


def archive(target, paths):
    names = [str(path).lstrip('/') for path in paths]
    sp.run(['tar', '--create', '--file', str(target), '--directory', '/', '--acls', '--xattrs',
            '--numeric-owner', '--use-compress-program=zstd -T2 -3', '--', *names], check=True)
    target.chmod(0o600)
    sp.run(['zstd', '--test', '--quiet', str(target)], check=True)


def system_backup(home):
    if os.geteuid() != 0:
        raise RuntimeError('Run system-backup with sudo from your desktop terminal')
    if Path('/var/lib/pacman/db.lck').exists():
        raise RuntimeError('Package manager is busy; wait until it finishes')
    base, data = inspect(home)
    loaded = Path('/sys/module/nvidia/version').read_text().strip()
    if loaded != '470.256.02':
        raise RuntimeError('Loaded driver is not the tested 470.256.02')
    # Read the current images with root before declaring a useful recovery kit.
    kernels = []
    for pkgbase in sorted(Path('/usr/lib/modules').glob('*/pkgbase')):
        name = pkgbase.read_text().strip()
        if name not in ('linux', 'linux-lts'):
            continue
        version = pkgbase.parent.name
        image = Path('/boot') / ('initramfs-' + name + '.img')
        listing = sp.check_output(['lsinitcpio', str(image)], text=True)
        if '/modules/' + version + '/' not in listing:
            raise RuntimeError('Initramfs does not match: ' + version)
        for module in ['nvidia', 'nvidia_drm', 'nvidia_modeset', 'nvidia_uvm']:
            vermagic = sp.check_output(['modinfo', '-k', version, '-F', 'vermagic', module], text=True)
            if not vermagic.startswith(version + ' '):
                raise RuntimeError('Kernel/module mismatch: ' + version)
        kernels.append(version)
    if len(kernels) < 2 or not Path('/boot/efi').is_mount():
        raise RuntimeError('Both installed kernels and the EFI mount are required')
    final_target = Path('/var/backups') / time.strftime('nvidia470-recovery-%Y%m%d-%H%M%S')
    target = Path(str(final_target) + '.incomplete')
    target.mkdir(mode=0o700)
    (target / 'packages').mkdir(mode=0o700)
    for item in data['packages'].values():
        dest = target / 'packages' / item['file']
        shutil.copyfile(base / 'packages' / item['file'], dest)
        dest.chmod(0o600)
        if sha(dest) != item['sha256']:
            raise RuntimeError('Copied package differs')
    shutil.copyfile(base / 'manifest.json', target / 'package-manifest.json')
    shutil.copyfile(base / 'isolated-verification.json', target / 'isolated-verification.json')
    print('Saving current /boot including the mounted EFI partition...', flush=True)
    archive(target / 'boot-and-efi.tar.zst', [Path('/boot')])
    paths = [Path(name) for name in [
        '/etc/modprobe.d', '/etc/workstation', '/etc/mkinitcpio.conf', '/etc/mkinitcpio.d',
        '/etc/default/grub', '/etc/X11', '/etc/sddm.conf', '/etc/pacman.d/hooks',
        '/etc/systemd/logind.conf.d', '/usr/lib/systemd/system-sleep/nvidia',
        '/usr/local/libexec/nvidia470-compat', '/usr/local/libexec/nvidia470-sleep-policy',
        '/usr/local/libexec/sync-efi-kernels', '/usr/local/share/workstation-repair/nvidia470',
        '/var/lib/dkms/mok.key', '/var/lib/dkms/mok.pub']]
    for pattern in ['nvidia*', 'systemd-suspend.service.*', 'systemd-hibernate.service.*']:
        paths.extend(Path('/etc/systemd/system').glob(pattern))
    for name, version in data['versions'].items():
        paths.append(Path('/var/lib/pacman/local') / (name + '-' + version))
    for version in kernels:
        paths.extend((Path('/usr/lib/modules') / version / 'updates/dkms').glob('nvidia*.ko*'))
    paths = sorted(set(path for path in paths if path.exists() or path.is_symlink()))
    print('Saving driver modules, sleep policy and package metadata...', flush=True)
    archive(target / 'driver-state.tar.zst', paths)
    if installed() != data['versions'] or Path('/var/lib/pacman/db.lck').exists():
        raise RuntimeError('Package state changed during the backup; do not use this incomplete kit')
    state = {'complete': True, 'created': time.strftime('%Y-%m-%dT%H:%M:%S%z'),
             'loaded_driver': loaded, 'kernels': kernels, 'versions': data['versions'],
             'package_installation_performed': False, 'reboot_performed': False}
    (target / 'state.json').write_text(json.dumps(state, indent=2) + '\n')
    checksums = []
    for path in sorted(target.rglob('*')):
        if path.is_file():
            checksums.append(sha(path) + '  ' + path.relative_to(target).as_posix())
    (target / 'SHA256SUMS').write_text('\n'.join(checksums) + '\n')
    target.rename(final_target)
    target = final_target
    # Expose only a non-secret completion summary to the invoking user.
    invoking = pwd.getpwuid(int(os.environ['SUDO_UID']))
    report_dir = Path('/run') / ('nvidia470-recovery-' + str(invoking.pw_uid))
    if report_dir.is_symlink() or report_dir.exists() and report_dir.stat().st_uid != 0:
        raise RuntimeError('Unsafe report directory')
    report_dir.mkdir(mode=0o750, exist_ok=True)
    os.chown(report_dir, 0, invoking.pw_gid)
    report_dir.chmod(0o750)
    report = report_dir / 'report.json'
    temporary = report_dir / 'report.tmp'
    if temporary.is_symlink():
        raise RuntimeError('Unsafe temporary report')
    temporary.write_text(json.dumps(dict(state, backup_directory=str(target), archives_tested=True,
                                       archive_bytes={p.name: p.stat().st_size for p in target.glob('*.tar.zst')}), indent=2) + '\n')
    os.chown(temporary, 0, invoking.pw_gid)
    temporary.chmod(0o640)
    temporary.replace(report)
    print('Completed. Verified recovery snapshot:', target)
    print('Read-only completion report:', report)
    print('Driver, services, sleep policy and boot configuration were not changed.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['check', 'system-backup'], nargs='?', default='check')
    args = parser.parse_args()
    os.umask(0o077)
    if os.geteuid() == 0:
        invoking_uid = int(os.environ.get('SUDO_UID', '0'))
        if invoking_uid == 0:
            raise SystemExit('Run from the desktop user terminal with sudo')
        home = Path(pwd.getpwuid(invoking_uid).pw_dir)
    else:
        home = Path.home()
    if args.action == 'system-backup':
        system_backup(home)
    else:
        base, data = inspect(home)
        print('OK: 7 recovery packages, live hashes and isolated installation proof match.')
        print('Local kit:', base)
