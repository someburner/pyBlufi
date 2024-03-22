#!/usr/bin/env python3

import blufi
import time
import sys

from creds import *

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
TEST_POST_WIFI = True

# Test sending custom data
TEST_CUSTOM_DATA = False

# Test behavior when disabling rx notifications
TEST_NOTIFY = False

################################################################################

# Create client instance
client = blufi.BlufiClient()

SCAN_NAME = None

if 'BLE_SCAN_NAME' in globals():
    SCAN_NAME = BLE_SCAN_NAME
else:
    SCAN_NAME = 'BLUFI_DEVICE'

print('Using scan name: %s' % SCAN_NAME)

# connect to BLUFI_DEVICE
# NOTE: atexit is used internally to send disconnect before script exits
client.connectByName(SCAN_NAME)

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
    if not 'WIFI_CREDS' in globals():
        print('\ncreds.py missing or missing required variables! See README.md.\n')
        sys.exit(1)
    client.postDeviceMode(blufi.OP_MODE_STA)
    client.postStaWifiInfo(WIFI_CREDS)

if TEST_CUSTOM_DATA:
    client.postCustomData(data=bytes.fromhex('010203'))
    client.wait(0.5)
    # Test sending large payload
    # NOTE: esp32 receives large payloads fine, but appears to break if response
    # payload is >= 1984 bytes, at least if echoed inside the event handler
    repeatStr = lambda s, count: ''.join([s for n in range(count)])
    genStr = lambda count: ''.join([ repeatStr('%X' % n, count) for n in range(16) ])
    client.postCustomData(data=bytes.fromhex(genStr(240))) # 240 max for echo
    client.wait(3)

if TEST_NOTIFY:
    client.stopNotify()
    client.postDeviceMode(blufi.OP_MODE_NULL)
    client.postDeviceMode(blufi.OP_MODE_NULL)

    client.startNotify()
    client.postDeviceMode(blufi.OP_MODE_NULL)
    client.postDeviceMode(blufi.OP_MODE_NULL)

    sys.exit(0)

print('Exiting')
