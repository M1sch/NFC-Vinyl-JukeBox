# NFC Vinyl Jukebox (Raspberry Pi Pico 2 + PN532 + DFPlayer Mini)

This is a birthday present project: a small “vinyl jukebox” that plays MP3 tracks
from a DFPlayer Mini when an NFC tag is detected by a PN532 reader. NFC tags are
embedded in 3D-printed “vinyls”, and each tag UID is mapped to one track on the
microSD card.

The project targets a Raspberry Pi Pico / Pico 2 running MicroPython.

## Features

- NFC tag UID → track mapping in a single Python dictionary.
- PN532 over I²C (Elechouse PN532 V3) and DFPlayer Mini over UART.
- Simple state machine:
  - **Idle mode:** waits for a new tag, then starts playback for the mapped track.
  - **Play mode:** continuously polls the PN532; stops playback when the tag is removed.
- Optional `end_track.mp3` (e.g. vinyl crackle) that plays briefly when a tag is removed.
- Minimal DFPlayer driver (reset, volume, play, stop).
- Audio path via DFPlayer DAC outputs into a PAM8403 GF1002 amplifier module → speaker.

## Hardware

- Raspberry Pi Pico or Pico 2 (RP2040 / RP2350)
- Elechouse PN532 NFC reader (V3) configured for **I²C** mode  
- DFPlayer Mini MP3 player module (with microSD card)  
- PAM8403 GF1002 stereo amplifier breakout (2×3 W, 2.5–5 V)  
- Speaker (4–8 Ω, up to 3 W)  
- NFC tags (embedded in 3D-printed “vinyls”)
- 5 V USB power supply (e.g. 5 V / 2 A)

All modules share a **common GND**.

## Wiring (default pins)

### PN532 (I²C, Elechouse V3)

Configure the PN532’s onboard switch/jumpers for **I²C mode** (CH1=ON, CH2=OFF on the V3 board).

Connections to the Pico:

- Pico **GP2** (I²C1 SDA) → PN532 SDA  
- Pico **GP3** (I²C1 SCL) → PN532 SCL  
- Pico **GP6** (optional) → PN532 `RSTPD_N` (hardware reset)  
- Pico **3V3** → PN532 VCC  
- Pico **GND** → PN532 GND  

The PN532 supports 3.3–5 V on VCC, but 3.3 V is safer for the Pi Pico GPIO logic.

### DFPlayer Mini (UART + audio)

UART control (Pico UART1):

- Pico **GP4** (UART1 TX) → DFPlayer **RX**  
- Pico **GP5** (UART1 RX, optional) ← DFPlayer **TX**  

Power:

- Pico **VBUS** (5 V from USB) → DFPlayer **VCC**  
- Pico **GND** → DFPlayer **GND**

### Audio (DFPlayer → PAM8403 GF1002 → Speaker)

DFPlayer line out to amplifier:

- DFPlayer `DAC_L` → PAM8403 **L_IN**  
- DFPlayer `DAC_R` → PAM8403 **R_IN**  
- DFPlayer GND → PAM8403 **G** (audio/input GND)

PAM8403 power and speaker:

- PAM8403 `V+` → 5 V (same 5 V as DFPlayer, e.g. Pico VBUS)  
- PAM8403 `GND` → common GND  
- PAM8403 `L+` / `L-` → Speaker ±  

Do **not** connect any speaker terminal to GND; the PAM8403 uses a BTL output.

If you only need mono, you can use a single channel (e.g. L+ / L-).

## Software / Setup

1. Flash **MicroPython** onto the Pico (via UF2).
2. Using Thonny or another MicroPython tool, copy these files onto the Pico:
   - `main.py` – main loop, state machine, and tag→track mapping
   - `pn532_i2c.py` – PN532 I²C driver
   - `adafruit_pn532.py` – PN532 base driver
   - `digitalio.py` – small shim that emulates CircuitPython’s `digitalio` for MicroPython

   The PN532 files are based on the Adafruit PN532 library, via the
   `somervda/nfc-tester` MicroPython port.

3. Prepare the microSD card for the DFPlayer:
   - Format as **FAT16 or FAT32** (single partition).
   - Copy MP3 files into the root directory.
   - Name them with 3-digit prefixes as expected by DFPlayer commands, e.g.:

     ```text
     001.mp3
     002_my_song.mp3
     003_another_track.mp3
     ...
     099_end_track.mp3   # optional vinyl noise / end sound
     ```

4. Plug the Pico into USB, open Thonny, select `MicroPython (Raspberry Pi Pico)` and run `main.py`.

## Tag mapping

In `main.py`, map tag UIDs (hex strings) to track numbers:

```python
TAG_TO_TRACK = {
    "40CBAD25F6180": 1,  # plays 001.mp3
    "41E9DD05F6180": 2,  # plays 002.mp3
    "42CA09F4F6180": 3,  # plays 003.mp3
    # ...
}
````

To find UIDs:

1. Run `main.py` with an empty `TAG_TO_TRACK = {}`.

2. Hold each NFC “vinyl” on the PN532.

3. Watch the Thonny shell; it will print:

   ```text
   Tag detected, UID = 40CBAD25F6180
   No track mapped for this UID. Add it to TAG_TO_TRACK.
   ```

4. Copy that UID string into the `TAG_TO_TRACK` dictionary and assign a track number.

## Runtime behavior

The firmware uses a simple state machine:

* **Idle mode (no tag / “check” mode)**

  * PN532 is polled regularly via `read_passive_target(timeout=...)`.
  * When a new tag UID is detected and found in `TAG_TO_TRACK`, the corresponding track is started on the DFPlayer and the state switches to **Playing**.

* **Playing mode**

  * The PN532 continues to be polled.
  * If the reader reports **no tag** for longer than a configurable debounce time (e.g. >700 ms), the tag is considered **removed**:

    * The current track is stopped.
    * Optionally an `end_track` (e.g. `099_end_track.mp3`) is played to simulate a vinyl end noise.
    * State returns to **Idle**.

This pattern avoids constant retriggering while a tag remains on the reader and gives a natural “lift the vinyl to stop” behavior.

## Project files

* `main.py`
  Main application: pin config, PN532 + DFPlayer init, state machine, tag→track mapping.

* `pn532_i2c.py`
  PN532 I²C transport layer for MicroPython (from the `nfc-tester` project).

* `adafruit_pn532.py`
  PN532 high-level driver adapted from the Adafruit CircuitPython PN532 library.

* `digitalio.py`
  Compatibility layer that implements a subset of CircuitPython’s `digitalio` API on MicroPython.

* `songs/numbered_mp3.sh` (optional)
  Helper script to batch-rename MP3 files to 3-digit names like `001.mp3`, `002.mp3`, etc.

* `songs/`
  Example MP3 files (numbered for the DFPlayer).

## Notes / Gotchas

* **PN532 quirks**

  * Elechouse PN532 V3 boards are known to be unreliable in SPI mode on some hosts; I²C is used here and works well with the MicroPython PN532 port.
  * After I²C errors, the PN532 can hang; wiring the `RSTPD_N` pin to a Pico GPIO and doing a hardware reset in software greatly improves robustness.

* **DFPlayer Mini**

  * Expects a properly formatted FAT16/FAT32 card and 3-digit track numbers; strange filenames or multiple partitions can cause silent failures.
  * In some error states a full power-cycle of the DFPlayer is more reliable than a soft reset; future versions of this project may switch DFPlayer 5 V with a MOSFET or relay from a Pico GPIO.

* **Audio**

  * The PAM8403 GF1002 module is a 2×3 W Class-D amp that needs 2.5–5 V and can directly drive 4–8 Ω speakers.
  * Its outputs are BTL; never connect speaker terminals to GND.

## License

See `LICENSE`