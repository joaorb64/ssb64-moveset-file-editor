from typing import NamedTuple
from enum import Enum, auto
from dataclasses import dataclass
from abc import ABC, abstractmethod
import DataType
import math


def get_hex(s, pos, amount=1):
    return int(s[pos*2:pos*2+amount*2], 16)


@dataclass
class BaseCommand(ABC):
    _hex: str
    command_name: str
    command_size: int = 8

    def __init__(self, _hex: str):
        self._hex = _hex

    def ToHex(self):
        return self._hex


def int_to_mips_signed(value):
    # Ensure the input value is within the range of a 64-bit signed integer
    value %= 1 << 8

    # Perform wrapping around the range if necessary
    if value >= (1 << 7):
        value -= 1 << 8

    return value


class HITBOX(BaseCommand):
    command_name = "Hitbox"
    command_size = 40

    id1: DataType.UNSIGNED_INT
    id2: DataType.UNSIGNED_INT
    damage: DataType.UNSIGNED_INT
    base_knockback: DataType.UNSIGNED_INT
    fixed_knockback: DataType.UNSIGNED_INT
    knockback_scaling: DataType.UNSIGNED_INT
    angle: DataType.SIGNED_INT3
    bone: DataType.UNSIGNED_INT
    x: DataType.SIGNED_INT
    y: DataType.SIGNED_INT
    z: DataType.SIGNED_INT
    hit_aerial_targets: DataType.UNSIGNED_INT
    hit_grounded_targets: DataType.UNSIGNED_INT
    shield_damage: DataType.UNSIGNED_INT
    clang: DataType.UNSIGNED_INT
    size: DataType.UNSIGNED_INT
    effect: DataType.EFFECT_TYPE
    sound_type: DataType.SOUND_TYPE
    sound_level: DataType.SOUND_LEVEL

    def __init__(self, _hex: str):
        super().__init__(_hex)

        self.id1 = DataType.UNSIGNED_INT(((get_hex(_hex, 1) >> 4) +
                                         (get_hex(_hex, 0) << 4) - 0xC0) / 8)

        self.id2 = DataType.UNSIGNED_INT(((get_hex(_hex, 1) >> 4) +
                                         (get_hex(_hex, 0) << 4) - 0xC0) % 8)

        self.damage = DataType.UNSIGNED_INT(((get_hex(_hex, 3) >> 4) +
                                             ((get_hex(_hex, 2) << 4) & 0xFF)) / 2)
        self.base_knockback = DataType.UNSIGNED_INT(((get_hex(_hex, 19) >> 4) +
                                                     (get_hex(_hex, 18) << 4)) / 8)
        self.fixed_knockback = DataType.UNSIGNED_INT(
            (get_hex(_hex, 15) + ((get_hex(_hex, 14) << 8) & 0xFFF)) / 4)
        self.knockback_scaling = DataType.UNSIGNED_INT(((get_hex(_hex, 14) >> 4) & 0xF) +
                                                       ((get_hex(_hex, 13) << 4) & 0xFF))

        self.angle = DataType.SIGNED_INT3(
            ((get_hex(_hex, 12) << 4) +
            (get_hex(_hex, 13) >> 4)) / 4
        )

        self.bone = DataType.UNSIGNED_INT((((get_hex(_hex, 1) << 4) & 0xFF) +
                                           (get_hex(_hex, 2) >> 4)) / 2)

        self.x = DataType.SIGNED_INT(
            get_hex(_hex, 7) + (get_hex(_hex, 6) << 8))
        self.y = DataType.SIGNED_INT(
            get_hex(_hex, 9) + (get_hex(_hex, 8) << 8))
        self.z = DataType.SIGNED_INT(
            get_hex(_hex, 11) + (get_hex(_hex, 10) << 8))

        self.hit_aerial_targets = DataType.UNSIGNED_INT(get_hex(_hex, 15) & 1)
        self.hit_grounded_targets = DataType.UNSIGNED_INT(
            (get_hex(_hex, 15) >> 1) & 1)
        self.shield_damage = DataType.UNSIGNED_INT(get_hex(_hex, 16))
        self.clang = DataType.UNSIGNED_INT((get_hex(_hex, 3) >> 4) & 1)
        self.size = DataType.UNSIGNED_INT(
            (get_hex(_hex, 5) + (get_hex(_hex, 4) << 8)) / 2)

        self.effect = DataType.EFFECT_TYPE(get_hex(_hex, 3) & 0xF)
        self.sound_type = DataType.SOUND_TYPE((get_hex(_hex, 17) & 0xF) / 2)
        self.sound_level = DataType.SOUND_LEVEL((get_hex(_hex, 17) >> 4) / 2)

    def ToHex(self):
        # ID1 DMG BKB FKB KBS Angle Bone X Y Z GT AT SD Clang Size Effect SoundType SoundLevel
        output = ""

        ''' 8-digit block '''
        out_hex = (0xC000000 | (self.id1.value * 0x800000)
                   + (self.id2.value * 0x100000))
        out_hex |= (self.bone.value << 13)
        out_hex |= (self.damage.value << 5)  # Damage
        out_hex |= (self.clang.value << 4)  # Clang

        # Effect. Change 5 into 7
        effect_value = 7 if self.effect.value == 5 else self.effect.value
        out_hex += effect_value  # Effect

        output += f'{hex(out_hex)[2:]:0>8}'
        print(f'{hex(out_hex)[2:]:0>8}')

        ''' 8-digit block '''
        out_hex = 0 | (self.size.value << 17)  # Size
        out_hex |= (self.x.GetValue() & 0xFFFF)  # X

        output += f'{hex(out_hex)[2:]:0>8}'
        print(f'{hex(out_hex)[2:]:0>8}')

        ''' 8-digit block '''
        out_hex = (self.y.GetValue() << 16) & 0xFFFF0000  # Y
        out_hex |= (self.z.GetValue() & 0xFFFF)  # Z

        output += f'{hex(out_hex)[2:]:0>8}'
        print(f'{hex(out_hex)[2:]:0>8}')

        ''' 8-digit block '''
        out_hex = (self.angle.GetValue() << 22) & 0xFFF00000  # Angle
        out_hex += self.knockback_scaling.value << 12  # Knockback Scaling
        out_hex += self.fixed_knockback.value * 4  # Fixed knocback
        out_hex += self.hit_grounded_targets.value * 2  # Grounded targets
        out_hex += self.hit_aerial_targets.value  # Aerial targets

        output += f'{hex(out_hex)[2:]:0>8}'
        print(f'{hex(out_hex)[2:]:0>8}')

        ''' 8-digit block '''
        out_hex = self.shield_damage.value << 24  # Shield Damage
        out_hex += (self.sound_level.value * 2) << 20  # Sound level
        out_hex += (self.sound_type.value * 2) << 16  # Sound type

        bkb = self.base_knockback.value
        out_hex += ((bkb * 8) << 4)  # Base Knockback

        output += f'{hex(out_hex)[2:]:0>8}'
        print(f'{hex(out_hex)[2:]:0>8}')

        return output


class AFTER(BaseCommand):
    command_name = "After"

    time: DataType.UNSIGNED_INT

    def __init__(self, _hex: str):
        super().__init__(_hex)
        self.time = DataType.UNSIGNED_INT(get_hex(_hex, 2, 2))

    def ToHex(self):
        return self._hex[0:2]+f'{(hex(self.time.value)[2:]):0>6}'


class WAIT(BaseCommand):
    command_name = "Wait"

    time: DataType.UNSIGNED_INT

    def __init__(self, _hex: str):
        super().__init__(_hex)
        self.time = DataType.UNSIGNED_INT(get_hex(_hex, 2, 2))

    def ToHex(self):
        return self._hex[0:2]+f'{(hex(self.time.value)[2:]):0>6}'


class END_HITBOX(BaseCommand):
    command_name = "End Hitboxes"
    command_size = 8


class MOVESET_END(BaseCommand):
    command_name = "Move Data End"
    command_size = 8


class UNKNOWN(BaseCommand):
    command_name = "???"
    command_size = 8


class PLAY_SFX(BaseCommand):
    command_name = "Play SFX"
    command_size = 8

    sfx: DataType.SFX

    def __init__(self, _hex: str):
        super().__init__(_hex)
        self.sfx = DataType.SFX(get_hex(_hex, 2, 2))

    def ToHex(self):
        return self._hex[0:2]+f'{(hex(self.sfx.value)[2:]):0>6}'


class SET_SPECIFIC_HURTBOX_STATE(BaseCommand):
    command_name = "Set Specific Hurtbox State"
    command_size = 8

    part: DataType.UNSIGNED_INT
    state: DataType.HURTBOX_STATE

    def __init__(self, _hex: str):
        super().__init__(_hex)
        self.part = DataType.UNSIGNED_INT(get_hex(_hex, 1)/8)
        self.state = DataType.HURTBOX_STATE(get_hex(_hex, 3))

    def ToHex(self):
        part = f'{(hex(self.part.value*8)[2:]):0>2}'
        state = f'{(hex(self.state.value)[2:]):0>2}'
        return self._hex[0:2]+part+"00"+state


class VOICE_SFX(BaseCommand):
    command_name = "Voice SFX"
    command_size = 8

    sfx: DataType.SFX

    def __init__(self, _hex: str):
        super().__init__(_hex)
        self.sfx = DataType.SFX(get_hex(_hex, 2, 2))

    def ToHex(self):
        return self._hex[0:2]+f'{(hex(self.sfx.value)[2:]):0>6}'


class SET_SLOPE_CONTOUR_STATE(BaseCommand):
    command_name = "Set slope contour state"
    command_size = 8

    state: DataType.CONTOUR_STATE

    def __init__(self, _hex: str):
        super().__init__(_hex)
        self.state = DataType.CONTOUR_STATE(get_hex(_hex, 2, 2))

    def ToHex(self):
        return self._hex[0:2]+f'{(hex(self.state.value)[2:]):0>6}'


class SWORD_TRAIL(BaseCommand):
    command_name = "Sword trail"
    command_size = 8

    command: DataType.SWORD_TRAIL

    def __init__(self, _hex: str):
        super().__init__(_hex)
        self.command = DataType.SWORD_TRAIL(get_hex(_hex, 1, 3))
        print("Command:", _hex, get_hex(_hex, 1, 3), self.command.value)

    def ToHex(self):
        return self._hex[0:2]+f'{(hex(self.command.value)[2:]):0>6}'


class GFX(BaseCommand):
    command_name = "GFX"
    command_size = 32

    flag: DataType.UNSIGNED_INT
    bone: DataType.UNSIGNED_INT
    effect: DataType.GFX
    x1: DataType.SIGNED_INT
    y1: DataType.SIGNED_INT
    z1: DataType.SIGNED_INT
    x2: DataType.SIGNED_INT
    y2: DataType.SIGNED_INT
    z2: DataType.SIGNED_INT

    def __init__(self, _hex: str):
        super().__init__(_hex)

        # MOD(HEXADEC(EXT.TEXTO(D670;2;1));8)*(2^5)+ARREDONDAR.PARA.BAIXO(HEXADEC(EXT.TEXTO(D670;3;2))/8;0)

        self.flag = DataType.UNSIGNED_INT(int(_hex[1:2], 16) / 10)

        self.bone = DataType.UNSIGNED_INT(math.floor(get_hex(_hex, 1)/8))

        # MOD(HEXADEC(EXT.TEXTO(D670;4;3));2048)/4
        self.effect = DataType.GFX((int(_hex[3:6], 16) % 2048) / 4)

        self.x1 = DataType.SIGNED_INT(int(_hex[8:12], 16))
        self.y1 = DataType.SIGNED_INT(int(_hex[12:16], 16))
        self.z1 = DataType.SIGNED_INT(int(_hex[16:20], 16))
        self.x2 = DataType.SIGNED_INT(int(_hex[20:24], 16))
        self.y2 = DataType.SIGNED_INT(int(_hex[24:28], 16))
        self.z2 = DataType.SIGNED_INT(int(_hex[28:31], 16))

    def ToHex(self):
        return self._hex
        # return self._hex[0:2]+f'{(hex(self.effect.value)[2:]):0>6}'


COMMANDS = {
    "00": MOVESET_END,
    "04": WAIT,
    "08": AFTER,
    "0C": HITBOX,
    "0D": HITBOX,
    #     "10": ("ftScriptEvent_Kind_HitScaleOffset", "Item Hitbox"),
    #     "14": ("ftScriptEvent_Kind_ClearHitIndex", "Delete Hitbox"),
    #     "18": ("ftScriptEvent_Kind_ClearHitAll", "End Hitbox"),
    #     "1C": ("ftScriptEvent_Kind_SetHitOffset", "[7]"),
    #     "20": ("ftScriptEvent_Kind_SetHitDamage", "Change Hitbox Damage"),
    #     "24": ("ftScriptEvent_Kind_SetHitSize", "Change Hitbox Size"),
    "18": END_HITBOX,
    #     "28": ("ftScriptEvent_Kind_SetHitSoundLevel", "[12]"),
    #     "2C": ("ftScriptEvent_Kind_RefreshHit", "Revive Hitbox"),
    #     "30": ("ftScriptEvent_Kind_SetFighterThrow", "Throw Data"),
    #     "34": ("ftScriptEvent_Kind_SubroutineThrown", "Subroutine? [13]"),
    #     "38": ("ftScriptEvent_Kind_PlaySFX", "SFX [14]"),
    #     "3c": ("ftScriptEvent_Kind_PlayLoopSFXStoreInfo", "[15]"),
    #     "40": ("ftScriptEvent_Kind_StopLoopSFX", "[16]"),
    "44": VOICE_SFX,
    #     "48": ("ftScriptEvent_Kind_PlayLoopVoiceStoreInfo", "[18]"),
    "4C": PLAY_SFX,
    #     "50": ("ftScriptEvent_Kind_PlaySmashVoice", "Generic Voice FX"),
    #     "54": ("ftScriptEvent_Kind_SetFlag0", "Create Prop"),
    #     "58": ("ftScriptEvent_Kind_SetFlag1", "Set Flag (Turn Around?)"),
    #     "5C": ("ftScriptEvent_Kind_SetFlag2", "Apply Throw?"),
    #     "60": ("ftScriptEvent_Kind_SetFlag3", "[24]"),
    #     "64": ("ftScriptEvent_Kind_SetAirJumpAdd", "[25]"),
    #     "68": ("ftScriptEvent_Kind_SetAirJumpMax", "[26]"),
    #     "6C": ("ftScriptEvent_Kind_SetHitStatusPartAll", "Reset Hurtbox State"),
    "70": SET_SPECIFIC_HURTBOX_STATE,
    #     "74": ("ftScriptEvent_Kind_SetHitStatusAll", "Set Hurtbox State"),
    #     "78": ("ftScriptEvent_Kind_ResetHurtAll", "Reset Hurtbox Sizes?"),
    #     "7C": ("ftScriptEvent_Kind_SetHurtPart", "Set Hurtbox Size?"),
    #     "80": ("ftScriptEvent_Kind_LoopBegin", "Begin Loop"),
    #     "84": ("ftScriptEvent_Kind_LoopEnd", "End Loop"),
    #     "88": ("ftScriptEvent_Kind_Subroutine", "Subroutine"),
    #     "8C": ("ftScriptEvent_Kind_Return", "Return"),
    #     "90": ("ftScriptEvent_Kind_Goto", "Goto"),
    #     "94": ("ftScriptEvent_Kind_ScriptPause", "[37]"),
    "98": GFX,
    "9A": GFX,
    #     "9C": ("ftScriptEvent_Kind_GFXScaleOffset", "GFX 2"),
    #     "A0": ("ftScriptEvent_Kind_SetModelPart", "Set Model Form"),
    #     "A4": ("ftScriptEvent_Kind_ResetModelPartAll", "[41]"),
    #     "A8": ("ftScriptEvent_Kind_HideModelPartAll", "[42]"),
    #     "AC": ("ftScriptEvent_Kind_SetTexturePart", "Set Texture Form"),
    #     "B0": ("ftScriptEvent_Kind_SetColAnim", "[44]"),
    #     "B4": ("ftScriptEvent_Kind_ResetColAnim", "[45]"),
    #     "B8": ("ftScriptEvent_Kind_SetParallelScript", "Concurrent Stream"),
    "BC": SET_SLOPE_CONTOUR_STATE,
    #     "C0": ("ftScriptEvent_Kind_HideItem", "[48]"),
    #     "C4": ("ftScriptEvent_Kind_MakeRumble", "[49]"),
    #     "C8": ("ftScriptEvent_Kind_StopRumble", "[50]"),
    "CC": SWORD_TRAIL,
    #     "D0": ("", "52"),
    #     "D4": ("", "53"),
    #     "D8": ("", "54"),
    #     "DC": ("", "55"),
    #     "E0": ("", "56"),
    #     "E4": ("", "57"),
    #     "E8": ("", "58"),
    #     "EC": ("", "59"),
    #     "F0": ("", "60"),
    #     "F4": ("", "61"),
    #     "F8": ("", "62"),
    #     "FF": ("", "63"),
}


def GetCommand(code) -> BaseCommand:
    if code in COMMANDS:
        return COMMANDS[code]
    else:
        return UNKNOWN
