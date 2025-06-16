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

- `unified_analyzer.py` - Main analyzer with all functionality
- `streamlit_app.py` - Web interface dashboard
- `requirements.txt` - Dependencies
- `README.md` - This documentation

## 🚀 Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Prepare Data

**Option 1: Upload Files in Web Interface (Recommended)**
1. Export your Letterboxd data from Settings → Import & Export → Export Your Data
2. Keep the ZIP files - no need to extract
3. Use the web interface to upload and analyze

**Option 2: Use Local Data**
1. Export your Letterboxd data from Settings → Import & Export → Export Your Data
2. Extract ZIP files to separate folders
3. The system will auto-detect local data folders

### 3. Run Analysis

**Web Interface (Recommended):**
```bash
streamlit run streamlit_app.py
```

Then:
1. Configure 2-4 profiles using the web interface
2. Choose between uploading ZIP files or using local data
3. Load profiles and start analysis

**Command Line:**
```bash
python3 unified_analyzer.py
```

### 4. Enable LLM Analysis (Optional)

**For Local LLM (Recommended):**
- Install [Ollama](https://ollama.ai) or [LM Studio](https://lmstudio.ai)
- Start the service
- The analyzer will auto-detect and use local LLM

**For OpenAI:**
```bash
export OPENAI_API_KEY="your-api-key"
python3 unified_analyzer.py
```

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
