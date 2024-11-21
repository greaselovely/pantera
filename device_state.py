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

os.makedirs(EXPORT_DIR, exist_ok=True)

def authenticate_firewalls(ip):
    print(f"Authenticating to firewall at {ip}...")
    username = input(f"Enter the username for firewall {ip}: ")
    password = getpass.getpass(f"Enter the password for firewall {ip}: ")
    return retrieve_api_key(ip, username, password)

def retrieve_api_key(ip, username, password):
    api_url = f"https://{ip}/api/?type=keygen"
    payload = {'user': username, 'password': password}
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

def export_device_state(ip, api_key, ntfy_topic):
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
                        send_notification(f"Backup successful for {hostname}", ntfy_topic)
    except requests.exceptions.RequestException as e:
        print(f"Failed to export device state for {ip}: {e}")
        send_notification(f"Backup failed for firewall {ip}. Error: {e}", ntfy_topic)

def manage_export_directory(ntfy_topic):
    files = [os.path.join(EXPORT_DIR, f) for f in os.listdir(EXPORT_DIR) if os.path.isfile(os.path.join(EXPORT_DIR, f))]
    files.sort(key=os.path.getmtime)
    deleted_files_count = 0

    while len(files) > 7:
        oldest_file = files.pop(0)
        try:
            os.remove(oldest_file)
            print(f"Deleted old backup file: {oldest_file}")
            deleted_files_count += 1
        except OSError as e:
            print(f"Error deleting file {oldest_file}: {e}")

    if deleted_files_count > 0:
        message = f"Cleanup completed: {deleted_files_count} backup file(s) deleted."
        send_notification(message, ntfy_topic)


def send_notification(message, ntfy_topic):
    if not ntfy_topic:
        print("[Warning] Notification skipped: No ntfy subscription topic configured.")
        return
    
    ntfy_topic = "https://ntfy.sh/" + ntfy_topic
    try:
        response = requests.post(ntfy_topic, data=message.encode('utf-8'), headers={'Title': 'Device Backup Notification'})
        if response.status_code == 200:
            print("Notification sent successfully.")
        else:
            print(f"Failed to send notification: {response.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"Error sending notification: {e}")


def main():
    config = load_config(CONFIG_VERSION)
    if not config.get('devices'):
        print("No devices found in the existing configuration.")
        create_config()
    else:
        ntfy_topic = config.get('alerts', {}).get('ntfy', {}).get('subscription_topic', '')
        for ip, details in config['devices'].items():
            print(f"Exporting device state for firewall {ip}...")
            export_device_state(ip, details['api_key'], ntfy_topic)
            manage_export_directory(ntfy_topic)


if __name__ == '__main__':
    main()
