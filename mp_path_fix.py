import sys
import os

sys.dont_write_bytecode = True
os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")


def fix_windows_unicode_path(caller_file=None):
    if os.name != "nt":
        return
    if os.environ.get("_MP_FIX_DONE") == "1":
        return

    import ctypes
    from ctypes import wintypes
    import subprocess

    _GetShortPathNameW = ctypes.windll.kernel32.GetShortPathNameW
    _GetShortPathNameW.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.DWORD]
    _GetShortPathNameW.restype = wintypes.DWORD

    def get_short_path(long_path):
        long_path = os.path.abspath(long_path)
        buf_size = _GetShortPathNameW(long_path, None, 0)
        if buf_size == 0:
            return long_path
        buf = ctypes.create_unicode_buffer(buf_size)
        if _GetShortPathNameW(long_path, buf, buf_size) == 0:
            return long_path
        return buf.value

    def _has_unicode(s):
        try:
            s.encode("ascii")
            return False
        except UnicodeEncodeError:
            return True

    if caller_file is None:
        caller_file = sys.argv[0]
        if not caller_file or not os.path.exists(caller_file):
            for frame_info in sys._current_frames().values():
                f = frame_info.f_back
                while f is not None:
                    if f.f_globals.get("__name__") == "__main__":
                        caller_file = f.f_globals.get("__file__") or caller_file
                        break
                    f = f.f_back
                break

    cwd = os.getcwd()
    script = os.path.abspath(caller_file)
    short_cwd = get_short_path(cwd)
    short_script = get_short_path(script)
    need_fix = (
        _has_unicode(cwd)
        or _has_unicode(script)
        or (cwd != short_cwd)
        or (script != short_script)
    )

    if need_fix:
        env = os.environ.copy()
        env["_MP_FIX_DONE"] = "1"
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        args = sys.argv[1:]
        cmd = [sys.executable, short_script] + args
        sys.stdout.flush()
        sys.stderr.flush()
        p = subprocess.Popen(cmd, cwd=short_cwd, env=env, shell=False)
        p.wait()
        sys.exit(p.returncode if p.returncode is not None else 0)
