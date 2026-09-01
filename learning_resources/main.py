import secrets
import string
import time
import requests

# Configuration
BASE_URL = "https://dm3.callengine.org/vicidial/admin.php"
AUTH_USER = "6666"
AUTH_PASS = "***REMOVED***"

# Target Server IP where extensions should be registered
SERVER_IP = "***REMOVED***"

# Template Extension to clone settings from (Extension|ServerIP)
SOURCE_PHONE_TEMPLATE = f"7001|{SERVER_IP}"

# Extension Range Configuration
START_EXT = 7002
END_EXT = 7010  # Inclusive range

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Content-Type": "application/x-www-form-urlencoded",
    "Origin": "https://dm3.callengine.org",
    "Referer": BASE_URL,
}


def generate_conf_secret(length=24):
    """Generates a cryptographically secure random alphanumeric string for new_conf_secret."""
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def create_vicidial_extension(ext_number):
    """Submits a POST request to clone/add a new phone extension in ViciDial."""
    ext_str = str(ext_number)
    conf_secret = generate_conf_secret()

    payload = {
        "ADD": "21222222222",  # Action code for copying phone settings
        "DB": "0",
        "new_extension": ext_str,
        "new_dialplan_number": ext_str,
        "new_voicemail_id": ext_str,
        "new_outbound_cid": ext_str,
        "new_server_ip": SERVER_IP,
        "new_login": ext_str,
        "new_pass": ext_str,
        "new_conf_secret": conf_secret,
        "new_fullname": f"Extension {ext_str}",
        "source_phone": SOURCE_PHONE_TEMPLATE,
        "SUBMIT": "SUBMIT",
    }

    try:
        response = requests.post(
            BASE_URL,
            auth=(AUTH_USER, AUTH_PASS),
            headers=HEADERS,
            data=payload,
            timeout=10,
        )

        if response.status_code == 200:
            # Check for generic success cues in ViciDial's HTML response
            if "PHONE ADDED" in response.text.upper() or ext_str in response.text:
                print(
                    f"[+] Extension {ext_str} created successfully (Secret: {conf_secret})"
                )
            else:
                print(
                    f"[?] Extension {ext_str} submitted, but output unexpected. Check admin logs."
                )
        else:
            print(
                f"[-] Failed to create Extension {ext_str}. HTTP Status: {response.status_code}"
            )

    except requests.exceptions.RequestException as e:
        print(f"[!] Network error creating Extension {ext_str}: {e}")


def main():
    print(
        f"Starting bulk creation from extension {START_EXT} to {END_EXT}...\n"
    )

    for ext in range(START_EXT, END_EXT + 1):
        create_vicidial_extension(ext)
        # Small delay to prevent rate-limiting or heavy MySQL lock load on ViciDial
        time.sleep(0.5)

    print("\n[Done] Process completed.")


if __name__ == "__main__":
    main()