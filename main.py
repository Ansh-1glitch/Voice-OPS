import speech_recognition as sr
import pyttsx3
import os
import shutil
import time

# Initialize text-to-speech engine
engine = pyttsx3.init()

def speak(text):
    """Speak the given text aloud"""
    engine.say(text)
    engine.runAndWait()

def listen_command():
    """Listen to user's voice and convert it to text"""
    r = sr.Recognizer()
    with sr.Microphone() as source:
        print("🎤 Listening...")
        r.pause_threshold = 1
        audio = r.listen(source)
    try:
        print("🧠 Recognizing...")
        command = r.recognize_google(audio, language='en-in')
        print(f"🗣️ You said: {command}")
        return command.lower()
    except sr.UnknownValueError:
        speak("Sorry, I could not understand that.")
        return ""
    except sr.RequestError:
        speak("Network error in recognition.")
        return ""

def upload_file(source_path, dest_path):
    """Move file from source to destination"""
    if not os.path.exists(source_path):
        speak("File not found. Please check the path.")
        print(f"❌ File not found: {source_path}")
        return
    try:
        if not os.path.exists(dest_path):
            os.makedirs(dest_path)
        shutil.move(source_path, dest_path)
        speak("File uploaded successfully.")
        print(f"✅ Moved {source_path} → {dest_path}")
    except Exception as e:
        speak("Error while uploading the file.")
        print(f"❌ Error: {e}")

def main():
    speak("Hello, I am Echo. How can I help you today?")
    time.sleep(1)
    
    while True:
        speak("Please say a command: upload or exit.")
        command = listen_command()

        if "upload" in command:
            speak("Please say the full file path to upload.")
            source = listen_command().strip()
            speak("Please say the destination folder path.")
            destination = listen_command().strip()
            upload_file(source, destination)

        elif "exit" in command or "quit" in command:
            speak("Goodbye! See you soon.")
            break

        elif command != "":
            speak("Command not recognized. Please say upload or exit.")

if __name__ == "__main__":
    main()
