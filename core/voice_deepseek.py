"""
ALFA / DEEPSEEK VOICE DAEMON v1.0
Pętla głosowa: Mikrofon → Rozpoznawanie → DeepSeek → TTS
Zero UI. Tylko terminal i głos.
"""

import speech_recognition as sr
import pyttsx3
from core.api_deepseek import deepseek_query, CFG

# TTS engine
engine = pyttsx3.init()
engine.setProperty("rate", 160)

# Speech recognizer
recognizer = sr.Recognizer()


def speak(text: str):
    """Mówi tekst przez TTS."""
    print(f"[ALFA]: {text}")
    engine.say(text)
    engine.runAndWait()


def listen() -> str:
    """Słucha mikrofonu i zwraca rozpoznany tekst."""
    with sr.Microphone() as source:
        recognizer.adjust_for_ambient_noise(source, duration=0.5)
        print("[🎤] Słucham...")
        audio = recognizer.listen(source, timeout=10, phrase_time_limit=15)
    
    text = recognizer.recognize_google(audio, language="pl-PL")
    return text.strip()


def voice_loop():
    """
    Główna pętla głosowa.
    Powiedz 'koniec' lub 'stop' aby zakończyć.
    """
    print("=" * 50)
    print("ALFA / DEEPSEEK VOICE DAEMON v1.0")
    print("Powiedz 'koniec' lub 'stop' aby zakończyć.")
    print("=" * 50)

    speak("System ALFA gotowy. Słucham.")

    while True:
        try:
            user_text = listen()
            print(f"[Ty]: {user_text}")

            # Exit commands
            if user_text.lower() in ("koniec", "stop", "zakończ", "wyjdź"):
                speak("Zamykam system. Do zobaczenia, Królu.")
                break

            # Query DeepSeek
            response = deepseek_query(
                prompt=user_text,
                system_prompt="Jesteś systemem ALFA. Odpowiadaj krótko, konkretnie, po polsku."
            )

            speak(response)

        except sr.WaitTimeoutError:
            print("[INFO] Cisza... czekam dalej.")
        except sr.UnknownValueError:
            print("[INFO] Nie zrozumiałem. Powtórz.")
        except KeyboardInterrupt:
            speak("Przerwano. Zamykam.")
            break
        except Exception as e:
            print(f"[BŁĄD] {e}")
            speak("Wystąpił błąd. Spróbuj ponownie.")


if __name__ == "__main__":
    if not CFG.get("voice_mode", True):
        print("[WARN] voice_mode wyłączony w configu. Uruchamiam mimo to.")
    voice_loop()
