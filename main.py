# main.py
#
# Raspberry Pi Pico + PN532 (I2C) + DFPlayer Mini (UART)
# NFC tag UID -> MP3 track number

from machine import Pin, I2C, UART
import time

from pn532_i2c import PN532_I2C
from adafruit_pn532 import MIFARE_CMD_AUTH_A  # imported to ensure module is loaded


# ========= CONFIGURATION =========

# I2C for PN532
I2C_ID = 0
PN532_SDA_PIN = 0   # GP0 -> PN532 SDA
PN532_SCL_PIN = 1   # GP1 -> PN532 SCL

# UART for DFPlayer Mini
UART_ID = 1
DFPLAYER_TX_PIN = 4  # Pico TX -> DFPlayer RX
DFPLAYER_RX_PIN = 5  # Pico RX <- DFPlayer TX (optional, can stay unconnected)

# DFPlayer volume (0..30)
DEFAULT_VOLUME = 20

# Map NFC tag UID (hex string) -> track number on SD card
# Fill this with your real UIDs after testing.
TAG_TO_TRACK = {
    # "YOUR_TAG_UID_HEX" : track_number,
    # Example:
    # "04AABBCCDD11": 1,
    # "04332211FF55": 2,
}


# ========= DFPLAYER MINI DRIVER (very small) =========

class DFPlayerMini:
    """
    Minimal DFPlayer Mini driver using UART.
    Only implements: reset, set_volume, play_track.
    """

    def __init__(self, uart):
        self.uart = uart

    def _send_command(self, cmd, param=0):
        """
        Send a 10-byte DFPlayer command frame.
        Frame structure:
        0: 0x7E  start
        1: 0xFF  version
        2: 0x06  data length
        3: cmd
        4: 0x00  no feedback
        5: param high byte
        6: param low byte
        7: checksum high byte
        8: checksum low byte
        9: 0xEF  end
        """
        version = 0xFF
        length = 0x06
        feedback = 0x00
        high = (param >> 8) & 0xFF
        low = param & 0xFF

        checksum = 0xFFFF - (version + length + cmd + feedback + high + low) + 1
        cs_high = (checksum >> 8) & 0xFF
        cs_low = checksum & 0xFF

        frame = bytes([
            0x7E,
            version,
            length,
            cmd,
            feedback,
            high,
            low,
            cs_high,
            cs_low,
            0xEF,
        ])
        self.uart.write(frame)

    def reset(self):
        # Command 0x0C: Reset module
        self._send_command(0x0C, 0)
        time.sleep(1.5)

    def set_volume(self, level):
        # Clamp volume between 0 and 30
        if level < 0:
            level = 0
        if level > 30:
            level = 30
        # Command 0x06: Set volume
        self._send_command(0x06, level)
        time.sleep(0.1)

    def play_track(self, track_number):
        """
        Play track in root folder, addressed by global index (1..2999).
        (Files named like 001_xxx.mp3, 002_xxx.mp3, ...)
        Command 0x03: Play track.
        """
        if track_number < 1:
            track_number = 1
        self._send_command(0x03, track_number)
        # No delay needed, DFPlayer starts playing asynchronously


# ========= PN532 + DFPLAYER INITIALIZATION =========

def init_pn532():
    print("Initializing PN532 over I2C...")

    i2c = I2C(
        I2C_ID,
        scl=Pin(PN532_SCL_PIN),
        sda=Pin(PN532_SDA_PIN),
        freq=400000,
    )

    pn532 = PN532_I2C(i2c, debug=False)

    # Read firmware version just to check communication
    fw = pn532.firmware_version
    if fw is None:
        raise RuntimeError("Could not detect PN532. Check wiring and I2C mode switch.")
    ic, ver, rev, support = fw
    print("PN532 detected, IC: 0x%02X, Ver: %d.%d, Support: 0x%02X" % (ic, ver, rev, support))

    # Configure PN532 as reader
    pn532.SAM_configuration()
    print("PN532 SAM configuration done.")
    return pn532


def init_dfplayer():
    print("Initializing DFPlayer Mini over UART...")

    uart = UART(
        UART_ID,
        baudrate=9600,
        bits=8,
        parity=None,
        stop=1,
        tx=Pin(DFPLAYER_TX_PIN),
        rx=Pin(DFPLAYER_RX_PIN),
    )

    player = DFPlayerMini(uart)
    time.sleep(1.0)  # allow DFPlayer to boot

    player.reset()
    player.set_volume(DEFAULT_VOLUME)
    print("DFPlayer ready at volume", DEFAULT_VOLUME)
    return player


# ========= MAIN LOOP =========

def uid_bytes_to_hex(uid_bytes):
    """Convert PN532 UID (bytes / bytearray) to upper-case hex string."""
    return "".join("{:02X}".format(b) for b in uid_bytes)


def main():
    pn532 = init_pn532()
    dfplayer = init_dfplayer()

    last_uid = None  # To avoid retrigger while tag stays on reader

    print("Waiting for NFC tags...")

    while True:
        # timeout in seconds; 0.5 keeps loop responsive
        uid = pn532.read_passive_target(timeout=0.5)

        if uid is None:
            # No card present; allow next card to trigger when it appears
            if last_uid is not None:
                print("Tag removed.")
                last_uid = None
            continue

        # Same card still present? Ignore to avoid repeated triggers.
        if last_uid is not None and uid == last_uid:
            continue

        # New card detected
        last_uid = bytes(uid)  # make stable copy
        uid_str = uid_bytes_to_hex(uid)
        print("Tag detected, UID =", uid_str)

        track = TAG_TO_TRACK.get(uid_str)
        if track is None:
            print("No track mapped for this UID yet. Add it to TAG_TO_TRACK.")
        else:
            print("Playing track", track)
            dfplayer.play_track(track)

        # Small debounce delay
        time.sleep(0.3)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("Fatal error:", e)

