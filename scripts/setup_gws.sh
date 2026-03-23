#!/usr/bin/env bash
# setup_gws.sh — Install and configure the Google Workspace CLI for AFS
# Run this on your Mac: ./scripts/setup_gws.sh
set -euo pipefail

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info()  { echo -e "${GREEN}[✓]${NC} $*"; }
warn()  { echo -e "${YELLOW}[!]${NC} $*"; }
error() { echo -e "${RED}[✗]${NC} $*"; }

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  AFS — Google Workspace CLI Setup"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo

# Step 1: Install gws CLI
echo "Step 1: Installing gws CLI..."
if command -v gws &>/dev/null; then
    info "gws is already installed: $(gws --version 2>/dev/null || echo 'unknown version')"
else
    if command -v brew &>/dev/null; then
        warn "Installing via Homebrew..."
        brew install googleworkspace-cli
    elif command -v npm &>/dev/null; then
        warn "Installing via npm..."
        npm install -g @googleworkspace/cli
    else
        error "Neither brew nor npm found. Install one of them first."
        exit 1
    fi
    if command -v gws &>/dev/null; then
        info "gws installed successfully: $(gws --version 2>/dev/null || echo 'ok')"
    else
        error "gws installation failed. Check output above."
        exit 1
    fi
fi
echo

# Step 2: Move credentials JSON
echo "Step 2: Setting up OAuth credentials..."
GWS_CONFIG_DIR="$HOME/.config/gws"
CLIENT_SECRET="$GWS_CONFIG_DIR/client_secret.json"

mkdir -p "$GWS_CONFIG_DIR"

if [[ -f "$CLIENT_SECRET" ]]; then
    info "client_secret.json already exists at $CLIENT_SECRET"
else
    # Look for the downloaded file from GCP console
    DOWNLOADED=$(find "$HOME/Downloads" -maxdepth 1 -name 'client_secret_767964393702-*.json' -type f 2>/dev/null | head -1)
    if [[ -n "$DOWNLOADED" ]]; then
        cp "$DOWNLOADED" "$CLIENT_SECRET"
        info "Copied credentials from $(basename "$DOWNLOADED") → $CLIENT_SECRET"
    else
        error "Could not find the downloaded client_secret JSON in ~/Downloads/"
        echo "  Please manually copy it:"
        echo "    cp ~/Downloads/client_secret_767964393702-*.json $CLIENT_SECRET"
        echo "  Then re-run this script."
        exit 1
    fi
fi
echo

# Step 3: Authenticate
echo "Step 3: Authenticating with Google..."
echo "  This will open a browser window for OAuth consent."
echo "  Select Gmail, Calendar, and Drive scopes when prompted."
echo
read -p "  Press Enter to start the OAuth flow..."
gws auth login -s gmail,calendar,drive
echo
info "Authentication complete!"
echo

# Step 4: Verify
echo "Step 4: Verifying..."
echo
echo "  Auth status:"
gws auth status 2>/dev/null || warn "gws auth status not available"
echo
echo "  Testing Gmail (list 1 message):"
gws gmail users.messages.list --params '{"userId": "me", "maxResults": 1}' 2>/dev/null && info "Gmail API works!" || warn "Gmail test failed"
echo
echo "  Testing Calendar (list 1 event):"
gws calendar events.list --params '{"calendarId": "primary", "maxResults": 1}' 2>/dev/null && info "Calendar API works!" || warn "Calendar test failed"
echo
echo "  Testing Drive (list 1 file):"
gws drive files.list --params '{"pageSize": 1}' 2>/dev/null && info "Drive API works!" || warn "Drive test failed"
echo

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Setup complete! Test with AFS:"
echo "    afs gws status"
echo "    afs gws agenda"
echo "    afs gws unread"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
