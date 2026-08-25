"""Parser/writer for Remix's per-character THROWF_DATA.bin / THROWB_DATA.bin
files. These are a fixed 56-byte struct — two back-to-back FTThrowHitDesc
(src/ft/fttypes.h in the decomp), NOT a moveset command stream, so they get
their own small model instead of going through Command.py.

Confirmed against ftcommonthrown2.c: `capture_fp->throw_desc[1]` is read for
grab-release damage, proving throw_desc is an array of 2 FTThrowHitDesc —
index 0 is the full-throw hit, index 1 is what happens if the grab is
released early instead of completed.
"""

import DataType


def sx32(val: int) -> int:
    """Sign-extend a 32-bit unsigned value."""
    if val & 0x80000000:
        val -= 0x100000000
    return val


# (field name, UI label, DataType class) — order matches FTThrowHitDesc exactly.
# status_id uses ACTION_ID (FTCommonStatus, hex fallback for unrecognized IDs);
# element uses EFFECT_TYPE, the same "damage type" enum HITBOX.effect already
# uses in Command.py. Everything else is a plain signed 32-bit value.
FIELDS = [
    ("status_id",        "Action ID",            DataType.ACTION_ID),
    ("damage",            "Damage",               DataType.SIGNED_INT),
    ("angle",              "Angle",                 DataType.SIGNED_INT),
    ("knockback_scale",    "Knockback Scaling",     DataType.SIGNED_INT),
    ("knockback_weight",   "Fixed Knockback",       DataType.SIGNED_INT),
    ("knockback_base",     "Base Knockback",        DataType.SIGNED_INT),
    ("element",             "Damage Type / Effect", DataType.EFFECT_TYPE),
]


class ThrowHitDesc:
    """FTThrowHitDesc — 7 signed 32-bit words (28 bytes)."""
    SIZE = 28  # bytes

    def __init__(self, _hex: str):
        self.values = {}
        for i, (name, _label, dtype) in enumerate(FIELDS):
            word = int(_hex[i * 8:i * 8 + 8], 16)
            # EFFECT_TYPE (UNSIGNED_INT) wants the raw word, same convention
            # as HITBOX.effect in Command.py; the signed fields want it
            # properly sign-extended (e.g. status_id's -1 sentinel).
            value = word if issubclass(dtype, DataType.UNSIGNED_INT) else sx32(word)
            self.values[name] = dtype(value)

    def ToHex(self) -> str:
        return ''.join(f'{self.values[name].GetValue() & 0xFFFFFFFF:08X}' for name, _, _ in FIELDS)


class ThrowDataFile:
    """THROWF_DATA.bin / THROWB_DATA.bin — two ThrowHitDesc back-to-back:
    `thrown` (throw_desc[0]) and `grab_release` (throw_desc[1])."""
    SIZE = ThrowHitDesc.SIZE * 2  # 56 bytes

    def __init__(self, _hex: str = ""):
        _hex = _hex.upper()
        _hex = _hex + '0' * max(0, self.SIZE * 2 - len(_hex))
        self.thrown = ThrowHitDesc(_hex[:ThrowHitDesc.SIZE * 2])
        self.grab_release = ThrowHitDesc(_hex[ThrowHitDesc.SIZE * 2:ThrowHitDesc.SIZE * 4])

    def ToHex(self) -> str:
        return self.thrown.ToHex() + self.grab_release.ToHex()

    def ToBytes(self) -> bytes:
        return bytes.fromhex(self.ToHex())
