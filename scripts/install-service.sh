#!/usr/bin/env bash
# Install Ouroboros as a systemd user service.
# Run as your normal user (not root).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_FILE="$SCRIPT_DIR/ouroboros.service"

if [ ! -f "$SERVICE_FILE" ]; then
    echo "Error: $SERVICE_FILE not found"
    exit 1
fi

# Make run.sh executable
chmod +x "$SCRIPT_DIR/run.sh"

# Install systemd user service
mkdir -p ~/.config/systemd/user
cp "$SERVICE_FILE" ~/.config/systemd/user/ouroboros.service

# Reload systemd
systemctl --user daemon-reload

# Enable (start on login / boot with linger)
systemctl --user enable ouroboros

echo ""
echo "✓ Ouroboros service installed and enabled."
echo ""
echo "Commands:"
echo "  systemctl --user start ouroboros     # Start now"
echo "  systemctl --user stop ouroboros      # Stop"
echo "  systemctl --user status ouroboros    # Check status"
echo "  journalctl --user -u ouroboros -f    # Follow logs"
echo ""
echo "For headless servers (persist after logout):"
echo "  sudo loginctl enable-linger $(whoami)"
echo ""
