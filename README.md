# DistillTube

**Turn any YouTube video into a searchable knowledge base.**

Paste a URL → get an AI-generated summary, timestamped key moments, social posts, and a chat interface to ask questions about the video — all powered by the actual captions, no audio processing required.

---

## Features

- **Instant Summaries** — AI reads the full transcript and writes a clean summary
- **Key Moments** — timestamped highlights spread across the video
- **Topic Tags** — auto-extracted topics for quick context
- **Social Posts** — ready-to-post LinkedIn writeup and tweet thread
- **RAG Chat** — ask any question and get answers with clickable timestamp citations
- **Video Library** — all your processed videos saved to your account
- **Google Login** — one-click auth via Supabase

---

## Tech Stack

### Frontend
| Tool | Purpose |
|------|---------|
| Next.js 14 (App Router) | React framework |
| TypeScript | Type safety |
| Tailwind CSS | Styling |
| shadcn/ui | Component library |
| Supabase JS | Auth + DB client |

### Backend
| Tool | Purpose |
|------|---------|
| Python 3.11 | Runtime |
| FastAPI | REST API framework |
| yt-dlp | YouTube caption extraction |
| youtube-transcript-api | Fallback transcript fetcher |

### AI & Data
| Tool | Purpose |
|------|---------|
| Groq (llama-3.1-8b-instant) | LLM — summaries, social posts, chat |
| Nomic AI (nomic-embed-text-v1.5) | Text embeddings (768 dimensions) |
| Qdrant Cloud | Vector database for semantic search |
| Supabase (Postgres) | User data, video metadata, summaries |

### Deployment
| Tool | Purpose |
|------|---------|
| Vercel | Frontend hosting |
| Railway | Backend hosting |

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                    Browser (Next.js)                 │
│  Login → Paste URL → Summary → Chat with video      │
└──────────────────────┬──────────────────────────────┘
                       │ REST API (JWT auth)
┌──────────────────────▼──────────────────────────────┐
│                  FastAPI Backend                      │
│                                                      │
│  /transcript  →  yt-dlp → parse VTT → chunk →      │
│                  embed (Nomic) → upsert (Qdrant)    │
│                                                      │
│  /summary     →  Groq LLM → summary + moments +    │
│                  topics + LinkedIn + tweet           │
│                                                      │
│  /chat        →  embed question → Qdrant search →  │
│                  Groq LLM → answer + citations      │
│                                                      │
│  /videos      →  Supabase CRUD (library)            │
└──────┬───────────────┬──────────────────────────────┘
       │               │
  ┌────▼────┐    ┌─────▼─────┐    ┌──────────┐
  │ Qdrant  │    │ Supabase  │    │  Groq /  │
  │ (vecs)  │    │ (postgres)│    │  Nomic   │
  └─────────┘    └───────────┘    └──────────┘
```

### Data Flow

1. User pastes a YouTube URL
2. Backend extracts video ID and fetches captions via `yt-dlp` (iOS client headers to bypass bot detection, with `youtube-transcript-api` as fallback)
3. Captions are chunked into **45-second windows** with 2-segment overlap
4. Each chunk is embedded by **Nomic AI** and stored in **Qdrant** with `video_id` as a filter payload
5. A single **Groq** prompt generates the summary, key moments, topics, and social posts from the full transcript
6. All metadata is saved to **Supabase** (Postgres)
7. For chat, the question is embedded → top-5 Qdrant chunks retrieved → passed to Groq → answer returned with timestamp citations

---

## Project Structure

```
distilltube/
├── api/                        # FastAPI backend
│   ├── main.py                 # App entry, CORS, router registration
│   ├── config.py               # Env var loading (Pydantic Settings)
│   ├── requirements.txt
│   ├── Dockerfile
│   ├── Procfile
│   ├── routers/
│   │   ├── transcript.py       # POST /transcript, GET /transcript/{id}
│   │   ├── summary.py          # POST /summary
│   │   ├── chat.py             # POST /chat
│   │   ├── videos.py           # GET/DELETE /videos
│   │   └── health.py           # GET /health
│   ├── services/
│   │   ├── transcript.py       # yt-dlp + VTT parsing + fallback
│   │   ├── embedding.py        # Nomic AI embeddings + chunking
│   │   ├── llm_service.py      # Groq completions
│   │   ├── qdrant_service.py   # Vector DB operations
│   │   └── db_service.py       # Supabase queries
│   └── middleware/
│       └── auth.py             # Supabase JWT validation
└── ui/                         # Next.js frontend
    ├── app/
    │   ├── page.tsx            # Main single-page app
    │   └── layout.tsx          # Root layout + Vercel Analytics
    ├── components/ui/          # shadcn/ui component library
    └── lib/
        ├── supabase.ts         # Supabase browser client
        └── utils.ts            # Tailwind class utilities
```

---

## Running Locally

### Prerequisites

- Python 3.11+
- Node.js 18+
- Free accounts on: [Groq](https://console.groq.com), [Nomic AI](https://atlas.nomic.ai), [Qdrant Cloud](https://cloud.qdrant.io), [Supabase](https://supabase.com)

### 1. Clone the repo

```bash
git clone https://github.com/AliyaanZahid/DistillTube.git
cd DistillTube
```

### 2. Backend

```bash
cd api
pip install -r requirements.txt
cp .env.example .env
# Fill in your API keys (see Environment Variables below)
uvicorn main:app --reload --port 8000
```

### 3. Frontend

```bash
cd ui
npm install
# Create ui/.env.local (see Environment Variables below)
npm run dev
```

Open [http://localhost:3000](http://localhost:3000)

---

## Environment Variables

### `api/.env`

```env
GROQ_API_KEY=gsk_...
NOMIC_API_KEY=...
QDRANT_URL=https://your-cluster.gcp.cloud.qdrant.io
QDRANT_API_KEY=...
QDRANT_COLLECTION=transcripts
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_KEY=...
```

### `ui/.env.local`

```env
NEXT_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=...
NEXT_PUBLIC_API_URL=http://localhost:8000
```

| Variable | Where to get it |
|---|---|
| `GROQ_API_KEY` | [console.groq.com](https://console.groq.com) — free |
| `NOMIC_API_KEY` | [atlas.nomic.ai](https://atlas.nomic.ai) — free |
| `QDRANT_URL` + `QDRANT_API_KEY` | [cloud.qdrant.io](https://cloud.qdrant.io) — free tier |
| `SUPABASE_URL` + keys | [supabase.com](https://supabase.com) — free tier |

---

## Deployment

### Backend → Railway

1. Connect your GitHub repo to [Railway](https://railway.app)
2. Set root directory to `api/`
3. Add all env vars from `api/.env` in the Railway dashboard
4. Railway auto-detects the `Procfile` and deploys

### Frontend → Vercel

1. Connect your GitHub repo to [Vercel](https://vercel.com)
2. Set **Root Directory** to `ui/` in project settings
3. Add the `ui/.env.local` variables as Vercel environment variables
4. Set `NEXT_PUBLIC_API_URL` to your Railway backend URL

---

## Key Implementation Notes

- **Captions only** — no audio downloaded, no Whisper. Much faster and cheaper.
- **Bot detection bypass** — yt-dlp uses the iOS YouTube client (`player_client: ['ios', 'web']`) with matching iOS headers. Falls back to `youtube-transcript-api` if blocked.
- **Chunking** — 45-second windows with 2-segment overlap so no context is lost at chunk boundaries
- **Single LLM call** — summary, key moments, topics, and social posts are all generated in one Groq request to minimise latency
- **Qdrant filtering** — every vector search filters by `video_id` payload so results are scoped to the active video

---

## License

MIT
