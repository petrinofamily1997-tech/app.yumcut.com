import os
import random
import sys
import asyncio
import requests
from pathlib import Path
from dotenv import load_dotenv
from groq import Groq
import edge_tts
from moviepy.editor import ColorClip, VideoFileClip, AudioFileClip, TextClip, CompositeVideoClip, ImageClip, concatenate_videoclips

load_dotenv()

# Конфигурация
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
VIDEO_LANGUAGE = os.getenv("VIDEO_LANGUAGE", "ru")
OUTRO_IMAGE_URL = "https://app.yumcut.com/content/photo.png"

# Папки
OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def require_env():
    if not GROQ_API_KEY:
        raise RuntimeError("Missing GROQ_API_KEY")

def generate_script(topic):
    print(f"📝 Generating script for: {topic}...")
    client = Groq(api_key=GROQ_API_KEY)
    response = client.chat.completions.create(
        model="openai/gpt-oss-120b",
        messages=[
            {"role": "system", "content": "Ты сценарист Shorts. Напиши короткий, динамичный текст (до 50 секунд) на русском. Без markdown. Только текст."},
            {"role": "user", "content": f"Тема: {topic}"},
        ],
        temperature=0.7,
    )
    return (response.choices[0].message.content or "").strip()

async def generate_audio(text):
    print("🎙️ Generating voice-over...")
    output_audio = OUTPUT_DIR / "voice.mp3"
    communicate = edge_tts.Communicate(text, "ru-RU-SvetlanaNeural")
    await communicate.save(str(output_audio))
    return output_audio

def download_file(url, filename):
    path = OUTPUT_DIR / filename
    print(f"📥 Downloading {filename}...")
    try:
        with requests.get(url, stream=True, timeout=15) as r:
            r.raise_for_status()
            with open(path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
    except Exception as e:
        print(f"⚠️ Warning: Could not download {filename}: {e}")
        return None
    return path

def create_video(script_text, audio_path):
    print("🎬 Rendering video...")
    
    # 1. Работа с фоном
    audio = AudioFileClip(str(audio_path))
    
    # Пытаемся найти background.mp4 в корне репозитория
    local_bg = Path("background.mp4")
    if local_bg.exists():
        print("✅ Using local background.mp4")
        bg_video = VideoFileClip(str(local_bg)).loop(duration=audio.duration)
    else:
        print("⚠️ Local background.mp4 not found! Using fallback color background.")
        # Создаем черный фон, если видео не найдено
        bg_video = ColorClip(size=(1080, 1920), color=(0, 0, 0)).set_duration(audio.duration)
    
    bg_video = bg_video.set_audio(audio)
    
    # 2. Создаем субтитры
    # Используем метод 'caption' для автоматического переноса строк
    try:
        txt_clip = TextClip(
            script_text, 
            fontsize=60, 
            color='white', 
            font='Arial', 
            method='caption', 
            size=(bg_video.w*0.8, None)
        ).set_duration(audio.duration).set_position('center')
    except Exception as e:
        print(f"⚠️ Subtitles error: {e}. Creating video without text.")
        txt_clip = None
    
    if txt_clip:
        main_video = CompositeVideoClip([bg_video, txt_clip])
    else:
        main_video = bg_video
    
    # 3. Добавляем Outro-фото
    outro_img_path = download_file(OUTRO_IMAGE_URL, "outro.png")
    if outro_img_path and outro_img_path.exists():
        print("✅ Adding outro photo...")
        outro = ImageClip(str(outro_img_path)).set_duration(3).set_fps(24)
        # Подгоняем размер фото под размер видео
        outro = outro.resize(height=bg_video.h)
        final_video = concatenate_videoclips([main_video, outro])
    else:
        print("⚠️ Outro photo missing, skipping...")
        final_video = main_video
    
    output_path = OUTPUT_DIR / "video.mp4"
    final_video.write_videofile(str(output_path), fps=24, codec="libx264", audio_codec="aac")
    return output_path

def choose_topic():
    return random.choice([
        "Как инфляция в 2026 году съедает сбережения",
        "Криптовалюты: новый пузырь или будущее денег?",
        "Как эмоции мешают зарабатывать на бирже",
        "Почему богатые инвестируют, а бедные копят",
    ])

async def main():
    require_env()
    
    topic = choose_topic()
    script = generate_script(topic)
    audio_path = await generate_audio(script)
    create_video(script, audio_path)
    
    print("🎉 DONE! Video created at output/video.mp4")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"❌ ERROR: {e}")
        sys.exit(1)
