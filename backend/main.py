from fastapi import FastAPI, UploadFile, File, HTTPException
from core.analyzer import UnifiedLetterboxdAnalyzer
import tempfile
import zipfile
import os
import shutil

app = FastAPI()

# In-memory storage for loaded profiles.
# In a production environment, this should be replaced with a more robust solution
# like a database or a distributed cache (e.g., Redis).
profiles_data = {}
analyzer = UnifiedLetterboxdAnalyzer()

def extract_zip_file(uploaded_file, temp_dir):
    """Extract uploaded zip file to temporary directory"""
    zip_path = os.path.join(temp_dir, uploaded_file.filename)
    with open(zip_path, "wb") as f:
        f.write(uploaded_file.file.read())

    extract_dir = os.path.join(temp_dir, uploaded_file.filename.replace('.zip', ''))
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(extract_dir)

    # Find the actual data directory (might be nested)
    for root, dirs, files in os.walk(extract_dir):
        if any(f in files for f in ['ratings.csv', 'watched.csv', 'reviews.csv']):
            return root

    return extract_dir

@app.post("/profiles/")
async def upload_profile(username: str, file: UploadFile = File(...)):
    if not file.filename.endswith('.zip'):
        raise HTTPException(status_code=400, detail="Invalid file type. Please upload a ZIP file.")

    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            profile_path = extract_zip_file(file, temp_dir)
            profile = analyzer.load_profile(profile_path, username)
            profiles_data[username] = profile
            return {"message": f"Profile for {username} loaded successfully."}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to process profile: {str(e)}")

@app.get("/profiles/{username}/analysis")
async def get_analysis(username: str):
    if username not in profiles_data:
        raise HTTPException(status_code=404, detail="Profile not found.")

    profile = profiles_data[username]

    analysis = {
        "username": profile.username,
        "total_movies": profile.total_movies,
        "avg_rating": profile.avg_rating,
        "total_reviews": profile.total_reviews,
        "join_date": profile.join_date.isoformat() if profile.join_date else None,
        "enhanced_metrics": analyzer.get_enhanced_profile_metrics(profile),
        "advanced_stats": analyzer.get_advanced_statistics([profile]).to_dict('records'),
        "rating_distribution": profile.ratings['Rating'].value_counts().to_dict()
    }

    return analysis

@app.get("/analysis/comparison")
async def get_comparison_analysis(user1: str, user2: str):
    if user1 not in profiles_data or user2 not in profiles_data:
        raise HTTPException(status_code=404, detail="One or both profiles not found.")

    profile1 = profiles_data[user1]
    profile2 = profiles_data[user2]

    common_movies = analyzer.find_common_movies(profile1, profile2)
    compatibility = analyzer.calculate_compatibility(profile1, profile2)

    return {
        "common_movies": common_movies,
        "compatibility": compatibility
    }

@app.get("/profiles/")
async def list_profiles():
    return {"profiles": list(profiles_data.keys())}

@app.get("/analysis/llm_comparison")
async def get_llm_comparison(user1: str, user2: str):
    if user1 not in profiles_data or user2 not in profiles_data:
        raise HTTPException(status_code=404, detail="One or both profiles not found.")

    profile1 = profiles_data[user1]
    profile2 = profiles_data[user2]

    try:
        llm_result = analyzer.llm_analyze_profiles(profile1, profile2)
        return {"analysis": llm_result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM analysis failed: {str(e)}")

@app.get("/analysis/llm_individual/{username}")
async def get_llm_individual(username: str):
    if username not in profiles_data:
        raise HTTPException(status_code=404, detail="Profile not found.")

    profile = profiles_data[username]

    try:
        llm_result = analyzer.llm_analyze_individual_profile(profile)
        return {"analysis": llm_result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM analysis failed: {str(e)}")
