import json
import os

CONFIG_FILE = "bot_config.json"

DEFAULT_CONFIG = {
    "user_data_dir": "./user_data_v6",
    "account_number": "202744967",
    "dispute_comment": "Reason for dispute- Products are CUSMA compliant. COO is Canada. FTN CCP 10221998 / PWDBW 7702060 Database and USMCA on file.",
    "headless": False,
    "fedex_url": "https://www.fedex.com/en-ca/logged-in-home.html"
}

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                return {**DEFAULT_CONFIG, **json.load(f)}
        except:
            return DEFAULT_CONFIG
    return DEFAULT_CONFIG

def save_config(config):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=4)

def get_config_value(key):
    config = load_config()
    return config.get(key)



