import tkinter as tk
from tkinter import filedialog
import sounddevice as sd
import soundfile as sf
import numpy as np
import threading
import os

root = tk.Tk()
root.title("🎧 Soundboard with VB-Audio & Features")
root.geometry("600x600")

NUM_SFX = 5

# audio log
audio_files = [None] * NUM_SFX
audio_data = [None] * NUM_SFX
audio_samplerates = [None] * NUM_SFX
current_positions = [0] * NUM_SFX
streams = [None] * NUM_SFX
is_playing = [False] * NUM_SFX
current_index = None
monitor_stream = None

is_looping = False

# device info for output and the input
device_list = sd.query_devices()
input_devices = [d['name'] for d in device_list if d['max_input_channels'] > 0]
output_devices = [d['name'] for d in device_list if d['max_output_channels'] > 0]

input_var = tk.StringVar()
output_var = tk.StringVar()

input_var.set(input_devices[0] if input_devices else "No Input Device")
output_var.set(output_devices[0] if output_devices else "No Output Device")

vb_input = "CABLE Output (VB-Audio Virtual Cable)"
vb_output = "CABLE Input (VB-Audio Virtual Cable)"
if vb_input in input_devices:
    input_var.set(vb_input)
if vb_output in output_devices:
    output_var.set(vb_output)

tk.Label(root, text="🎚 Pilih Output Device:").pack()
tk.OptionMenu(root, output_var, *output_devices).pack()

tk.Label(root, text="🎚 Pilih Input Device:").pack()
tk.OptionMenu(root, input_var, *input_devices).pack()

output_label = tk.Label(root, text=f"[OUTPUT] {output_var.get()}", fg="blue")
output_label.pack(pady=2)
input_label = tk.Label(root, text=f"[INPUT] {input_var.get()}", fg="green")
input_label.pack(pady=2)

def update_labels(*args):
    output_label.config(text=f"[OUTPUT] {output_var.get()}")
    input_label.config(text=f"[INPUT] {input_var.get()}")

output_var.trace_add("write", update_labels)
input_var.trace_add("write", update_labels)

file_label = tk.Label(root, text="No file loaded", font=("Arial", 12))
file_label.pack(pady=10)

duration_slider = tk.Scale(root, from_=0, to=100, orient="horizontal", length=400, label="Position")
duration_slider.pack(pady=10)

def load_file(index):
    path = filedialog.askopenfilename(filetypes=[("Audio files", "*.mp3 *.wav")])
    if path:
        data, samplerate = sf.read(path, dtype='float32', always_2d=True)
        audio_files[index] = path
        audio_data[index] = data
        audio_samplerates[index] = samplerate
        current_positions[index] = 0
        print(f"[INFO] Loaded {path} with {len(data)} samples @ {samplerate} Hz")

        file_label.config(text=os.path.basename(path))
        duration_slider.config(to=len(data))

def stop_all():
    global monitor_stream
    if monitor_stream:
        monitor_stream.stop()
        monitor_stream.close()
        monitor_stream = None

    for i in range(NUM_SFX):
        is_playing[i] = False
        if streams[i]:
            streams[i].stop()
            streams[i].close()
            streams[i] = None

def play_audio(index):
    global streams, current_index, monitor_stream
    if not isinstance(audio_data[index], np.ndarray):
        return

    out_device_index = next((i for i, d in enumerate(device_list) if d['name'] == output_var.get()), None)
    monitor_index = None
    preferred_keywords = ["speaker", "realtek", "headphones", "output", "microsoft sound mapper"]
    monitor_index = next(
        (
            i for i, d in enumerate(device_list)
            if d['max_output_channels'] > 0 and
            any(keyword in d['name'].lower() for keyword in preferred_keywords)
        ),
        None
    )
    print(f"[Monitor] Menggunakan device: {device_list[monitor_index]['name']} (index {monitor_index})")

    def callback(outdata, frames, time, status):
        nonlocal index
        if not is_playing[index]:
            raise sd.CallbackStop
        chunk = audio_data[index][current_positions[index]:current_positions[index] + frames]
        if len(chunk) < frames:
            if is_looping:
                current_positions[index] = 0
                chunk = audio_data[index][0:frames]
            else:
                chunk = np.pad(chunk, ((0, frames - len(chunk)), (0, 0)), mode='constant')
                is_playing[index] = False
        outdata[:] = chunk
        current_positions[index] += frames
        duration_slider.set(current_positions[index])

    is_playing[index] = True
    current_index = index

    if monitor_stream:
        monitor_stream.stop()
        monitor_stream.close()
        monitor_stream = None

    streams[index] = sd.OutputStream(
        device=out_device_index,
        channels=audio_data[index].shape[1],
        samplerate=audio_samplerates[index],
        callback=callback
    )
    streams[index].start()
    monitor_pos = current_positions[index]

    if monitor_index is not None:
        def monitor_callback(outdata, frames, time, status):
            nonlocal monitor_pos
            chunk = audio_data[index][monitor_pos:monitor_pos + frames]
            if len(chunk) < frames:
                if is_looping:
                    monitor_pos = 0
                    chunk = audio_data[index][0:frames]
                else:
                    chunk = np.pad(chunk, ((0, frames - len(chunk)), (0, 0)), mode='constant')
            outdata[:] = chunk
            monitor_pos += frames

        if monitor_stream:
            monitor_stream.stop()
            monitor_stream.close()

        monitor_stream = sd.OutputStream(
            device=monitor_index,
            channels=audio_data[index].shape[1],
            samplerate=audio_samplerates[index],
            callback=monitor_callback
        )
        monitor_stream.start()

def play(index):
    stop_all()
    duration_slider.set(0)
    duration_slider.config(to=len(audio_data[index]) if audio_data[index] is not None else 100)
    file_label.config(text=os.path.basename(audio_files[index]) if audio_files[index] else "No file loaded")
    threading.Thread(target=play_audio, args=(index,)).start()

def on_slider_release(event):
    global current_index
    if current_index is not None:
        current_positions[current_index] = duration_slider.get()

def toggle_loop():
    global is_looping
    is_looping = not is_looping
    loop_button.config(text=f"Looper: {'ON' if is_looping else 'OFF'}")

# /sfxf
for i in range(NUM_SFX):
    frame = tk.Frame(root)
    frame.pack(pady=5)
    tk.Button(frame, text="📂 Load", command=lambda i=i: load_file(i)).pack(side="left", padx=5)
    tk.Button(frame, text=f"▶️ Play SFX {i+1}", command=lambda i=i: play(i)).pack(side="left", padx=5)

duration_slider.bind("<ButtonRelease-1>", on_slider_release)

tk.Button(root, text="🛑 Stop All", bg="red", fg="white", command=lambda: threading.Thread(target=stop_all).start()).pack(pady=10)
loop_button = tk.Button(root, text="Looper: OFF", command=toggle_loop)
loop_button.pack(pady=5)

root.mainloop()
