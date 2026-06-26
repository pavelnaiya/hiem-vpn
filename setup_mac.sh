#!/bin/bash

# Exit on error
set -e

echo "======================================"
echo " Tor Proxy & Dashboard Setup (Mac)  "
echo "======================================"

echo "1. Installing Tor and Privoxy via Homebrew..."
brew install tor privoxy

echo "2. Configuring Tor..."
TOR_CONF="/opt/homebrew/etc/tor/torrc"
TOR_PASSWORD="my_secret_password"

# Generate password hash
echo "Generating Tor password hash..."
HASH=$(tor --hash-password "$TOR_PASSWORD" | tail -n 1)

# Back up original if it exists and we haven't already
if [ -f "$TOR_CONF" ] && [ ! -f "${TOR_CONF}.bak" ]; then
    cp "$TOR_CONF" "${TOR_CONF}.bak"
fi

# Write minimal required configuration
cat > "$TOR_CONF" << EOF
SocksPort 9050
ControlPort 9051
HashedControlPassword $HASH
CookieAuthentication 0
EOF

echo "3. Configuring Privoxy..."
PRIVOXY_CONF="/opt/homebrew/etc/privoxy/config"

# Back up original
if [ ! -f "${PRIVOXY_CONF}.bak" ]; then
    cp "$PRIVOXY_CONF" "${PRIVOXY_CONF}.bak"
fi

# Ensure it forwards to Tor
if ! grep -q "forward-socks5t / 127.0.0.1:9050 ." "$PRIVOXY_CONF"; then
    echo "forward-socks5t / 127.0.0.1:9050 ." >> "$PRIVOXY_CONF"
fi

echo "4. Starting Background Services..."
brew services restart tor
brew services restart privoxy

echo "======================================"
echo " Setup Complete! "
echo " Tor is running on port 9050 (Control Port 9051)"
echo " Privoxy is running on port 8118"
echo ""
echo " You can now run ./start_dashboard.sh to start the Web Dashboard!"
echo "======================================"
