import os
import random
import sys
import asyncio
import requests
import json
from pathlib import Path
from dotenv import load_dotenv
from groq import Groq
import edge_tts
from moviepy.editor import VideoFileClip, AudioFileClip, TextClip, CompositeVideoClip, ImageClip, concatenate_videoclips, ColorClip

load_dotenv()

# Конфигурация
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")
VIDEO_LANGUAGE = os.getenv("VIDEO_LANGUAGE", "ru")
OUTRO_IMAGE_URL = "https://app.yumcut.com/content/photo.png"

# Папки
OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def require_env():
    if not GROQ_API_KEY or not PEXELS_API_KEY:
        raise RuntimeError("Missing GROQ_API_KEY or PEXELS_API_KEY in secrets")

def generate_smart_script(topic):
    print(f"🧠 Planning video for: {topic}...")
    client = Groq(api_key=GROQ_API_KEY)
    
    prompt = (
        "Ты профессиональный монтажер Reels/Shorts. Создай сценарий для видео на тему: " + topic + ". "
        "Верни ответ СТРОГО в формате JSON списка. Каждый элемент списка - это сцена. "
        "Формат: [{\"text\": \"текст для озвучки\", \"keyword\": \"keyword for pexels video search in english\"}, ...]. "
        "Сделай 5-7 сцен. Текст должен быть динамичным, финансовым. "
        "Только JSON, без комментариев и markdown."
    )

    response = client.chat.completions.create(
        model="openai/gpt-oss-120b",
        messages=[{"role": "system", "content": prompt}],
        temperature=0.7,
        response_format={"type": "json_object"} # Требуем JSON
    )
    
    res_content = response.choices[0].message.content
    # Если Groq обернул JSON в объект { "scenes": [...] }, извлекаем список
    data = json.loads(res_content)
    if isinstance(data, dict):
        for key in data:
            if isinstance(data[key], list):
                return data[key]
    return data

async def generate_audio(text):
    print("🎙️ Generating male finance voice-over...")
    output_audio = OUTPUT_DIR / "voice.mp3"
    # la-RU-DmitryNeural - глубокий мужской голос
    communicate = edge_tts.Communicate(text, "ru-RU-DmitryNeural")
    await communicate.save(str(output_audio))
    return output_audio

def get_pexels_video(keyword):
    print(f"🔍 Searching Pexels for: {keyword}...")
    url = f"https://api.pexels.com/videos/search?query={keyword}&per_page=1&orientation=portrait"
    headers = {"Authorization": PEXELS_API_KEY}
    
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        data = resp.json()
        if data.get("videos"):
            video_url = data["videos"][0]["video_files"][0]["link"]
            filename = f"clip_{random.randint(1000,9999)}.mp4"
            path = OUTPUT_DIR / filename
            with requests.get(video_url, stream=True) as r:
                with open(path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
            return path
    except Exception as e:
        print(f"⚠️ Pexels error for {keyword}: {e}")
    return None

def create_smart_video(scenes, audio_path):
    print("🎬 Starting smart montage...")
    full_audio = AudioFileClip(str(audio_path))
    total_duration = full_audio.duration
    
    # Рассчитываем длительность одной сцены
    scene_duration = total_duration / len(scenes)
    clips = []
    
    for i, scene in enumerate(scenes):
        text = scene.get("text", "")
        keyword = scene.get("keyword", "finance")
        
        # 1. Получаем видео для сцены
        video_path = get_pexels_video(keyword)
        if video_path:
            clip = VideoFileClip(str(video_path)).loop(duration=scene_duration).resize(height=1920)
        else:
            clip = ColorClip(size=(1080, 1920), color=(0,0,0)).set_duration(scene_duration)
        
        # 2. Добавляем динамический текст (субтитры)
        try:
            txt = TextClip(
                text, 
                fontsize=70, 
                color='white', 
                font='Arial-Bold', 
                method='caption', 
                size=(1080*0.8, None),
                stroke_color='black', 
                stroke_width=2
            ).set_duration(scene_duration).set_position('center')
            clip = CompositeVideoClip([clip.set_position("center"), txt])
        except:
            print(f"⚠️ TextClip error in scene {i}")

        clips.append(clip)

    # Склеиваем все сцены
    main_video = concatenate_videoclips(clips, method="compose")
    main_video = main_video.set_audio(full_audio)
    
    # 3. Добавляем Outro-фото
    print("🖼️ Adding outro photo...")
    outro_img_path = OUTPUT_DIR / "outro.png"
    try:
        with requests.get(OUTRO_IMAGE_URL) as r:
            with open(outro_img_path, 'wb') as f:
                f.write(r.content)
        outro = ImageClip(str(outro_img_path)).set_duration(3).set_fps(24).resize(height=1920)
        final_video = concatenate_videoclips([main_video, outro], method="compose")
    except:
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
    scenes = generate_smart_script(topic)
    
    # Собираем весь текст для озвучки в одну строку
    full_text = " ".join([s["text"] for s in scenes])
    audio_path = await generate_audio(full_text)
    
    create_smart_video(scenes, audio_path)
    print("🎉 DONE! Smart video created at output/video.mp4")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"❌ ERROR: {e}")
        sys.exit(1)
