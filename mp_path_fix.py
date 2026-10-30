import sys
import os
import inspect

sys.dont_write_bytecode = True
os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")


def _get_entry_script(fallback=None):
    """Tra ve script goc (do nguoi dung chay truc tiep), khong phai module duoc import."""
    main_mod = sys.modules.get("__main__")
    main_file = getattr(main_mod, "__file__", None)
    if main_file and os.path.exists(main_file):
        return main_file
    if sys.argv and sys.argv[0] and os.path.exists(sys.argv[0]):
        return sys.argv[0]
    return fallback


def _caller_is_main():
    try:
        frame = inspect.currentframe().f_back.f_back
        return frame.f_globals.get("__name__") == "__main__"
    except Exception:
        return False


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
    if caller_file and _caller_is_main():
        target = caller_file
    else:
        target = _get_entry_script(caller_file)

    if not target:
        return

    cwd = os.getcwd()
    script = os.path.abspath(target)
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
        env["PYTHONUNBUFFERED"] = "1"
        args = sys.argv[1:]
        cmd = [sys.executable, short_script] + args
        sys.stdout.flush()
        sys.stderr.flush()
        p = subprocess.Popen(cmd, cwd=short_cwd, env=env, shell=False)
        p.wait()
        sys.exit(p.returncode if p.returncode is not None else 0)
