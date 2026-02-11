import mmap
import struct
import subprocess
import time
import os
import sys
import json
import atexit

# -----------------------------
# Paths (NO __file__)
# -----------------------------
def get_base_dir() -> str:
    p = os.path.abspath(sys.argv[0])
    return os.path.dirname(p)

BASE_DIR = get_base_dir()

# -----------------------------
# Default config (external)
# -----------------------------
DEFAULT_CONFIG = {
    "virpil": {
        "exe": "VPC_LED_Control.exe",
        "vid": "3344",
        "pid": "025A"
    },
    "bms": {
        "tag": "FalconSharedMemoryArea",
        "mmap_size": 132,
        "startup_delay_sec": 12.0,
        "reopen_retry_sec": 1.0,
        "poll_hz": 10,

        "lightBits_off": 108,
        "lightBits2_off": 124,
        "lightBits3_off": 128
    },
    "failsafe": {
        "off_on_exit": True,
        "off_when_bms_missing": True
    },
    "mappings": [
        {"name": "Master Caution", "word": "lb",  "mask": "0x1",        "cmd": 6,  "on": ["FF","80","00"], "off": ["00","00","00"]},
        {"name": "SpeedBrake",     "word": "lb3", "mask": "0x800000",   "cmd": 9,  "on": ["00","FF","00"], "off": ["00","00","00"]},
        {"name": "GearHandle",     "word": "lb2", "mask": "0x40000000", "cmd": 10, "on": ["FF","00","00"], "off": ["00","00","00"]},
        {"name": "LeftGearDown",   "word": "lb3", "mask": "0x20000",    "cmd": 12, "on": ["00","FF","00"], "off": ["00","00","00"]},
        {"name": "NoseGearDown",   "word": "lb3", "mask": "0x10000",    "cmd": 13, "on": ["00","FF","00"], "off": ["00","00","00"]},
        {"name": "RightGearDown",  "word": "lb3", "mask": "0x40000",    "cmd": 14, "on": ["00","FF","00"], "off": ["00","00","00"]}
    ]
}

CONFIG_PATH = os.path.join(BASE_DIR, "virpil_bms_leds.json")

def parse_int(x):
    if isinstance(x, int):
        return x
    if isinstance(x, str):
        return int(x, 0)  # "123" or "0x1A"
    raise ValueError(f"Expected int/str int, got {type(x)}")

def load_config():
    created = False
    if not os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_CONFIG, f, indent=2)
        created = True

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    # normalize + validate mappings
    mappings = cfg.get("mappings", [])
    for m in mappings:
        m["mask"] = parse_int(m.get("mask"))
        m["cmd"] = int(m.get("cmd"))
        m["on"] = tuple(m.get("on"))
        m["off"] = tuple(m.get("off"))
        if m.get("word") not in ("lb", "lb2", "lb3"):
            raise RuntimeError(f"Invalid mapping word: {m.get('word')} (must be lb/lb2/lb3)")
        if len(m["on"]) != 3 or len(m["off"]) != 3:
            raise RuntimeError(f"Mapping {m.get('name')} must have on/off like ['FF','00','00']")

    return cfg, created

# -----------------------------
# Virpil tool
# -----------------------------
CREATE_NO_WINDOW = 0x08000000

def vpc_led(exe_path: str, vid: str, pid: str, cmd_dec: int, r: str, g: str, b: str):
    subprocess.run(
        [exe_path, vid, pid, str(cmd_dec), r, g, b],
        cwd=BASE_DIR,
        creationflags=CREATE_NO_WINDOW,
        check=False
    )

# -----------------------------
# BMS shared memory
# -----------------------------
def read_u32(mm: mmap.mmap, offset: int) -> int:
    mm.seek(offset)
    return struct.unpack("<I", mm.read(4))[0]

def try_open_bms_mmap(tag: str, size: int):
    try:
        return mmap.mmap(-1, size, tagname=tag, access=mmap.ACCESS_READ)
    except Exception:
        return None

def sleep_interruptible(seconds: float, step: float = 0.1):
    # allows clean Ctrl+C without ugly tracebacks from deep sleeps
    end = time.time() + seconds
    while True:
        remaining = end - time.time()
        if remaining <= 0:
            return
        time.sleep(min(step, remaining))

def open_bms_mmap_blocking(tag: str, size: int, startup_delay_sec: float, reopen_retry_sec: float):
    sleep_interruptible(float(startup_delay_sec))
    while True:
        mm = try_open_bms_mmap(tag, size)
        if mm is not None:
            return mm
        sleep_interruptible(float(reopen_retry_sec))

# -----------------------------
# Failsafe helpers
# -----------------------------
def unique_cmds(mappings):
    seen = set()
    out = []
    for m in mappings:
        c = int(m["cmd"])
        if c not in seen:
            seen.add(c)
            out.append(c)
    return out

def make_set_all_off(exe_path, vid, pid, mappings):
    cmds = unique_cmds(mappings)
    def _set_all_off():
        for cmd in cmds:
            vpc_led(exe_path, vid, pid, cmd, "00", "00", "00")
    return _set_all_off

# -----------------------------
# Main
# -----------------------------
def main():
    cfg, created = load_config()
    if created:
        print(f"Created default config: {CONFIG_PATH}")
        print("Edit it if you want, or just run again. (Continuing with defaults now.)")

    v = cfg["virpil"]
    b = cfg["bms"]
    f = cfg.get("failsafe", {})

    exe_path = os.path.join(BASE_DIR, v.get("exe", "VPC_LED_Control.exe"))
    vid = v.get("vid", "3344")
    pid = v.get("pid", "025A")

    mappings = cfg.get("mappings", [])
    set_all_off = make_set_all_off(exe_path, vid, pid, mappings)

    if f.get("off_on_exit", True):
        atexit.register(set_all_off)

    tag = b.get("tag", "FalconSharedMemoryArea")
    mmap_size = int(b.get("mmap_size", 132))
    startup_delay_sec = float(b.get("startup_delay_sec", 12.0))
    reopen_retry_sec = float(b.get("reopen_retry_sec", 1.0))
    poll_hz = float(b.get("poll_hz", 10))
    poll_dt = 1.0 / poll_hz if poll_hz > 0 else 0.1

    off_lb  = int(b.get("lightBits_off", 108))
    off_lb2 = int(b.get("lightBits2_off", 124))
    off_lb3 = int(b.get("lightBits3_off", 128))

    try:
        mm = open_bms_mmap_blocking(tag, mmap_size, startup_delay_sec, reopen_retry_sec)
    except KeyboardInterrupt:
        # Clean exit if you Ctrl+C while waiting to start
        return

    last = [None] * len(mappings)
    bms_present = True

    while True:
        try:
            lb  = read_u32(mm, off_lb)
            lb2 = read_u32(mm, off_lb2)
            lb3 = read_u32(mm, off_lb3)
            words = {"lb": lb, "lb2": lb2, "lb3": lb3}

            if not bms_present:
                bms_present = True
                last = [None] * len(mappings)

            for i, m in enumerate(mappings):
                active = (words[m["word"]] & m["mask"]) != 0
                if active != last[i]:
                    r, g, b_ = m["on"] if active else m["off"]
                    vpc_led(exe_path, vid, pid, int(m["cmd"]), r, g, b_)
                    last[i] = active

            time.sleep(poll_dt)

        except KeyboardInterrupt:
            # Clean exit (atexit will run)
            return

        except Exception:
            # BMS likely exited or mapping became invalid
            bms_present = False
            try:
                mm.close()
            except Exception:
                pass
            mm = None

            if f.get("off_when_bms_missing", True):
                set_all_off()

            # retry until BMS returns (Ctrl+C here should be clean too)
            try:
                while mm is None:
                    mm = try_open_bms_mmap(tag, mmap_size)
                    if mm is None:
                        sleep_interruptible(reopen_retry_sec)
            except KeyboardInterrupt:
                return

if __name__ == "__main__":
    main()
