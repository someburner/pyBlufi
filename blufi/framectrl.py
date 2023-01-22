from blufi.constants import *

def getTypeValue(type, subtype):
    return (subtype << 2) | type

def getPackageType(typeValue):
    return typeValue & 0b11

def getSubType(typeValue):
    return ((typeValue & 0b11111100) >> 2)

class FrameCtrlData:
    FRAME_CTRL_POSITION_ENCRYPTED = 0
    FRAME_CTRL_POSITION_CHECKSUM = 1
    FRAME_CTRL_POSITION_DATA_DIRECTION = 2
    FRAME_CTRL_POSITION_REQUIRE_ACK = 3
    FRAME_CTRL_POSITION_FRAG = 4

    def __init__(self, frameCtrlValue: int):
        self.mValue = frameCtrlValue

    def check(self, position: int) -> bool:
        return ((self.mValue >> position) & 1) == 1

    def isEncrypted(self) -> bool:
        return self.check(self.FRAME_CTRL_POSITION_ENCRYPTED)

    def isChecksum(self) -> bool:
        return self.check(self.FRAME_CTRL_POSITION_CHECKSUM)

    def isAckRequirement(self) -> bool:
        return self.check(self.FRAME_CTRL_POSITION_REQUIRE_ACK)

    def hasFrag(self) -> bool:
        return self.check(self.FRAME_CTRL_POSITION_FRAG)

    @staticmethod
    def getFrameCTRLValue(encrypted: bool, checksum: bool, direction: int, requireAck: bool, frag: bool) -> int:
        frame = 0
        if encrypted:
            frame = frame | (1 << FrameCtrlData.FRAME_CTRL_POSITION_ENCRYPTED)
        if checksum:
            frame = frame | (1 << FrameCtrlData.FRAME_CTRL_POSITION_CHECKSUM)
        if direction == DIRECTION_INPUT:
            frame = frame | (1 << FrameCtrlData.FRAME_CTRL_POSITION_DATA_DIRECTION)
        if requireAck:
            frame = frame | (1 << FrameCtrlData.FRAME_CTRL_POSITION_REQUIRE_ACK)
        if frag:
            frame = frame | (1 << FrameCtrlData.FRAME_CTRL_POSITION_FRAG)

        return frame
