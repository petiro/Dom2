#!/bin/bash
#
# SuperAgent Installer
# Installs SuperAgent to /opt/superagent with desktop shortcut
#

set -e

APP_NAME="SuperAgent"
INSTALL_DIR="/opt/superagent"
BIN_LINK="/usr/local/bin/superagent"
DESKTOP_FILE="/usr/share/applications/superagent.desktop"

echo "============================================"
echo "  SuperAgent Installer"
echo "============================================"
echo ""

# Check root
if [ "$EUID" -ne 0 ]; then
    echo "This installer requires root privileges."
    echo "Run: sudo ./install.sh"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Remove previous installation
if [ -d "$INSTALL_DIR" ]; then
    echo "Removing previous installation..."
    rm -rf "$INSTALL_DIR"
fi

# Create install directory
echo "Installing to $INSTALL_DIR..."
mkdir -p "$INSTALL_DIR"
mkdir -p "$INSTALL_DIR/config"
mkdir -p "$INSTALL_DIR/logs"
mkdir -p "$INSTALL_DIR/data"

# Copy executable
cp "$SCRIPT_DIR/SuperAgent" "$INSTALL_DIR/SuperAgent"
chmod +x "$INSTALL_DIR/SuperAgent"

# Copy config
if [ -f "$SCRIPT_DIR/config/config.yaml" ]; then
    cp "$SCRIPT_DIR/config/config.yaml" "$INSTALL_DIR/config/config.yaml"
fi

# Create symlink in PATH
echo "Creating command-line shortcut..."
ln -sf "$INSTALL_DIR/SuperAgent" "$BIN_LINK"

# Create desktop entry
echo "Creating desktop shortcut..."
cat > "$DESKTOP_FILE" << 'DESKTOP'
[Desktop Entry]
Name=SuperAgent
Comment=Intelligent RPA Desktop Agent
Exec=/opt/superagent/SuperAgent
Terminal=false
Type=Application
Categories=Utility;Development;
StartupNotify=true
DESKTOP

chmod 644 "$DESKTOP_FILE"

# Create uninstaller
cat > "$INSTALL_DIR/uninstall.sh" << 'UNINSTALL'
#!/bin/bash
set -e
if [ "$EUID" -ne 0 ]; then
    echo "Run: sudo ./uninstall.sh"
    exit 1
fi
echo "Uninstalling SuperAgent..."
rm -f /usr/local/bin/superagent
rm -f /usr/share/applications/superagent.desktop
rm -rf /opt/superagent
echo "SuperAgent uninstalled."
UNINSTALL
chmod +x "$INSTALL_DIR/uninstall.sh"

echo ""
echo "============================================"
echo "  Installation complete!"
echo "============================================"
echo ""
echo "  Location:    $INSTALL_DIR"
echo "  Command:     superagent"
echo "  Desktop:     Search 'SuperAgent' in apps"
echo "  Uninstall:   sudo $INSTALL_DIR/uninstall.sh"
echo ""
