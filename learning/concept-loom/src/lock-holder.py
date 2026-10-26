"""Hold an OS advisory lock until the Node parent closes stdin (also after a crash)."""
import os
import errno
import sys
import time

path, timeout = sys.argv[1], float(sys.argv[2])
flags = os.O_RDWR | os.O_CREAT | getattr(os, 'O_NOFOLLOW', 0)
descriptor = os.open(path, flags, 0o600)
deadline = time.monotonic() + timeout
try:
    if os.name == 'nt':
        import msvcrt
        if os.fstat(descriptor).st_size == 0:
            os.write(descriptor, b'0')
        def acquire():
            os.lseek(descriptor, 0, os.SEEK_SET)
            msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
    else:
        import fcntl
        def acquire():
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
    while True:
        try:
            acquire()
            break
        except OSError as error:
            if error.errno not in (errno.EACCES, errno.EAGAIN):
                raise
            if time.monotonic() >= deadline:
                raise TimeoutError('learning session lock is busy; retry later')
            time.sleep(0.02)
    print('LOCKED', flush=True)
    sys.stdin.buffer.read()
finally:
    os.close(descriptor)
