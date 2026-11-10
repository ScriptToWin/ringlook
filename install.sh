#!/usr/bin/env bash
# install.sh – install ringlook so you can type "ringlook" from any terminal
# Works on virtually all Linux distros (Debian, Ubuntu, Fedora, Arch, etc.)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC_PY="$SCRIPT_DIR/ringlook.py"

if [[ ! -f "$SRC_PY" ]]; then
  echo "Error: ringlook.py not found next to install.sh" >&2
  exit 1
fi

# Prefer system-wide install when we have root, otherwise user-local
if [[ "$(id -u)" -eq 0 ]]; then
  DEST_DIR="/usr/local/lib/ringlook"
  BIN_LINK="/usr/local/bin/ringlook"
  SCOPE="system-wide (all users)"
else
  DEST_DIR="${HOME}/.local/lib/ringlook"
  BIN_LINK="${HOME}/.local/bin/ringlook"
  SCOPE="user-local (${HOME})"
  mkdir -p "${HOME}/.local/bin"
fi

echo "Installing ringlook ($SCOPE)..."
mkdir -p "$DEST_DIR"

# Install the Python script
cp "$SRC_PY" "$DEST_DIR/ringlook.py"

# Install a portable launcher that correctly follows symlinks
cat > "$DEST_DIR/ringlook" << 'LAUNCHER'
#!/usr/bin/env bash
# Portable ringlook launcher (follows symlinks)
SOURCE="${BASH_SOURCE[0]}"
while [[ -L "$SOURCE" ]]; do
  DIR="$(cd -P "$(dirname "$SOURCE")" && pwd)"
  SOURCE="$(readlink "$SOURCE")"
  [[ $SOURCE != /* ]] && SOURCE="$DIR/$SOURCE"
done
DIR="$(cd -P "$(dirname "$SOURCE")" && pwd)"

if command -v python3 >/dev/null 2>&1; then
  exec python3 "$DIR/ringlook.py" "$@"
elif command -v python >/dev/null 2>&1; then
  exec python "$DIR/ringlook.py" "$@"
else
  echo "ringlook: python3 (or python) not found in PATH" >&2
  exit 1
fi
LAUNCHER

chmod 755 "$DEST_DIR/ringlook" "$DEST_DIR/ringlook.py"

# Symlink into a directory that is normally on PATH
ln -sf "$DEST_DIR/ringlook" "$BIN_LINK"
chmod 755 "$BIN_LINK" 2>/dev/null || true

echo
echo "Installed successfully."
echo "  Binary : $BIN_LINK"
echo "  Files  : $DEST_DIR/"
echo

# Make sure the bin directory is on PATH for the current shell
if [[ "$(id -u)" -ne 0 ]]; then
  case ":$PATH:" in
    *":${HOME}/.local/bin:"*) ;;
    *)
      echo "Note: ${HOME}/.local/bin is not in your PATH yet."
      echo "Add this line to your ~/.bashrc or ~/.zshrc:"
      echo "  export PATH=\"\$HOME/.local/bin:\$PATH\""
      echo
      export PATH="${HOME}/.local/bin:$PATH"
      echo "(PATH updated for this terminal session)"
      ;;
  esac
fi

# Quick test
if command -v ringlook >/dev/null 2>&1; then
  echo "You can now run:"
  echo "  ringlook"
  echo "  ringlook --list"
  echo "  sudo ringlook          # unlocks ring 0"
else
  echo "Almost done. Open a new terminal or run:"
  echo "  export PATH=\"${BIN_LINK%/*}:\$PATH\""
  echo "Then type:  ringlook"
fi
