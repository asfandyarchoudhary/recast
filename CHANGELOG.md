# Changelog

All notable changes to Recast will be documented in this file.

---

## [0.1.0] — 2026-03-11

### Initial release

- Interactive mode with drive auto-detection
- Non-interactive mode via `--device` and `--format` flags
- Animated progress bar during formatting
- Drive table showing device, size, label and model
- Safety guard — refuses to format system/internal disks
- Dry-run mode via `--dry-run`
- Confirmation prompt before any format operation
- Volume label support with per-format sanitization
- `--list` to list all connected removable drives
- `--formats` to show supported formats for current OS
- `--version` to show version
- Linux support: ext4, ext3, ext2, NTFS, exFAT, FAT32, FAT16
- macOS support: APFS, NTFS, exFAT, FAT32, FAT16
- Auto-installs formatting dependencies on Linux via package manager
- Auto-installs macFUSE + ntfs-3g on macOS for full NTFS read/write support
- Installer script (`recast.sh`) with `--install`, `--uninstall`, `--help` flags
- Compatible with Python 3.6+ and Bash 3.2+
