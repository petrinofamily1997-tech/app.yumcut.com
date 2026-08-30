import json
import os
import random
import sys
import time
import uuid
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
YUMCUT_BASE_URL = os.getenv("YUMCUT_BASE_URL", "https://app.yumcut.com").rstrip("/")
YUMCUT_API_KEY = os.getenv("YUMCUT_API_KEY")
VIDEO_DURATION_SECONDS = int(os.getenv("VIDEO_DURATION_SECONDS", "60"))
VIDEO_LANGUAGE = os.getenv("VIDEO_LANGUAGE", "ru")

TIMEOUT = 60
POLL_SECONDS = 20
MAX_WAIT_SECONDS = 20 * 60


def require_env():
    # Проверяем, не запущен ли скрипт в режиме проверки API
    is_check_mode = "--check" in sys.argv
    
    missing = []
    # Groq не нужен, если мы только проверяем связь с YumCut
    if not is_check_mode and not GROQ_API_KEY:
        missing.append("GROQ_API_KEY")
    if not YUMCUT_API_KEY:
        missing.append("YUMCUT_API_KEY")
        
    if missing:
        raise RuntimeError("Missing environment variables: " + ", ".join(missing))

    if not YUMCUT_API_KEY.startswith("ycu_"):
        raise RuntimeError(
            "YUMCUT_API_KEY is not a YumCut User API key. "
            "Create one in Account -> API keys. YumCut keys start with ycu_."
        )


def headers():
    return {
        "Authorization": f"Bearer {YUMCUT_API_KEY}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


def print_api_error(resp, action):
    print(f"❌ YumCut {action}: HTTP {resp.status_code}")
    try:
        print(json.dumps(resp.json(), ensure_ascii=False, indent=2)[:10000])
    except Exception:
        print(resp.text[:10000])


def extract(obj: Any, keys: set[str]):
    """Recursively find a value while tolerating harmless response-shape changes."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k.lower() in keys and v not in (None, ""):
                return v
        for v in obj.values():
            found = extract(v, keys)
            if found not in (None, ""):
                return found
    elif isinstance(obj, list):
        for v in obj:
            found = extract(v, keys)
            if found not in (None, ""):
                return found
    return None


def api_get(path):
    resp = requests.get(
        f"{YUMCUT_BASE_URL}{path}",
        headers=headers(),
        timeout=TIMEOUT,
    )
    return resp


def check_api():
    require_env()
    print(f"🔎 Checking YumCut: {YUMCUT_BASE_URL}")

    resp = api_get("/api/user/v1/account")
    if resp.status_code != 200:
        print_api_error(resp, "account check failed")
        sys.exit(1)

    data = resp.json()
    print("✅ YumCut API authentication works.")
    print(f"   Account: {data.get('email') or data.get('name') or data.get('id')}")
    print(f"   Token balance: {data.get('tokenBalance')}")


def choose_topic():
    return random.choice([
        "Как инфляция в 2026 году съедает сбережения",
        "Криптовалюты: новый пузырь или будущее денег?",
        "Как эмоции мешают зарабатывать на бирже",
        "Почему богатые инвестируют, а бедные копят",
        "Что делать с деньгами во время рецессии",
        "Почему деньги теряют покупательную способность",
        "Как работает сложный процент и почему время важнее большой зарплаты",
        "Какие финансовые ошибки люди совершают после получения первой крупной суммы",
    ])


def generate_script(topic):
    client = Groq(api_key=GROQ_API_KEY)

    response = client.chat.completions.create(
        model="openai/gpt-oss-120b",
        messages=[
            {
                "role": "system",
                "content": (
                    "Ты сценарист коротких финансовых видео. "
                    "Напиши динамичный сценарий примерно на 60 секунд на русском языке. "
                    "Начни с сильного hook. Структура: hook -> объяснение -> пример -> вывод. "
                    "Не обещай доходность и не давай персональных инвестиционных рекомендаций. "
                    "Возвращай только готовый текст сценария без markdown и комментариев."
                ),
            },
            {"role": "user", "content": f"Тема: {topic}"},
        ],
        temperature=0.75,
        max_completion_tokens=900,
    )

    script = (response.choices[0].message.content or "").strip()
    if not script:
        raise RuntimeError("Groq returned an empty script.")

    return script


def build_project_payload(title, script):
    return {
        "prompt": title,
        "rawScript": script,
        "durationSeconds": VIDEO_DURATION_SECONDS,
        "languages": [VIDEO_LANGUAGE],
        "projectExperience": "story",
        "includeDefaultMusic": True,
        "captionsEnabled": True,
        "watermarkEnabled": False,
        "outroImage": "https://app.yumcut.com/content/photo.png", # Добавлено фото в конец
    }


def create_project(title, script):
    payload = build_project_payload(title, script)
    idem = f"github-actions-{uuid.uuid4()}"

    print("🎬 Creating YumCut project...")

    resp = requests.post(
        f"{YUMCUT_BASE_URL}/api/user/v1/projects",
        headers={
            **headers(),
            "Idempotency-Key": idem,
        },
        json=payload,
        timeout=TIMEOUT,
    )

    if resp.status_code not in (200, 201):
        print_api_error(resp, "project creation failed")
        resp.raise_for_status()

    data = resp.json()
    project_id = extract(data, {"id", "projectid", "project_id"})

    if not project_id:
        print(json.dumps(data, ensure_ascii=False, indent=2)[:10000])
        raise RuntimeError("YumCut did not return a project ID.")

    print(f"✅ Project created: {project_id}")
    return str(project_id)


def get_status(project_id):
    resp = api_get(f"/api/user/v1/projects/{project_id}/status")

    if resp.status_code != 200:
        print_api_error(resp, "status request failed")
        resp.raise_for_status()

    data = resp.json()
    status = extract(data, {"status", "projectstatus", "project_status"})

    if not status:
        raise RuntimeError(
            "No status in YumCut response:\n"
            + json.dumps(data, ensure_ascii=False)[:10000]
        )

    return str(status).lower(), data


def wait_for_completion(project_id):
    print("⏳ Waiting for video generation...")

    started = time.monotonic()
    last_status = None

    success = {"completed", "complete", "done", "success", "succeeded", "finished"}
    failure = {"failed", "failure", "error", "cancelled", "canceled", "stopped"}

    while time.monotonic() - started < MAX_WAIT_SECONDS:
        status, data = get_status(project_id)

        if status != last_status:
            print(f"   Status: {status}")
            last_status = status

        if status in success:
            print("✅ Video generation completed.")
            return

        if status in failure:
            print(json.dumps(data, ensure_ascii=False, indent=2)[:10000])
            raise RuntimeError(f"YumCut generation failed: {status}")

        time.sleep(POLL_SECONDS)

    raise TimeoutError("YumCut generation exceeded 20 minutes.")


def get_download_url(project_id):
    resp = api_get(f"/api/user/v1/projects/{project_id}/downloads/video")

    if resp.status_code != 200:
        print_api_error(resp, "video download URL request failed")
        resp.raise_for_status()

    data = resp.json()

    url = extract(
        data,
        {
            "url",
            "downloadurl",
            "download_url",
            "videourl",
            "video_url",
            "mediaurl",
            "media_url",
        },
    )

    if not url or not isinstance(url, str) or not url.startswith(("http://", "https://")):
        print(json.dumps(data, ensure_ascii=False, indent=2)[:10000])
        raise RuntimeError("Could not find a video download URL in YumCut response.")

    return url


def download_video(project_id, url):
    out = Path("output/video.mp4")
    out.parent.mkdir(parents=True, exist_ok=True)

    print("📥 Downloading final MP4...")

    with requests.get(url, stream=True, timeout=TIMEOUT, allow_redirects=True) as resp:
        if resp.status_code != 200:
            print_api_error(resp, "media download failed")
            resp.raise_for_status()

        with out.open("wb") as f:
            for chunk in resp.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    f.write(chunk)

    if not out.exists() or out.stat().st_size == 0:
        raise RuntimeError("Downloaded video file is empty.")

    print(f"✅ Saved: {out} ({out.stat().st_size / 1024 / 1024:.2f} MB)")


def main():
    if "--check" in sys.argv:
        check_api()
        return

    require_env()
    check_api()

    topic = choose_topic()
    print(f"📌 Topic: {topic}")

    script = generate_script(topic)
    print("📝 Script generated.")
    print(f"   Characters: {len(script)}")

    project_id = create_project(topic, script)
    wait_for_completion(project_id)

    download_url = get_download_url(project_id)
    download_video(project_id, download_url)

    print("🎉 DONE")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n❌ Interrupted.")
        sys.exit(130)
    except Exception as exc:
        print(f"\n❌ ERROR: {exc}")
        sys.exit(1)
