import math
from abc import ABC
from dataclasses import dataclass
import DataType


# ── Helpers ───────────────────────────────────────────────────────────────────

def get_hex(s, pos, amount=1):
    return int(s[pos*2:pos*2+amount*2], 16)


def get_word(s, word_idx=0):
    """Read a 32-bit big-endian word from a hex string by word index."""
    return int(s[word_idx*8:(word_idx+1)*8], 16)


def sx(val, bits):
    """Sign-extend val from the given number of bits."""
    if val & (1 << (bits - 1)):
        val -= (1 << bits)
    return val


def _opcode(hex_str):
    """Return the 6-bit opcode from the first byte of a hex string."""
    return int(hex_str[0:2], 16) >> 2


def _w1(opcode, payload=0):
    """Build the first word of a 1-word command."""
    return f'{(opcode << 26) | (payload & 0x3FFFFFF):08X}'


# ── Base ──────────────────────────────────────────────────────────────────────

@dataclass
class BaseCommand(ABC):
    _hex: str
    command_name: str
    command_size: int = 8

    def __init__(self, _hex: str):
        self._hex = _hex

    def ToHex(self):
        return self._hex


# ── End / timing ──────────────────────────────────────────────────────────────

class MOVESET_END(BaseCommand):
    command_name = "Move Data End"
    command_size = 8


class WAIT(BaseCommand):
    command_name = "Wait"
    time: DataType.UNSIGNED_INT

    def __init__(self, _hex):
        super().__init__(_hex)
        self.time = DataType.UNSIGNED_INT(get_hex(_hex, 2, 2))

    def ToHex(self):
        return self._hex[0:2] + f'{self.time.value:06X}'


class AFTER(BaseCommand):
    command_name = "After"
    time: DataType.UNSIGNED_INT

    def __init__(self, _hex):
        super().__init__(_hex)
        self.time = DataType.UNSIGNED_INT(get_hex(_hex, 2, 2))

    def ToHex(self):
        return self._hex[0:2] + f'{self.time.value:06X}'


# ── Hitbox creation ───────────────────────────────────────────────────────────

class HITBOX(BaseCommand):
    """MakeAttackColl / MakeAttackCollScaled (opcodes 3 & 4 — 5 words)."""
    command_name = "Hitbox"
    command_size = 40

    hitbox_id: DataType.UNSIGNED_INT
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

        combined = ((get_hex(_hex, 1) >> 4) + (get_hex(_hex, 0) << 4) - 0xC0)
        self.hitbox_id = DataType.UNSIGNED_INT(combined / 8)  # attack_id bits[25:23]
        self._group_id  = combined % 8                        # group_id bits[22:20], not user-editable
        self.damage = DataType.UNSIGNED_INT(((get_hex(_hex, 3) >> 4) +
                                             ((get_hex(_hex, 2) << 4) & 0xFF)) / 2)
        self.base_knockback = DataType.UNSIGNED_INT(((get_hex(_hex, 19) >> 4) +
                                                     (get_hex(_hex, 18) << 4)) / 8)
        self.fixed_knockback = DataType.UNSIGNED_INT(
            (get_hex(_hex, 15) + ((get_hex(_hex, 14) << 8) & 0xFFF)) / 4)
        self.knockback_scaling = DataType.UNSIGNED_INT(((get_hex(_hex, 14) >> 4) & 0xF) +
                                                       ((get_hex(_hex, 13) << 4) & 0xFF))
        self.angle = DataType.SIGNED_INT3(
            ((get_hex(_hex, 12) << 4) + (get_hex(_hex, 13) >> 4)) / 4)
        self.bone = DataType.UNSIGNED_INT((((get_hex(_hex, 1) << 4) & 0xFF) +
                                           (get_hex(_hex, 2) >> 4)) / 2)
        self.x = DataType.SIGNED_INT(get_hex(_hex, 7) + (get_hex(_hex, 6) << 8))
        self.y = DataType.SIGNED_INT(get_hex(_hex, 9) + (get_hex(_hex, 8) << 8))
        self.z = DataType.SIGNED_INT(get_hex(_hex, 11) + (get_hex(_hex, 10) << 8))
        self.hit_aerial_targets = DataType.UNSIGNED_INT(get_hex(_hex, 15) & 1)
        self.hit_grounded_targets = DataType.UNSIGNED_INT((get_hex(_hex, 15) >> 1) & 1)
        self.shield_damage = DataType.UNSIGNED_INT(get_hex(_hex, 16))
        self.clang = DataType.UNSIGNED_INT((get_hex(_hex, 3) >> 4) & 1)
        self.size = DataType.UNSIGNED_INT((get_hex(_hex, 5) + (get_hex(_hex, 4) << 8)) / 2)
        self.effect = DataType.EFFECT_TYPE(get_hex(_hex, 3) & 0xF)
        self.sound_type = DataType.SOUND_TYPE((get_hex(_hex, 17) & 0xF) / 2)
        self.sound_level = DataType.SOUND_LEVEL((get_hex(_hex, 17) >> 4) / 2)

    def ToHex(self):
        opc = _opcode(self._hex)
        w1 = (opc << 26) | (self.hitbox_id.value << 23) | (self._group_id << 20)
        w1 |= (self.bone.value << 13)
        w1 |= (self.damage.value << 5)
        w1 |= (self.clang.value << 4)
        w1 |= (7 if self.effect.value == 5 else self.effect.value)
        w2 = (self.size.value << 17) | (self.x.GetValue() & 0xFFFF)
        w3 = ((self.y.GetValue() << 16) & 0xFFFF0000) | (self.z.GetValue() & 0xFFFF)
        w4 = ((self.angle.GetValue() << 22) & 0xFFF00000)
        w4 += self.knockback_scaling.value << 12
        w4 += self.fixed_knockback.value * 4
        w4 += self.hit_grounded_targets.value * 2
        w4 += self.hit_aerial_targets.value
        w5 = self.shield_damage.value << 24
        w5 += (self.sound_level.value * 2) << 20
        w5 += (self.sound_type.value * 2) << 16
        w5 += (self.base_knockback.value * 8) << 4
        return f'{w1:08X}{w2:08X}{w3:08X}{w4:08X}{w5:08X}'


# ── Hitbox modification ───────────────────────────────────────────────────────

class CLEAR_HITBOX(BaseCommand):
    command_name = "Delete Hitbox"
    command_size = 8
    hitbox_id: DataType.UNSIGNED_INT

    def __init__(self, _hex):
        super().__init__(_hex)
        self.hitbox_id = DataType.UNSIGNED_INT((get_word(_hex) >> 23) & 0x7)

    def ToHex(self):
        return _w1(5, self.hitbox_id.value << 23)


class END_HITBOX(BaseCommand):
    command_name = "End Hitboxes"
    command_size = 8


class SET_HITBOX_OFFSET(BaseCommand):
    """SetAttackCollOffset — 2 words."""
    command_name = "Set Hitbox Offset"
    command_size = 16
    attack_id: DataType.UNSIGNED_INT
    x: DataType.SIGNED_INT
    y: DataType.SIGNED_INT
    z: DataType.SIGNED_INT

    def __init__(self, _hex):
        super().__init__(_hex)
        w1 = get_word(_hex, 0)
        w2 = get_word(_hex, 1)
        self.attack_id = DataType.UNSIGNED_INT((w1 >> 23) & 0x7)
        self.x = DataType.SIGNED_INT(sx((w1 >> 7) & 0xFFFF, 16))
        self.y = DataType.SIGNED_INT(sx((w2 >> 16) & 0xFFFF, 16))
        self.z = DataType.SIGNED_INT(sx(w2 & 0xFFFF, 16))

    def ToHex(self):
        w1 = (7 << 26) | (self.attack_id.value << 23) | ((self.x.GetValue() & 0xFFFF) << 7)
        w2 = ((self.y.GetValue() & 0xFFFF) << 16) | (self.z.GetValue() & 0xFFFF)
        return f'{w1:08X}{w2:08X}'


class SET_HITBOX_DAMAGE(BaseCommand):
    command_name = "Set Hitbox Damage"
    command_size = 8
    attack_id: DataType.UNSIGNED_INT
    damage: DataType.UNSIGNED_INT

    def __init__(self, _hex):
        super().__init__(_hex)
        w = get_word(_hex)
        self.attack_id = DataType.UNSIGNED_INT((w >> 23) & 0x7)
        self.damage = DataType.UNSIGNED_INT((w >> 15) & 0xFF)

    def ToHex(self):
        return _w1(8, (self.attack_id.value << 23) | (self.damage.value << 15))


class SET_HITBOX_SIZE(BaseCommand):
    command_name = "Set Hitbox Size"
    command_size = 8
    attack_id: DataType.UNSIGNED_INT
    size: DataType.UNSIGNED_INT

    def __init__(self, _hex):
        super().__init__(_hex)
        w = get_word(_hex)
        self.attack_id = DataType.UNSIGNED_INT((w >> 23) & 0x7)
        self.size = DataType.UNSIGNED_INT((w >> 7) & 0xFFFF)

    def ToHex(self):
        return _w1(9, (self.attack_id.value << 23) | (self.size.value << 7))


class SET_HITBOX_SOUND_LEVEL(BaseCommand):
    command_name = "Set Hitbox Sound Level"
    command_size = 8
    attack_id: DataType.UNSIGNED_INT
    level: DataType.SOUND_LEVEL

    def __init__(self, _hex):
        super().__init__(_hex)
        w = get_word(_hex)
        self.attack_id = DataType.UNSIGNED_INT((w >> 23) & 0x7)
        self.level = DataType.SOUND_LEVEL((w >> 20) & 0x7)

    def ToHex(self):
        return _w1(10, (self.attack_id.value << 23) | (self.level.value << 20))


class REVIVE_HITBOX(BaseCommand):
    command_name = "Revive Hitbox"
    command_size = 8
    attack_id: DataType.UNSIGNED_INT

    def __init__(self, _hex):
        super().__init__(_hex)
        self.attack_id = DataType.UNSIGNED_INT((get_word(_hex) >> 23) & 0x7)

    def ToHex(self):
        return _w1(11, self.attack_id.value << 23)


# ── Throw ─────────────────────────────────────────────────────────────────────

class THROW_DATA(BaseCommand):
    """SetThrow — 2 words, word 2 is a file-relative pointer to FTThrowHitDesc."""
    command_name = "Throw Data"
    command_size = 16
    pointer: DataType.UNSIGNED_INT

    def __init__(self, _hex):
        super().__init__(_hex)
        self.pointer = DataType.UNSIGNED_INT(get_word(_hex, 1))

    def ToHex(self):
        return _w1(12) + f'{self.pointer.value:08X}'


class THROW_SUBROUTINE(BaseCommand):
    """SetDamageThrown — 2 words."""
    command_name = "Throw Subroutine"
    command_size = 16
    pointer: DataType.UNSIGNED_INT

    def __init__(self, _hex):
        super().__init__(_hex)
        self.pointer = DataType.UNSIGNED_INT(get_word(_hex, 1))

    def ToHex(self):
        return _w1(13) + f'{self.pointer.value:08X}'


# ── Audio ─────────────────────────────────────────────────────────────────────

class PLAY_SFX(BaseCommand):
    command_name = "Play SFX"
    command_size = 8
    sfx: DataType.SFX

    def __init__(self, _hex):
        super().__init__(_hex)
        self.sfx = DataType.SFX(get_hex(_hex, 2, 2))

    def ToHex(self):
        return self._hex[0:2] + f'{self.sfx.value:06X}'


class PLAY_LOOP_SFX(BaseCommand):
    command_name = "Play Loop SFX"
    command_size = 8
    sfx: DataType.SFX

    def __init__(self, _hex):
        super().__init__(_hex)
        self.sfx = DataType.SFX(get_word(_hex) & 0x3FFFFFF)

    def ToHex(self):
        return _w1(15, self.sfx.value)


class STOP_LOOP_SFX(BaseCommand):
    command_name = "Stop Loop SFX"
    command_size = 8

    def ToHex(self):
        return _w1(16)


class VOICE_SFX(BaseCommand):
    command_name = "Voice SFX"
    command_size = 8
    sfx: DataType.SFX

    def __init__(self, _hex):
        super().__init__(_hex)
        self.sfx = DataType.SFX(get_hex(_hex, 2, 2))

    def ToHex(self):
        return self._hex[0:2] + f'{self.sfx.value:06X}'


class PLAY_LOOP_VOICE(BaseCommand):
    command_name = "Play Loop Voice"
    command_size = 8
    sfx: DataType.SFX

    def __init__(self, _hex):
        super().__init__(_hex)
        self.sfx = DataType.SFX(get_word(_hex) & 0x3FFFFFF)

    def ToHex(self):
        return _w1(18, self.sfx.value)


class PLAY_FGM_STORE(BaseCommand):
    """PlayFGMStoreInfo — same payload shape as PLAY_SFX but opcode 19."""
    command_name = "Play FGM (Store)"
    command_size = 8
    sfx: DataType.SFX

    def __init__(self, _hex):
        super().__init__(_hex)
        self.sfx = DataType.SFX(get_hex(_hex, 2, 2))

    def ToHex(self):
        return self._hex[0:2] + f'{self.sfx.value:06X}'


class SMASH_VOICE(BaseCommand):
    command_name = "Smash Voice"
    command_size = 8
    sfx: DataType.SFX

    def __init__(self, _hex):
        super().__init__(_hex)
        self.sfx = DataType.SFX(get_word(_hex) & 0x3FFFFFF)

    def ToHex(self):
        return _w1(20, self.sfx.value)


# ── Game flags ────────────────────────────────────────────────────────────────

class _SET_FLAG(BaseCommand):
    command_size = 8
    value: DataType.UNSIGNED_INT

    def __init__(self, _hex):
        super().__init__(_hex)
        self.value = DataType.UNSIGNED_INT(get_word(_hex) & 0x3FFFFFF)

    def ToHex(self):
        return _w1(_opcode(self._hex), self.value.value)


class SET_FLAG0(_SET_FLAG):
    command_name = "Set Flag 0"


class SET_FLAG1(_SET_FLAG):
    command_name = "Set Flag 1"


class SET_FLAG2(_SET_FLAG):
    command_name = "Set Flag 2"


class SET_FLAG3(_SET_FLAG):
    command_name = "Set Flag 3"


class SET_AIR_JUMP_ADD(BaseCommand):
    command_name = "Set Air Jump Add"
    command_size = 8
    value: DataType.UNSIGNED_INT

    def __init__(self, _hex):
        super().__init__(_hex)
        self.value = DataType.UNSIGNED_INT(get_word(_hex) & 0x3FFFFFF)

    def ToHex(self):
        return _w1(25, self.value.value)


class SET_AIR_JUMP_MAX(BaseCommand):
    command_name = "Set Air Jump Max"
    command_size = 8
    value: DataType.UNSIGNED_INT

    def __init__(self, _hex):
        super().__init__(_hex)
        self.value = DataType.UNSIGNED_INT(get_word(_hex) & 0x3FFFFFF)

    def ToHex(self):
        return _w1(26, self.value.value)


# ── Hurtboxes ─────────────────────────────────────────────────────────────────

class SET_ALL_HURTBOX_STATE(BaseCommand):
    command_name = "Set All Hurtbox State"
    command_size = 8
    state: DataType.HURTBOX_STATE

    def __init__(self, _hex):
        super().__init__(_hex)
        self.state = DataType.HURTBOX_STATE(get_word(_hex) & 0x3FFFFFF)

    def ToHex(self):
        return _w1(27, self.state.value)


class SET_SPECIFIC_HURTBOX_STATE(BaseCommand):
    command_name = "Set Specific Hurtbox State"
    command_size = 8
    part: DataType.UNSIGNED_INT
    state: DataType.HURTBOX_STATE

    def __init__(self, _hex):
        super().__init__(_hex)
        self.part = DataType.UNSIGNED_INT(get_hex(_hex, 1) / 8)
        self.state = DataType.HURTBOX_STATE(get_hex(_hex, 3))

    def ToHex(self):
        return self._hex[0:2] + f'{self.part.value*8:02X}' + '00' + f'{self.state.value:02X}'


class SET_HURTBOX_STATE(BaseCommand):
    command_name = "Set Hurtbox State"
    command_size = 8
    state: DataType.HURTBOX_STATE

    def __init__(self, _hex):
        super().__init__(_hex)
        self.state = DataType.HURTBOX_STATE(get_word(_hex) & 0x3FFFFFF)

    def ToHex(self):
        return _w1(29, self.state.value)


class RESET_DAMAGE_COLL(BaseCommand):
    command_name = "Reset Damage Collision"
    command_size = 8

    def ToHex(self):
        return _w1(30)


class SET_HURTBOX_SIZE(BaseCommand):
    """SetDamageCollPartID — 4 words, sets per-part hurtbox offset + size."""
    command_name = "Set Hurtbox Size"
    command_size = 32
    joint_id: DataType.SIGNED_INT
    ox: DataType.SIGNED_INT
    oy: DataType.SIGNED_INT
    oz: DataType.SIGNED_INT
    sx_: DataType.SIGNED_INT
    sy: DataType.SIGNED_INT
    sz: DataType.SIGNED_INT

    def __init__(self, _hex):
        super().__init__(_hex)
        w1 = get_word(_hex, 0)
        w2 = get_word(_hex, 1)
        w3 = get_word(_hex, 2)
        w4 = get_word(_hex, 3)
        self.joint_id = DataType.SIGNED_INT(sx((w1 >> 19) & 0x7F, 7))
        self.ox = DataType.SIGNED_INT(sx((w2 >> 16) & 0xFFFF, 16))
        self.oy = DataType.SIGNED_INT(sx(w2 & 0xFFFF, 16))
        self.oz = DataType.SIGNED_INT(sx((w3 >> 16) & 0xFFFF, 16))
        self.sx_ = DataType.SIGNED_INT(sx(w3 & 0xFFFF, 16))
        self.sy = DataType.SIGNED_INT(sx((w4 >> 16) & 0xFFFF, 16))
        self.sz = DataType.SIGNED_INT(sx(w4 & 0xFFFF, 16))

    def ToHex(self):
        w1 = (31 << 26) | ((self.joint_id.GetValue() & 0x7F) << 19)
        w2 = ((self.ox.GetValue() & 0xFFFF) << 16) | (self.oy.GetValue() & 0xFFFF)
        w3 = ((self.oz.GetValue() & 0xFFFF) << 16) | (self.sx_.GetValue() & 0xFFFF)
        w4 = ((self.sy.GetValue() & 0xFFFF) << 16) | (self.sz.GetValue() & 0xFFFF)
        return f'{w1:08X}{w2:08X}{w3:08X}{w4:08X}'


# ── Control flow ──────────────────────────────────────────────────────────────

class LOOP_START(BaseCommand):
    command_name = "Loop Start"
    command_size = 8
    iterations: DataType.UNSIGNED_INT

    def __init__(self, _hex):
        super().__init__(_hex)
        self.iterations = DataType.UNSIGNED_INT(get_hex(_hex, 2, 2))

    def ToHex(self):
        return self._hex[0:2] + f'{self.iterations.value:06X}'


class LOOP_END(BaseCommand):
    command_name = "Loop End"
    command_size = 8


class SUBROUTINE(BaseCommand):
    """Call a subroutine at a file-relative word offset."""
    command_name = "Subroutine"
    command_size = 16
    address: DataType.UNSIGNED_INT

    def __init__(self, _hex):
        super().__init__(_hex)
        self.address = DataType.UNSIGNED_INT(get_word(_hex, 1))

    def ToHex(self):
        return _w1(34) + f'{self.address.value:08X}'


class RETURN(BaseCommand):
    command_name = "Return"
    command_size = 8

    def ToHex(self):
        return _w1(35)


class GOTO(BaseCommand):
    """Jump to a file-relative word offset."""
    command_name = "Goto"
    command_size = 16
    address: DataType.UNSIGNED_INT

    def __init__(self, _hex):
        super().__init__(_hex)
        self.address = DataType.UNSIGNED_INT(get_word(_hex, 1))

    def ToHex(self):
        return _w1(36) + f'{self.address.value:08X}'


class PAUSE_SCRIPT(BaseCommand):
    command_name = "Pause Script"
    command_size = 8
    value: DataType.UNSIGNED_INT

    def __init__(self, _hex):
        super().__init__(_hex)
        self.value = DataType.UNSIGNED_INT(get_word(_hex) & 0x3FFFFFF)

    def ToHex(self):
        return _w1(37, self.value.value)


# ── GFX / Effects ─────────────────────────────────────────────────────────────

class GFX(BaseCommand):
    """Effect — 4 words."""
    command_name = "GFX"
    command_size = 32
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
        self.bone = DataType.UNSIGNED_INT(math.floor(get_hex(_hex, 1) / 8))
        self.effect = DataType.GFX((int(_hex[3:6], 16) % 2048) / 4)
        self.x1 = DataType.SIGNED_INT(int(_hex[8:12], 16))
        self.y1 = DataType.SIGNED_INT(int(_hex[12:16], 16))
        self.z1 = DataType.SIGNED_INT(int(_hex[16:20], 16))
        self.x2 = DataType.SIGNED_INT(int(_hex[20:24], 16))
        self.y2 = DataType.SIGNED_INT(int(_hex[24:28], 16))
        self.z2 = DataType.SIGNED_INT(int(_hex[28:32], 16))

    def ToHex(self):
        # TODO: reconstruct from fields; returning raw hex for now
        return self._hex


class GFX_ITEM(GFX):
    """EffectItemHold — identical layout to GFX, different opcode (39)."""
    command_name = "GFX (Item Hold)"


# ── Model / texture ───────────────────────────────────────────────────────────

class SET_MODEL_PART(BaseCommand):
    command_name = "Set Model Part"
    command_size = 8
    joint_id: DataType.SIGNED_INT
    model_id: DataType.SIGNED_INT

    def __init__(self, _hex):
        super().__init__(_hex)
        w = get_word(_hex)
        self.joint_id = DataType.SIGNED_INT(sx((w >> 19) & 0x7F, 7))
        self.model_id = DataType.SIGNED_INT(sx(w & 0x7FFFF, 19))

    def ToHex(self):
        w = (40 << 26) | ((self.joint_id.GetValue() & 0x7F) << 19) | (self.model_id.GetValue() & 0x7FFFF)
        return f'{w:08X}'


class RESET_MODEL_ALL(BaseCommand):
    command_name = "Reset All Model Parts"
    command_size = 8

    def ToHex(self):
        return _w1(41)


class HIDE_MODEL_ALL(BaseCommand):
    command_name = "Hide All Model Parts"
    command_size = 8

    def ToHex(self):
        return _w1(42)


class SET_TEXTURE_PART(BaseCommand):
    command_name = "Set Texture Part"
    command_size = 8
    value: DataType.UNSIGNED_INT

    def __init__(self, _hex):
        super().__init__(_hex)
        self.value = DataType.UNSIGNED_INT(get_word(_hex) & 0x3FFFFFF)

    def ToHex(self):
        return _w1(43, self.value.value)


class SET_COL_ANIM(BaseCommand):
    command_name = "Set Color Anim"
    command_size = 8
    color_id: DataType.UNSIGNED_INT
    length: DataType.UNSIGNED_INT

    def __init__(self, _hex):
        super().__init__(_hex)
        w = get_word(_hex)
        self.color_id = DataType.UNSIGNED_INT((w >> 18) & 0xFF)
        self.length = DataType.UNSIGNED_INT(w & 0x3FFFF)

    def ToHex(self):
        w = (44 << 26) | (self.color_id.value << 18) | (self.length.value & 0x3FFFF)
        return f'{w:08X}'


class RESET_COL_ANIM(BaseCommand):
    command_name = "Reset Color Anim"
    command_size = 8

    def ToHex(self):
        return _w1(45)


class SET_PARALLEL_SCRIPT(BaseCommand):
    """SetParallelScript — 2 words, word 2 is a file-relative pointer."""
    command_name = "Set Parallel Script"
    command_size = 16
    address: DataType.UNSIGNED_INT

    def __init__(self, _hex):
        super().__init__(_hex)
        self.address = DataType.UNSIGNED_INT(get_word(_hex, 1))

    def ToHex(self):
        return _w1(46) + f'{self.address.value:08X}'


# ── Misc ──────────────────────────────────────────────────────────────────────

class SET_SLOPE_CONTOUR_STATE(BaseCommand):
    command_name = "Set Slope Contour State"
    command_size = 8
    state: DataType.CONTOUR_STATE

    def __init__(self, _hex):
        super().__init__(_hex)
        self.state = DataType.CONTOUR_STATE(get_hex(_hex, 2, 2))

    def ToHex(self):
        return self._hex[0:2] + f'{self.state.value:06X}'


class HIDE_ITEM(BaseCommand):
    command_name = "Hide Item"
    command_size = 8
    value: DataType.UNSIGNED_INT

    def __init__(self, _hex):
        super().__init__(_hex)
        self.value = DataType.UNSIGNED_INT(get_word(_hex) & 0x3FFFFFF)

    def ToHex(self):
        return _w1(48, self.value.value)


class MAKE_RUMBLE(BaseCommand):
    command_name = "Make Rumble"
    command_size = 8
    length: DataType.UNSIGNED_INT
    rumble_id: DataType.UNSIGNED_INT

    def __init__(self, _hex):
        super().__init__(_hex)
        w = get_word(_hex)
        self.length = DataType.UNSIGNED_INT((w >> 13) & 0x1FFF)
        self.rumble_id = DataType.UNSIGNED_INT(w & 0x1FFF)

    def ToHex(self):
        w = (49 << 26) | (self.length.value << 13) | (self.rumble_id.value & 0x1FFF)
        return f'{w:08X}'


class STOP_RUMBLE(BaseCommand):
    command_name = "Stop Rumble"
    command_size = 8

    def ToHex(self):
        return _w1(50)


class SWORD_TRAIL(BaseCommand):
    command_name = "Sword Trail"
    command_size = 8
    command: DataType.SWORD_TRAIL

    def __init__(self, _hex):
        super().__init__(_hex)
        self.command = DataType.SWORD_TRAIL(get_hex(_hex, 1, 3))

    def ToHex(self):
        return self._hex[0:2] + f'{self.command.value:06X}'


# ── Remix-specific commands ───────────────────────────────────────────────────

class SET_FRAME_SPEED_MULTIPLIER(BaseCommand):
    command_name = "Set Frame Speed Multiplier (Remix)"
    command_size = 8
    speed_flag: DataType.UNSIGNED_INT
    fsm: DataType.FLOAT32

    def __init__(self, _hex: str):
        super().__init__(_hex)
        self.speed_flag = DataType.UNSIGNED_INT(bytes.fromhex(_hex[2:4]))
        # Read 2 big-endian bytes, pad with 2 zero bytes to form a 4-byte float
        fsm_bytes = bytes.fromhex(_hex[4:8]) + b'\x00\x00'
        self.fsm = DataType.FLOAT32(fsm_bytes)

    def ToHex(self):
        sf_hex = f"{self.speed_flag.GetValue():02X}"
        # Store only the 2 most significant bytes of the float
        fsm_hex = self.fsm.ToBytes()[:2].hex().upper()
        return self._hex[0:2] + sf_hex + fsm_hex


class _HitboxMultiplier(BaseCommand):
    """Base for DD/DE: DDXYZZZZ — X=apply_all bool, Y=hitbox_id (0–3), ZZZZ=upper float bytes."""
    command_size = 8
    apply_all: DataType.UNSIGNED_INT
    hitbox_id: DataType.UNSIGNED_INT
    multiplier: DataType.FLOAT32

    def __init__(self, _hex: str):
        super().__init__(_hex)
        xy = int(_hex[2:4], 16)
        self.apply_all = DataType.UNSIGNED_INT((xy >> 4) & 0xF)
        self.hitbox_id = DataType.UNSIGNED_INT(xy & 0xF)
        self.multiplier = DataType.FLOAT32(bytes.fromhex(_hex[4:8]) + b'\x00\x00')

    def ToHex(self):
        xy = ((self.apply_all.value & 0xF) << 4) | (self.hitbox_id.value & 0xF)
        mult_hex = self.multiplier.ToBytes()[:2].hex().upper()
        return self._hex[0:2] + f'{xy:02X}' + mult_hex


class SET_HITBOX_HITLAG_MULT(_HitboxMultiplier):
    command_name = "Set Hitbox Hitlag Multiplier (Remix)"


class SET_HITBOX_DI_MULT(_HitboxMultiplier):
    command_name = "Set Hitbox DI Multiplier (Remix)"


class _REMIX_STUB(BaseCommand):
    """Unimplemented Remix command — round-trips raw bytes."""
    command_size = 8


class SET_ARMOR(_REMIX_STUB):
    command_name = "Set Armor (Remix)"


class OVERRIDE_HITBOX_DIRECTION(_REMIX_STUB):
    command_name = "Override Hitbox Direction (Remix)"


class TOPJOINT_TRANSLATION_MULTI(_REMIX_STUB):
    command_name = "Topjoint Translation Multi (Remix)"


class SET_Y_VEL(_REMIX_STUB):
    command_name = "Set Y Velocity (Remix)"


class FAST_FALL(_REMIX_STUB):
    command_name = "Fast Fall (Remix)"


class RANDOM_SFX(_REMIX_STUB):
    command_name = "Random SFX (Remix)"


class SET_KINETIC_STATE(_REMIX_STUB):
    command_name = "Set Kinetic State (Remix)"


class SET_HITBOX_FGM(_REMIX_STUB):
    command_name = "Set Hitbox FGM (Remix)"


class SET_ENV_COLOR(_REMIX_STUB):
    command_name = "Set Env Color (Remix)"


class SWITCH_DIRECTION(_REMIX_STUB):
    command_name = "Switch Direction (Remix)"


class GO_TO_MOVESET_FILE(_REMIX_STUB):
    command_name = "Go To Moveset File (Remix)"


class L_VOICE_SFX(_REMIX_STUB):
    command_name = "L Voice SFX (Remix)"


# ── Unknown ───────────────────────────────────────────────────────────────────

class UNKNOWN(BaseCommand):
    command_name = "???"
    command_size = 8


# ── Lookup tables ─────────────────────────────────────────────────────────────

# Vanilla opcode → command class (opcode = first_byte >> 2, range 0–51).
# One entry per opcode value; the parser uses (first_byte >> 2) as the key.
_VANILLA: dict = {
    0:  MOVESET_END,
    1:  WAIT,
    2:  AFTER,
    3:  HITBOX,              # MakeAttackColl
    4:  HITBOX,              # MakeAttackCollScaled (same layout)
    5:  CLEAR_HITBOX,
    6:  END_HITBOX,
    7:  SET_HITBOX_OFFSET,
    8:  SET_HITBOX_DAMAGE,
    9:  SET_HITBOX_SIZE,
    10: SET_HITBOX_SOUND_LEVEL,
    11: REVIVE_HITBOX,
    12: THROW_DATA,
    13: THROW_SUBROUTINE,
    14: PLAY_SFX,
    15: PLAY_LOOP_SFX,
    16: STOP_LOOP_SFX,
    17: VOICE_SFX,
    18: PLAY_LOOP_VOICE,
    19: PLAY_FGM_STORE,
    20: SMASH_VOICE,
    21: SET_FLAG0,
    22: SET_FLAG1,
    23: SET_FLAG2,
    24: SET_FLAG3,
    25: SET_AIR_JUMP_ADD,
    26: SET_AIR_JUMP_MAX,
    27: SET_ALL_HURTBOX_STATE,
    28: SET_SPECIFIC_HURTBOX_STATE,
    29: SET_HURTBOX_STATE,
    30: RESET_DAMAGE_COLL,
    31: SET_HURTBOX_SIZE,
    32: LOOP_START,
    33: LOOP_END,
    34: SUBROUTINE,
    35: RETURN,
    36: GOTO,
    37: PAUSE_SCRIPT,
    38: GFX,
    39: GFX_ITEM,
    40: SET_MODEL_PART,
    41: RESET_MODEL_ALL,
    42: HIDE_MODEL_ALL,
    43: SET_TEXTURE_PART,
    44: SET_COL_ANIM,
    45: RESET_COL_ANIM,
    46: SET_PARALLEL_SCRIPT,
    47: SET_SLOPE_CONTOUR_STATE,
    48: HIDE_ITEM,
    49: MAKE_RUMBLE,
    50: STOP_RUMBLE,
    51: SWORD_TRAIL,
}

# Remix commands use the full first byte as the key (opcode range 52+ in vanilla
# terms, but Remix doesn't follow the 6-bit opcode convention here).
_REMIX: dict = {
    0xD0: SET_FRAME_SPEED_MULTIPLIER,
    0xD1: SET_ARMOR,
    0xD2: OVERRIDE_HITBOX_DIRECTION,
    0xD3: TOPJOINT_TRANSLATION_MULTI,
    0xD4: SET_Y_VEL,
    0xD5: FAST_FALL,
    0xD6: RANDOM_SFX,
    0xD7: SET_KINETIC_STATE,
    0xD8: SET_HITBOX_FGM,
    0xD9: SET_ENV_COLOR,
    0xDA: SWITCH_DIRECTION,
    0xDB: GO_TO_MOVESET_FILE,
    0xDC: L_VOICE_SFX,
    0xDD: SET_HITBOX_HITLAG_MULT,
    0xDE: SET_HITBOX_DI_MULT,
}

# COMMANDS is iterated by the GUI to populate the "Add command" menu.
# Keys are the canonical first byte for each command (opcode << 2).
COMMANDS: dict = {
    f'{(opc << 2):02X}': cls
    for opc, cls in _VANILLA.items()
    if cls is not UNKNOWN and _VANILLA.get(opc - 1) is not cls  # deduplicate HITBOX
}
# Re-add HITBOX once under its canonical opcode 3 byte
COMMANDS['0C'] = HITBOX
# Add Remix commands
COMMANDS.update({f'{byte:02X}': cls for byte, cls in _REMIX.items()})


def GetCommand(code: str) -> type:
    first_byte = int(code, 16)
    opcode = first_byte >> 2
    if opcode < 52:
        return _VANILLA.get(opcode, UNKNOWN)
    return _REMIX.get(first_byte, UNKNOWN)
