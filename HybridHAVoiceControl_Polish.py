import os
import sys
import json
import time
import pyaudio
import numpy as np
from google.cloud import speech
from vosk import Model, KaldiRecognizer

# List of synonyms for the wake word
WakeWords = ["sara", "sarah"]

# Google Speech-to-Text client configuration
google_client = speech.SpeechClient()

# PyAudio settings
RATE = 16000
CHUNK = int(RATE / 10)  # 100ms

# Initialize PyAudio
audio = pyaudio.PyAudio()

# Initialize Vosk model
vosk_model_path = "models/vosk-model-small-pl-0.22"
if not os.path.exists(vosk_model_path):
    print(f"Model '{vosk_model_path}' was not found. Please check the path.")
    exit(1)
vosk_model = Model(vosk_model_path)

# Command table
commands = {
    (("włącz", "załącz"), ("światło",)): "homeassistant/switch/1/on",
    (("wyłącz", "odłącz"), ("światło",)): "homeassistant/switch/1/off",
    (("włącz", "załącz"), ("światło",), ("kuchnia","kuchni",)): "homeassistant/switch/2/on",
    (("wyłącz", "odłącz"), ("światło",), ("kuchnia","kuchni",)): "homeassistant/switch/2/off",
    (("włącz", "załącz"), ("światło",), ("sypialnia","sypialni",)): "homeassistant/switch/3/on",
    (("wyłącz", "odłącz"), ("światło",), ("sypialnia","sypialni",)): "homeassistant/switch/3/off",
    (("podgłośnij", "zwiększ", "podnieś"), ("głośność",), ("telewizor", "telewizora")): "homeassistant/TV/1/volup",
    (("ścisz", "zmniejsz", "obniż"), ("głośność",), ("telewizor", "telewizora")): "homeassistant/TV/1/voldown",
    (("podgłośnij", "zwiększ", "podnieś"), ("głośność",), ("telewizor", "telewizora"), ("sypialnia",)): "homeassistant/TV/2/volup",
    (("ścisz", "zmniejsz", "obniż"), ("głośność",), ("telewizor", "telewizora"), ("sypialnia",)): "homeassistant/TV/2/voldown",
    (("włącz", "załącz"), ("telewizor", "telewizora")): "homeassistant/TV/1/on",
    (("wyłącz", "odłącz"), ("telewizor", "telewizora")): "homeassistant/TV/1/off",
    (("włącz", "załącz"), ("telewizor", "telewizor"), ("sypialnia","sypialni",)): "homeassistant/TV/2/on",
    (("wyłącz", "odłącz"), ("telewizor", "telewizor"), ("sypialnia","sypialni",)): "homeassistant/TV/2/off",
    (("włącz", "załącz"), ("klimatyzator", "klime")): "homeassistant/climate/1/on",
    (("wyłącz", "odłącz"), ("klimatyzator", "klime")): "homeassistant/climate/1/off",
    (("podnieś", "zwiększ"), ("temperature",)): "homeassistant/climate/1/tempup",
    (("obniż", "zmniejsz"), ("temperature",)): "homeassistant/climate/1/tempdown",
    (("otwórz",), ("drzwi", "drzwi frontowe")): "homeassistant/lock/1/unlock",
    (("zamknij",), ("drzwi", "drzwi frontowe")): "homeassistant/lock/1/lock",
}

def send_to_ha(topic, message, user="<user>", password="<your password>"):
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
    
def process_google_response(transcript):
    # Assume 'transcript' is a single string of the spoken command
    topic = match_command(transcript)
    if topic:
        send_to_ha(topic, "Command executed")

def google_listen_print_loop(responses):
    for response in responses:
        if not response.results:
            continue

        result = response.results[0]

        if result.is_final:
            transcript = result.alternatives[0].transcript.lower()
            print(f'\ronline: {transcript}          ')
            process_google_response(transcript)
            print("\nCzekam na WakeWord... ")
            vosk_listen_for_wake_word()
        else:
            interim_transcript = result.alternatives[0].transcript.lower()
            print(f'\ronline: {interim_transcript}          ', end='', flush=True)

def vosk_listen_for_wake_word():
    recognizer = KaldiRecognizer(vosk_model, RATE)
    stream = audio.open(format=pyaudio.paInt16, channels=1, rate=RATE, input=True, frames_per_buffer=CHUNK)
    
    while True:
        data = stream.read(CHUNK)
        if recognizer.AcceptWaveform(data):
            result_json = json.loads(recognizer.Result())
            text = result_json.get('text', '').lower()
            print(f'\roffline: {text} ')
            if any(wake_word in text.split() for wake_word in WakeWords):
                print("\nWakeword wykryte. Powiedz komendę... ")
                google_listen_for_command()
                break
        else:
            partial_json = json.loads(recognizer.PartialResult())
            partial = partial_json.get('partial', '').lower()
            sys.stdout.write(f'\roffline: {partial}          ')
            sys.stdout.flush()

def google_listen_for_command():
    stream = audio.open(format=pyaudio.paInt16, channels=1, rate=RATE, input=True, frames_per_buffer=CHUNK)
    requests = (speech.StreamingRecognizeRequest(audio_content=content)
                for content in iter(lambda: stream.read(CHUNK), b''))
    
    config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
        sample_rate_hertz=RATE,
        language_code="pl-PL",
    )
    streaming_config = speech.StreamingRecognitionConfig(
        config=config,
        interim_results=True
    )

    responses = google_client.streaming_recognize(config=streaming_config, requests=requests)
    google_listen_print_loop(responses)

os.system('clear')
print("\nCzekam na WakeWord... ")

vosk_listen_for_wake_word()
