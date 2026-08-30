import os
import random
import sys
import asyncio
import requests
from pathlib import Path
from dotenv import load_dotenv
from groq import Groq
import edge_tts
from moviepy.editor import VideoFileClip, AudioFileClip, TextClip, CompositeVideoClip, ImageClip, concatenate_videoclips

load_dotenv()

# Конфигурация
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
VIDEO_LANGUAGE = os.getenv("VIDEO_LANGUAGE", "ru")
OUTRO_IMAGE_URL = "https://app.yumcut.com/content/photo.png"
BG_VIDEO_URL = "https://assets.mixkit.co/videos/stock/video/24044-4k-abstract-golden-particles-background.mp4" # Замени на любую ссылку на mp4

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
    with requests.get(url, stream=True) as r:
        with open(path, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
    return path

def create_video(script_text, audio_path):
    print("🎬 Rendering video...")
    
    # 1. Загружаем ресурсы
    bg_video_path = download_file(BG_VIDEO_URL, "background.mp4")
    outro_img_path = download_file(OUTRO_IMAGE_URL, "outro.png")
    
    audio = AudioFileClip(str(audio_path))
    bg_video = VideoFileClip(str(bg_video_path)).loop(duration=audio.duration)
    bg_video = bg_video.set_audio(audio)
    
    # 2. Создаем простые субтитры (весь текст по центру)
    # Для полноценных субтитров по словам нужен Whisper, здесь делаем базовый вариант
    txt_clip = TextClip(
        script_text, 
        fontsize=70, 
        color='white', 
        font='Arial-Bold', 
        method='caption', 
        size=(bg_video.w*0.8, None)
    ).set_duration(audio.duration).set_position('center')
    
    main_video = CompositeVideoClip([bg_video, txt_clip])
    
    # 3. Создаем Outro (фото в конце на 3 секунды)
    outro = ImageClip(str(outro_img_path)).set_duration(3).set_fps(24)
    
    # Склеиваем основное видео и фото
    final_video = concatenate_videoclips([main_video, outro])
    
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
