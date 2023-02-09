from typing import Optional, Callable

import asyncio
import atexit
import io
import queue
import struct
import threading
import time

from bleak import BleakClient, BleakScanner
from bleak.backends.characteristic import BleakGATTCharacteristic

from blufi.exceptions import BluetoothError
from blufi.security import BlufiAES, BlufiCRC, BlufiCrypto
from blufi.utils import *
from blufi.constants import *
from blufi.framectrl import *

import logging
log = logging.getLogger("blufi")
logging.basicConfig(level=logging.ERROR)
logging.getLogger("blufi").setLevel(logging.DEBUG)

class BlufiClient:
    def __init__(self):
        # Created on demand in self._bleak_thread context.
        self._scanner = None
        self._bleak_client = None
        self._bleak_loop = None
        self._bleak_thread = threading.Thread(target=self._run_bleak_loop)
        # Discard thread quietly on exit.
        self._bleak_thread.daemon = True
        self._bleak_thread_ready = threading.Event()
        self._bleak_thread.start()
        # Wait for thread to start.
        self._bleak_thread_ready.wait()
        # Sync
        self.secEvent = Event_ts(self._bleak_loop)
        self.ssidListEvent = Event_ts(self._bleak_loop)
        # Security
        self.crypto = None
        self.mAESKey = None
        self.mEncrypted = False
        self.mChecksum = False
        self.mRequireAck = False
        # Services
        self.dev = None
        self.svc = None
        self.write_char = None
        self.mWriteChar = None
        self.notifyChar = None
        # Settings
        self.mPackageLengthLimit = -1
        self.mBlufiMTU = -1
        # State data
        self._reset_state()
        self.ssidList = []
        self.mAck = queue.Queue()
        self.rxBuf = bytearray()
        self.rxPubKeyBuf = bytearray()

        # Clean up connections, etc. when exiting (even by KeyboardInterrupt)
        atexit.register(self._cleanup)

    def _reset_state(self) -> None:
        self.connected = False
        self._notify_en = False
        self.mSendSequence = -1
        self.mReadSequence = -1
        self.mEncrypted = False
        self.mChecksum = False
        self.crypto = None
        self.mAESKey = None
        self.version = None
        self.wifiState = {
            "opMode": -1,
            "staConn": -1,
            "softAPConn": -1
        }

    def _cleanup(self) -> None:
        """Clean up connections, so that the underlying OS software does not
        leave them open.
        """
        self._reset_state()
        if self._bleak_client:
            self.await_bleak(self._disconnect_async())

    def setPostPackageLengthLimit(self, lengthLimit):
        """Arbirarily lower send package size. NOTE: MTU for esp32 BLE nimble
        can be up to 512, but the blufi spec only allows for one byte for data
        length. BT Classic can handle even higher MTUs.
        """
        if lengthLimit <= 0:
            self.mPackageLengthLimit = -1
        else:
            # subtract 4: 3 for BLE header, 1 reserved (Blufi, unused)
            self.mPackageLengthLimit = max(lengthLimit-4, MIN_PACKAGE_LENGTH)

    async def _disconnect_async(self) -> None:
        """Disconnects from the remote peripheral. Does nothing if already disconnected."""
        await self._bleak_client.disconnect()

    def _run_bleak_loop(self) -> None:
        self._bleak_loop = asyncio.new_event_loop()
        # Event loop is now available.
        self._bleak_thread_ready.set()
        self._bleak_loop.run_forever()

    def await_bleak(self, coro, timeout: Optional[float] = None):
        """Call an async routine in the bleak thread from sync code, and await its result."""
        # This is a concurrent.Future.
        future = asyncio.run_coroutine_threadsafe(coro, self._bleak_loop)
        return future.result(timeout)

    def onNotify(self, characteristic: BleakGATTCharacteristic, data: bytearray):
        """Simple notification handler which prints the data received."""
        # print("%s: %r" % (characteristic.description, data))
        self.parseNotification(data)

    # def connectByAddr(self, addr: str, timeout: float) -> None:
    #     return self.await_bleak(self._connect_async(address, timeout=timeout))

    def stopNotify(self):
        if not self.connected:
            log.warning("stopNotify: Not connected")
            return
        if not self._notify_en:
            log.warning("stopNotify: already disabled")
            return
        self.await_bleak(self._bleak_client.stop_notify(BLUFI_NOTIF_CHAR_UUID))
        self._notify_en = False

    def startNotify(self):
        if not self.connected:
            log.warning("startNotify: Not connected")
            return
        if self._notify_en:
            log.warning("stopNotify: already enabled")
            return
        self.await_bleak(self._bleak_client.start_notify(BLUFI_NOTIF_CHAR_UUID, self.onNotify))
        self._notify_en = True

    def connectByName(self, name: str, timeout: float = None) -> None:
        return self.await_bleak(self._connect_async_name(name, timeout=timeout))

    async def _connect_async_name(self, name: str, timeout: float) -> bool:
        self._reset_state()
        # Use cached device if possible, to avoid having BleakClient do
        # a scan again.
        device = await BleakScanner.find_device_by_name(
            name, cb=dict(use_bdaddr=False)
        )

        client = BleakClient(device)
        # connect() takes a timeout, but it's a timeout to do a
        # discover() scan, not an actual connect timeout.
        try:
            await client.connect(timeout=timeout)
            if get_platform_type() != 'Linux':
                log.info("MTU: %d" % client.mtu_size)
                self.mBlufiMTU = client.mtu_size - 4
            # This does not seem to connect reliably.
            # await asyncio.wait_for(client.connect(), timeout)
            svc = client.services.get_service(BLUFI_SERVICE_UUID)
            self.notif_char = svc.get_characteristic(BLUFI_NOTIF_CHAR_UUID)
            self.write_char = svc.get_characteristic(BLUFI_WRITE_CHAR_UUID)
            await client.start_notify(BLUFI_NOTIF_CHAR_UUID, self.onNotify)
            self._notify_en = True
        except asyncio.TimeoutError:
            # raise BluetoothError("Failed to connect: timeout") from asyncio.TimeoutError
            return False

        self.connected = True
        self._bleak_client = client
        return True

    def generateSendSequence(self):
        self.mSendSequence += 1
        self.mSendSequence = self.mSendSequence & 0xFF
        return self.mSendSequence

    def parsePublicKey(self, data):
        log.debug("parsePublicKey %d bytes" % len(data))
        self.rxPubKeyBuf.extend(data)
        self.mAESKey = self.crypto.deriveSharedKey(self.rxPubKeyBuf)
        # This method is called from the bt notify callback and thus outside of
        # the event loop. Set an async event that gets checked in the main
        # thread, which will then call postSetSecurity
        self.secEvent.set()

    def parseVersion(self, data):
        self.version = "%d.%d" % (data[0], data[1])
        log.info("parseVersion = %s" % self.version)

    def getVersion(self):
        return self.version

    def parseWifiState(self, data):
        if len(data) < 3:
            log.error("invalid wifi state data")
            return
        dataIS = io.BytesIO(data)
        opMode = dataIS.read(1)[0] & 0xff
        log.debug("opMode = 0x%02X" % opMode)
        self.wifiState["opMode"] = opMode

        staConn = dataIS.read(1)[0] & 0xff
        log.debug("staConn = 0x%02X" % staConn)
        self.wifiState["staConn"] = staConn

        softAPConn = dataIS.read(1)[0] & 0xff
        log.debug("softAPConn = 0x%02X" % softAPConn)
        self.wifiState["softAPConn"] = softAPConn

    def getWifiState(self):
        return self.wifiState

    def parseWifiScanList(self, data):
        self.ssidList = []
        dataReader = io.BytesIO(data)
        readLeft = len(data)
        scannedSSIDs = 0
        while readLeft > 0:
            length = dataReader.read(1)[0] & 0xff
            readLeft -= 1
            if length < 1:
                log.error("Parse WifiScan invalid length")
                break
            rssi = dataReader.read(1)
            rssi = struct.unpack('<b', rssi)[0]
            ssidBytes = dataReader.read(length-1)
            readLeft -= length
            if len(ssidBytes) != length - 1:
                log.error("Parse WifiScan parse ssid failed")
                break

            ssid = 'malformed'
            try:
                ssid = ssidBytes.decode()
                self.ssidList.append({
                    "ssid": ssid,
                    "rssi": rssi
                })
            except Exception as e:
                log.error(e)
            log.debug("%s [%d]" % (ssid, rssi))
            scannedSSIDs += 1
        log.info("Scanned %d SSIDs" % scannedSSIDs)
        self.ssidListEvent.set()

    def getSSIDList(self):
        return self.ssidList

    def parseAck(self, data):
        ack = 0x100
        if len(data) > 0:
            ack = data[0] & 0xff
            log.debug('gotack = 0x%02X' % ack)
        # self.mAck.put(ack)
        # TODO: handle ack checking

    def parseCtrlData(self, subType, data):
        log.debug("parseCtrlData: %d" % subType)
        if subType == CTRL.SUBTYPE_ACK:
            self.parseAck(data)

    def parseDataData(self, subType, data):
        log.debug("parseDataData: %d" % subType)
        if subType == DATA.SUBTYPE_NEG:
            self.parsePublicKey(data)
        elif subType == DATA.SUBTYPE_VERSION:
            self.parseVersion(data)
        elif subType == DATA.SUBTYPE_WIFI_CONNECTION_STATE:
            self.parseWifiState(data)
        elif subType == DATA.SUBTYPE_WIFI_LIST:
            try:
                self.parseWifiScanList(data)
            except Exception as e:
                log.error('parseWifiScanList error')
                log.error(e)
        else:
            log.error('parseDataData: Unknown subtype')

    def parseNotification(self, data):
        seq = int(data[2])
        self.mReadSequence += 1
        if seq != self.mReadSequence:
            log.error("seq %d != self.mReadSequence %d" % (seq, self.mReadSequence))
        type = int(data[0])
        pkgType = getPackageType(type)
        subType = getSubType(type)

        frameCtrl = int(data[1])
        fctl = FrameCtrlData(frameCtrl)

        dataLen = int(data[3])
        log.debug("seq %d type %d pkgType %d subType %d dataLen %d" % (seq, type, pkgType, subType, dataLen))

        dataBytes = bytearray(data[4:4+dataLen])

        if fctl.isEncrypted():
            aes = BlufiAES(self.mAESKey, generateAESIV(seq))
            dataBytes = aes.decrypt(dataBytes)

        if fctl.isChecksum():
            log.info('got checksum')
            respChecksum1 = int(data[len(data) - 1])
            respChecksum2 = int(data[len(data) - 2])

            nonDataBytes = struct.pack("<BB", seq, dataLen)
            crc = BlufiCRC.calcCRC(0, nonDataBytes)
            crc = BlufiCRC.calcCRC(crc, dataBytes)
            calcChecksum1 = crc >> 8 & 0xff
            calcChecksum2 = crc & 0xff

            if (respChecksum1 != calcChecksum1) or (respChecksum2 != calcChecksum2):
                log.error("parseNotification: read invalid checksum")
                log.debug("expect checksum: ", respChecksum1, ", ", respChecksum2)
                log.debug("received checksum: ", calcChecksum1, ", ", calcChecksum2)
                return
            else:
                log.info("CRC OK!")
                pass

        dataOffset = 0

        if fctl.hasFrag():
            log.debug("got hasFrag")
            dataOffset = 2
            self.rxBuf.extend(dataBytes[2:])
        else:
            self.rxBuf.extend(dataBytes)

        # TODO: neet a notif obj to collect for various types

        # If no more fragments, buffer is ready to be parsed
        if not fctl.hasFrag():
            if pkgType == CTRL.PACKAGE_VALUE:
                self.parseCtrlData(subType, self.rxBuf)
            elif pkgType == DATA.PACKAGE_VALUE:
                self.parseDataData(subType, self.rxBuf)
            # reset rxBuf
            self.rxBuf = bytearray()

    def getPostBytes(self, type: int, encrypt: bool, checksum: bool, requireAck: bool, hasFrag: bool, sequence: int, data: bytes) -> bytes:
        byteOS = io.BytesIO()

        dataLength = len(data) if data else 0
        frameCtrl = FrameCtrlData.getFrameCTRLValue(encrypt, checksum, DIRECTION_OUTPUT, requireAck, hasFrag)

        byteOS.write(bytes([type]))
        byteOS.write(bytes([frameCtrl]))
        byteOS.write(bytes([sequence]))
        byteOS.write(bytes([dataLength]))

        if checksum:
            willCheckBytes = struct.pack("<BB", sequence, dataLength)
            crc = BlufiCRC.calcCRC(0, willCheckBytes)
            if dataLength > 0:
                crc = BlufiCRC.calcCRC(crc, data)
            checksumBytes = struct.pack("<H", crc)
        else:
            checksumBytes = None

        if encrypt and dataLength > 0:
            aes = BlufiAES(self.mAESKey, generateAESIV(sequence))
            data = aes.encrypt(data)

        if data:
            byteOS.write(data)

        if checksumBytes:
            byteOS.write(checksumBytes)

        return byteOS.getvalue()

    async def postNonData(self, encrypt: bool, checksum: bool, requireAck: bool, type: int) -> bool:
        sequence = self.generateSendSequence()
        postBytes = self.getPostBytes(type, encrypt, checksum, requireAck, False, sequence, None)
        await self._bleak_client.write_gatt_char(self.write_char, postBytes, True)
        # return posted and (not requireAck or receiveAck(sequence))
        return True

    async def postContainData(self, encrypt: bool, checksum: bool, requireAck: bool, type: int, data: bytearray) -> bool:
        dataIS = io.BytesIO(data)
        readLeft = len(data)
        dataContent = io.BytesIO()
        pkgLengthLimit = self.mPackageLengthLimit if self.mPackageLengthLimit > 0 else (self.mBlufiMTU if self.mBlufiMTU > 0 else DEFAULT_PACKAGE_LENGTH)
        postDataLengthLimit = pkgLengthLimit - PACKAGE_HEADER_LENGTH
        postDataLengthLimit -= 2  # if frag, two bytes total length in data
        if checksum:
            postDataLengthLimit -= 2
        dataBuf = bytearray(postDataLengthLimit)
        # print('postDataLengthLimit ', postDataLengthLimit)
        while True:
            read = dataIS.readinto(dataBuf)
            if not read:
                # print('break')
                break
            readLeft -= read
            # print('read = ', read)
            # print('read = ', dataIS.readall())
            dataContent.write(dataBuf[:read])
            # print("dataIS.readable() = ", dataIS.readable())
            if readLeft > 0 and readLeft <= 2:
                read = dataIS.readinto(dataBuf)
                dataContent.write(dataBuf[:read])
                readLeft -= read
            frag = readLeft > 0
            sequence = self.generateSendSequence()
            if frag:
                totalLen = dataContent.tell() + readLeft
                tempData = dataContent.getvalue()
                dataContent.seek(0)
                dataContent.write(struct.pack("<H", totalLen))
                dataContent.write(tempData)
                # print('totalLen =', totalLen)
                # print('tempData = ', dataContent.getvalue())
            postBytes = self.getPostBytes(type, encrypt, checksum, requireAck, frag, sequence, dataContent.getvalue())
            dataContent.seek(0)
            dataContent.truncate()
            log.debug("sending %d bytes" % len(postBytes))
            if requireAck:
                log.debug("sending seq %d" % sequence)
                # TODO: verify sequence when ack requested
            await self._bleak_client.write_gatt_char(self.write_char, postBytes, True)
            await asyncio.sleep(0.05)

            if frag:
                # print("frag waiting")
                if requireAck and not self.receiveAck(sequence):
                    return False
                # time.sleep(10)
                # self.esp.waitForNotifications(10)
            else:
                # return not requireAck or self.receiveAck(sequence)
                pass
        return True

    async def post(self, encrypt: bool, checksum: bool, requireAck: bool, type: int, data: bytearray):
        if requireAck and not self._notify_en:
            log.warning('ack requested but notifications not enabled. Incrementing read seq.')
            self.mReadSequence += 1
        if not data or len(data) == 0:
            await self.postNonData(encrypt, checksum, requireAck, type)
        else:
            await self.postContainData(encrypt, checksum, requireAck, type, data)

    async def postNegotiateSecurity(self):
        type = getTypeValue(DATA.PACKAGE_VALUE, DATA.SUBTYPE_NEG)

        pBytes = self.crypto.getPBytes()
        gBytes = self.crypto.getGBytes()
        kBytes = self.crypto.getYBytes()

        pgkLength = len(pBytes) + len(gBytes) + len(kBytes) + 6
        pgkLen1 = (pgkLength >> 8) & 0xff
        pgkLen2 = pgkLength & 0xff

        txBuf = io.BytesIO()
        txBuf.write(bytes([NEG_SECURITY_SET_TOTAL_LENGTH]))
        txBuf.write(bytes([pgkLen1]))
        txBuf.write(bytes([pgkLen2]))

        await self.post(False, False, self.mRequireAck, type, txBuf.getvalue())
        await asyncio.sleep(0.1)

        txBuf.seek(0)
        txBuf.truncate()

        txBuf.write(bytes([NEG_SECURITY_SET_ALL_DATA]))

        pLength = len(pBytes)
        pLen1 = (pLength >> 8) & 0xff
        pLen2 = pLength & 0xff
        txBuf.write(bytes([pLen1]))
        txBuf.write(bytes([pLen2]))
        txBuf.write(pBytes)

        gLength = len(gBytes)
        gLen1 = (gLength >> 8) & 0xff
        gLen2 = gLength & 0xff
        txBuf.write(bytes([gLen1]))
        txBuf.write(bytes([gLen2]))
        txBuf.write(gBytes)

        kLength = len(kBytes)
        kLen1 = (kLength >> 8) & 0xff
        kLen2 = kLength & 0xff
        txBuf.write(bytes([kLen1]))
        txBuf.write(bytes([kLen2]))
        txBuf.write(kBytes)

        await self.post(False, False, self.mRequireAck, type, txBuf.getvalue())
        await asyncio.sleep(0.1)

    async def postSetSecurity(self, ctrlEncrypted, ctrlChecksum, dataEncrypted, dataChecksum):
        type = getTypeValue(CTRL.PACKAGE_VALUE, CTRL.SUBTYPE_SET_SEC_MODE)
        data = 0
        if dataChecksum:
            data |= 0b1
        if dataEncrypted:
            data |= 0b10
        if ctrlChecksum:
            data |= 0b10000
        if ctrlEncrypted:
            data |= 0b100000

        postData = (data).to_bytes(1, byteorder='little')
        await self.post(False, dataChecksum, self.mRequireAck, type, postData)

    def negotiateSecurity(self):
        self.crypto = BlufiCrypto()
        self.crypto.genKeys()
        self.secEvent.clear()
        self.await_bleak(self.postNegotiateSecurity())

        if not self.await_bleak(event_wait(self.secEvent, 5)):
            log.error('negotiateSecurity failed!')            # ctrlEncrypted, ctrlChecksum, dataEncrypted, dataChecksum
        else:
            log.info('negotiateSecurity success!')
            self.await_bleak(self.postSetSecurity(False, False, True, True))
            self.mEncrypted = True
            self.mChecksum = True

    def requestVersion(self):
        type = getTypeValue(CTRL.PACKAGE_VALUE, CTRL.SUBTYPE_GET_VERSION)
        self.await_bleak(self.post(self.mEncrypted, self.mChecksum, False, type, None))

    def requestDeviceStatus(self):
        type = getTypeValue(CTRL.PACKAGE_VALUE, CTRL.SUBTYPE_GET_WIFI_STATUS)
        self.await_bleak(self.post(self.mEncrypted, self.mChecksum, False, type, None))

    def requestDeviceScan(self, timeout=10):
        type = getTypeValue(CTRL.PACKAGE_VALUE, CTRL.SUBTYPE_GET_WIFI_LIST)
        self.ssidListEvent.clear()
        self.await_bleak(self.post(self.mEncrypted, self.mChecksum, False, type, None))
        if not self.await_bleak(event_wait(self.ssidListEvent, timeout)):
            log.error('parseWifiScanList timed out!')
        else:
            log.info('parseWifiScanList success!')

    def postDeviceMode(self, opMode):
        type = getTypeValue(CTRL.PACKAGE_VALUE, CTRL.SUBTYPE_SET_OP_MODE)
        data = (opMode).to_bytes(1, byteorder='little')
        self.await_bleak(self.post(self.mEncrypted, self.mChecksum, True, type, data))

    def postStaWifiInfo(self, params):
        ssidType = getTypeValue(DATA.PACKAGE_VALUE, DATA.SUBTYPE_STA_WIFI_SSID)
        ssidBytes = params['ssid'].encode('utf-8')
        self.await_bleak(self.post(self.mEncrypted, self.mChecksum, self.mRequireAck, ssidType, ssidBytes))

        pwdType = getTypeValue(DATA.PACKAGE_VALUE, DATA.SUBTYPE_STA_WIFI_PASSWORD)
        pwdBytes = params['pass'].encode('utf-8')
        self.await_bleak(self.post(self.mEncrypted, self.mChecksum, self.mRequireAck, pwdType, pwdBytes))

        comfirmType = getTypeValue(CTRL.PACKAGE_VALUE, CTRL.SUBTYPE_CONNECT_WIFI)
        self.await_bleak(self.post(False, False, self.mRequireAck, comfirmType, None))
