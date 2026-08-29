# YumCut GitHub Actions Bot

This version does NOT pull `igorshadurin/yumcut` from Docker and does NOT start a local YumCut server.

It uses YumCut's User API directly. This is intentional: the repository's current API exposes project creation, status polling and final video download through `/api/user/v1/...`.

## GitHub Secrets

Open:

Settings -> Secrets and variables -> Actions -> New repository secret

Create exactly these 3 secrets:

1. `GROQ_API_KEY`
2. `YUMCUT_API_KEY`
3. `YUMCUT_BASE_URL`

For the hosted YumCut service:

`YUMCUT_BASE_URL=https://app.yumcut.com`

Create the YumCut key in:

Account -> API keys

The key must start with:

`ycu_`

The key needs read/write access because the workflow creates projects and reads their status/media.

## What happens

Every 5 hours (and manually through Actions -> YumCut Video Bot -> Run workflow):

1. GitHub starts Ubuntu.
2. Python 3.11 is installed.
3. The bot authenticates against YumCut.
4. Groq generates a Russian financial script.
5. The bot creates a YumCut `story` project.
6. YumCut generates the voice, visuals, captions and final video.
7. The bot polls the project status.
8. When finished, it obtains the signed video URL.
9. The MP4 is downloaded to `output/video.mp4`.
10. GitHub uploads it as an artifact.

## Important

Do not put `ycu_...` or `gsk_...` keys into committed files.

The old workflow used:

`DATABASE_URL=file:./dev.db`

and attempted to start YumCut locally. That is not appropriate for the current YumCut architecture. The current project documentation uses MySQL/Prisma and a separate storage/daemon architecture.

The workflow here deliberately avoids that whole self-hosting stack and uses the official User API instead.
