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


def check_machine(plan):
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
    if Path('/etc/workstation/nvidia-sleep-mode').read_text().strip() != 'callback':
        raise RuntimeError('Sleep mode differs from the tested callback policy')


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


def transaction(run, archives, policy):
    # Normal interactive pacman: no forced dependency removal and no global --noconfirm.
    # Even on a partial failure, restore the explicitly selected sleep configuration.
    try:
        run(['pacman', '-U', '--', *archives])
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


def finish(run, plan, stage, version):
    for kernel in plan['kernels']:
        run(['dkms', 'autoinstall', '-k', kernel])
        for name in ('nvidia', 'nvidia_drm', 'nvidia_modeset', 'nvidia_uvm'):
            if output(['modinfo', '-k', kernel, '-F', 'version', name]) != version:
                raise RuntimeError('Wrong installed module version: ' + kernel + ' ' + name)
    run(['mkinitcpio', '-P'])
    run(['/usr/local/libexec/sync-efi-kernels'])
    run([stage / 'assets/verify-kernel-stack'])
    effective = output(['modprobe', '-c'])
    options = [line for line in effective.splitlines() if line.startswith('options nvidia ')]
    values = [word.split('=', 1)[1] for line in options for word in line.split()
              if word.startswith('NVreg_PreserveVideoMemoryAllocations=')]
    if not values or set(values) != {'0'}:
        raise RuntimeError('Effective callback sleep module options differ')
    if os.access('/usr/lib/systemd/system-sleep/nvidia', os.X_OK):
        raise RuntimeError('NVIDIA vendor sleep hook remains executable')
    for unit in UNITS:
        if (Path('/usr/lib/systemd/system') / unit).exists():
            result = sp.run(['systemctl', 'is-enabled', unit], capture_output=True, text=True)
            if result.stdout.strip() != 'disabled':
                raise RuntimeError('NVIDIA sleep service not disabled: ' + unit)
    for name in ('vmlinuz-linux', 'vmlinuz-linux-lts', 'initramfs-linux.img', 'initramfs-linux-lts.img'):
        if sha(Path('/boot') / name) != sha(Path('/boot/efi/EFI/ARCH') / name):
            raise RuntimeError('EFI image differs: ' + name)


def apply(plan, rollback):
    if os.geteuid() != 0:
        raise RuntimeError('Run the selected action with sudo in your terminal')
    if not sys.stdin.isatty():
        raise RuntimeError('An interactive terminal is required for package confirmation')
    check_machine(plan)
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
    else:
        installed_matches(plan['reverse'])
        if Path('/sys/module/nvidia/version').read_text().strip() != '470.256.02':
            raise RuntimeError('Loaded driver differs from the tested 470')
        archives = verify_forward(plan)
        records, version = plan['forward'], '580.178.04'
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
    stable_archives = []
    for path, item in zip(archives, records):
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
    report = {'complete': False, 'action': 'restore470' if rollback else 'apply580',
              'stage': str(stage), 'reboot_performed': False,
              'created': time.strftime('%Y-%m-%dT%H:%M:%S%z'),
              'target_version': version, 'kernels': plan['kernels']}
    print('Rollback command: sudo python', stage / 'nvidia-transition.py', '--restore470', flush=True)
    try:
        policy = '/usr/local/libexec/nvidia470-sleep-policy'
        run([policy])
        transaction(run, stable_archives, policy)
        installed_matches(records)
        finish(run, plan, stage, version)
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
    args = parser.parse_args()
    plan = json.loads(PLAN.read_text())
    if args.apply580 or args.restore470:
        apply(plan, args.restore470)
        return
    check_machine(plan)
    verify_forward(plan)
    installed_matches(plan['reverse'])
    for path in assets().values():
        if not path.is_file():
            raise RuntimeError('Missing helper: ' + str(path))
    print('OK: machine, kernels, 10 pinned packages, dependencies and module build proofs.')
    print('Root will additionally verify the complete protected rollback backup before installation.')
    print('Check only: no system changes. Installation: sudo python', Path(__file__).resolve(), '--apply580')


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, OSError, ValueError, KeyError, sp.CalledProcessError) as error:
        print('STOP:', error, file=sys.stderr)
        print('No reboot performed. If a transaction started, do not suspend; inspect its log or restore 470.', file=sys.stderr)
        sys.exit(1)
