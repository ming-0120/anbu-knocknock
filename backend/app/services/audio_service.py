import os
import random

RECORDING_DIR = "recordings"

def get_random_recording():

    files = [
        f for f in os.listdir(RECORDING_DIR)
        if f.endswith(".wav") or f.endswith(".mp3") or f.endswith(".m4a")
    ]

    if not files:
        return None

    selected = random.choice(files)

    return f"/recordings/{selected}"