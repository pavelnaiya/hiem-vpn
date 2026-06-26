import time
import requests
from stem import Signal
from stem.control import Controller
import os

# Configuration matching our docker-compose setup
PROXY_URL = "http://127.0.0.1:8118" # Privoxy
TOR_CONTROL_PORT = 9051
TOR_PASSWORD = os.environ.get("TOR_PASSWORD", "my_secret_password")

proxies = {
    'http': PROXY_URL,
    'https': PROXY_URL
}

def get_current_ip():
    try:
        response = requests.get('https://api.myip.com/', proxies=proxies, timeout=10)
        return response.json()
    except Exception as e:
        print(f"Error fetching IP: {e}")
        return None

def change_tor_ip():
    print("Requesting new Tor identity...")
    with Controller.from_port(port=TOR_CONTROL_PORT) as controller:
        controller.authenticate(password=TOR_PASSWORD)
        controller.signal(Signal.NEWNYM)
    
    # Wait a moment for the new circuit to be established
    time.sleep(3)

def main():
    print("Fetching initial IP through Tor...")
    initial_ip_info = get_current_ip()
    print(f"Initial IP: {initial_ip_info}")
    
    print("\nRotating IP...")
    change_tor_ip()
    
    print("Fetching new IP through Tor...")
    new_ip_info = get_current_ip()
    print(f"New IP: {new_ip_info}")

if __name__ == "__main__":
    main()
