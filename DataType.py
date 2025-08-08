from typing import NamedTuple
from enum import Enum, auto
from dataclasses import dataclass
from abc import ABC, abstractmethod
import re
import struct

class BASE_TYPE(ABC):
    value: int = 0
    template: dict = None

    def __init__(self, value) -> None:
        self.SetValue(value)

    @abstractmethod
    def SetValue(self, value):
        self.value = value

    def GetLabel(self):
        if self.template is not None:
            try:
                idx = list(self.template.values()).index(self.value)
                return list(self.template.keys())[idx]
            except ValueError:
                return str(self.value)

    def GetLabelValue(self, label):
        if self.template is not None:
            return self.template.get(label, 0)


class SIGNED_INT(BASE_TYPE):
    """Example for 2-byte signed int"""
    def SetValue(self, value) -> None:
        if isinstance(value, bytes):
            self.value = int.from_bytes(value, byteorder="little", signed=True)
        else:
            self.value = int(value)

    def GetValue(self) -> int:
        return int(self.value)


class SIGNED_INT3(BASE_TYPE):
    """Example for 10-bit signed int (packed in 2 bytes)"""
    def SetValue(self, value) -> None:
        if isinstance(value, bytes):
            raw = int.from_bytes(value, byteorder="little", signed=False)
            self.value = raw
        else:
            self.value = int(value)
        
        if self.value >= 512:
            self.value = -(1024 - self.value)

    def GetValue(self) -> int:
        return int(self.value)


class UNSIGNED_INT(BASE_TYPE):
    """Example for 4-byte unsigned int"""
    def SetValue(self, value) -> None:
        if isinstance(value, bytes):
            self.value = int.from_bytes(value, byteorder="little", signed=False)
        else:
            self.value = int(max(0, min(value, 4294967295)))
    
    def GetValue(self):
        return self.value

class FLOAT32(BASE_TYPE):
    def SetValue(self, value) -> None:
        if isinstance(value, bytes):
            if len(value) != 4:
                raise ValueError("FLOAT32 requires exactly 4 bytes")
            self.value = struct.unpack('>f', value)[0]  # big endian
        else:
            self.value = float(value)

    def GetValue(self) -> float:
        return float(self.value)

    def ToBytes(self) -> bytes:
        return struct.pack('>f', float(self.value))  # big endian

class HURTBOX_STATE(UNSIGNED_INT):
    template = {
        "?": 0,
        "VULNERABLE": 1,
        "INVINCIBLE": 2,
        "INTANGIBLE": 3
    }


class SOUND_LEVEL(UNSIGNED_INT):
    template = {
        "S": 0,
        "M": 1,
        "L": 2,
        "H": 3
    }


class SFX(UNSIGNED_INT):
    template = {
        "L WHOOSH":	41,
        "M WHOOSH":	42,
        "S WHOOSH":	43,
        "L SWIPE":	258,
        "M SWIPE":	259,
        "S SWIPE":	260
    }


class SOUND_TYPE(UNSIGNED_INT):
    template = {
        "PUNCH": 0,
        "KICK": 1,
        "COIN": 2,
        "BURN": 3,
        "SHOCK": 4,
        "SLASH": 5,
        "PAPER": 6,
        "BAT": 7,
    }


class EFFECT_TYPE(UNSIGNED_INT):
    template = {
        "NORMAL": 0,
        "FLAME": 1,
        "ELECTRIC": 2,
        "SLASH": 3,
        "COIN": 4,
        "SLEEP": 6
    }


class CONTOUR_STATE(UNSIGNED_INT):
    template = {
        "NONE": 0,
        "[1]": 1,
        "[2]": 2,
        "FEET": 3,
        "FULL": 4,
        "[5]": 5,
        "[6]": 6,
        "[7]": 7
    }


class SWORD_TRAIL(UNSIGNED_INT):
    template = {
        "LINK": 0,
        "END": 262143
    }


class GFX(UNSIGNED_INT):
    template = {
        "FOOTSTEP SMOKE": 11,
        "JUMP SMOKE": 13,
        "FRONT SKID SMOKE": 15,
        "BACK SKID SMOKE": 16,
        "BACK-SMOKE": 19,
        "WHITE SPARK": 31,
        "SHOCKWAVE": 33,
        "LARGE SHOCKWAVE?": 34,
        "WHITE SPARKLE": 41,
        "SMALL TECH FLASH?": 42,
        "TECH FLASH": 43,
        "LARGE TECH FLASH?": 44,
    }


def LoadRemixStuff():
    try:
        buildlog = open("./output.log", 'r').read()

        # SFX
        pattern = re.compile("Added (.*)\nFGM_ID: 0x\w+ \((.*)\)")

        for match in re.findall(pattern, buildlog):
            SFX.template[match[0]] = int(match[1])

        # Damage type
        pattern = re.compile("Added Damage Type: (\w+) - ID is (\w+)\n")

        for match in re.findall(pattern, buildlog):
            EFFECT_TYPE.template[match[0]] = int(match[1], 16)

        # GFX
        pattern = re.compile(
            " - Added GFX_ID (\w+) \(Command ID \w+\) with Instruction ID \w+\): (.*)\n")

        for match in re.findall(pattern, buildlog):
            GFX.template[match[1]] = int(match[0], 16)

        # SWORD TRAILS
        pattern = re.compile(
            "Added Sword Trail: (\w+) - Moveset command is (.*)\n")

        for match in re.findall(pattern, buildlog):
            SWORD_TRAIL.template[match[0]] = int(match[1][4:], 16)
        
        return True
    except:
        print("output.log not found")
        return False