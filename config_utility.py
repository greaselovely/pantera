import json
import os
import requests
import getpass
import urllib3
import xmltodict

CONFIG_VERSION = '1.0'
CONFIG_FILE = 'config.json'

# Suppress InsecureRequestWarning for unverified HTTPS requests
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Function to load the configuration file
def load_config(version):
    if not os.path.exists(CONFIG_FILE):
        create_config()
    with open(CONFIG_FILE, 'r') as f:
        config = json.load(f)
        if 'version' not in config or config['version'] != version:
            print(f"Updating configuration file to version {version}.")
            config['version'] = version
            if 'devices' not in config:
                config['devices'] = {}
            save_config(config)
        return config

# Function to save the configuration file
def save_config(config):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=4)

# Function to create the configuration file
def create_config():
    config = {
        'version': CONFIG_VERSION,
        'devices': {}
    }
    print("Creating configuration file...")
    same_api_key = input("Will all firewalls use the same API key? (yes/no) [yes]: ").strip().lower() or 'yes'
    api_key = None
    username = None
    password = None
    if same_api_key == 'yes':
        username = input("Enter the username for all firewalls: ")
        password = getpass.getpass("Enter the password for all firewalls: ")
    while True:
        try:
            ip = input("Enter the IP address of the firewall (or type 'exit' to finish): ")
            if ip.lower() == 'exit':
                break
            if same_api_key == 'yes' and api_key is None:
                api_key = retrieve_api_key(ip, username, password)
                if not api_key:
                    print("Failed to retrieve API key. Skipping this firewall...")
                    continue
            elif same_api_key != 'yes':
                username = input(f"Enter the username for firewall {ip}: ")
                password = getpass.getpass(f"Enter the password for firewall {ip}: ")
                api_key = retrieve_api_key(ip, username, password)
                if not api_key:
                    print(f"Failed to retrieve API key for firewall {ip}. Skipping...")
                    continue
            config['devices'][ip] = {'api_key': api_key}
        except KeyboardInterrupt:
            print("\nProcess interrupted by user. Exiting configuration...")
            break
    
    if config['devices']:
        save_config(config)
        print(f"Configuration file {CONFIG_FILE} created successfully.")
    else:
        print("No valid firewalls were added to the configuration.")

# Function to retrieve the API key from the firewall
def retrieve_api_key(ip, username, password):
    # Actual logic to retrieve the API key from the firewall
    api_url = f"https://{ip}/api/?type=keygen"
    payload = {
        'user': username,
        'password': password
    }
    try:
        response = requests.post(api_url, data=payload, verify=False)
        response.raise_for_status()
        response_data = xmltodict.parse(response.text)
        if 'response' in response_data and 'result' in response_data['response'] and 'key' in response_data['response']['result']:
            return response_data['response']['result']['key']
        else:
            print(f"Unexpected response format from firewall {ip}: {response.text}")
            return None
    except requests.exceptions.RequestException as e:
        print(f"Failed to retrieve API key for firewall {ip}: {e}")
        return None
    except ValueError:
        print(f"Failed to parse XML response from firewall {ip}: {response.text}")
        return None

if __name__ == '__main__':
    create_config()
