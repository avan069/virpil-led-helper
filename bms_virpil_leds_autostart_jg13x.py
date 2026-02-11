import atexit
import os
import subprocess
import sys
import time

# Optional: if running inside JG, this logs to Gremlin's log window
try:
    import gremlin
    def log(msg: str):
        try:
            gremlin.util.log(f"[VirpilLED] {msg}")
        except Exception:
            print(msg)
except Exception:
    def log(msg: str):
        print(msg)

CREATE_NO_WINDOW   = 0x08000000
DETACHED_PROCESS   = 0x00000008

def _this_dir() -> str:
    # Works both in normal python and inside JG
    if "__file__" in globals():
        return os.path.dirname(os.path.abspath(__file__))
    return os.getcwd()

BASE_DIR = _this_dir()

EXE_NAME = "virpil_led_helper.exe"   # <-- change if you named it differently
EXE_PATH = os.path.join(BASE_DIR, EXE_NAME)

# A simple lock so you don’t launch multiple copies if the script is added twice
LOCK_PATH = os.path.join(BASE_DIR, ".virpil_led_helper.lock")

_proc = None
_lock_fd = None

def _acquire_lock() -> bool:
    global _lock_fd
    try:
        # exclusive create
        _lock_fd = os.open(LOCK_PATH, os.O_CREAT | os.O_EXCL | os.O_RDWR)
        os.write(_lock_fd, str(os.getpid()).encode("ascii", "ignore"))
        return True
    except FileExistsError:
        return False
    except Exception as e:
        log(f"Lock error (continuing anyway): {e}")
        return True

def _release_lock():
    global _lock_fd
    try:
        if _lock_fd is not None:
            os.close(_lock_fd)
            _lock_fd = None
        if os.path.exists(LOCK_PATH):
            os.remove(LOCK_PATH)
    except Exception:
        pass

def start_helper():
    global _proc

    if not os.path.isfile(EXE_PATH):
        log(f"EXE not found: {EXE_PATH}")
        return

    if not _acquire_lock():
        log("Helper already running (lock exists). Not starting a second copy.")
        return

    # Start hidden + detached so it doesn’t pop a window or steal focus
    try:
        _proc = subprocess.Popen(
            [EXE_PATH],
            cwd=BASE_DIR,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=CREATE_NO_WINDOW | DETACHED_PROCESS,
        )
        log(f"Started: {EXE_NAME} (pid={_proc.pid})")
    except Exception as e:
        log(f"Failed to start helper: {e}")
        _release_lock()

def stop_helper():
    global _proc
    try:
        if _proc is not None and _proc.poll() is None:
            log("Stopping helper…")
            _proc.terminate()
            # give it a moment
            for _ in range(20):
                if _proc.poll() is not None:
                    break
                time.sleep(0.05)
            _proc = None
    except Exception:
        pass
    finally:
        _release_lock()

atexit.register(stop_helper)

# ---- run on import (i.e., when JG loads the script) ----
start_helper()
