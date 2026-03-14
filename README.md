# 🎬 Spyboxd

A modern, full-stack application for analyzing and tracking Letterboxd profiles with real-time data synchronization, advanced analytics, and a cinema-inspired UI.

## ✨ Features

### 🎯 Core Functionality
- **Profile Management**: Add, update, and manage multiple Letterboxd profiles
- **Real-time Scraping**: Queue-backed scraping with progress tracking
- **Advanced Analytics**: Comprehensive statistics and insights
- **Data Persistence**: SQLAlchemy ORM with PostgreSQL-ready migrations
- **Export & Backup**: Data export and backup capabilities

### 🎨 User Experience  
- **Cinema-themed UI**: Glassmorphism design with film-inspired aesthetics
- **Smooth Animations**: Framer Motion for fluid transitions and micro-interactions
- **Responsive Design**: Mobile-first approach with TailwindCSS
- **Real-time Updates**: Manual refresh with optimistic UI updates
- **Interactive Charts**: Chart.js visualizations for data insights

### 🔧 Technical Stack
- **Backend**: FastAPI + Celery workers
- **Frontend**: Next.js App Router + React 19 + Clerk auth
- **Database**: SQLAlchemy ORM with PostgreSQL (legacy SQLite import supported)
- **Queue/Broker**: Celery + Redis
- **Styling**: TailwindCSS with custom cinema theme
- **Charts**: Chart.js with react-chartjs-2
- **Animations**: Framer Motion for advanced animations

## 🚀 Quick Start

### Prerequisites
- Python 3.9+
- Node.js 18+
- PostgreSQL 15+
- Redis 7+

### Local Development (No Scripts)

```bash
# Clone and enter project
git clone <repository-url>
cd letterboxd-reviewer

# Python env + backend deps
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Frontend deps
cd frontend
npm install
cd ..

# Env files
cp .env.example .env
cp frontend/.env.example frontend/.env.local

# Ensure Postgres + Redis are running, and database exists
createdb spyboxd

# Run migrations
.venv/bin/alembic upgrade head
```

Start the app in 3 terminals:

```bash
# Terminal 1: API
source .venv/bin/activate
cd backend
uvicorn main:app --reload --port 8000
```

```bash
# Terminal 2: Worker (solo pool is safer on macOS)
source .venv/bin/activate
cd backend
celery -A celery_app.celery_app worker --loglevel=info --pool=solo
```

```bash
# Terminal 3: Frontend
cd frontend
npm run dev
```

Open:
- Frontend: `http://localhost:3000`
- API health: `http://localhost:8000/health`

## 📁 Project Structure

```
letterboxd-reviewer/
├── 📁 backend/                 # FastAPI backend application
│   ├── 📁 config/             # Configuration files
│   ├── 📁 core/               # Core analysis logic
│   ├── 📁 database/           # Database models & repositories
│   ├── 📁 services/           # Data ingestion/scrape orchestration
│   ├── 📁 tasks/              # Celery task entrypoints
│   ├── main.py                # FastAPI application entry point
│   ├── celery_app.py          # Celery app configuration
│   └── scraper.py             # Web scraping functionality
├── 📁 frontend/               # Next.js frontend application
│   ├── 📁 public/             # Static assets
│   ├── 📁 src/
│   │   ├── 📁 components/     # Reusable React components
│   │   ├── 📁 app/            # App Router pages/layouts
│   │   └── 📁 services/       # API integration
│   ├── middleware.ts          # Clerk route protection
│   ├── package.json
│   └── tailwind.config.js     # TailwindCSS configuration
├── 📁 alembic/                # Database migrations
├── 📁 data/                   # Application data
│   ├── 📁 scraped/           # Scraped profile data
│   ├── 📁 exports/           # Exported data files
│   └── 📁 backups/           # Database backups
├── docker-compose.yml         # Local full-stack deployment
├── .env.example              # Environment variables template
├── .gitignore               # Git ignore rules
├── requirements.txt         # Python dependencies
└── README.md               # This file
```

## 🎯 Usage Guide

### 1. 🏠 Dashboard
- View system-wide statistics and metrics
- Monitor active scraping jobs
- Access quick actions for profile management
- Interactive charts for data visualization

### 2. 👥 Profile Manager
- Add new Letterboxd profiles for tracking
- Update existing profile information
- Initiate data scraping operations
- View scraping status and progress

### 3. 🔄 Data Scraping
- Background scraping with progress tracking
- Real-time status updates
- Comprehensive data collection (ratings, reviews, lists)
- Error handling and retry mechanisms

### 4. 📊 Analytics
- Rating distribution analysis
- Monthly activity trends
- Profile comparison tools
- Export functionality for further analysis

## 🔧 API Endpoints

### Profiles
- `GET /profiles/` - List all profiles
- `POST /profiles/create` - Create new profile
- `PUT /profiles/{username}` - Update profile
- `DELETE /profiles/{username}` - Delete profile
- `GET /profiles/{username}/analysis` - Get detailed analysis
- `GET /public/profile/{username}` - Public profile snapshot for share pages/OG

### Scraping
- `POST /scrape/profile/{username}` - Start scraping
- `GET /scrape/status/{username}` - Check scraping status
- `GET /scrape/progress/{job_id}/stream` - Stream live progress (SSE)
- `DELETE /profiles/{username}/data` - Clear scraped data

Note: the scraping endpoint enqueues a Celery task; make sure Redis and the worker are running locally.

### Analytics
- `GET /api/dashboard/analytics` - System-wide statistics
- `GET /profiles/suggestions/update` - Profiles needing updates

### Health
- `GET /health` - Liveness endpoint for deployment healthchecks

Most routes require a valid Clerk bearer token. Public routes are limited to `/health`, `/public/profile/{username}`, and the scrape progress stream endpoint.

## 🎨 Design System

### Color Palette
- **Cinema Orange**: Primary brand color (`#e65100`)
- **Noir Black**: Deep backgrounds (`#0f172a`)
- **Glass Effects**: Transparency with backdrop blur
- **Gradient Accents**: Dynamic color transitions

### Components
- **Glassmorphism Cards**: Modern card design with transparency
- **Animated Buttons**: Hover effects and micro-interactions
- **Interactive Charts**: Responsive data visualizations
- **Status Indicators**: Real-time status with animations

## 🔒 Environment Configuration

Create a `.env` file based on `.env.example`:

```bash
# Copy the example file
cp .env.example .env

# Edit with your configuration
DATABASE_URL=postgresql+psycopg://localhost/spyboxd
API_HOST=localhost
API_PORT=8000
FRONTEND_URL=http://localhost:3000
CORS_ALLOWED_ORIGINS=http://localhost:3000
# Optional Celery tuning (defaults to solo/1 on macOS, prefork/2 elsewhere)
# CELERY_WORKER_POOL=solo
# CELERY_WORKER_CONCURRENCY=1
# SCRAPE_STALE_JOB_MINUTES=20
# CLERK_JWKS_URL=https://your-instance.clerk.accounts.dev/.well-known/jwks.json
# CLERK_FRONTEND_API=https://your-instance.clerk.accounts.dev
```

For frontend env vars, copy `frontend/.env.example` and set:
- `NEXT_PUBLIC_API_BASE_URL` (browser API URL)
- `API_URL` (server-side API URL for Next routes)
- Clerk publishable/secret keys

### Local Postgres Workflow

1. Start PostgreSQL locally and create a `spyboxd` database.
2. Copy `.env.example` to `.env` and confirm `DATABASE_URL`.
3. Run `alembic upgrade head` from the repo root to create the schema.
4. Optional: import existing SQLite data with `python -m backend.database.migrate import-sqlite`.

Useful database commands:

```bash
# Inspect the active database target
python -m backend.database.migrate check

# Import the legacy SQLite database into Postgres
python -m backend.database.migrate import-sqlite --source ./data/letterboxd_analyzer.db
```

## 🚀 Deployment

### Docker Compose (Ready)
```bash
# Build and start all services (frontend, api, worker, postgres, redis)
docker compose up --build -d

# Tail logs
docker compose logs -f api worker frontend

# Stop
docker compose down
```

### Manual Deployment
1. Set up a production database (PostgreSQL recommended)
2. Configure backend env (`DATABASE_URL`, `REDIS_URL`, Clerk JWKS, CORS origins)
3. Run migrations: `alembic upgrade head`
4. Run API: `uvicorn main:app --host 0.0.0.0 --port 8000`
5. Run worker: `celery -A celery_app.celery_app worker --loglevel=info`
6. Build/start frontend with Next.js (`npm run build && npm run start`)

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Commit changes: `git commit -m 'Add amazing feature'`
4. Push to branch: `git push origin feature/amazing-feature`
5. Open a Pull Request

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **Letterboxd**: For the amazing platform and data
- **React Community**: For the excellent ecosystem
- **FastAPI**: For the modern Python web framework
- **TailwindCSS**: For the utility-first CSS framework

## 📬 Support

- **Issues**: Report bugs and feature requests via GitHub Issues
- **Discussions**: Join community discussions in GitHub Discussions
- **Documentation**: Check the `/docs` folder for detailed guides

---

**Made with ❤️ for film enthusiasts and data lovers**
