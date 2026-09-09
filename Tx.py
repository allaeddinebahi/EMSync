import subprocess
import os
from datetime import datetime
import time

# Settings
program_path = "~/Desktop/EMSync/stress-io"
start_time_str = "2025-11-03 15:58:00"
binary_pattern = "1010110100110100110100101110101000100110011110001111010100011010110010110100111011110011010011000011011010001110"

min_duration_seconds = 12.5  # Minimum duration per bit position

# Wait until start time
start_time = datetime.strptime(start_time_str, "%Y-%m-%d %H:%M:%S")
print(f"Waiting until {start_time} to start launches based on pattern: {binary_pattern}...")

while datetime.now() < start_time:
    time_remaining = (start_time - datetime.now()).total_seconds()
    print(f"Time remaining: {time_remaining:.1f} seconds", end='\r')
    time.sleep(0.1)

# Process binary pattern
print(f"\nStarting launches based on pattern: {binary_pattern}...")

for i, bit in enumerate(binary_pattern):
    position_start_time = datetime.now()
    print(f"\nProcessing bit {i+1}/{len(binary_pattern)} (Bit={bit}) at {position_start_time.strftime('%H:%M:%S')}...")
    
    bit_start_time = time.time()
    
    if bit == '1':
        print(f"🚀 Launching program...")
        subprocess.run([os.path.expanduser(program_path)])
        print(f"✅ Program completed")
    else:
        print(f"⏭️  Skipping launch (Bit=0)")
    
    # Calculate elapsed time and wait remaining time to reach minimum duration
    elapsed_time = time.time() - bit_start_time
    remaining_wait = max(0, min_duration_seconds - elapsed_time)
    
    if remaining_wait > 0:
        print(f"⏳ Waiting {remaining_wait:.2f} seconds to complete {min_duration_seconds}s duration...")
        time.sleep(remaining_wait)
    
    total_duration = time.time() - bit_start_time
    print(f"✅ Bit {i+1} processing completed in {total_duration:.2f} seconds")

print(f"\n🎉 All {len(binary_pattern)} pattern positions processed!")
