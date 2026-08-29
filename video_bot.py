import os
import time
import random
import requests
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
YUMCUT_URL = os.getenv("YUMCUT_URL", "http://localhost:3000")
YUMCUT_API_KEY = os.getenv("YUMCUT_API_KEY", "test")  # Добавлено!

def choose_topic():
    topics = [
        "Как инфляция в 2026 году съедает сбережения",
        "Криптовалюты: новый пузырь или будущее денег?",
        "Как эмоции мешают зарабатывать на бирже",
        "Почему богатые инвестируют, а бедные копят",
        "Что делать с деньгами во время рецессии"
    ]
    return random.choice(topics)

def generate_script(topic):
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

def create_video_with_yumcut(title, script):
    print("🎬 Sending to YumCut...")
    
    project_data = {
        "prompt": f"{title}: {script[:300]}",
        "durationSeconds": 60,
        "languages": ["ru"],
        "captionsEnabled": True
    }
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {YUMCUT_API_KEY}"  # Добавлено!
    }
    
    try:
        resp = requests.post(
            f"{YUMCUT_URL}/api/user/v1/projects",
            json=project_data,
            headers=headers,
            timeout=60
        )
        
        if resp.status_code != 200:
            print(f"❌ YumCut API error: {resp.status_code} - {resp.text}")
            return False
        
        project_id = resp.json()["id"]
        print(f"✅ Project created: {project_id}")
        
        print("⏳ Waiting for video generation...")
        max_wait = 600
        wait_time = 0
        status = "pending"
        
        while status in ["pending", "processing"] and wait_time < max_wait:
            time.sleep(30)
            wait_time += 30
            
            status_resp = requests.get(
                f"{YUMCUT_URL}/api/user/v1/projects/{project_id}/status",
                headers=headers,
                timeout=30
            )
            
            if status_resp.status_code == 200:
                status = status_resp.json().get("status", "pending")
                print(f"   ⏳ Status: {status} ({wait_time}s)")
            else:
                print(f"   ⚠️ Status check failed")
        
        if status != "completed":
            print(f"❌ Failed. Final status: {status}")
            return False
        
        print("📥 Downloading video...")
        download_resp = requests.get(
            f"{YUMCUT_URL}/api/user/v1/projects/{project_id}/downloads/video",
            headers=headers,
            timeout=60
        )
        
        if download_resp.status_code != 200:
            print(f"❌ Failed to download: {download_resp.status_code}")
            return False
        
        os.makedirs("output", exist_ok=True)
        with open("output/video.mp4", "wb") as f:
            f.write(download_resp.content)
        
        print("✅ Video saved to output/video.mp4")
        return True
        
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to YumCut server. Is it running?")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def main():
    topic = choose_topic()
    print(f"📌 Topic: {topic}")
    
    script_data = generate_script(topic)
    print(f"📝 Script ready")
    
    create_video_with_yumcut(script_data["title"], script_data["script"])

if __name__ == "__main__":
    main()
