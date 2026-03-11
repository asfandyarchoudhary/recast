#!/usr/bin/env python3
import os
import sys

if sys.version_info < (3, 6):
    sys.exit("Recast requires Python 3.6 or newer. "
             "Current version: {}.{}.".format(*sys.version_info[:2]))

import re
import platform
import subprocess
import argparse
import shutil
import json
import time
import threading
import plistlib

class C:
    RED    = "\033[91m"
    GREEN  = "\033[92m"
    YELLOW = "\033[93m"
    CYAN   = "\033[96m"
    BOLD   = "\033[1m"
    DIM    = "\033[2m"
    RESET  = "\033[0m"

if not sys.stdout.isatty():
    for _a in list(vars(C)):
        if not _a.startswith("_"):
            setattr(C, _a, "")

def info(msg):    print(f"{C.CYAN}i {C.RESET}{msg}")
def success(msg): print(f"{C.GREEN}✔  {C.RESET}{msg}")
def warn(msg):    print(f"{C.YELLOW}!  {C.RESET}{msg}")
def error(msg):   print(f"{C.RED}✖  {C.RESET}{msg}", file=sys.stderr)
def bold(msg):    return f"{C.BOLD}{msg}{C.RESET}"
def hr(n=56):     print(C.DIM + "─" * n + C.RESET)

VERSION = "0.1.0"
OS      = platform.system()

_RECAST_ART = [
    r" ██████╗ ███████╗ ██████╗ █████╗ ███████╗████████╗",
    r" ██╔══██╗██╔════╝██╔════╝██╔══██╗██╔════╝╚══██╔══╝",
    r" ██████╔╝█████╗  ██║     ███████║███████╗   ██║   ",
    r" ██╔══██╗██╔══╝  ██║     ██╔══██║╚════██║   ██║   ",
    r" ██║  ██║███████╗╚██████╗██║  ██║███████║   ██║   ",
    r" ╚═╝  ╚═╝╚══════╝ ╚═════╝╚═╝  ╚═╝╚══════╝   ╚═╝  ",
]

_ANSI_RE = re.compile(r'\033\[[0-9;]*m')

def _vlen(s):
    """Visible length of a string (strips ANSI escape codes before measuring)."""
    return len(_ANSI_RE.sub('', s))

def _pad(s, width):
    """Left-pad a string to visible width, regardless of embedded ANSI codes."""
    return s + ' ' * max(0, width - _vlen(s))

def print_banner():
    print()
    for line in _RECAST_ART:
        print(C.BOLD + C.CYAN + line + C.RESET)
    print()
    print(C.DIM + "  v{}  ·  by Asfandyar Choudhary".format(VERSION) + C.RESET)
    print()
    hr(56)
    print()

def _animate_bar(label, stop_event, result_box, width=38):
    """Bouncing progress bar running in a background thread."""
    spinner = ['⠋','⠙','⠹','⠸','⠼','⠴','⠦','⠧','⠇','⠏']
    i = 0
    sys.stdout.write('\n')
    while not stop_event.is_set():
        pos  = i % (width * 2)
        fill = pos if pos <= width else width * 2 - pos
        bar  = C.CYAN + '█' * fill + C.DIM + '░' * (width - fill) + C.RESET
        spin = C.CYAN + spinner[i % len(spinner)] + C.RESET
        sys.stdout.write('\r  {} {}  [{}] '.format(spin, C.BOLD + label + C.RESET, bar))
        sys.stdout.flush()
        time.sleep(0.065)
        i += 1

    ok   = result_box[0]
    bar  = (C.GREEN if ok else C.RED) + '█' * width + C.RESET
    icon = (C.GREEN + '✔' if ok else C.RED + '✖') + C.RESET
    tag  = (C.GREEN + ' done' if ok else C.RED + ' failed') + C.RESET
    sys.stdout.write('\r  {} {}  [{}]{}\n'.format(
        icon, C.BOLD + label + C.RESET, bar, tag))
    sys.stdout.flush()

def _run_with_progress(cmd, label, dry_run=False):
    """Run a command, showing an animated progress bar until it completes."""
    print('  {}{}{}'.format(C.DIM, ' '.join(str(c) for c in cmd), C.RESET))
    if dry_run:
        warn("Dry-run — command NOT executed.")
        return True

    result_box = [None]
    stop_ev    = threading.Event()
    bar_thread = threading.Thread(
        target=_animate_bar,
        args=(label, stop_ev, result_box),
        daemon=True
    )
    bar_thread.start()

    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )
        result_box[0] = (proc.returncode == 0)
    except FileNotFoundError as e:
        result_box[0] = False
        stop_ev.set()
        bar_thread.join()
        error(str(e))
        return False

    stop_ev.set()
    bar_thread.join()

    if not result_box[0] and proc.stderr.strip():
        print('  {}{}{}'.format(C.DIM, proc.stderr.strip(), C.RESET))

    return result_box[0]

FORMAT_SUPPORT = {
    "Darwin": ["apfs", "exfat", "fat32", "fat", "ntfs"],
    "Linux":  ["ext4", "ext3", "ext2", "ntfs", "exfat", "fat32", "fat"],
}

LABEL_RULES = {
    "fat":   (11,  True,  r'[^A-Z0-9_\-]'),
    "fat32": (11,  True,  r'[^A-Z0-9_\-]'),
    "ntfs":  (32,  False, r'[\\/:*?"<>|]'),
    "exfat": (15,  False, r'[\\/:*?"<>|]'),
    "apfs":  (255, False, r''),
    "ext4":  (16,  False, r''),
    "ext3":  (16,  False, r''),
    "ext2":  (16,  False, r''),
}

def sanitize_label(label: str, fmt: str) -> str:
    max_len, upper, bad_re = LABEL_RULES.get(fmt, (16, False, r''))
    if upper:
        label = label.upper()
    label = label.replace(" ", "_")
    if bad_re:
        label = re.sub(bad_re, "_", label)
    label = label[:max_len].strip("_").strip()
    return label or "USB_DRIVE"

def require_root():
    if OS not in ("Linux", "Darwin"):
        error(f"Unsupported OS: {OS}. Recast supports Linux and macOS only.")
        sys.exit(1)
    if os.geteuid() != 0:
        error("Root privileges required. Run with: sudo recast ...")
        sys.exit(1)

def _run(cmd, dry_run=False):
    """Run a command silently. Used for unmount, wipefs and other prep steps."""
    if dry_run:
        print('  {}{}{}'.format(C.DIM, ' '.join(str(c) for c in cmd), C.RESET))
        warn("Dry-run — command NOT executed.")
        return True
    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )
        return result.returncode == 0
    except FileNotFoundError as e:
        error(str(e))
        return False

def _tool(*names):
    for name in names:
        p = shutil.which(name)
        if p:
            return p
    return None

def _human(n) -> str:
    try:
        n = int(n)
    except (TypeError, ValueError):
        return "?"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PB"

def _collect_label_linux(node: dict) -> str:
    """Return first non-empty label found on the disk or any of its partitions."""
    lbl = (node.get("label") or "").strip()
    if lbl:
        return lbl
    for child in node.get("children", []):
        lbl = _collect_label_linux(child)
        if lbl:
            return lbl
    return ""

def list_disks_linux() -> list:
    try:
        out = subprocess.check_output(
            ["lsblk", "-J", "-b", "-o",
             "NAME,SIZE,TYPE,TRAN,VENDOR,MODEL,RM,HOTPLUG,LABEL"],
            universal_newlines=True, stderr=subprocess.DEVNULL
        )
        data = json.loads(out)
    except Exception as e:
        error(f"lsblk failed: {e}")
        return []

    disks = []
    for dev in data.get("blockdevices", []):
        if dev.get("type") != "disk":
            continue
        rm      = str(dev.get("rm", "0")).lower() in ("1", "true")
        hotplug = str(dev.get("hotplug", "0")).lower() in ("1", "true")
        tran    = str(dev.get("tran") or "").lower()
        if not (rm or hotplug or tran == "usb"):
            continue
        disk_dev = "/dev/" + dev["name"]
        disks.append({
            "device": disk_dev,
            "size":   _human(dev.get("size", 0)),
            "vendor": (dev.get("vendor") or "").strip(),
            "model":  (dev.get("model")  or "").strip(),
            "label":  _collect_label_linux(dev),
        })
    return disks

def list_disks_macos() -> list:
    try:
        raw = subprocess.check_output(
            ["diskutil", "list", "-plist"], stderr=subprocess.DEVNULL
        )
        pl = plistlib.loads(raw)
    except Exception as e:
        error(f"diskutil list failed: {e}")
        return []

    disks = []
    for disk in pl.get("WholeDisks", []):
        try:
            raw2 = subprocess.check_output(
                ["diskutil", "info", "-plist", disk], stderr=subprocess.DEVNULL
            )
            d = plistlib.loads(raw2)
        except Exception:
            continue
        if not (d.get("Removable") or d.get("RemovableMediaOrExternalDevice")):
            continue

        label = (d.get("VolumeName") or "").strip()
        if not label:
            for entry in pl.get("AllDisksAndPartitions", []):
                if entry.get("DeviceIdentifier") != disk:
                    continue
                for part in entry.get("Partitions", []):
                    part_id = part.get("DeviceIdentifier", "")
                    if not part_id:
                        continue
                    try:
                        raw3 = subprocess.check_output(
                            ["diskutil", "info", "-plist", part_id],
                            stderr=subprocess.DEVNULL
                        )
                        p = plistlib.loads(raw3)
                        label = (p.get("VolumeName") or "").strip()
                        if label:
                            break
                    except Exception:
                        continue
                if label:
                    break

        disks.append({
            "device": f"/dev/{disk}",
            "size":   _human(d.get("TotalSize", 0)),
            "vendor": (d.get("VendorID") or "").strip(),
            "model":  (d.get("MediaName") or "").strip(),
            "label":  label,
        })
    return disks

def list_disks() -> list:
    if OS == "Linux":  return list_disks_linux()
    if OS == "Darwin": return list_disks_macos()
    error(f"Unsupported OS: {OS}. Recast supports Linux and macOS only.")
    sys.exit(1)

def _is_removable_linux(device: str) -> bool:
    try:
        out = subprocess.check_output(
            ["lsblk", "-dno", "RM,HOTPLUG,TRAN", device],
            universal_newlines=True, stderr=subprocess.DEVNULL
        ).strip()
        fields = out.split()
        rm      = len(fields) > 0 and fields[0] in ("1", "true")
        hotplug = len(fields) > 1 and fields[1] in ("1", "true")
        tran    = fields[2].lower() if len(fields) > 2 else ""
        return rm or hotplug or tran == "usb"
    except Exception:
        return False

def is_system_disk(device: str) -> bool:
    if OS == "Linux":
        if _is_removable_linux(device):
            return False
        protected = set()
        try:
            out = subprocess.check_output(
                ["findmnt", "-n", "-o", "SOURCE"],
                universal_newlines=True, stderr=subprocess.DEVNULL
            )
            for src in out.splitlines():
                src = src.strip()
                if src:
                    protected.add(src)
                    protected.add(re.sub(r"p?\d+$", "", src))
        except Exception:
            pass
        try:
            out = subprocess.check_output(
                ["swapon", "--show=NAME", "--noheadings"],
                universal_newlines=True, stderr=subprocess.DEVNULL
            )
            for src in out.splitlines():
                src = src.strip()
                if src:
                    protected.add(src)
                    protected.add(re.sub(r"p?\d+$", "", src))
        except Exception:
            pass
        return device in protected

    if OS == "Darwin":
        try:
            raw = subprocess.check_output(
                ["diskutil", "info", "-plist", device],
                stderr=subprocess.DEVNULL
            )
            d = plistlib.loads(raw)
            return bool(d.get("Internal") and not d.get("Removable")
                        and not d.get("RemovableMediaOrExternalDevice"))
        except Exception:
            return False

    return False

def _get_all_nodes_linux(device: str) -> list:
    nodes = [device]
    try:
        out = subprocess.check_output(
            ["lsblk", "-lno", "NAME", device],
            universal_newlines=True, stderr=subprocess.DEVNULL
        )
        for line in out.splitlines():
            path = f"/dev/{line.strip()}"
            if path not in nodes:
                nodes.append(path)
    except Exception:
        pass
    return nodes

def unmount_linux(device: str) -> bool:
    nodes = _get_all_nodes_linux(device)
    for node in nodes:
        try:
            out = subprocess.check_output(
                ["findmnt", "-n", "-o", "TARGET", node],
                universal_newlines=True, stderr=subprocess.DEVNULL
            ).strip()
        except Exception:
            out = ""
        if not out:
            continue
        info(f"Unmounting {node} (mounted at {out}) …")
        r = subprocess.run(["umount", node], stderr=subprocess.PIPE, universal_newlines=True)
        if r.returncode == 0:
            continue
        r2 = subprocess.run(["umount", "-f", "-l", node], stderr=subprocess.PIPE, universal_newlines=True)
        if r2.returncode == 0:
            continue
        subprocess.run(["fuser", "-km", node], stderr=subprocess.DEVNULL)
        time.sleep(0.8)
        r3 = subprocess.run(["umount", "-f", "-l", node], stderr=subprocess.PIPE, universal_newlines=True)
        if r3.returncode != 0:
            error(f"Could not unmount {node}: {r3.stderr.strip()}")
            return False
    return True

def unmount_macos(device: str) -> bool:
    info(f"Unmounting {device} …")
    r = subprocess.run(
        ["diskutil", "unmountDisk", "force", device],
        universal_newlines=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
    )
    if r.returncode != 0:
        error(f"diskutil unmountDisk failed:\n{r.stdout.strip()}")
        return False
    return True

def unmount_disk(device: str) -> bool:
    if OS == "Linux":  return unmount_linux(device)
    if OS == "Darwin": return unmount_macos(device)
    return True

def wipe_linux(device: str, dry_run: bool):
    wipe = _tool("wipefs")
    if not wipe:
        warn("wipefs not found — skipping pre-wipe (util-linux missing).")
        return
    info("Wiping existing partition table and filesystem signatures …")
    _run([wipe, "--all", "--force", device], dry_run)

def format_linux(device: str, fmt: str, label: str, dry_run: bool) -> bool:
    label = sanitize_label(label, fmt)
    wipe_linux(device, dry_run)

    if fmt in ("fat", "fat32"):
        t = _tool("mkfs.fat", "mkdosfs")
        if not t:
            error("mkfs.fat not found.  Fix: sudo apt install dosfstools")
            return False
        fat_bits = "32" if fmt == "fat32" else "16"
        return _run_with_progress([t, "-F{}".format(fat_bits), "-I", "-n", label, device],
                                  "Formatting {}".format(fmt.upper()), dry_run)

    if fmt == "exfat":
        t = _tool("mkfs.exfat", "mkexfatfs")
        if not t:
            error("mkfs.exfat not found.  Fix: sudo apt install exfatprogs")
            return False
        return _run_with_progress([t, "-n", label, device],
                                  "Formatting exFAT", dry_run)

    if fmt == "ntfs":
        t = _tool("mkfs.ntfs", "mkntfs")
        if not t:
            error("mkfs.ntfs not found.  Fix: sudo apt install ntfs-3g")
            return False
        return _run_with_progress([t, "-f", "-F", "-L", label, device],
                                  "Formatting NTFS", dry_run)

    if fmt in ("ext4", "ext3", "ext2"):
        t = _tool("mkfs.{}".format(fmt))
        if not t:
            error("mkfs.{} not found.  Fix: sudo apt install e2fsprogs".format(fmt))
            return False
        return _run_with_progress([t, "-F", "-L", label, device],
                                  "Formatting {}".format(fmt), dry_run)

    error("Unknown format '{}' for Linux.".format(fmt))
    return False

def _brew_installed() -> bool:
    return _tool("brew") is not None

def _ntfs3g_installed() -> bool:
    return _tool("ntfs-3g") is not None or _tool("mount.ntfs-3g") is not None

def _install_homebrew(dry_run: bool) -> bool:
    info("Installing Homebrew …")
    install_cmd = '/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"'
    print(f"  {C.DIM}$ {install_cmd}{C.RESET}")
    if dry_run:
        warn("Dry-run — command NOT executed.")
        return True
    result = subprocess.run(install_cmd, shell=True)
    return result.returncode == 0

def _install_ntfs_write_support(dry_run: bool) -> bool:
    print()
    hr()
    print(f"  {C.BOLD}macOS NTFS Write Support{C.RESET}")
    hr()
    print(f"  macOS can only {C.BOLD}read{C.RESET} NTFS drives natively.")
    print(f"  To enable {C.BOLD}read/write{C.RESET}, Recast can install:")
    print(f"    {C.CYAN}macFUSE{C.RESET}   — open-source filesystem driver  (free)")
    print(f"    {C.CYAN}ntfs-3g{C.RESET}   — open-source NTFS driver         (free)")
    print(f"  Both are installed via Homebrew.")
    print()

    try:
        ans = input(f"{C.BOLD}Install NTFS write support now? [Y/n]: {C.RESET}").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        ans = "n"

    if ans in ("n", "no"):
        warn("Skipping — drive will be formatted as NTFS but will be READ-ONLY on this Mac.")
        return True

    if not _brew_installed():
        print()
        warn("Homebrew is not installed. Homebrew is required to install ntfs-3g.")
        try:
            ans2 = input(f"{C.BOLD}Install Homebrew first? [Y/n]: {C.RESET}").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            ans2 = "n"
        if ans2 in ("n", "no"):
            warn("Skipping — drive will be READ-ONLY on this Mac.")
            return True
        if not _install_homebrew(dry_run):
            error("Homebrew installation failed.")
            error("Install manually from https://brew.sh then re-run recast.")
            return False
        success("Homebrew installed.")

    print()
    info("Installing macFUSE …")
    ok1 = _run(["brew", "install", "--cask", "macfuse"], dry_run)
    if not ok1:
        error("macFUSE installation failed.")
        error("Try manually: brew install --cask macfuse")
        return False
    success("macFUSE installed.")

    print()
    info("Installing ntfs-3g …")
    ok2 = _run(["brew", "install", "ntfs-3g-apple"], dry_run)
    if not ok2:
        warn("ntfs-3g-apple failed, trying ntfs-3g …")
        ok2 = _run(["brew", "install", "ntfs-3g"], dry_run)
    if not ok2:
        error("ntfs-3g installation failed.")
        error("Try manually: brew install ntfs-3g-apple")
        return False

    print()
    success("NTFS read/write support installed successfully.")
    warn("A system restart may be required before NTFS write support is active.")
    print()
    return True

def format_macos(device: str, fmt: str, label: str, dry_run: bool) -> bool:
    label = sanitize_label(label, fmt)
    fs_map = {
        "fat":   "MS-DOS FAT16",
        "fat32": "MS-DOS FAT32",
        "exfat": "ExFAT",
        "ntfs":  "NTFS",
        "apfs":  "APFS",
    }
    fs_str = fs_map.get(fmt)
    if not fs_str:
        error(f"'{fmt}' is not supported on macOS.")
        return False

    if fmt == "ntfs":
        if not _ntfs3g_installed():
            ok = _install_ntfs_write_support(dry_run)
            if not ok:
                return False
        else:
            success("ntfs-3g detected — full read/write NTFS support active.")

    scheme = "GPT" if fmt == "apfs" else "MBR"
    return _run_with_progress(
        ["diskutil", "eraseDisk", fs_str, label, scheme, device],
        "Formatting {}".format(fmt.upper()), dry_run
    )

def format_disk(device: str, fmt: str, label: str, dry_run: bool) -> bool:
    fmt = fmt.lower()
    supported = FORMAT_SUPPORT.get(OS, [])
    if fmt not in supported:
        error(f"'{fmt}' is not supported on {OS}. Supported: {', '.join(supported)}")
        return False
    if OS == "Linux":  return format_linux(device, fmt, label, dry_run)
    if OS == "Darwin": return format_macos(device, fmt, label, dry_run)
    return False

def validate_device(device: str) -> bool:
    if not os.path.exists(device):
        error(f"Device '{device}' does not exist.")
        return False

    name = os.path.basename(device)
    is_partition = False
    if OS == "Linux"  and re.search(r"\d+$", name):
        is_partition = True
    if OS == "Darwin" and re.search(r"s\d+$", name):
        is_partition = True

    if is_partition:
        warn(f"'{device}' looks like a partition, not a whole disk.")
        warn("It's usually better to target the whole disk (e.g. /dev/sdb not /dev/sdb1).")
        try:
            ans = input("Continue targeting this partition? [y/N]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            return False
        if ans != "y":
            return False
    return True

def interactive():
    print_banner()

    info("Scanning for removable drives …\n")
    disks = list_disks()
    if not disks:
        warn("No removable drives detected. Plug in your USB and try again.")
        sys.exit(1)

    COL = {'num': 3, 'dev': 14, 'size': 9, 'label': 18, 'model': 22}

    header = (
        '  ' +
        _pad(C.BOLD + C.CYAN + '#'      + C.RESET, COL['num']   + 1) +
        _pad(C.BOLD + C.CYAN + 'Device' + C.RESET, COL['dev']   + 2) +
        _pad(C.BOLD + C.CYAN + 'Size'   + C.RESET, COL['size']  + 2) +
        _pad(C.BOLD + C.CYAN + 'Label'  + C.RESET, COL['label'] + 2) +
        C.BOLD + C.CYAN + 'Model' + C.RESET
    )
    print(header)
    hr(COL['num'] + COL['dev'] + COL['size'] + COL['label'] + COL['model'] + 10)

    for i, d in enumerate(disks):
        num   = C.BOLD + C.CYAN + str(i + 1) + C.RESET
        dev   = C.BOLD + d['device'] + C.RESET
        size  = d['size']
        label = d['label'] if d['label'] else C.DIM + '(no label)' + C.RESET
        model = (d['vendor'] + ' ' + d['model']).strip() or C.DIM + '—' + C.RESET
        print(
            '  ' +
            _pad(num,   COL['num']   + 1) +
            _pad(dev,   COL['dev']   + 2) +
            _pad(size,  COL['size']  + 2) +
            _pad(label, COL['label'] + 2) +
            model
        )
    print()

    while True:
        try:
            choice = input(f"{C.BOLD}Select drive number (or 'q' to quit): {C.RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print(); sys.exit(0)
        if choice.lower() in ("q", "quit", "exit"):
            sys.exit(0)
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(disks):
                selected = disks[idx]; break
        except ValueError:
            pass
        warn("Invalid selection, try again.")

    device = selected["device"]
    if not validate_device(device): sys.exit(1)
    if is_system_disk(device):
        error(f"REFUSED: {device} is a system/internal disk. Aborting.")
        sys.exit(1)

    supported = FORMAT_SUPPORT.get(OS, [])
    print(f"\n  Supported formats: {C.CYAN}{', '.join(supported)}{C.RESET}\n")
    while True:
        try:
            fmt = input(f"{C.BOLD}Enter format: {C.RESET}").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print(); sys.exit(0)
        if fmt in supported: break
        warn(f"'{fmt}' is invalid. Choose from: {', '.join(supported)}")

    try:
        raw_label = input(f"{C.BOLD}Volume label [USB_DRIVE]: {C.RESET}").strip()
    except (EOFError, KeyboardInterrupt):
        print(); sys.exit(0)
    raw_label = raw_label or "USB_DRIVE"
    label = sanitize_label(raw_label, fmt)
    if label != raw_label:
        warn(f"Label adjusted to '{label}' (rules for {fmt.upper()}).")

    print()
    print(C.YELLOW + C.BOLD + "  ╔══════════════════════════════════════════════╗" + C.RESET)
    print(C.YELLOW + C.BOLD + "  ║   ⚠   WARNING — ALL DATA WILL BE ERASED   ⚠  ║" + C.RESET)
    print(C.YELLOW + C.BOLD + "  ╚══════════════════════════════════════════════╝" + C.RESET)
    print(f"  {C.BOLD}Device{C.RESET} : {bold(device)}  {C.DIM}({selected['size']}){C.RESET}")
    print(f"  {C.BOLD}Format{C.RESET} : {bold(fmt.upper())}")
    print(f"  {C.BOLD}Label {C.RESET} : {bold(label)}")
    print()
    try:
        confirm = input(f"{C.BOLD}{C.RED}Type 'YES' to confirm: {C.RESET}").strip()
    except (EOFError, KeyboardInterrupt):
        print(); warn("Aborted."); sys.exit(0)
    if confirm != "YES":
        warn("Aborted."); sys.exit(0)

    print()
    if not unmount_disk(device):
        error("Could not unmount all partitions. Aborting.")
        sys.exit(1)
    info(f"Formatting {device} as {fmt.upper()} …\n")
    ok = format_disk(device, fmt, label, dry_run=False)
    print()
    if ok:
        success(f"Done! {device} formatted as {fmt.upper()}, label '{label}'.")
    else:
        error("Formatting failed. See output above for details.")
        sys.exit(1)

def build_parser() -> argparse.ArgumentParser:
    all_fmts = sorted({f for fmts in FORMAT_SUPPORT.values() for f in fmts})
    p = argparse.ArgumentParser(
        prog="recast",
        description="Recast — format USB drives from the terminal\nDeveloped by Asfandyar Choudhary",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Formats: {', '.join(all_fmts)}

Examples:
  recast
  recast --list
  recast --device /dev/sdb --format ntfs
  recast --device /dev/sdb --format fat32 --label MYUSB
  recast --device /dev/disk2 --format apfs
  recast --device /dev/sdb --format ext4 --dry-run

Developed by Asfandyar Choudhary
        """
    )
    p.add_argument("--list",    action="store_true", help="List removable drives and exit")
    p.add_argument("--device",  metavar="DEV",       help="Target device (e.g. /dev/sdb, /dev/disk2)")
    p.add_argument("--format",  metavar="FMT",       help=f"Filesystem: {', '.join(all_fmts)}")
    p.add_argument("--label",   metavar="LABEL", default="USB_DRIVE", help="Volume label")
    p.add_argument("--dry-run", action="store_true", help="Preview without executing")
    p.add_argument("--yes",     action="store_true", help="Skip confirmation prompt")
    p.add_argument("--formats", action="store_true", help="Show supported formats and exit")
    p.add_argument("--version", action="version",    version="recast {}".format(VERSION))
    return p

def main():
    parser = build_parser()
    args   = parser.parse_args()

    if args.formats:
        print_banner()
        supported = FORMAT_SUPPORT.get(OS, [])
        print(f"  {C.BOLD}Supported formats on {OS}:{C.RESET}")
        print()
        for f in supported:
            print(f"  {C.CYAN}·{C.RESET} {f}")
        print()
        return

    if args.list:
        require_root()
        print_banner()
        disks = list_disks()
        if not disks:
            warn("No removable drives found.")
            return
        COL = {'dev': 14, 'size': 9, 'label': 20, 'model': 24}
        header = (
            '  ' +
            _pad(C.BOLD + C.CYAN + 'Device' + C.RESET, COL['dev']   + 2) +
            _pad(C.BOLD + C.CYAN + 'Size'   + C.RESET, COL['size']  + 2) +
            _pad(C.BOLD + C.CYAN + 'Label'  + C.RESET, COL['label'] + 2) +
            C.BOLD + C.CYAN + 'Model' + C.RESET
        )
        print(header)
        hr(COL['dev'] + COL['size'] + COL['label'] + COL['model'] + 10)
        for d in disks:
            dev   = C.BOLD + d['device'] + C.RESET
            size  = d['size']
            label = d['label'] if d['label'] else C.DIM + '(no label)' + C.RESET
            model = (d['vendor'] + ' ' + d['model']).strip() or C.DIM + '—' + C.RESET
            print(
                '  ' +
                _pad(dev,   COL['dev']   + 2) +
                _pad(size,  COL['size']  + 2) +
                _pad(label, COL['label'] + 2) +
                model
            )
        print()
        return

    if args.device or args.format:
        if not args.device: parser.error("--device is required with --format")
        if not args.format: parser.error("--format is required with --device")

        require_root()

        device = args.device
        fmt    = args.format.lower()
        label  = sanitize_label(args.label, fmt)

        if label != args.label:
            warn(f"Label sanitized: '{args.label}' -> '{label}'")

        if not validate_device(device): sys.exit(1)

        if is_system_disk(device):
            error(f"REFUSED: {device} is a system disk. Aborting.")
            sys.exit(1)

        supported = FORMAT_SUPPORT.get(OS, [])
        if fmt not in supported:
            error(f"'{fmt}' not supported on {OS}. Options: {', '.join(supported)}")
            sys.exit(1)

        if not args.yes and not args.dry_run:
            print()
            print(C.YELLOW + C.BOLD + "  ╔══════════════════════════════════════════════╗" + C.RESET)
            print(C.YELLOW + C.BOLD + "  ║   ⚠   WARNING — ALL DATA WILL BE ERASED   ⚠  ║" + C.RESET)
            print(C.YELLOW + C.BOLD + "  ╚══════════════════════════════════════════════╝" + C.RESET)
            print(f"  {C.BOLD}Device{C.RESET} : {bold(device)}")
            print(f"  {C.BOLD}Format{C.RESET} : {bold(fmt.upper())}   {C.BOLD}Label{C.RESET} : {bold(label)}")
            print()
            try:
                confirm = input(f"{C.BOLD}{C.RED}Type 'YES' to confirm: {C.RESET}").strip()
            except (EOFError, KeyboardInterrupt):
                print(); warn("Aborted."); sys.exit(0)
            if confirm != "YES":
                warn("Aborted."); sys.exit(0)

        print()
        if not unmount_disk(device):
            error("Could not unmount. Aborting.")
            sys.exit(1)
        info(f"Formatting {device} as {fmt.upper()} …\n")
        ok = format_disk(device, fmt, label, dry_run=args.dry_run)
        print()
        if ok:
            success(f"Done! {device} -> {fmt.upper()}, label '{label}'.")
        else:
            error("Formatting failed.")
            sys.exit(1)
        return

    require_root()
    interactive()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(); warn("Interrupted."); sys.exit(0)
