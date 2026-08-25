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
            return self.template.get(label, None)


class SIGNED_INT(BASE_TYPE):
    """Example for 2-byte signed int"""
    def SetValue(self, value) -> None:
        if isinstance(value, bytes):
            self.value = int.from_bytes(value, byteorder="little", signed=False)
        else:
            self.value = int(value)
        
        if self.value >= 0x8000:
            self.value = -(0xFFFF - self.value)

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
    """GMHitStatus (gmdef.h)."""
    template = {
        "NONE (hurtboxes disabled)": 0,
        "NORMAL": 1,
        "INVINCIBLE (hittable, no damage)": 2,
        "INTANGIBLE (unhittable)": 3
    }


class SOUND_LEVEL(UNSIGNED_INT):
    """GMAttackLevel — only 3 levels exist (nGMHitLevelEnumCount = 3)."""
    template = {
        "WEAK": 0,
        "MEDIUM": 1,
        "STRONG": 2
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
    """FTSlopeContours (ftdef.h) is a bitmask: LFOOT=1, RFOOT=2, FULL=4."""
    template = {
        "NONE": 0,
        "L FOOT": 1,
        "R FOOT": 2,
        "BOTH FEET": 3,
        "FULL": 4,
        "L FOOT + FULL": 5,
        "R FOOT + FULL": 6,
        "BOTH FEET + FULL": 7
    }


class SWORD_TRAIL(UNSIGNED_INT):
    """SetAfterImage(is_itemswing, drawstatus) packed as is_itemswing<<18 | drawstatus
    (ftmain.c). drawstatus=-1 (0x3FFFF, 18-bit) is the "off" sentinel."""
    template = {
        "SWORD TRAIL ON": 0,
        "ITEM SWING TRAIL ON": 262144,
        "TRAIL OFF": 262143
    }


class GFX(UNSIGNED_INT):
    """efKind (src/ef/efdef.h). IDs have real gaps (e.g. 1-5, 35-36, 55-69 are
    unused) — this replaces an earlier hand-guessed table that had drifted
    off by several IDs past DustLight (11)."""
    template = {
        "DAMAGE NORMAL": 0,
        "FLAME LR": 6,
        "FLAME RANDOM": 7,
        "FLAME STATIC": 8,
        "SHOCK SMALL": 10,
        "DUST LIGHT": 11,
        "DUST LIGHT RAPID": 12,
        "DUST HEAVY DOUBLE": 13,
        "DUST HEAVY DOUBLE RAPID": 14,
        "DUST HEAVY": 15,
        "DUST HEAVY REVERSE": 16,
        "DUST EXPAND LARGE": 17,
        "DUST EXPAND SMALL": 18,
        "DUST DASH SMALL": 19,
        "DUST DASH LARGE": 20,
        "DAMAGE FLY ORBS": 21,
        "IMPACT WAVE": 22,
        "STAR ROD SPARK": 23,
        "DAMAGE FLY SPARKS": 24,
        "DAMAGE FLY SPARKS REVERSE": 25,
        "DAMAGE FLY METAL DUST": 26,
        "DAMAGE FLY METAL DUST REVERSE": 27,
        "SPARKLE WHITE": 28,
        "SPARKLE WHITE MULTI EXPLODE": 29,
        "SPARKLE WHITE MULTI": 30,
        "SPARKLE WHITE SCALE": 31,
        "QUAKE MAG 0": 32,
        "QUAKE MAG 1": 33,
        "QUAKE MAG 2": 34,
        "FIRE SPARK": 37,
        "FURA SPARKLE": 40,
        "PSIONIC": 41,
        "FLASH SMALL (TECH)": 42,
        "FLASH MIDDLE (LEDGE GRAB)": 43,
        "FLASH LARGE": 44,
        "BOX SMASH": 46,
        "CRASH THE GAME": 47,
        "KIRBY STAR": 54,
        "THUNDER AMP": 70,
        "RIPPLE": 71,
        "CHARGE SPARKLE": 73,
        "HEAL SPARKLES": 74,
        "YOSHI EGG ESCAPE": 87,
        "MUSIC NOTE": 90,
        "EGG BREAK": 91,
    }


class ACTION_ID(SIGNED_INT):
    """FTCommonStatus (ftdef.h) — the fighter status/action-state a throw
    puts the victim into. -1 is a "no override, keep current status"
    sentinel seen throughout relocData (e.g. dDonkeyMainMotion_0x0C14).
    Unrecognized/custom (e.g. Remix-added) IDs fall back to hex display."""
    template = {
        "NONE / NO OVERRIDE": -1,
        "DEAD DOWN": 0,
        "DEAD LEFT RIGHT": 1,
        "DEAD UP STAR": 2,
        "DEAD UP FALL": 3,
        "SLEEP": 4,
        "ENTRY": 5,
        "ENTRY NULL": 6,
        "REBIRTH DOWN": 7,
        "REBIRTH STAND": 8,
        "REBIRTH WAIT": 9,
        "WAIT": 10,
        "WALK SLOW": 11,
        "WALK MIDDLE": 12,
        "WALK FAST": 13,
        "WALK END": 14,
        "DASH": 15,
        "RUN": 16,
        "RUN BRAKE": 17,
        "TURN": 18,
        "TURN RUN": 19,
        "KNEE BEND": 20,
        "GUARD KNEE BEND": 21,
        "JUMP F": 22,
        "JUMP B": 23,
        "JUMP AERIAL F": 24,
        "JUMP AERIAL B": 25,
        "FALL": 26,
        "FALL AERIAL": 27,
        "SQUAT": 28,
        "SQUAT WAIT": 29,
        "SQUAT RV": 30,
        "LANDING LIGHT": 31,
        "LANDING HEAVY": 32,
        "PASS": 33,
        "GUARD PASS": 34,
        "OTTOTTO WAIT": 35,
        "OTTOTTO": 36,
        "DAMAGE HI 1": 37,
        "DAMAGE HI 2": 38,
        "DAMAGE HI 3": 39,
        "DAMAGE N 1": 40,
        "DAMAGE N 2": 41,
        "DAMAGE N 3": 42,
        "DAMAGE LW 1": 43,
        "DAMAGE LW 2": 44,
        "DAMAGE LW 3": 45,
        "DAMAGE AIR 1": 46,
        "DAMAGE AIR 2": 47,
        "DAMAGE AIR 3": 48,
        "DAMAGE E 1": 49,
        "DAMAGE E 2": 50,
        "DAMAGE FLY HI": 51,
        "DAMAGE FLY N": 52,
        "DAMAGE FLY LW": 53,
        "DAMAGE FLY TOP": 54,
        "DAMAGE FLY ROLL": 55,
        "WALL DAMAGE": 56,
        "DAMAGE FALL": 57,
        "FALL SPECIAL": 58,
        "LANDING FALL SPECIAL": 59,
        "TWISTER": 60,
        "TARU CANN": 61,
        "DOKAN START": 62,
        "DOKAN WAIT": 63,
        "DOKAN END": 64,
        "DOKAN WALK": 65,
        "STOP CEIL": 66,
        "DOWN BOUNCE D": 67,
        "DOWN BOUNCE U": 68,
        "DOWN WAIT D": 69,
        "DOWN WAIT U": 70,
        "DOWN STAND D": 71,
        "DOWN STAND U": 72,
        "PASSIVE STAND F": 73,
        "PASSIVE STAND B": 74,
        "DOWN FORWARD D": 75,
        "DOWN FORWARD U": 76,
        "DOWN BACK D": 77,
        "DOWN BACK U": 78,
        "DOWN ATTACK D": 79,
        "DOWN ATTACK U": 80,
        "PASSIVE": 81,
        "REBOUND WAIT": 82,
        "REBOUND": 83,
        "CLIFF CATCH": 84,
        "CLIFF WAIT": 85,
        "CLIFF QUICK": 86,
        "CLIFF CLIMB QUICK 1": 87,
        "CLIFF CLIMB QUICK 2": 88,
        "CLIFF SLOW": 89,
        "CLIFF CLIMB SLOW 1": 90,
        "CLIFF CLIMB SLOW 2": 91,
        "CLIFF ATTACK QUICK 1": 92,
        "CLIFF ATTACK QUICK 2": 93,
        "CLIFF ATTACK SLOW 1": 94,
        "CLIFF ATTACK SLOW 2": 95,
        "CLIFF ESCAPE QUICK 1": 96,
        "CLIFF ESCAPE QUICK 2": 97,
        "CLIFF ESCAPE SLOW 1": 98,
        "CLIFF ESCAPE SLOW 2": 99,
        "LIGHT GET": 100,
        "HEAVY GET": 101,
        "LIFT WAIT": 102,
        "LIFT TURN": 103,
        "LIGHT THROW DROP": 104,
        "LIGHT THROW DASH": 105,
        "LIGHT THROW F": 106,
        "LIGHT THROW B": 107,
        "LIGHT THROW HI": 108,
        "LIGHT THROW LW": 109,
        "LIGHT THROW F 4": 110,
        "LIGHT THROW B 4": 111,
        "LIGHT THROW HI 4": 112,
        "LIGHT THROW LW 4": 113,
        "LIGHT THROW AIR F": 114,
        "LIGHT THROW AIR B": 115,
        "LIGHT THROW AIR HI": 116,
        "LIGHT THROW AIR LW": 117,
        "LIGHT THROW AIR F 4": 118,
        "LIGHT THROW AIR B 4": 119,
        "LIGHT THROW AIR HI 4": 120,
        "LIGHT THROW AIR LW 4": 121,
        "HEAVY THROW F": 122,
        "HEAVY THROW B": 123,
        "HEAVY THROW F 4": 124,
        "HEAVY THROW B 4": 125,
        "SWORD SWING 1": 126,
        "SWORD SWING 3": 127,
        "SWORD SWING 4": 128,
        "SWORD SWING DASH": 129,
        "BAT SWING 1": 130,
        "BAT SWING 3": 131,
        "BAT SWING 4": 132,
        "BAT SWING DASH": 133,
        "HARISEN SWING 1": 134,
        "HARISEN SWING 3": 135,
        "HARISEN SWING 4": 136,
        "HARISEN SWING DASH": 137,
        "STAR ROD SWING 1": 138,
        "STAR ROD SWING 3": 139,
        "STAR ROD SWING 4": 140,
        "STAR ROD SWING DASH": 141,
        "LGUN SHOOT": 142,
        "LGUN SHOOT AIR": 143,
        "FIRE FLOWER SHOOT": 144,
        "FIRE FLOWER SHOOT AIR": 145,
        "HAMMER WAIT": 146,
        "HAMMER WALK": 147,
        "HAMMER TURN": 148,
        "HAMMER KNEE BEND": 149,
        "HAMMER FALL": 150,
        "HAMMER LANDING": 151,
        "GUARD ON": 152,
        "GUARD": 153,
        "GUARD OFF": 154,
        "GUARD SET OFF": 155,
        "ESCAPE F": 156,
        "ESCAPE B": 157,
        "SHIELD BREAK FLY": 158,
        "SHIELD BREAK FALL": 159,
        "SHIELD BREAK DOWN D": 160,
        "SHIELD BREAK DOWN U": 161,
        "SHIELD BREAK STAND D": 162,
        "SHIELD BREAK STAND U": 163,
        "FURA FURA": 164,
        "FURA SLEEP": 165,
        "CATCH": 166,
        "CATCH PULL": 167,
        "CATCH WAIT": 168,
        "THROW F": 169,
        "THROW B": 170,
        "CAPTURE PULLED": 171,
        "CAPTURE WAIT": 172,
        "CAPTURE KIRBY": 173,
        "CAPTURE WAIT KIRBY": 174,
        "THROWN KIRBY STAR": 175,
        "THROWN COPY STAR": 176,
        "CAPTURE YOSHI": 177,
        "YOSHI EGG": 178,
        "CAPTURE CAPTAIN": 179,
        "THROWN DONKEY UNK": 180,
        "THROWN DONKEY F": 181,
        "THROWN MARIO B START": 182,
        "THROWN FOX F START": 183,
        "SHOULDERED": 184,
        "THROWN MARIO B": 185,
        "THROWN COMMON": 186,
        "THROWN FOX F": 187,
        "THROWN FOX B": 188,
        "APPEAL": 189,
        "ATTACK 11": 190,
        "ATTACK 12": 191,
        "ATTACK DASH": 192,
        "ATTACK S 3 HI": 193,
        "ATTACK S 3 HI S": 194,
        "ATTACK S 3": 195,
        "ATTACK S 3 LW S": 196,
        "ATTACK S 3 LW": 197,
        "ATTACK HI 3 F": 198,
        "ATTACK HI 3": 199,
        "ATTACK HI 3 B": 200,
        "ATTACK LW 3": 201,
        "ATTACK S 4 HI": 202,
        "ATTACK S 4 HI S": 203,
        "ATTACK S 4": 204,
        "ATTACK S 4 LW S": 205,
        "ATTACK S 4 LW": 206,
        "ATTACK HI 4": 207,
        "ATTACK LW 4": 208,
        "ATTACK AIR N": 209,
        "ATTACK AIR F": 210,
        "ATTACK AIR B": 211,
        "ATTACK AIR HI": 212,
        "ATTACK AIR LW": 213,
        "LANDING AIR N": 214,
        "LANDING AIR F": 215,
        "LANDING AIR B": 216,
        "LANDING AIR HI": 217,
        "LANDING AIR LW": 218,
        "LANDING AIR NULL": 219,
        "SPECIAL START": 220,
    }

    def GetLabel(self):
        if self.template is not None:
            try:
                idx = list(self.template.values()).index(self.value)
                return list(self.template.keys())[idx]
            except ValueError:
                pass
        return f'0x{self.value & 0xFFFFFFFF:X}'


class BOOL_TOGGLE(UNSIGNED_INT):
    template = {"Off": 0, "On": 1}


class KINETIC_STATE(UNSIGNED_INT):
    template = {"Grounded": 0, "Aerial": 1}


class HITBOX_DIR_OVERRIDE(UNSIGNED_INT):
    template = {"No Override": 0, "Force Forward": 1, "Force Backward": 2}


class SFX_PLAY_TYPE(UNSIGNED_INT):
    template = {"SFX": 0, "Voice FX": 1}


def LoadRemixStuff(path="./output.log"):
    try:
        buildlog = open(path, 'r').read()

        # SFX
        pattern = re.compile(r"Added (.*)\nFGM_ID: 0x\w+ \((.*)\)")

        for match in re.findall(pattern, buildlog):
            SFX.template[match[0]] = int(match[1])

        # Damage type
        pattern = re.compile(r"Added Damage Type: (\w+) - ID is (\w+)\n")

        for match in re.findall(pattern, buildlog):
            EFFECT_TYPE.template[match[0]] = int(match[1], 16)

        # GFX
        pattern = re.compile(
            r" - Added GFX_ID (\w+) \(Command ID \w+\) with Instruction ID \w+\): (.*)\n")

        for match in re.findall(pattern, buildlog):
            GFX.template[match[1]] = int(match[0], 16)

        # SWORD TRAILS
        pattern = re.compile(
            r"Added Sword Trail: (\w+) - Moveset command is (.*)\n")

        for match in re.findall(pattern, buildlog):
            SWORD_TRAIL.template[match[0]] = int(match[1][4:], 16)
        
        return True
    except OSError:
        print(f"{path} not found")
        return False