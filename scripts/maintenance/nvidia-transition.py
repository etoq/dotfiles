#!/usr/bin/python
"""Pinned workstation NVIDIA migration and offline rollback. Default: check only."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import pwd
import shutil
import subprocess as sp
import sys
import time

HERE = Path(__file__).resolve().parent
PLAN = HERE / 'nvidia-transition-plan.json'
UNITS = ['nvidia-suspend.service', 'nvidia-resume.service',
         'nvidia-hibernate.service', 'nvidia-suspend-then-hibernate.service']
ASSETS = {
    'nvidia470-sleep-policy': ('scripts/system/nvidia470-sleep-policy', '/usr/local/libexec/nvidia470-sleep-policy', 0o755),
    'nvidia470-compat': ('scripts/system/nvidia470-compat', '/usr/local/libexec/nvidia470-compat', 0o755),
    'sync-efi-kernels': ('scripts/system/sync-efi-kernels', '/usr/local/libexec/sync-efi-kernels', 0o755),
    'verify-kernel-stack': ('scripts/local-bin/verify-kernel-stack', None, 0o755),
    '65-nvidia470-compat.hook': ('configs/etc/pacman.d/hooks/65-nvidia470-compat.hook', '/etc/pacman.d/hooks/65-nvidia470-compat.hook', 0o644),
    '66-nvidia470-sleep-policy.hook': ('configs/etc/pacman.d/hooks/66-nvidia470-sleep-policy.hook', '/etc/pacman.d/hooks/66-nvidia470-sleep-policy.hook', 0o644),
    '99-copy-kernel-to-efi.hook': ('configs/etc/pacman.d/hooks/99-copy-kernel-to-efi.hook', '/etc/pacman.d/hooks/99-copy-kernel-to-efi.hook', 0o644),
}


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def output(args):
    return sp.check_output(args, text=True).strip()


def verify_archive(path, item):
    if path.is_symlink() or sha(path) != item['sha256']:
        raise RuntimeError('Package checksum differs: ' + str(path))
    if output(['pacman', '-Qp', '--', str(path)]).split() != [item['name'], item['version']]:
        raise RuntimeError('Package identity differs: ' + str(path))


def kernels():
    return sorted(path.parent.name for path in Path('/usr/lib/modules').glob('*/pkgbase')
                  if path.read_text().strip() in ('linux', 'linux-lts'))


def assets():
    if (HERE / 'assets').is_dir():
        return {name: HERE / 'assets' / name for name in ASSETS}
    repo = HERE.parents[1]
    return {name: repo / relative for name, (relative, _, _) in ASSETS.items()}


def check_machine(plan, allowed_profiles=('callback',)):
    if Path('/sys/class/dmi/id/product_name').read_text().strip() != plan['machine']:
        raise RuntimeError('Machine identity differs')
    if output(['findmnt', '-n', '-o', 'UUID', '/']) != plan['root_uuid']:
        raise RuntimeError('Root filesystem differs')
    if kernels() != sorted(plan['kernels']):
        raise RuntimeError('Installed kernels changed; prepare a new tested plan')
    if not Path('/boot/efi').is_mount():
        raise RuntimeError('EFI is not mounted')
    if Path('/var/lib/pacman/db.lck').exists():
        raise RuntimeError('Package manager is busy')
    if Path('/etc/workstation/nvidia-sleep-mode').read_text().strip() not in allowed_profiles:
        raise RuntimeError('Unexpected NVIDIA sleep profile')


def preserve_preflight(plan):
    memory = sum(int(value) for value in output(['nvidia-smi', '--query-gpu=memory.total',
                                               '--format=csv,noheader,nounits']).splitlines()) * 1024 ** 2
    needed = (memory * 105 + 99) // 100 + 8 * 1024 ** 3
    if shutil.disk_usage('/var/tmp').free < needed:
        raise RuntimeError('Not enough disk space for full VRAM plus the transition reserve')
    fd = os.open('/var/tmp', os.O_TMPFILE | os.O_RDWR, 0o600)
    try:
        os.write(fd, b'workstation-nvidia-vram-check')
        os.lseek(fd, 0, os.SEEK_SET)
        if os.read(fd, 64) != b'workstation-nvidia-vram-check':
            raise RuntimeError('VRAM backing filesystem failed a temporary-file check')
    finally:
        os.close(fd)
    for kernel in plan['kernels']:
        config = Path('/usr/lib/modules') / kernel / 'build/.config'
        if 'CONFIG_DRM_SIMPLEDRM=y\n' not in config.read_text():
            raise RuntimeError('Early boot framebuffer not verified for ' + kernel)
    for preset in Path('/etc/mkinitcpio.d').glob('linux*.preset'):
        if any(line.strip().startswith(('ALL_config=', 'default_config=')) for line in preset.read_text().splitlines()):
            raise RuntimeError('Explicit preset config would bypass the managed mkinitcpio drop-in')
    # The same pinned 580 cohort previously produced 288 MiB images. Budget 320
    # MiB each even though late loading should make them smaller; do not depend
    # on that reduction to fit the first atomic synchronization.
    remaining = shutil.disk_usage('/boot/efi').free
    for base in ('linux', 'linux-lts'):
        for name in ('vmlinuz-' + base, 'initramfs-' + base + '.img'):
            new_size = 320 * 1024 ** 2 if name.startswith('initramfs-') else (Path('/boot') / name).stat().st_size
            old_size = (Path('/boot/efi/EFI/ARCH') / name).stat().st_size
            if remaining < new_size + 8 * 1024 ** 2:
                raise RuntimeError('Insufficient EFI space for the conservative 580 image budget')
            remaining += old_size - new_size


def inhibit_sleep(run):
    unit = 'workstation-nvidia-transition-inhibit.service'
    if sp.run(['systemctl', 'is-active', '--quiet', unit]).returncode:
        run(['systemd-run', '--unit=' + unit, '--collect', '--property=Type=exec', '--',
             '/usr/bin/systemd-inhibit', '--what=sleep', '--mode=block',
             '--who=workstation-nvidia-transition', '--why=Reboot after driver transition',
             '/usr/bin/sleep', 'infinity'])
    for _ in range(30):
        locks = json.loads(output(['systemd-inhibit', '--list', '--json=short', '--no-pager']))
        if any(lock.get('who') == 'workstation-nvidia-transition'
               and lock.get('mode') == 'block' and 'sleep' in lock.get('what', '').split(':')
               for lock in locks):
            return
        time.sleep(.1)
    raise RuntimeError('Could not establish the sleep inhibitor before changing the driver')


def select_profile(run, profile, root=Path('/')):
    marker = root / 'etc/workstation/nvidia-sleep-mode'
    before = marker.read_bytes()
    temporary = marker.with_name(marker.name + '.transition-new')
    temporary.write_text(profile + '\n')
    temporary.chmod(0o644)
    temporary.replace(marker)
    try:
        run(['/usr/local/libexec/nvidia470-sleep-policy'])
    except Exception:
        temporary.write_bytes(before)
        temporary.chmod(0o644)
        temporary.replace(marker)
        try:
            run(['/usr/local/libexec/nvidia470-sleep-policy'])
        except Exception as restore_error:
            print('Previous profile marker restored; policy needs inspection:', restore_error, file=sys.stderr)
        raise


def verify_backup(plan):
    base = Path(plan['backup'])
    if base.is_symlink() or base.stat().st_uid != 0 or base.stat().st_mode & 0o077:
        raise RuntimeError('Recovery backup must be root-owned and private')
    state = json.loads((base / 'state.json').read_text())
    if not state.get('complete') or sorted(state['kernels']) != sorted(plan['kernels']):
        raise RuntimeError('Recovery backup is incomplete or for different kernels')
    for line in (base / 'SHA256SUMS').read_text().splitlines():
        expected, relative = line.split('  ', 1)
        path = base / relative
        if Path(relative).is_absolute() or '..' in Path(relative).parts or path.is_symlink() or sha(path) != expected:
            raise RuntimeError('Recovery backup checksum failed: ' + relative)
    for item in plan['reverse']:
        verify_archive(base / 'packages' / item['file'], item)
    return base


def verify_forward(plan):
    base = Path(plan['home']) / plan['repair_relative']
    proof = json.loads((base / 'logs/nvidia-transactions-verification.json').read_text())
    if not proof.get('verified') or not proof.get('dependencies_enabled') or proof.get('forward_packages') != len(plan['forward']):
        raise RuntimeError('Complete dependency transaction has not been verified')
    modules = json.loads((base / 'logs/nvidia580-build-verification.json').read_text())
    for kernel in plan['kernels']:
        for name in ('nvidia', 'nvidia-modeset', 'nvidia-drm', 'nvidia-uvm'):
            record = modules[kernel][name]
            if record['version'] != '580.178.04' or not record['vermagic'].startswith(kernel + ' '):
                raise RuntimeError('Precompiled module proof differs')
    paths = []
    for item in plan['forward']:
        path = base / item['path']
        verify_archive(path, item)
        paths.append(path)
    return paths


def installed_matches(records):
    for item in records:
        if output(['pacman', '-Q', '--', item['name']]).split() != [item['name'], item['version']]:
            raise RuntimeError('Installed package differs: ' + item['name'])


class Runner:
    def __init__(self, log):
        self.log = log

    def __call__(self, args):
        print('+', ' '.join(map(str, args)), flush=True)
        with self.log.open('ab') as log:
            log.write(('\n+ ' + ' '.join(map(str, args)) + '\n').encode())
            with sp.Popen(list(map(str, args)), stdout=sp.PIPE, stderr=sp.STDOUT) as process:
                # read1 forwards even prompts without a trailing newline; stdin stays the user's TTY.
                while chunk := process.stdout.read1(8192):
                    sys.stdout.buffer.write(chunk)
                    sys.stdout.buffer.flush()
                    log.write(chunk)
                    log.flush()
                if process.wait():
                    raise RuntimeError('Command failed; see ' + str(self.log))


def transaction(run, archives, policy, unattended_rollback=False):
    # Normal interactive pacman: no forced dependency removal and no global --noconfirm.
    # Even on a partial failure, restore the explicitly selected sleep configuration.
    try:
        options = ['--noconfirm', '--ask=4'] if unattended_rollback else []
        run(['pacman', '-U', *options, '--', *archives])
    finally:
        run([policy])


def publish_report(plan, report):
    account = pwd.getpwuid(Path(plan['home']).stat().st_uid)
    directory = Path('/run') / ('nvidia-transition-' + str(account.pw_uid))
    if directory.is_symlink() or directory.exists() and directory.stat().st_uid != 0:
        raise RuntimeError('Unsafe transition report directory')
    directory.mkdir(mode=0o750, exist_ok=True)
    directory.chmod(0o750)
    os.chown(directory, 0, account.pw_gid)
    temporary = directory / 'report.json.new'
    # Remove any stale path inside this root-owned directory before creating it.
    temporary.unlink(missing_ok=True)
    with temporary.open('x') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    temporary.chmod(0o640)
    os.chown(temporary, 0, account.pw_gid)
    temporary.replace(directory / 'report.json')
    # Retain a non-secret root-owned result across an emergency reboot.
    persistent = Path('/var/lib/workstation-driver-transition')
    if persistent.is_symlink() or persistent.exists() and persistent.stat().st_uid != 0:
        raise RuntimeError('Unsafe persistent transition report directory')
    persistent.mkdir(mode=0o750, exist_ok=True)
    persistent.chmod(0o750)
    os.chown(persistent, 0, account.pw_gid)
    temporary = persistent / 'report.json.new'
    temporary.unlink(missing_ok=True)
    with temporary.open('x') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    temporary.chmod(0o640)
    os.chown(temporary, 0, account.pw_gid)
    temporary.replace(persistent / 'report.json')


def finish(run, plan, stage, version, profile='callback'):
    for kernel in plan['kernels']:
        run(['dkms', 'autoinstall', '-k', kernel])
        for name in ('nvidia', 'nvidia_drm', 'nvidia_modeset', 'nvidia_uvm'):
            module_version = output(['modinfo', '-k', kernel, '-F', 'version', name])
            if version == '470.256.02' and name == 'nvidia_uvm' and not module_version:
                # 470 UVM has no MODULE_VERSION. Verify its installed bytes against
                # the artifact belonging to this exact DKMS version and kernel.
                installed = Path(output(['modinfo', '-k', kernel, '-F', 'filename', name]))
                artifact = Path('/var/lib/dkms/nvidia') / version / kernel / 'x86_64/module' / installed.name
                if not artifact.is_file() or sha(installed) != sha(artifact):
                    raise RuntimeError('470 UVM differs from its DKMS artifact: ' + kernel)
            elif module_version != version:
                raise RuntimeError('Wrong installed module version: ' + kernel + ' ' + name)
            if not output(['modinfo', '-k', kernel, '-F', 'vermagic', name]).startswith(kernel + ' '):
                raise RuntimeError('Wrong module kernel ABI: ' + kernel + ' ' + name)
    run(['mkinitcpio', '-P'])
    run(['/usr/local/libexec/sync-efi-kernels'])
    run([stage / 'assets/verify-kernel-stack'])
    effective = output(['modprobe', '-c'])
    options = [line for line in effective.splitlines() if line.startswith('options nvidia ')]
    values = [word.split('=', 1)[1] for line in options for word in line.split()
              if word.startswith('NVreg_PreserveVideoMemoryAllocations=')]
    preserve = profile == 'preserve-vram'
    if not values or set(values) != ({'1'} if preserve else {'0'}):
        raise RuntimeError('Effective NVIDIA sleep module options differ')
    if os.access('/usr/lib/systemd/system-sleep/nvidia', os.X_OK) != preserve:
        raise RuntimeError('NVIDIA vendor sleep hook mode differs from the selected profile')
    for unit in UNITS:
        if (Path('/usr/lib/systemd/system') / unit).exists():
            result = sp.run(['systemctl', 'is-enabled', unit], capture_output=True, text=True)
            if result.stdout.strip() != ('enabled' if preserve else 'disabled'):
                raise RuntimeError('NVIDIA sleep service state differs: ' + unit)
    if preserve:
        temporary_paths = [word.split('=', 1)[1] for line in options for word in line.split()
                           if word.startswith('NVreg_TemporaryFilePath=')]
        if not temporary_paths or set(temporary_paths) != {'/var/tmp'}:
            raise RuntimeError('VRAM backing path differs')
        required = output(['systemctl', 'show', 'systemd-suspend.service', '-p', 'Requires', '--value']).split()
        if not {'nvidia-suspend.service', 'nvidia-resume.service'} <= set(required):
            raise RuntimeError('Suspend is missing required NVIDIA dependencies')
        for name in ('linux', 'linux-lts'):
            listing = output(['lsinitcpio', '/boot/initramfs-' + name + '.img'])
            if any('/nvidia.ko' in line or any('/nvidia' + separator + suffix + '.ko' in line
                   for separator in ('-', '_') for suffix in ('uvm', 'drm', 'modeset', 'peermem'))
                   for line in listing.splitlines()):
                raise RuntimeError('NVIDIA was unexpectedly included in the early initramfs: ' + name)
    for name in ('vmlinuz-linux', 'vmlinuz-linux-lts', 'initramfs-linux.img', 'initramfs-linux-lts.img'):
        if sha(Path('/boot') / name) != sha(Path('/boot/efi/EFI/ARCH') / name):
            raise RuntimeError('EFI image differs: ' + name)


def apply(plan, rollback, resume=False, unattended_rollback=False, finish_only=False, preserve_vram=False):
    if os.geteuid() != 0:
        raise RuntimeError('Run the selected action with sudo in your terminal')
    if unattended_rollback and (not rollback or resume):
        raise RuntimeError('Unattended mode is restricted to the pinned 470 rollback')
    if ((preserve_vram or resume) and rollback) or (finish_only and not rollback):
        raise RuntimeError('Invalid combination of transition actions')
    if not rollback and not preserve_vram:
        raise RuntimeError('580 with callback failed the sleep test; use --apply580-preserve')
    if not sys.stdin.isatty() and not unattended_rollback:
        raise RuntimeError('An interactive terminal is required for package confirmation')
    check_machine(plan, ('callback', 'preserve-vram') if rollback or resume else ('callback',))
    base = verify_backup(plan)
    source_assets = assets()
    for path in source_assets.values():
        if not path.is_file():
            raise RuntimeError('Missing helper: ' + str(path))
    if shutil.disk_usage('/').free < 8 * 1024 ** 3:
        raise RuntimeError('At least 8 GiB free on root is required')
    if rollback:
        archives = [base / 'packages' / item['file'] for item in plan['reverse']]
        records, version = plan['reverse'], '470.256.02'
        if finish_only:
            installed_matches(records)
    else:
        installed_matches(plan['forward'] if resume else plan['reverse'])
        if not resume and Path('/sys/module/nvidia/version').read_text().strip() != '470.256.02':
            raise RuntimeError('Loaded driver differs from the tested 470')
        archives = verify_forward(plan)
        records, version = plan['forward'], '580.178.04'
        preserve_preflight(plan)
    # Retain a self-contained root-owned rollback command before any host changes.
    stage = Path('/var/backups') / time.strftime('nvidia-transition-%Y%m%d-%H%M%S')
    stage.mkdir(mode=0o700)
    (stage / 'assets').mkdir(mode=0o700)
    (stage / 'packages').mkdir(mode=0o700)
    shutil.copyfile(Path(__file__).resolve(), stage / 'nvidia-transition.py')
    (stage / 'nvidia-transition-plan.json').write_text(json.dumps(plan, indent=2) + '\n')
    for name, path in source_assets.items():
        shutil.copyfile(path, stage / 'assets' / name)
        (stage / 'assets' / name).chmod(ASSETS[name][2])
    # Keep the exact pre-transition marker and NVIDIA options alongside the rollback command.
    previous_etc = stage / 'previous/etc'
    previous_etc.mkdir(parents=True, exist_ok=True)
    shutil.copytree('/etc/modprobe.d', previous_etc / 'modprobe.d', symlinks=True)
    for relative in ('workstation/nvidia-sleep-mode',
                     'mkinitcpio.conf.d/95-workstation-nvidia-late.conf',
                     'systemd/system/systemd-suspend.service.d/60-workstation-nvidia-vram.conf'):
        source = Path('/etc') / relative
        if source.exists():
            dest = previous_etc / relative
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, dest)
    stable_archives = []
    for path, item in ([] if resume or finish_only else zip(archives, records)):
        stable = stage / 'packages' / path.name
        shutil.copyfile(path, stable)
        stable.chmod(0o600)
        verify_archive(stable, item)
        stable_archives.append(stable)
    for name, (_, destination, mode) in ASSETS.items():
        if destination is None:
            continue
        dest = Path(destination)
        if dest.exists() or dest.is_symlink():
            previous = stage / 'previous' / destination.lstrip('/')
            previous.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(dest, previous)
        dest.parent.mkdir(parents=True, exist_ok=True)
        temporary = dest.with_name(dest.name + '.transition-new')
        shutil.copyfile(stage / 'assets' / name, temporary)
        temporary.chmod(mode)
        temporary.replace(dest)
    run = Runner(stage / 'transition.log')
    report = {'complete': False, 'action': ('finish470' if finish_only else 'restore470') if rollback else ('resume580' if resume else 'apply580'),
              'stage': str(stage), 'reboot_performed': False,
              'created': time.strftime('%Y-%m-%dT%H:%M:%S%z'),
              'target_version': version, 'kernels': plan['kernels'],
              'sleep_profile': 'preserve-vram' if preserve_vram else 'callback'}
    print('Rollback command: sudo python', stage / 'nvidia-transition.py', '--restore470', flush=True)
    try:
        policy = '/usr/local/libexec/nvidia470-sleep-policy'
        inhibit_sleep(run)
        select_profile(run, report['sleep_profile'])
        if not resume and not finish_only:
            transaction(run, stable_archives, policy, unattended_rollback)
        installed_matches(records)
        finish(run, plan, stage, version, report['sleep_profile'])
        report['complete'] = True
    finally:
        (stage / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
        publish_report(plan, report)
    print('Completed. Installed NVIDIA:', version, flush=True)
    print('No reboot, display-manager restart or sleep test was performed.', flush=True)
    print('Save work, then reboot manually into Linux LTS. Do not suspend before reboot.', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument('--apply580', action='store_true')
    actions.add_argument('--restore470', action='store_true')
    actions.add_argument('--resume580', action='store_true')
    actions.add_argument('--apply580-preserve', action='store_true', help='580 trial: full VRAM preservation, procfs sleep services, late GPU loading')
    actions.add_argument('--resume580-preserve', action='store_true')
    actions.add_argument('--restore470-unattended', action='store_true', help='Emergency: verified pinned rollback, auto-answer only package conflicts')
    actions.add_argument('--finish470-unattended', action='store_true', help='Finish verification and images for an already installed pinned 470 cohort')
    args = parser.parse_args()
    plan = json.loads(PLAN.read_text())
    if args.apply580 or args.restore470 or args.resume580 or args.restore470_unattended or args.finish470_unattended or args.apply580_preserve or args.resume580_preserve:
        apply(plan, args.restore470 or args.restore470_unattended or args.finish470_unattended,
              args.resume580 or args.resume580_preserve, args.restore470_unattended or args.finish470_unattended,
              args.finish470_unattended, args.apply580_preserve or args.resume580_preserve)
        return
    check_machine(plan)
    verify_forward(plan)
    installed_matches(plan['reverse'])
    preserve_preflight(plan)
    for path in assets().values():
        if not path.is_file():
            raise RuntimeError('Missing helper: ' + str(path))
    print('OK: machine, kernels, 10 pinned packages, dependencies and module build proofs.')
    print('Root will additionally verify the complete protected rollback backup before installation.')
    print('Check only: no system changes. Installation: sudo python', Path(__file__).resolve(), '--apply580-preserve')


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, OSError, ValueError, KeyError, sp.CalledProcessError) as error:
        print('STOP:', error, file=sys.stderr)
        print('No reboot performed. If a transaction started, do not suspend; inspect its log or restore 470.', file=sys.stderr)
        sys.exit(1)
