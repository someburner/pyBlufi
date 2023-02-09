#!/usr/bin/env python3

import blufi
import time
import sys

client = blufi.BlufiClient()

client.connectByName('BLUFI_DEVICE')
# NOTE: See README.md about MTU
client.setPostPackageLengthLimit(256)
client.negotiateSecurity()
client.requestVersion()
print('Version: ', client.getVersion())

testNotify = False
if testNotify:
    client.stopNotify()
    client.postDeviceMode(blufi.OP_MODE_NULL)
    client.postDeviceMode(blufi.OP_MODE_NULL)

    client.startNotify()
    client.postDeviceMode(blufi.OP_MODE_NULL)
    client.postDeviceMode(blufi.OP_MODE_NULL)

    sys.exit(0)

# Reset STA state in case its attempting to connect
client.postDeviceMode(blufi.OP_MODE_NULL)
client.postDeviceMode(blufi.OP_MODE_STA)
client.requestDeviceScan()
print('SSIDs:')
for item in client.getSSIDList():
    print(item)

# client.postDeviceMode(blufi.OP_MODE_STA)
# params = {
#     'ssid': 'yourssid',
#     'pass': 'yourpass'
# }
# client.postStaWifiInfo(params)
