#!/usr/bin/env python3

import blufi
import time
import sys

################################################################################
# Options for misc. tests
################################################################################
# Enable/Disable negotiateSecurity
TEST_SECURITY = True

# Enable/Disable getVersion
TEST_VERSION = True

# Enable/Disable get SSID list
TEST_SCAN = False

# Enable/Disable send SSID/Pass
TEST_POST_WIFI = False
TEST_POST_WIFI_CREDS = {
    'ssid': 'yourssid',
    'pass': 'yourpass'
}

# Test sending custom data
TEST_CUSTOM_DATA = False

# Test behavior when disabling rx notifications
TEST_NOTIFY = False

################################################################################

# Create client instance
client = blufi.BlufiClient()

# connect to BLUFI_DEVICE
# NOTE: atexit is used internally to send disconnect before script exits
client.connectByName('BLUFI_DEVICE')

# Cap pkt size. See README.md about MTU
client.setPostPackageLengthLimit(256)

if TEST_SECURITY:
    client.negotiateSecurity()

if TEST_VERSION:
    client.requestVersion()
    print('Version: ', client.getVersion())

if TEST_SCAN:
    # Reset STA state in case its attempting to connect
    client.postDeviceMode(blufi.OP_MODE_NULL)
    client.postDeviceMode(blufi.OP_MODE_STA)
    client.requestDeviceScan()
    print('SSIDs:')
    for item in client.getSSIDList():
        print(item)

if TEST_POST_WIFI:
    client.postDeviceMode(blufi.OP_MODE_STA)
    client.postStaWifiInfo(TEST_POST_WIFI_CREDS)

if TEST_CUSTOM_DATA:
    client.postCustomData(data=bytes.fromhex('010203'))

if TEST_NOTIFY:
    client.stopNotify()
    client.postDeviceMode(blufi.OP_MODE_NULL)
    client.postDeviceMode(blufi.OP_MODE_NULL)

    client.startNotify()
    client.postDeviceMode(blufi.OP_MODE_NULL)
    client.postDeviceMode(blufi.OP_MODE_NULL)

    sys.exit(0)

print('Exiting')
