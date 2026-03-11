#!/usr/bin/env bash

set -e

SCRIPT_NAME="recast"
INSTALL_DIR="/usr/local/bin"
INSTALL_PATH="$INSTALL_DIR/$SCRIPT_NAME"
SOURCE="$(dirname "$0")/recast.py"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

info()    { printf "%b\n" "${CYAN}i  ${NC}$1"; }
success() { printf "%b\n" "${GREEN}✔  ${NC}$1"; }
warn()    { printf "%b\n" "${YELLOW}!  ${NC}$1"; }
error()   { printf "%b\n" "${RED}✖  ${NC}$1"; }
hr()      { printf "%b\n" "${BOLD}────────────────────────────────────────────────────${NC}"; }

check_root() {
    if [[ $EUID -ne 0 ]]; then
        error "Root privileges required. Run: sudo bash recast.sh $*"
        exit 1
    fi
}

check_python() {
    if command -v python3 &>/dev/null; then
        PY_VER=$(python3 --version 2>&1 | awk '{print $2}')
        success "python3 found (v$PY_VER)"
    else
        error "python3 not found. Install it first (e.g. sudo apt install python3)."
        exit 1
    fi
}

install_deps_linux() {
    info "Installing recommended formatting tools …"
    if command -v apt &>/dev/null; then
        apt install -y ntfs-3g dosfstools exfatprogs e2fsprogs util-linux 2>/dev/null || \
        apt install -y ntfs-3g dosfstools exfat-utils  e2fsprogs util-linux 2>/dev/null || true
    elif command -v dnf &>/dev/null; then
        dnf install -y ntfs-3g dosfstools exfatprogs e2fsprogs util-linux 2>/dev/null || true
    elif command -v pacman &>/dev/null; then
        pacman -S --noconfirm ntfs-3g dosfstools exfatprogs e2fsprogs util-linux 2>/dev/null || true
    elif command -v zypper &>/dev/null; then
        zypper install -y ntfs-3g dosfstools exfatprogs e2fsprogs util-linux 2>/dev/null || true
    else
        warn "Unknown package manager — skipping auto-install of dependencies."
        warn "Manually install: ntfs-3g dosfstools exfatprogs e2fsprogs util-linux"
    fi
}

install_ntfs_macos() {
    echo
    hr
    printf "%b\n" "  ${BOLD}macOS NTFS Write Support (Optional)${NC}"
    hr
    printf "%b\n" "  macOS can only ${BOLD}read${NC} NTFS drives by default."
    printf "%b\n" "  Installing ${CYAN}macFUSE${NC} + ${CYAN}ntfs-3g${NC} enables free read/write NTFS support."
    printf "%b\n" "  Both are free and open-source, installed via Homebrew."
    echo
    read -r -p "  Install NTFS write support? [Y/n]: " ans
    ans=$(echo "${ans:-y}" | tr '[:upper:]' '[:lower:]')
    
    if [[ "$ans" == "n" || "$ans" == "no" ]]; then
        warn "Skipping NTFS write support. NTFS drives will be read-only on this Mac."
        return
    fi

    if ! command -v brew &>/dev/null; then
        echo
        warn "Homebrew is not installed. It is required to install ntfs-3g."
        read -r -p "  Install Homebrew now? [Y/n]: " brew_ans
        brew_ans=$(echo "${brew_ans:-y}" | tr '[:upper:]' '[:lower:]')
        
        if [[ "$brew_ans" == "n" || "$brew_ans" == "no" ]]; then
            warn "Skipping. Install Homebrew manually from https://brew.sh"
            return
        fi
        info "Installing Homebrew …"
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
        if ! command -v brew &>/dev/null; then
            error "Homebrew installation failed. Install manually from https://brew.sh"
            return
        fi
        success "Homebrew installed."
    fi

    echo
    info "Installing macFUSE …"
    brew install --cask macfuse
    if [[ $? -ne 0 ]]; then
        error "macFUSE installation failed. Try: brew install --cask macfuse"
        return
    fi
    success "macFUSE installed."

    echo
    info "Installing ntfs-3g …"
    brew install ntfs-3g-apple 2>/dev/null || brew install ntfs-3g
    if [[ $? -ne 0 ]]; then
        error "ntfs-3g installation failed. Try: brew install ntfs-3g-apple"
        return
    fi
    success "ntfs-3g installed."

    echo
    success "NTFS read/write support installed successfully."
    warn "A system restart may be required before NTFS write support becomes active."
    echo
}

do_install() {
    echo
    hr
    printf "%b\n" "  ${BOLD}${GREEN}Recast v0.1.0 — Installer${NC}"
    printf "%b\n" "  ${CYAN}by Asfandyar Choudhary${NC}"
    hr
    echo

    check_python

    if [[ ! -f "$SOURCE" ]]; then
        error "recast.py not found at: $SOURCE"
        error "Make sure recast.sh and recast.py are in the same directory."
        exit 1
    fi

    if [[ "$(uname)" == "Linux" ]]; then
        install_deps_linux
    fi

    if [[ "$(uname)" == "Darwin" ]]; then
        install_ntfs_macos
    fi

    cp "$SOURCE" "$INSTALL_PATH"
    chmod +x "$INSTALL_PATH"

    PYTHON_PATH="$(command -v python3)"
    sed -i.bak "1s|^.*$|#!${PYTHON_PATH}|" "$INSTALL_PATH"
    rm -f "${INSTALL_PATH}.bak"

    echo
    success "Installed → $INSTALL_PATH"
    echo
    printf "%b\n" "  ${BOLD}Quick start:${NC}"
    printf "%b\n" "    ${YELLOW}recast${NC}                                — interactive mode"
    printf "%b\n" "    ${YELLOW}recast --list${NC}                         — list USB drives"
    printf "%b\n" "    ${YELLOW}recast --device /dev/sdb --format ntfs${NC} — format directly"
    printf "%b\n" "    ${YELLOW}recast --formats${NC}                      — show supported formats"
    printf "%b\n" "    ${YELLOW}recast --help${NC}                         — full help"
    echo
    printf "%b\n" "  ${BOLD}To uninstall later:${NC}"
    printf "%b\n" "    ${YELLOW}sudo bash recast.sh --uninstall${NC}"
    echo
}

do_uninstall() {
    echo
    hr
    printf "%b\n" "  ${BOLD}${RED}Recast v0.1.0 — Uninstaller${NC}"
    printf "%b\n" "  ${CYAN}by Asfandyar Choudhary${NC}"
    hr
    echo

    if [[ ! -f "$INSTALL_PATH" ]]; then
        warn "Recast is not installed at $INSTALL_PATH — nothing to remove."
        exit 0
    fi

    info "Removing $INSTALL_PATH …"
    rm -f "$INSTALL_PATH"

    if [[ ! -f "$INSTALL_PATH" ]]; then
        echo
        success "Recast has been uninstalled successfully."
        echo
    else
        error "Failed to remove $INSTALL_PATH. Try manually: sudo rm $INSTALL_PATH"
        exit 1
    fi
}

case "${1:-}" in
    --install)
        check_root "$@"
        do_install
        ;;
    --uninstall)
        check_root "$@"
        do_uninstall
        ;;
    --help)
        echo
        printf "%b\n" "  ${BOLD}Recast v0.1.0 — recast.sh${NC}"
        printf "%b\n" "  ${CYAN}by Asfandyar Choudhary${NC}"
        echo
        echo "  Usage:"
        echo "    sudo bash recast.sh --install    — install Recast"
        echo "    sudo bash recast.sh --uninstall  — uninstall Recast"
        echo "    sudo bash recast.sh --help       — show this help"
        echo
        ;;
    *)
        error "Unknown option: ${1:-no option given}"
        echo "  Usage: sudo bash recast.sh [--install | --uninstall | --help]"
        exit 1
        ;;
esac