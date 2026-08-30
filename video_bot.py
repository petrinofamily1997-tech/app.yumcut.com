import os
import random
import sys
import asyncio
import requests
import json
import whisper
import subprocess
from pathlib import Path
from dotenv import load_dotenv
from groq import Groq
import edge_tts
from moviepy.editor import VideoFileClip, AudioFileClip, TextClip, CompositeVideoClip, ImageClip, concatenate_videoclips, ColorClip

load_dotenv()

# Конфигурация
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")
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
        "Ты профессиональный монтажер Reels. Создай сценарий для видео на тему: " + topic + ". "
        "Верни ответ СТРОГО в формате JSON списка: [{\"text\": \"текст для озвучки\", \"keyword\": \"keyword in english\"}, ...]. "
        "Сделай 5-7 динамичных сцен. Только JSON."
    )
    response = client.chat.completions.create(
        model="openai/gpt-oss-120b",
        messages=[{"role": "system", "content": prompt}],
        temperature=0.7,
        response_format={"type": "json_object"}
    )
    data = json.loads(response.choices[0].message.content)
    return data.get("scenes", data) if isinstance(data, dict) else data

async def generate_audio(text):
    print("🎙️ Generating voice-over in chunks...")
    final_audio_path = OUTPUT_DIR / "voice.mp3"
    
    # Разбиваем текст на предложения, чтобы сервер не сбрасывал запрос
    sentences = text.split('. ')
    temp_files = []
    
    voice = "ru-RU-DmitryNeural"
    
    try:
        for i, sentence in enumerate(sentences):
            if not sentence.strip(): continue
            
            print(f"   Processing part {i+1}/{len(sentences)}...")
            temp_file = OUTPUT_DIR / f"part_{i}.mp3"
            communicate = edge_tts.Communicate(sentence, voice)
            await communicate.save(str(temp_file))
            temp_files.append(str(temp_file))
        
        # Склеиваем все части в один файл с помощью ffmpeg
        # Создаем список файлов для ffmpeg
        list_file = OUTPUT_DIR / "list.txt"
        with open(list_file, "w") as f:
            for tf in temp_files:
                f.write(f"file '{tf}'\n")
        
        # Команда ffmpeg для склейки без перекодирования
        cmd = [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0", 
            "-i", str(list_file), "-c", "copy", str(final_audio_path)
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        # Удаляем временные файлы
        for tf in temp_files: os.remove(tf)
        if list_file.exists(): os.remove(list_file)
        
        print("✅ Audio successfully merged!")
        return final_audio_path
        
    except Exception as e:
        print(f"❌ Audio generation failed: {e}")
        # Попытка с резервным голосом, если всё упало
        print("⚠️ Trying backup voice...")
        communicate = edge_tts.Communicate(text, "ru-RU-SvetlanaNeural")
        await communicate.save(str(final_audio_path))
        return final_audio_path

def transcribe_audio(audio_path):
    print("👂 Whisper is analyzing audio for word-level timings...")
    model = whisper.load_model("tiny")
    result = model.transcribe(str(audio_path), word_timestamps=True, language="ru")
    
    words_data = []
    for segment in result['segments']:
        for word in segment['words']:
            words_data.append({
                "word": word['word'].strip(),
                "start": word['start'],
                "end": word['end']
            })
    return words_data

def get_pexels_video(keyword):
    print(f"🔍 Searching Pexels for: {keyword}...")
    url = f"https://api.pexels.com/videos/search?query={keyword}&per_page=1&orientation=portrait"
    headers = {"Authorization": PEXELS_API_KEY}
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        data = resp.json()
        if data.get("videos"):
            video_url = data["videos"][0]["video_files"][0]["link"]
            path = OUTPUT_DIR / f"clip_{random.randint(1000,9999)}.mp4"
            with requests.get(video_url, stream=True) as r:
                with open(path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192): f.write(chunk)
            return path
    except Exception as e:
        print(f"⚠️ Pexels error: {e}")
    return None

def create_pro_video(scenes, audio_path, words):
    print("🎬 Starting Professional Montage...")
    full_audio = AudioFileClip(str(audio_path))
    total_duration = full_audio.duration
    
    scene_duration = total_duration / len(scenes)
    bg_clips = []
    for scene in scenes:
        v_path = get_pexels_video(scene.get("keyword", "finance"))
        if v_path:
            clip = VideoFileClip(str(v_path)).loop(duration=scene_duration).resize(height=1920)
        else:
            clip = ColorClip(size=(1080, 1920), color=(20, 20, 20)).set_duration(scene_duration)
        bg_clips.append(clip)
    
    background = concatenate_videoclips(bg_clips, method="compose").set_audio(full_audio)
    
    print("✍️ Creating dynamic subtitles...")
    subtitle_clips = []
    for w in words:
        try:
            txt = TextClip(
                w['word'].upper(), 
                fontsize=90, 
                color='yellow', 
                font='Arial-Bold', 
                stroke_color='black', 
                stroke_width=3,
                method='caption', 
                size=(1080*0.7, None)
            ).set_start(w['start']).set_end(w['end']).set_position('center')
            subtitle_clips.append(txt)
        except:
            continue

    final_main = CompositeVideoClip([background] + subtitle_clips)
    
    print("🖼️ Adding outro photo...")
    outro_img_path = OUTPUT_DIR / "outro.png"
    try:
        with requests.get(OUTRO_IMAGE_URL) as r:
            with open(outro_img_path, 'wb') as f: f.write(r.content)
        outro = ImageClip(str(outro_img_path)).set_duration(3).set_fps(24).resize(height=1920)
        final_video = concatenate_videoclips([final_main, outro], method="compose")
    except:
        final_video = final_main

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
    full_text = " ".join([s["text"] for s in scenes])
    
    audio_path = await generate_audio(full_text)
    words = transcribe_audio(audio_path)
    create_pro_video(scenes, audio_path, words)
    print("🎉 DONE! Professional video created at output/video.mp4")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"❌ ERROR: {e}")
        sys.exit(1)
