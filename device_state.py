import requests
import getpass
import urllib3
import xmltodict
from datetime import datetime
import os
import tarfile
from config_utility import load_config, create_config, CONFIG_VERSION

EXPORT_DIR = 'device_exports'

# Suppress InsecureRequestWarning for unverified HTTPS requests
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Ensure the export directory exists
if not os.path.exists(EXPORT_DIR):
    os.makedirs(EXPORT_DIR)

# Function to authenticate firewalls and retrieve API keys
def authenticate_firewalls(ip):
    print(f"Authenticating to firewall at {ip}...")
    username = input(f"Enter the username for firewall {ip}: ")
    password = getpass.getpass(f"Enter the password for firewall {ip}: ")
    return retrieve_api_key(ip, username, password)

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

# Function to export the device state
def export_device_state(ip, api_key):
    url = f"https://{ip}/api/?type=export&category=device-state&key={api_key}"
    try:
        response = requests.get(url, verify=False)
        response.raise_for_status()
        tgz_filename = f"{EXPORT_DIR}/device_state_{ip}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.tgz"
        with open(tgz_filename, 'wb') as f:
            f.write(response.content)
        print(f"Device state for {ip} exported successfully to {tgz_filename}.")

        # Extract hostname from the device state tgz
        with tarfile.open(tgz_filename, 'r:gz') as tar:
            for member in tar.getmembers():
                if 'running-config.xml' in member.name:
                    f = tar.extractfile(member)
                    if f is not None:
                        config_data = f.read()
                        config_dict = xmltodict.parse(config_data)
                        hostname = config_dict.get('config', {}).get('devices', {}).get('entry', {}).get('deviceconfig', {}).get('system', {}).get('hostname', ip)
                        new_filename = f"{EXPORT_DIR}/{hostname}_{datetime.now().strftime('%m%d%Y')}.tgz"
                        os.rename(tgz_filename, new_filename)
                        print(f"Exported device state renamed to {new_filename}.")

    except requests.exceptions.RequestException as e:
        print(f"Failed to export device state for {ip}: {e}")

# Main function to load the configuration and proceed
def main():
    config = load_config(CONFIG_VERSION)
    if not config.get('devices'):
        print("No devices found in the existing configuration.")
        create_config()
    else:
        # Export device state for each device in the configuration
        for ip, details in config['devices'].items():
            print(f"Exporting device state for firewall {ip}...")
            export_device_state(ip, details['api_key'])

if __name__ == '__main__':
    main()
