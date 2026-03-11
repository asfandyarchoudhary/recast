# Recast
A macOS and Linux command-line USB formatting tool.  
`v0.1.0` · by Asfandyar Choudhary

---

## Supported Formats

| Format | Linux | macOS |
|--------|-------|-------|
| ext4   | ✅    | ❌    |
| ext3   | ✅    | ❌    |
| ext2   | ✅    | ❌    |
| NTFS   | ✅    | ✅    |
| exFAT  | ✅    | ✅    |
| FAT32  | ✅    | ✅    |
| FAT16  | ✅    | ✅    |
| APFS   | ❌    | ✅    |

---

## Requirements

- Python 3.6+
- Root / sudo privileges

---

## Installation

```bash
sudo bash recast.sh --install
```

On **Linux** this also auto-installs all required formatting tools (`ntfs-3g`, `dosfstools`, `exfatprogs`, `e2fsprogs`, `util-linux`).

On **macOS** this prompts you to install `macFUSE` + `ntfs-3g` via Homebrew for full NTFS read/write support. If Homebrew is not installed, Recast will install it for you first.

### Uninstall

```bash
sudo bash recast.sh --uninstall
```

### Installer Flags

| Command | Action |
|---------|--------|
| `sudo bash recast.sh --install` | Install Recast |
| `sudo bash recast.sh --uninstall` | Uninstall Recast |
| `sudo bash recast.sh --help` | Show installer help |

### Manual / no install

```bash
python3 recast.py [options]
```

---

## Usage

```bash
recast                                              # interactive mode
recast --list                                       # list USB drives
recast --formats                                    # show supported formats
recast --device /dev/sdb --format ext4              # format directly
recast --device /dev/sdb --format fat32 --label MYUSB  # with label
recast --device /dev/sdb --format ntfs --yes        # skip confirmation
recast --device /dev/sdb --format ext4 --dry-run    # preview only
recast --version                                    # show version
recast --help                                       # full help
```

> macOS uses `/dev/diskN` (e.g. `/dev/disk2`), Linux uses `/dev/sdX` (e.g. `/dev/sdb`).
> Always target the whole disk, not a partition (`/dev/sdb` not `/dev/sdb1`).

---

## Flags

| Flag | Description |
|------|-------------|
| `--list` | List all connected removable drives |
| `--device DEV` | Target device path |
| `--format FMT` | Filesystem format |
| `--label LABEL` | Volume label (default: `USB_DRIVE`) |
| `--yes` | Skip the YES confirmation prompt |
| `--dry-run` | Preview the command without executing |
| `--formats` | List formats supported on the current OS |
| `--version` | Show version and exit |
| `--help` | Show full help and exit |

---

## Safety

- Refuses to format system/internal disks
- Always requires typing `YES` to confirm — unless `--yes` is passed
- `--dry-run` lets you preview the exact command without running it

---

## Troubleshooting

**"Root privileges required"**
Always run with `sudo`:
```bash
sudo recast --device /dev/sdb --format ext4
```

**"command not found: recast" after install**
Your PATH may not include `/usr/local/bin`. Add it for your shell:
```bash
# zsh (macOS default)
echo 'export PATH="/usr/local/bin:$PATH"' >> ~/.zshrc && source ~/.zshrc

# bash (Linux default)
echo 'export PATH="/usr/local/bin:$PATH"' >> ~/.bashrc && source ~/.bashrc
```

**Drive not showing in `--list` (Linux)**
Run `lsblk` to confirm the kernel sees the device. If it does, pass the path directly:
```bash
sudo recast --device /dev/sdb --format fat32
```

**Drive not showing in `--list` (macOS)**
Open Disk Utility (`Cmd+Space` → "Disk Utility") to confirm macOS sees the drive. Try unplugging and replugging if not.

**"mkfs.X not found" (Linux)**
Re-run the installer to auto-install missing tools:
```bash
sudo bash recast.sh --install
```

**"Could not unmount" (Linux)**
A file on the drive is open. Close it and retry, or force it:
```bash
sudo fuser -km /dev/sdb
sudo recast --device /dev/sdb --format ext4
```

**"diskutil unmountDisk failed" (macOS)**
A file on the drive is open in Finder or another app. Close it and retry.

**NTFS write not working after install (macOS)**
macFUSE requires a system restart to activate. Reboot and try again.

---

## License

This project is licensed under the [GNU General Public License v3.0](LICENSE).
