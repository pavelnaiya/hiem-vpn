# Tor Proxy & Web Dashboard (Native Mac Edition)

This setup uses Homebrew to natively run Tor and Privoxy on your Mac, bypassing Docker entirely. It also provides a beautiful Web Dashboard to manage your proxy and monitor its connection.

## Prerequisites

- macOS (Apple Silicon or Intel)
- [Homebrew](https://brew.sh/)
- Python 3.8+

## Installation

Run the automated setup script. This will use Homebrew to install the required packages and configure them to work together instantly.

```bash
./setup_mac.sh
```

## Running the Dashboard

Once the setup script finishes, Tor and Privoxy will run automatically in the background on your Mac. You can now start the Web Dashboard to monitor and control your proxy!

```bash
./start_dashboard.sh
```

Then open **[http://localhost:8080](http://localhost:8080)** in your browser.

## Exposed Ports
If you want to manually configure a web scraper without the dashboard, you can use these local ports:
- `8118`: Privoxy HTTP Proxy
- `9051`: Tor Control Port (requires password: `my_secret_password`)
- `9050`: Tor SOCKS5 Proxy

## Cleaning Up
Since these run via Homebrew, if you ever want to stop the proxy services from running in the background on your Mac, run:
```bash
brew services stop tor
brew services stop privoxy
```
