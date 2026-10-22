# EMSync — In-Board Electromagnetic Covert Channel

This repository contains the Python source codes used in the EMSync EM covert channel attack. For full technical details, please refer to the paper:

M. A. E. Bahi, M. M. Real, E. Nogues and M. Pelcat, "EMSync: An In-Board EM Covert Channel Attack that Circumvents EMC Protection," 2026 International Symposium on Electromagnetic Compatibility – EMC Europe, Prague, Czech Republic, 2026, pp. 1-6, doi: 10.1109/EMCEurope65281.2026.11733118.


**EMSync** is a research implementation of an in-board EM covert channel between logically and physically isolated processes running on the same computer system.

The project implements both sides of the communication channel:

- **Transmitter (Tx):** encodes binary data by controlling filesystem synchronization activity through repeated `write()` and `fsync()` operations.
- **Receiver (Rx):** analyzes an audio recording, extracts spectral power in the target frequency range, and reconstructs the transmitted binary sequence.

This repository contains the implementation used to experiment with the EMSync communication mechanism described in the associated research work.

> **Research / educational use only.**  
> This repository is intended for authorized security research, experimentation, and academic purposes. Do not use it to access, interfere with, or communicate through systems without authorization.


# Overview

EMSync demonstrates how controlled filesystem synchronization activity can be used to generate measurable EM emissions that can potentially serve as a covert communication channel.

The transmitter generates controlled I/O activity using a multithreaded C program. Each worker repeatedly writes a fixed-size buffer to a temporary file and calls `fsync()`.

The Python transmitter controls when this activity occurs according to a predefined binary sequence.

The receiver operates on a recorded WAV signal. It divides the recording into symbol-length segments, performs frequency-domain analysis using the Fast Fourier Transform (FFT), measures the signal power in a selected frequency range, and decides whether each segment represents a binary `0` or `1`.

The recovered binary sequence is then compared with the reference sequence and the **Bit Error Rate (BER)** is calculated.

---

# System Architecture

The communication chain can be summarized as:

```
                         EMSync Communication Channel

 ┌─────────────────────┐
 │     Binary Data     │
 │                     │
 └──────────┬──────────┘
            │
                  ▼
 ┌─────────────────────┐
 │                     │
 │                     │
 │                     │
 │  Bit 1 → I/O load   │
 │  Bit 0 → No I/O     │
 └──────────┬──────────┘
            │
                  ▼
 ┌─────────────────────┐
 │      stress-io      │
 │                     │
 │ write() + fsync()   │
 │ Multiple Threads    │
 └──────────┬──────────┘
            │
                  ▼
           EM
        Emissions
            │
                  ▼
 ┌─────────────────────┐
 │   Audio / ADC       │
 │      Recording      │
 └──────────┬──────────┘
            │
                  ▼
 ┌─────────────────────┐
 │                     │
 │                     │
 │ WAV → RMS → FFT     │
 │ → Frequency Power   │
 │ → Threshold         │
 │ → Binary Sequence   │
 └──────────┬──────────┘
            │
                  ▼
 ┌─────────────────────┐
 │    BER Analysis     │
 │                     │
 │ Received vs. Ref.   │
 └─────────────────────┘

```


---

# Transmitter

The transmitter consists of two components:

1. `Tx.py` — controls the binary transmission timing.
2. `stress-io.c` — generates the controlled filesystem activity.

## Tx.py

`Tx.py` contains the binary transmission pattern and controls the timing of each symbol.

The main configuration includes:

```python
program_path = "~/Desktop/EMSync/stress-io"
start_time_str = "2025-11-03 15:58:00"
binary_pattern = "..."
min_duration_seconds = 12.5
```

The Python program waits until the configured start time and then processes the binary pattern sequentially.

For each bit:

- **Bit `1`:** `stress-io` is executed.
- **Bit `0`:** the stressor is not executed.
- Each bit occupies at least **12.5 seconds**.

The transmitter invokes the compiled executable through Python's `subprocess` functionality.

---

## stress-io.c

`stress-io.c` is the C-based I/O stressor.

It uses multiple POSIX threads. Each worker thread:

1. Creates a temporary file.
2. Opens the file for writing.
3. Initializes a **16,384-byte** buffer.
4. Fills the buffer with the character `}`.
5. Repeatedly writes the buffer to the file.
6. Calls `fsync()` after each write.
7. Waits briefly between iterations.
8. Closes and removes the temporary file.

Conceptually:

```text
Worker Thread
     │
     ▼
Create temporary file
     │
     ▼
Write 16,384-byte buffer
     │
     ▼
     fsync()
     │
     ▼
Short delay
     │
     ▼
Repeat
```

The default transmitter configuration uses:

| Parameter | Value |
|---|---:|
| Number of threads | 2 |
| Iterations per thread | 2500 |
| Buffer size | 16,384 bytes |
| Delay between operations | 100 µs |
| Symbol duration | 12.5 s |

The number of threads and iterations can be supplied as command-line parameters to the C program.


---

# Running the Transmitter

The current version of `Tx.py` contains a machine-specific path and a fixed historical start time. These values should be changed before running the code on another machine.

After compiling the stressor, configure `Tx.py` with the correct path to the executable.

For example:

```python
program_path = "~/Desktop/EMSync/stress-io"
```

Then run:

```bash
python3 Tx.py
```

The transmitter waits until the configured start time.

---

# Receiver

The receiver is implemented in:

```text
receiver/Rx.py
```

The receiver processes a WAV recording containing the captured signal.

Its main tasks are:

1. Load the audio.
2. Calculate windowed RMS power.
3. Smooth the power signal.
4. Divide the recording into transmission segments.
5. Apply a Hanning window.
6. Calculate the FFT.
7. Extract power in the selected frequency range.
8. Apply a threshold to determine each bit.
9. Compare the received sequence with the reference sequence.
10. Calculate BER.
11. Generate diagnostic plots.

---

# Rx.py

The receiver loads the WAV file using `librosa`.


The receiver configuration is:

```python
window_ms=50
hop_ms=25
max_duration_minutes=30
smooth_seconds=1
first_line_time=30
vertical_line_interval=12.5
num_lines=129
```

Thus, the example uses:

| Parameter | Value |
|---|---:|
| RMS window | 50 ms |
| RMS hop | 25 ms |
| Maximum recording duration | 30 min |
| Smoothing window | 1 s |
| First transmission boundary | 30 s |
| Symbol interval | 12.5 s |
| Number of boundaries | 129 |

---

# Receiver Processing Pipeline

## 1. Load the WAV recording

The receiver loads the recorded audio and reports:

- Audio duration
- Sample rate
- Number of samples

If the recording is longer than the configured maximum duration, only the initial portion is loaded.

---

## 2. Windowed RMS analysis

The receiver calculates RMS energy using:

```text
Window = 50 ms
Hop    = 25 ms
```

The resulting RMS values are converted into decibels:

```text
Power(dB) = 20 × log10(RMS + ε)
```

where a small value is added to avoid taking the logarithm of zero.

---

## 3. Smoothing

The receiver optionally applies a moving average to the RMS power signal.

The example uses:

```text
Smoothing = 1 second
```

This is primarily useful for visualizing the overall power evolution of the recording.

---

## 4. Symbol segmentation

Transmission boundaries are generated starting at:

```text
30 seconds
```

and separated by:

```text
12.5 seconds
```

For example:

```text
30.0 s
42.5 s
55.0 s
67.5 s
80.0 s
...
```

Each interval corresponds to one transmitted symbol.

---

## 5. FFT processing

For every segment, the receiver applies a Hanning window before calculating the FFT.

The FFT provides the frequency-domain representation of the captured signal.

Only positive frequencies are retained and converted to kHz.

---

## 6. Frequency-band power

The receiver calculates the total spectral power in:

```text
17–20 kHz
```

The magnitude spectrum is squared to obtain a quantity proportional to power.

The resulting power is converted to dB.

---

## 7. Binary decision

The receiver uses:

```text
Threshold = -82 dB
```

The decision rule is:

```text
Power < -82 dB  →  0
Power ≥ -82 dB  →  1
```

Therefore:

```text
                    ┌── Power < -82 dB ──→ Bit 0
Segment → Power ────┤
                    └── Power ≥ -82 dB ──→ Bit 1
```

---

# Running the Receiver

Place the WAV recording in the expected location, for example:

```text
receiver/
└── t_data/
    └── f2.wav
```

Then run:

```bash
python3 Rx.py
```

Alternatively, modify:

```python
wav_file_path = "t_data/f2.wav"
```

to point to the desired recording.

---

# Receiver Output

The receiver produces two main visualizations.

## Plot 1 — Windowed RMS Power

The first plot shows the RMS power of the recording over time.

It includes:

- Raw RMS power
- Smoothed RMS power
- Vertical symbol boundaries

This provides a time-domain view of the captured signal.

---

## Plot 2 — Frequency-Band Power and BER

The second plot displays the calculated power for every transmission segment in the 17–25 kHz frequency range.

It also displays:

- The −82 dB threshold.
- The detected binary value.
- Comparison against the reference sequence.
- BER information.

Segments are visually distinguished according to whether their decoded bit matches the reference bit.

---

# Binary Encoding

The current implementation uses the following reference binary pattern:

```text
1010110100110100110100101110101000100110011110001111010100011010110010110100111011110011010011000011011010001110
```

The same reference pattern is currently embedded in both the transmitter and receiver.

The receiver uses this pattern to evaluate the accuracy of the recovered sequence.

### Transmission principle

The transmitter maps the binary sequence onto the presence or absence of I/O activity:

```text
Reference bit
     │
     ├── 0 ──→ No stress-io execution
     │
     └── 1 ──→ stress-io execution
```

The receiver performs the inverse operation:

```text
Captured segment
       │
       ▼
17–25 kHz power
       │
       ▼
Compare with -82 dB
       │
       ├── Below threshold ──→ 0
       │
       └── Above threshold ──→ 1
```

---

# BER Analysis

The receiver compares the recovered binary sequence against the reference pattern.

For each bit:

```text
Reference bit == Received bit
        │
        ├── Yes → Correct
        │
        └── No  → Error
```

The Bit Error Rate is calculated as:

```text
BER = Number of bit errors / Number of transmitted bits
```

The receiver also reports the positions of incorrect bits.

For example:

```text
Errors: 0 out of 128 bits
BER: 0.000 (0.0%)
Error positions: None
```

The exact result depends on the recording and experimental conditions.



---

# Dependencies

## Transmitter

The transmitter requires:

- Linux/Unix-like environment
- GCC
- POSIX threads
- Python 3

The C program is compiled with:

```bash
gcc -O2 -pthread stress-io.c -o stress-io
```

---

## Receiver

The Python receiver imports:

```python
librosa
matplotlib
numpy
scipy
```

Install the Python dependencies with:

```bash
pip install librosa matplotlib numpy scipy
```

Depending on the Python environment and operating system, additional audio-related dependencies may be required by `librosa`.

A virtual environment is recommended:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install librosa matplotlib numpy scipy
```

---

# Important Configuration Notes

## 1. Executable name

The transmitter executable is:

```text
stress-io
```

not:

```text
stress-io-ff
```

Make sure all scripts and documentation use the updated name.

---

## 2. Executable path

The current `Tx.py` contains a machine-specific path.

Before running it on another computer, update:

```python
program_path
```

to the location of the locally compiled `stress-io` executable.

---

## 3. Start time

The transmitter currently contains a fixed start time.

This value must be changed for a new experiment.

---

## 4. Reference binary pattern

The binary pattern is currently hard-coded.

The transmitter and receiver should use the same reference pattern when performing BER analysis.

If the transmitted pattern is changed, update both sides consistently.

---

## 5. Timing synchronization

The transmitter and receiver rely on the timing relationship between the transmission and recording.

The receiver currently assumes that the first relevant symbol boundary begins at:

```text
30 seconds
```

and that symbols are separated by:

```text
12.5 seconds
```

If the recording starts at a different offset, the receiver configuration must be adjusted.

---

## 6. Detection threshold

The current receiver uses:

```text
−82 dB
```

as its decision threshold.

This threshold is part of the current experimental configuration and may need to be recalibrated for different:

- Hardware
- Recording devices
- Sampling rates
- Environmental noise
- Physical configurations

---

# Research Context

This implementation is based on the research work:

> **EMSync: An In-Board EM Covert Channel Attack That Circumvents EMC Protection**

The work investigates an in-board electromagnetic covert channel between logically and physically isolated processes.

The research demonstrates a transmitter based on controlled filesystem synchronization operations and a receiver based on electromagnetic leakage captured through a general-purpose ADC/audio chipset.

The paper reports a Linux desktop implementation and evaluates the channel under different experimental conditions.

According to the research, the demonstrated implementation achieved a raw bit rate of approximately **0.08 bit/s** with a reported **0% BER** for the demonstrated 128-bit AES-key transmission experiment.

For the exact experimental methodology, platform configuration, measurements, and results, refer to the associated paper.



---

# Disclaimer

This project is provided for **academic research, education, and authorized security experimentation**.

The authors and contributors are not responsible for misuse of this software.

Do not deploy, test, or operate the transmitter or receiver against systems, networks, devices, or environments for which you do not have explicit authorization.
