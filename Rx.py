import librosa
import matplotlib.pyplot as plt
import numpy as np
from scipy.fft import fft, fftfreq

def moving_average(x, w):
    """Simple moving average with window size w."""
    return np.convolve(x, np.ones(w)/w, mode='same')

def plot_wav_windowed_power(wav_file_path, 
                            window_ms=100, 
                            hop_ms=50, 
                            max_duration_minutes=5,
                            smooth_seconds=2,
                            first_line_time=30,
                            vertical_line_interval=12.5,
                            num_lines=6):
    """
    Plot windowed RMS power of a WAV file in dB over time (minutes), with optional moving average smoothing.
    """

    # === Reference pattern ===
    ref_binary = "10001011110010101110111100111011000100101101101000010111000110010111000001000011101000110100111001100110010010101101011011101101"

    # === Load audio ===
    full_duration = librosa.get_duration(path=wav_file_path)
    max_duration_seconds = max_duration_minutes * 60

    if full_duration > max_duration_seconds:
        y, sr = librosa.load(wav_file_path, sr=None, duration=max_duration_seconds)
        print(f"⚠️ Loaded first {max_duration_minutes} minutes of audio (file is longer).")
    else:
        y, sr = librosa.load(wav_file_path, sr=None)
        print("✅ Loaded full audio file.")

    duration = len(y) / sr
    print(f"Audio duration: {duration:.2f} seconds ({duration/60:.2f} minutes)")
    print(f"Sample rate: {sr} Hz")
    print(f"Number of samples: {len(y)}")

    # === Windowed RMS Power ===
    win_length = int(window_ms * sr / 1000)
    hop_length = int(hop_ms * sr / 1000)

    rms = librosa.feature.rms(y=y, frame_length=win_length, hop_length=hop_length)[0]
    times = librosa.frames_to_time(np.arange(len(rms)), sr=sr, hop_length=hop_length) / 60

    power_dB = 20 * np.log10(rms + 1e-10)

    # === Apply smoothing ===
    if smooth_seconds > 0:
        frames_per_second = sr / hop_length
        smooth_frames = int(smooth_seconds * frames_per_second)
        if smooth_frames > 1:
            power_DB_smooth = moving_average(power_dB, smooth_frames)
        else:
            power_DB_smooth = power_dB
    else:
        power_DB_smooth = power_dB

    # === Calculate vertical line positions ===
    vertical_line_times_seconds = []
    current_time = first_line_time
    for i in range(num_lines):
        if current_time <= duration:
            vertical_line_times_seconds.append(current_time)
        current_time += vertical_line_interval

    vertical_line_times_minutes = [t / 60 for t in vertical_line_times_seconds]

    # === Calculate FFT for each segment ===
    segments_fft = []
    segments_freqs = []
    segment_info = []
    segment_power_17_20khz = []  # Store power in 17-20 kHz region
    binary_array = []  # Store binary values
    
    for i in range(len(vertical_line_times_seconds) - 1):
        start_time = vertical_line_times_seconds[i]
        end_time = vertical_line_times_seconds[i + 1]
        
        start_sample = int(start_time * sr)
        end_sample = int(end_time * sr)
        
        segment = y[start_sample:end_sample]
        
        if len(segment) > 0:
            # Apply window function to reduce spectral leakage
            window = np.hanning(len(segment))
            segment_windowed = segment * window
            
            # Calculate FFT
            N = len(segment_windowed)
            yf = fft(segment_windowed)
            
            # Calculate correct frequencies
            xf = fftfreq(N, 1 / sr)
            
            # Take only positive frequencies and convert to kHz
            pos_freq_mask = xf >= 0
            xf_pos = xf[pos_freq_mask] / 1000  # Convert to kHz
            
            # Magnitude spectrum (normalized)
            yf_magnitude = np.abs(yf[pos_freq_mask]) / N
            # For real-valued signals, we should double the magnitude (except DC and Nyquist)
            if N > 1:
                yf_magnitude[1:-1] *= 2
            
            segments_fft.append(yf_magnitude)
            segments_freqs.append(xf_pos)
            
            # Calculate power in 17-20 kHz region
            mask_17_20 = (xf_pos >= 17) & (xf_pos <= 20)
            if np.any(mask_17_20):
                # Power is proportional to square of magnitude
                power_in_region = np.sum(yf_magnitude[mask_17_20]**2)
                power_dB_in_region = 10 * np.log10(power_in_region + 1e-10)
            else:
                power_in_region = 0
                power_dB_in_region = -np.inf
            
            # Determine binary value based on -82 dB threshold
            if power_dB_in_region < -82:
                binary_value = 0
            else:
                binary_value = 1
            
            binary_array.append(binary_value)
            
            segment_power_17_20khz.append({
                'power_dB': power_dB_in_region,
                'binary': binary_value
            })
            
            segment_info.append({
                'start': start_time,
                'end': end_time,
                'duration': end_time - start_time,
                'samples': len(segment),
                'nyquist': sr / 2 / 1000  # Nyquist frequency in kHz
            })
            

        else:
            segments_fft.append(None)
            segments_freqs.append(None)
            segment_info.append(None)
            segment_power_17_20khz.append({'power_dB': -np.inf, 'binary': 0})
            binary_array.append(0)
            print(f"Segment {i+1}: {start_time:.1f}s to {end_time:.1f}s (empty segment) → Bit: 0")

    # === Compare with reference and compute BER ===
    # Convert binary array to string for comparison
    received_binary_str = ''.join(map(str, binary_array[:len(ref_binary)]))
    
    # Calculate Bit Error Rate (BER)
    errors = 0
    error_positions = []
    
    for i, (ref_bit, rec_bit) in enumerate(zip(ref_binary, received_binary_str)):
        if ref_bit != rec_bit:
            errors += 1
            error_positions.append(i + 1)  # Segment numbers (1-based)
    
    ber = errors / len(ref_binary) if len(ref_binary) > 0 else 0

    # === Plot 1: Time domain with vertical lines ===
    plt.figure(figsize=(14, 6))
    plt.plot(times, power_dB, linewidth=0.5, color="tab:blue", alpha=0.4, label="Raw")
    plt.plot(times, power_DB_smooth, linewidth=1.5, color="tab:red", label=f"Smoothed ({smooth_seconds}s window)")
    
    for i, line_time in enumerate(vertical_line_times_minutes):
        plt.axvline(x=line_time, color='green', linestyle='--', alpha=0.7, linewidth=0.8)
    
    plt.title(f"Windowed RMS Power\n{num_lines} vertical lines starting at {first_line_time}s")
    plt.xlabel("Time (minutes)")
    plt.ylabel("Power (dB)")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.show()
   
    # === Plot 2: Power in dB scale with threshold and comparison ===
    plt.figure(figsize=(12, 6))
    
    segment_numbers = []
    power_dB_values = []
    colors = []
    
    for i, power_info in enumerate(segment_power_17_20khz):
        if power_info is not None and i < len(ref_binary):
            segment_numbers.append(i + 1)
            power_dB_values.append(power_info['power_dB'])
            # Convert reference bit to integer for comparison
            ref_bit_int = int(ref_binary[i])
            # Green for correct, Red for error
            is_correct = (power_info['binary'] == ref_bit_int)
            colors.append('green' if is_correct else 'red')
    
    plt.bar(segment_numbers, power_dB_values, color=colors, alpha=0.7, edgecolor='black')
    
    # Add threshold line
    plt.axhline(y=-82, color='blue', linestyle='--', linewidth=2, label='Threshold (-82 dB)')
    
    plt.xlabel('Segment Number')
    plt.ylabel('Power (dB)')
    plt.title(f'Power in 17-20 kHz Region with BER Analysis\nBER: {ber:.3f} ({errors}/{len(ref_binary)} errors)')
    plt.grid(True, alpha=0.3)
    plt.legend()

    # Add value labels on bars
    for i, (segment, power) in enumerate(zip(segment_numbers, power_dB_values)):
        plt.text(segment, power + (1 if power >= -82 else -1), 
                f'{power:.1f} dB', ha='center', va='bottom' if power >= -82 else 'top',
                fontweight='bold')
    
    plt.tight_layout()
    plt.show()

    # === Print comprehensive results ===
    print("\n" + "="*70)
    print("🔢 BINARY DECODING RESULTS WITH BER ANALYSIS")
    print("="*70)
    print(f"Reference pattern: {ref_binary}")
    print(f"Received pattern:  {received_binary_str}")
    print(f"Threshold: -82 dB")
    print(f"Binary string received: {received_binary_str}")
    print(f"Reference string:       {ref_binary}")
    
    print(f"\n📊 BIT ERROR RATE (BER) ANALYSIS:")
    print(f"Errors: {errors} out of {len(ref_binary)} bits")
    print(f"BER: {ber:.3f} ({ber*100:.1f}%)")
    
    if error_positions:
        print(f"Error positions: Segments {error_positions}")
    else:
        print(f"Error positions: None ✓")
    
    print("\nSegment Details:")
    print("Segment | Time Range (s) | Power (dB) | Received | Reference | Status")
    print("-" * 75)
    
    for i, (power_info, seg_info) in enumerate(zip(segment_power_17_20khz, segment_info)):
        if power_info is not None and seg_info is not None and i < len(ref_binary):
            ref_bit_int = int(ref_binary[i])
            status = "✓ MATCH" if power_info['binary'] == ref_bit_int else "✗ ERROR"
            status_color = "✓" if power_info['binary'] == ref_bit_int else "✗"
            print(f"{i+1:7d} | {seg_info['start']:5.1f}-{seg_info['end']:5.1f} | "
                  f"{power_info['power_dB']:10.2f} dB | {power_info['binary']:8d} | {ref_bit_int:8d} | {status_color} {status}")


# === Usage Example ===
if __name__ == "__main__":
    wav_file_path = "data/f2.wav"
    plot_wav_windowed_power(wav_file_path, 
                          window_ms=50, 
                          hop_ms=25, 
                          max_duration_minutes=30, 
                          smooth_seconds=1,
                          first_line_time=30,
                          vertical_line_interval=12.5,
                          num_lines=129)