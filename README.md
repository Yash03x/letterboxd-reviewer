# 🎬 Letterboxd Multi-Profile Analyzer

A sophisticated system for analyzing and comparing up to 4 Letterboxd user profiles using both statistical analysis and local/cloud LLM-powered insights. Now supports file uploads for easy data import!

## 🌟 Features

- **Multi-Profile Comparison**: Compare up to 4 Letterboxd profiles simultaneously
- **File Upload Support**: Upload Letterboxd export ZIP files directly in the web interface
- **Local Data Support**: Use existing local data folders
- **Advanced Statistical Analysis**: Rating patterns, genre preferences, personality profiling
- **Local LLM Support**: Ollama/LM Studio integration for privacy-focused analysis
- **OpenAI Integration**: Optional cloud-based analysis with GPT models
- **Personality Insights**: Generate detailed personality profiles from viewing data
- **Compatibility Scoring**: Multi-dimensional compatibility assessment
- **Genre Intelligence**: Keyword-based genre detection and preference analysis
- **Web Interface**: Streamlit-based dashboard for interactive analysis
- **Flexible Data Sources**: Mix uploaded files with local data

## 📁 Project Structure

- `app.py`: The Streamlit frontend application.
- `backend/`: The FastAPI backend application.
  - `main.py`: The main FastAPI application file with API endpoints.
  - `core/`: Core application logic.
    - `analyzer.py`: The main analyzer class.
    - `recommendations.py`: The recommendation engine.
    - `recommendations.json`: A list of movie recommendations.
  - `config/`: Configuration files.
    - `settings.py`: Application settings.
    - `prompts.py`: LLM prompts.
- `requirements.txt`: Project dependencies.
- `README.md`: This documentation.

## 🚀 Quick Start

This application now runs as two separate services: a FastAPI backend and a Streamlit frontend.

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Environment
Create a `.env` file in the root of the project and add your OpenAI API key if you want to use the OpenAI LLM integration:
```
OPENAI_API_KEY="your-api-key"
```

### 3. Run the Backend
Start the FastAPI backend service from the root of the project:
```bash
python3 -m uvicorn backend.main:app --reload
```
The backend will be available at `http://127.0.0.1:8000`.

### 4. Run the Frontend
In a separate terminal, start the Streamlit frontend application:
```bash
streamlit run app.py
```
This will open the application in your web browser.

### 5. Use the Application
- Open the application in your browser.
- Upload your Letterboxd ZIP files using the file uploader.
- The application will analyze the profiles and display the comparison.

## 📊 What You Get

- **Multi-Profile Comparison**: Compare rating patterns across up to 4 users
- **File Upload Support**: Easy drag-and-drop ZIP file uploads
- **Compatibility Score**: Multi-dimensional compatibility percentage (2-profile mode)
- **Personality Types**: Adventurous Critic, Enthusiastic Fan, etc.
- **Genre Preferences**: Detailed breakdown of genre tastes
- **Common Movies Analysis**: Agreements and disagreements
- **LLM Insights**: Deep psychological analysis of taste compatibility
- **Interactive Charts**: Visual comparisons and statistics

## 🔧 Configuration

**Web Interface**: No configuration needed! Upload files or select local data through the interface.

**Command Line**: Update these paths in `unified_analyzer.py`:
```python
profile1_path = "path/to/user1/letterboxd/data"
profile2_path = "path/to/user2/letterboxd/data"
```

## 🎯 Example Output

```
Multi-Profile Analysis (4 users):
- User profiles: hashtag7781, whiteknight03x, cinephile123, moviebuff456
- Combined rating patterns and preferences
- Individual personality analysis for each user

Two-Profile Compatibility:
Overall Compatibility: 82.6% 🟢
hashtag7781: Enthusiastic Fan - Finds joy in most films
whiteknight03x: Casual Viewer - Balanced approach
Common movies: 66 | Avg difference: 0.66⭐
Perfect agreements: The Dark Knight, Fight Club, Dune: Part Two
```

## 🔄 Data Sources

The system supports multiple data sources:

1. **ZIP File Upload**: Upload Letterboxd export ZIP files directly
2. **Local Folders**: Use previously extracted data folders
3. **Mixed Sources**: Combine uploaded files with local data
4. **Auto-Detection**: Automatically finds and suggests local profiles

## 📱 Web Interface Features

- **Responsive Design**: Works on desktop and mobile
- **Drag & Drop**: Easy file uploading
- **Real-time Analysis**: Live updates and progress indicators
- **Interactive Charts**: Plotly-powered visualizations
- **Multi-Profile Support**: Compare 2-4 profiles simultaneously
- **LLM Integration**: Optional AI-powered insights

## 🤖 LLM Integration

The system prioritizes local LLMs for privacy:
1. **Ollama** (localhost:11434) - Detected automatically
2. **LM Studio** (localhost:1234) - Detected automatically  
3. **OpenAI** - Fallback option with API key

## 📄 License

Free to use and modify. Built for the film community! 🎬
