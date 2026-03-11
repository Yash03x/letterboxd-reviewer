# 🎬 Letterboxd Reviewer Pro

A modern, full-stack application for analyzing and tracking Letterboxd profiles with real-time data synchronization, advanced analytics, and a cinema-inspired UI.

## ✨ Features

### 🎯 Core Functionality
- **Profile Management**: Add, update, and manage multiple Letterboxd profiles
- **Real-time Scraping**: Background data collection with progress tracking
- **Advanced Analytics**: Comprehensive statistics and insights
- **Data Persistence**: SQLite database with proper relationships
- **Export & Backup**: Data export and backup capabilities

### 🎨 User Experience  
- **Cinema-themed UI**: Glassmorphism design with film-inspired aesthetics
- **Smooth Animations**: Framer Motion for fluid transitions and micro-interactions
- **Responsive Design**: Mobile-first approach with TailwindCSS
- **Real-time Updates**: Manual refresh with optimistic UI updates
- **Interactive Charts**: Chart.js visualizations for data insights

### 🔧 Technical Stack
- **Backend**: FastAPI with async support and background tasks
- **Frontend**: React 18 with TypeScript and React Query
- **Database**: SQLAlchemy ORM with SQLite
- **Styling**: TailwindCSS with custom cinema theme
- **Charts**: Chart.js with react-chartjs-2
- **Animations**: Framer Motion for advanced animations

## 🚀 Quick Start

### Prerequisites
- Python 3.9+
- Node.js 18+
- npm or yarn

### 🎬 Option 1: Automated Setup (Recommended)

```bash
# Clone the repository
git clone <repository-url>
cd letterboxd-reviewer

# Run the setup script
./scripts/setup.sh

# Start both servers
./scripts/start-all.sh
```

### 🛠️ Option 2: Manual Setup

#### Backend Setup
```bash
# Navigate to backend
cd backend

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r ../requirements.txt

# Create data directories
mkdir -p ../data/{scraped,exports,backups}

# Start the server
python3 -m uvicorn main:app --reload --port 8000
```

#### Frontend Setup
```bash
# Navigate to frontend (new terminal)
cd frontend

# Install dependencies
npm install

# Start development server
npm start
```

## 📁 Project Structure

```
letterboxd-reviewer/
├── 📁 backend/                 # FastAPI backend application
│   ├── 📁 config/             # Configuration files
│   ├── 📁 core/               # Core analysis logic
│   ├── 📁 database/           # Database models & repositories
│   ├── main.py                # FastAPI application entry point
│   └── scraper.py             # Web scraping functionality
├── 📁 frontend/               # React frontend application
│   ├── 📁 public/             # Static assets
│   ├── 📁 src/
│   │   ├── 📁 components/     # Reusable React components
│   │   ├── 📁 pages/          # Application pages
│   │   └── 📁 services/       # API integration
│   ├── package.json
│   └── tailwind.config.js     # TailwindCSS configuration
├── 📁 data/                   # Application data
│   ├── 📁 scraped/           # Scraped profile data
│   ├── 📁 exports/           # Exported data files
│   └── 📁 backups/           # Database backups
├── 📁 scripts/               # Automation scripts
│   ├── setup.sh             # Project setup
│   ├── start-all.sh         # Start both servers
│   ├── start-backend.sh     # Start backend only
│   └── start-frontend.sh    # Start frontend only
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

### Scraping
- `POST /scrape/profile/{username}` - Start scraping
- `GET /scrape/status/{username}` - Check scraping status
- `DELETE /profiles/{username}/data` - Clear scraped data

### Analytics
- `GET /analytics/dashboard` - System-wide statistics
- `GET /profiles/suggestions/update` - Profiles needing updates

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
DATABASE_URL=sqlite:///./data/letterboxd_analyzer.db
API_HOST=localhost
API_PORT=8000
FRONTEND_URL=http://localhost:3000
```

## 🚀 Deployment

### Docker (Coming Soon)
```bash
# Build and start with Docker Compose
docker-compose up --build
```

### Manual Deployment
1. Set up a production database (PostgreSQL recommended)
2. Configure environment variables
3. Build the frontend: `npm run build`
4. Deploy with a production WSGI server (Gunicorn + Nginx)

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