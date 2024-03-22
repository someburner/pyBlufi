#
# Example creds.py file.
# copy to creds.py to use with test.py
#

WIFI_CREDS = {
    'ssid': 'yourSSID',
    'pass': 'yourPASS'
}

# Change as needed, defaults to BLUFI_DEVICE if unset.
# ESP-IDF does not yet provide ability to change the advertised name,
# but I changed IDF manually in my case, and I believe they will
# add that feature in the future.
# BLE_SCAN_NAME = 'BLUFI_DEVICE'