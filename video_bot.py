import os
import time
import random
import requests
from dotenv import load_dotenv
from groq import Groq

# Попытка импортировать OmniVoice. Если он не установлен, будет использован gTTS.
try:
    from omnivoice import OmniVoice, VoicePreset
    OMNI_AVAILABLE = True
except ImportError:
    OMNI_AVAILABLE = False
    from gtts import gTTS

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
YUMCUT_URL = os.getenv("YUMCUT_URL", "http://localhost:3000")

def choose_topic():
    """Выбирает случайную тему для видео."""
    topics = [
        "Как инфляция в 2026 году съедает сбережения",
        "Криптовалюты: новый пузырь или будущее денег?",
        "Как эмоции мешают зарабатывать на бирже",
        "Почему богатые инвестируют, а бедные копят",
        "Что делать с деньгами во время рецессии"
    ]
    return random.choice(topics)

def generate_script(topic):
    """Генерирует сценарий для видео через Groq."""
    client = Groq(api_key=GROQ_API_KEY)
    response = client.chat.completions.create(
        model="openai/gpt-oss-120b",
        messages=[
            {"role": "system", "content": "Ты сценарист коротких финансовых видео. Напиши сценарий на 60 секунд. Пиши на русском, с хайпом в начале."},
            {"role": "user", "content": f"Тема: {topic}"}
        ],
        temperature=0.75,
        max_completion_tokens=800
    )
    script = response.choices[0].message.content
    return {"title": topic, "script": script}

def generate_voice(script):
    """Генерирует голос через OmniVoice или gTTS."""
    print("🎙️ Generating voice...")
    tts_script = script[:5000]  # Ограничиваем длину текста
    
    if OMNI_AVAILABLE:
        try:
            print("   Using OmniVoice (free, local)...")
            voice = OmniVoice(model="omnivoice-multilingual", device="cpu")
            preset = VoicePreset(language="ru", gender="male", speed=1.0)
            audio = voice.synthesize(tts_script, preset=preset, output_format="mp3")
            with open("voiceover.mp3", "wb") as f:
                f.write(audio)
            print("✅ Voice generated with OmniVoice")
            return True
        except Exception as e:
            print(f"⚠️ OmniVoice failed: {e}. Falling back to gTTS.")
    
    # Fallback на gTTS
    try:
        print("   Using gTTS (fallback)...")
        tts = gTTS(text=tts_script, lang='ru', slow=False)
        tts.save("voiceover.mp3")
        print("✅ Voice generated with gTTS")
        return True
    except Exception as e:
        print(f"❌ All TTS methods failed: {e}")
        return False

def create_video_with_yumcut(title, script):
    """Отправляет идею в YumCut через его API."""
    print("🎬 Sending to YumCut...")
    
    payload = {
        "prompt": f"{title}: {script[:300]}",
        "durationSeconds": 60,
        "languages": ["ru"],
        "captionsEnabled": True
    }
    
    try:
        # Создаем проект в YumCut
        resp = requests.post(
            f"{YUMCUT_URL}/api/user/v1/projects",
            json=payload,
            timeout=60
        )
        if resp.status_code != 200:
            print(f"❌ YumCut API error: {resp.text}")
            return False
        
        project_id = resp.json()["id"]
        print(f"✅ Project created: {project_id}")
        
        # Ждем генерации
        print("⏳ Waiting for generation...")
        for i in range(30):
            time.sleep(30)
            print(f"   ... {i+1}/30 minutes")
        
        print("✅ Video generation completed (simulated)")
        return True
    except Exception as e:
        print(f"❌ YumCut error: {e}")
        return False

def main():
    topic = choose_topic()
    print(f"📌 Topic: {topic}")
    
    script_data = generate_script(topic)
    print(f"📝 Script ready")
    
    if generate_voice(script_data["script"]):
        print("🎵 Voice file created")
    
    create_video_with_yumcut(script_data["title"], script_data["script"])

if __name__ == "__main__":
    main()
