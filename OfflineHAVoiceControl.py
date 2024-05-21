import os
import sys
import json
import pyaudio
from vosk import Model, KaldiRecognizer

# List of synonyms for the wake word
WakeWords = ["jarvis"]

# PyAudio settings
RATE = 16000
CHUNK = int(RATE / 10)  # 100ms

# Initialize PyAudio
audio = pyaudio.PyAudio()

# Initialize Vosk model
vosk_model_path = "models/vosk-model-small-en-us-0.15"
if not os.path.exists(vosk_model_path):
    print(f"Model '{vosk_model_path}' was not found. Please check the path.")
    exit(1)
vosk_model = Model(vosk_model_path)

# Command table
commands = {
    (("turn on", "switch on"), ("light",)): "homeassistant/switch/1/on",
    (("turn off", "switch off"), ("light",)): "homeassistant/switch/1/off",
    (("turn on", "switch on"), ("light",), ("kitchen",)): "homeassistant/switch/2/on",
    (("turn off", "switch off"), ("light",), ("kitchen",)): "homeassistant/switch/2/off",
    (("turn on", "switch on"), ("light",), ("bedroom",)): "homeassistant/switch/3/on",
    (("turn off", "switch off"), ("light",), ("bedroom",)): "homeassistant/switch/3/off",
    (("turn up", "increase", "raise"), ("volume",), ("tv", "television")): "homeassistant/TV/1/volup",
    (("turn down", "decrease", "lower"), ("volume",), ("tv", "television")): "homeassistant/TV/1/voldown",
    (("turn up", "increase", "raise"), ("volume",), ("tv", "television"), ("bedroom",)): "homeassistant/TV/2/volup",
    (("turn down", "decrease", "lower"), ("volume",), ("tv", "television"), ("bedroom",)): "homeassistant/TV/2/voldown",
    (("turn on", "switch on"), ("tv", "television")): "homeassistant/TV/1/on",
    (("turn off", "switch off"), ("tv", "television")): "homeassistant/TV/1/off",
    (("turn on", "switch on"), ("tv", "television"), ("bedroom",)): "homeassistant/TV/2/on",
    (("turn off", "switch off"), ("tv", "television"), ("bedroom",)): "homeassistant/TV/2/off",
    (("turn on", "switch on"), ("air conditioning", "ac")): "homeassistant/climate/1/on",
    (("turn off", "switch off"), ("air conditioning", "ac")): "homeassistant/climate/1/off",
    (("raise", "increase"), ("temperature",)): "homeassistant/climate/1/tempup",
    (("lower", "decrease"), ("temperature",)): "homeassistant/climate/1/tempdown",
    (("open",), ("door", "front door")): "homeassistant/lock/1/unlock",
    (("close",), ("door", "front door")): "homeassistant/lock/1/lock",
}

def send_to_ha(topic, message, user="Arczi", password="lukasek"):
    print(f'\033[92m{topic}\033[0m')  # Print topic in green color
    os.system(f'mosquitto_pub -h 192.168.1.199 -t "{topic}" -m "{message}" -u "{user}" -P "{password}"')

def match_command(spoken_command):
    best_match = None
    highest_match_count = 0

    for command_words, topic in commands.items():
        match_count = 0

        for group in command_words:
            if any(substring in spoken_command for substring in group):
                match_count += 1

        if match_count > highest_match_count:
            highest_match_count = match_count
            best_match = topic

    return best_match

def process_vosk_response(transcript, wake_word_detected):
    # Process the full transcript including the wake word
    transcript = transcript.lower().strip()
    if wake_word_detected or any(wake_word in transcript for wake_word in WakeWords):
        # Remove the wake word from the transcript
        for wake_word in WakeWords:
            transcript = transcript.replace(wake_word, '').strip()
        if transcript:  # Check if there are remaining words after the wake word
            topic = match_command(transcript)
            if topic:
                send_to_ha(topic, "Command executed")
        return True
    return False

def vosk_listen():
    recognizer = KaldiRecognizer(vosk_model, RATE)
    stream = audio.open(format=pyaudio.paInt16, channels=1, rate=RATE, input=True, frames_per_buffer=CHUNK)
    
    print("\nWaiting for WakeWord... ")
    wake_word_detected = False
    while True:
        data = stream.read(CHUNK)
        if recognizer.AcceptWaveform(data):
            result_json = json.loads(recognizer.Result())
            text = result_json.get('text', '').lower()
            print(f'\roffline: {text} ')
            if wake_word_detected:
                print("\nProcessing command... ")
                wake_word_detected = not process_vosk_response(text, wake_word_detected)
                if not wake_word_detected:
                    print("\nWaiting for WakeWord... ")
            elif any(wake_word in text.split() for wake_word in WakeWords):
                print("\nWake word detected. Speak your command... ")
                wake_word_detected = True
        else:
            partial_json = json.loads(recognizer.PartialResult())
            partial = partial_json.get('partial', '').lower()
            sys.stdout.write(f'\roffline: {partial}          ')
            sys.stdout.flush()

os.system('clear')
vosk_listen()
