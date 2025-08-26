import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import json
import asyncio
import requests
from core.analyzer import UnifiedLetterboxdAnalyzer, ProfileData
import os
import zipfile
import tempfile
import shutil
from datetime import datetime
import numpy as np
from scipy import stats
import seaborn as sns
import matplotlib.pyplot as plt
from config import settings

st.set_page_config(
    page_title="Letterboxd Profile Analyzer",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 3rem;
        font-weight: bold;
        text-align: center;
        background: linear-gradient(90deg, #ff6b6b, #4ecdc4);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 2rem;
    }
    .profile-card {
        background: #f8f9fa;
        padding: 1.5rem;
        border-radius: 10px;
        border: 2px solid #e9ecef;
        margin: 1rem 0;
    }
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 1rem;
        border-radius: 8px;
        text-align: center;
        margin: 0.5rem;
    }
    .comparison-section {
        background: #fff;
        padding: 2rem;
        border-radius: 10px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        margin: 1rem 0;
    }
    .upload-section {
        background: #f8f9fa;
        padding: 1.5rem;
        border-radius: 10px;
        border: 2px dashed #007bff;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)

@st.cache_data
def load_analyzer():
    """Load the analyzer (cached)"""
    return UnifiedLetterboxdAnalyzer()

@st.cache_data
def load_and_cache_profile(_analyzer, profile_path, username):
    """Wrapper to cache profile loading."""
    return _analyzer.load_profile(profile_path, username)

def extract_zip_file(uploaded_file, temp_dir):
    """Extract uploaded zip file to temporary directory"""
    zip_path = os.path.join(temp_dir, uploaded_file.name)
    with open(zip_path, "wb") as f:
        f.write(uploaded_file.getbuffer())

    extract_dir = os.path.join(temp_dir, uploaded_file.name.replace('.zip', ''))
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(extract_dir)

    # Find the actual data directory (might be nested)
    for root, dirs, files in os.walk(extract_dir):
        if any(f in files for f in ['ratings.csv', 'watched.csv', 'reviews.csv']):
            return root

    return extract_dir

def create_sortable_table(df, title, height=400):
    """Create a sortable table with enhanced features"""
    if df.empty:
        st.info(f"No data available for {title}")
        return

    st.subheader(title)

    # Add sorting controls
    col1, col2, col3 = st.columns([2, 2, 1])

    with col1:
        sort_col = st.selectbox(
            f"Sort {title} by:",
            options=df.columns.tolist(),
            key=f"sort_col_{title.replace(' ', '_')}"
        )

    with col2:
        sort_order = st.selectbox(
            "Order:",
            options=["Descending", "Ascending"],
            key=f"sort_order_{title.replace(' ', '_')}"
        )

    with col3:
        show_count = st.number_input(
            "Show top:",
            min_value=5,
            max_value=len(df),
            value=min(20, len(df)),
            key=f"show_count_{title.replace(' ', '_')}"
        )

    # Apply sorting
    ascending = sort_order == "Ascending"
    df_sorted = df.sort_values(by=sort_col, ascending=ascending)

    # Show table
    st.dataframe(
        df_sorted.head(show_count),
        use_container_width=True,
        height=height
    )

    return df_sorted

def display_profile_overview(profile: ProfileData):
    """Display profile overview"""
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.markdown(f"""
        <div class="metric-card">
            <h3>{profile.total_movies}</h3>
            <p>Movies Rated</p>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown(f"""
        <div class="metric-card">
            <h3>{profile.avg_rating:.2f}</h3>
            <p>Average Rating</p>
        </div>
        """, unsafe_allow_html=True)

    with col3:
        st.markdown(f"""
        <div class="metric-card">
            <h3>{profile.total_reviews}</h3>
            <p>Reviews Written</p>
        </div>
        """, unsafe_allow_html=True)

    with col4:
        join_date = profile.join_date.strftime("%Y-%m-%d") if profile.join_date else "Unknown"
        st.markdown(f"""
        <div class="metric-card">
            <h3>{join_date}</h3>
            <p>Joined</p>
        </div>
        """, unsafe_allow_html=True)

def setup_profile_upload(profile_num):
    """Setup profile upload interface"""
    st.subheader(f"Profile {profile_num}")

    # Option to use existing local data or upload new
    option = st.radio(
        f"Data source for Profile {profile_num}:",
        ("Upload ZIP file", "Use local data"),
        key=f"option_{profile_num}"
    )

    if option == "Upload ZIP file":
        uploaded_file = st.file_uploader(
            f"Upload Letterboxd export ZIP for Profile {profile_num}",
            type=['zip'],
            key=f"upload_{profile_num}",
            help="Upload your Letterboxd data export ZIP file"
        )

        if uploaded_file:
            # Get username from user input
            username = st.text_input(
                f"Enter username for Profile {profile_num}:",
                key=f"username_{profile_num}",
                placeholder="Enter the Letterboxd username"
            )

            if username:
                return ("upload", uploaded_file, username)

        return None

    else:  # Use local data
        # Show available local profiles
        local_profiles = []
        base_path = settings.DEFAULT_LOCAL_DATA_PATH

        if os.path.exists(base_path):
            for item in os.listdir(base_path):
                item_path = os.path.join(base_path, item)
                if os.path.isdir(item_path) and item not in ['__pycache__', '.git']:
                    # Check if it contains Letterboxd data
                    subfolders = os.listdir(item_path)
                    for subfolder in subfolders:
                        subfolder_path = os.path.join(item_path, subfolder)
                        if os.path.isdir(subfolder_path):
                            files = os.listdir(subfolder_path)
                            if any(f in files for f in ['ratings.csv', 'watched.csv']):
                                local_profiles.append((item, subfolder_path))
                                break
                        elif any(f in subfolders for f in ['ratings.csv', 'watched.csv']):
                            local_profiles.append((item, item_path))
                            break

        if local_profiles:
            selected = st.selectbox(
                f"Select local profile for Profile {profile_num}:",
                ["None"] + [f"{name} ({path})" for name, path in local_profiles],
                key=f"local_{profile_num}"
            )

            if selected != "None":
                idx = [f"{name} ({path})" for name, path in local_profiles].index(selected)
                name, path = local_profiles[idx]
                return ("local", path, name)

        else:
            st.info("No local profiles found")

        return None

def main():
    st.markdown('<h1 class="main-header">🎬 Letterboxd Multi-Profile Analyzer</h1>', unsafe_allow_html=True)

    st.markdown("""
    <div style="text-align: center; margin-bottom: 2rem;">
        <p style="font-size: 1.2rem; color: #666;">
            A sophisticated system for analyzing and comparing up to 4 Letterboxd user profiles using LLM-powered insights.
        </p>
    </div>
    """, unsafe_allow_html=True)

    # Sidebar for configuration
    with st.sidebar:
        st.header("⚙️ Configuration")

        # Number of profiles to compare
        num_profiles = st.slider("Number of profiles to compare:", 2, 4, 2)

        st.markdown("---")

        # OpenAI API Key input
        openai_key = st.text_input("OpenAI API Key (for LLM analysis)", type="password",
                                  help="Enter your OpenAI API key to enable advanced LLM-based analysis")

        st.markdown("---")
        st.info("💡 You can upload Letterboxd export ZIP files or use existing local data.")

    # Profile Setup Section
    with st.expander("📁 Profile Setup", expanded='profiles_loaded' not in st.session_state):
        with st.container():
            # Create temporary directory for uploads
            if 'temp_dir' not in st.session_state:
                st.session_state.temp_dir = tempfile.mkdtemp()

            # Setup each profile
            profile_configs = []
            cols = st.columns(min(num_profiles, 2))

            for i in range(num_profiles):
                with cols[i % 2]:
                    config = setup_profile_upload(i + 1)
                    profile_configs.append(config)

            # Load profiles button
            if st.button("🔄 Load Profiles", type="primary"):
        with st.spinner("Uploading and processing profiles..."):
            try:
                profiles = []
                for i, config in enumerate(profile_configs):
                    if config is None:
                        continue

                    source_type, data, username = config

                    if source_type == "upload":
                        files = {'file': (data.name, data.getvalue(), data.type)}
                        response = requests.post(f"http://127.0.0.1:8000/profiles/?username={username}", files=files)
                        if response.status_code == 200:
                            st.success(f"Successfully uploaded profile for {username}")
                            profiles.append(username)
                        else:
                            st.error(f"Error uploading profile for {username}: {response.text}")
                    elif source_type == "local":
                        # This part is more complex as it involves sending local file paths to the backend.
                        # For now, we will focus on the upload functionality.
                        # A robust solution would require the backend to have access to the same filesystem
                        # or to upload the files from the local path.
                        st.warning("Local data processing via API is not yet implemented. Please use file upload.")

                if profiles:
                    st.session_state.profiles_loaded = True
                    st.session_state.profile_names = profiles
                    st.experimental_rerun()
                else:
                    st.error("Please configure and upload at least one profile.")

            except Exception as e:
                st.error(f"Error loading profiles: {str(e)}")

    # Main analysis content
    if 'profiles_loaded' not in st.session_state:
        st.info("👋 Please configure and load profiles to begin analysis.")
        return

    profile_names = st.session_state.profile_names
    profiles = []
    for name in profile_names:
        response = requests.get(f"http://127.0.0.1:8000/profiles/{name}/analysis")
        if response.status_code == 200:
            profiles.append(response.json())
        else:
            st.error(f"Failed to fetch analysis for {name}: {response.text}")

    if not profiles:
        st.error("Could not fetch any profile data from the backend.")
        return

    # This is a bit of a hack to keep the UI compatible with the old structure.
    # A better approach would be to refactor the display functions to directly
    # use the dictionary structure returned by the API.
    class ProfileDataAPI:
        def __init__(self, data):
            self.username = data.get("username")
            self.total_movies = data.get("total_movies")
            self.avg_rating = data.get("avg_rating")
            self.total_reviews = data.get("total_reviews")
            self.join_date = datetime.fromisoformat(data.get("join_date")) if data.get("join_date") else None
            self.profile_info = {"Bio": "Bio not available via API yet."} # Placeholder
            self.ratings = pd.DataFrame(data.get("enhanced_metrics", {}).get("rating_distribution", {}).items(), columns=['Rating', 'Count'])
            self.diary = pd.DataFrame() # Placeholder
            self.reviews = pd.DataFrame() # Placeholder


    api_profiles = [ProfileDataAPI(p) for p in profiles]

    # Profile Overview Section
    st.header("📊 Profile Overview")

    # Display profiles in a grid
    cols = st.columns(min(len(api_profiles), 2))
    for i, profile in enumerate(api_profiles):
        with cols[i % 2]:
            st.subheader(f"👤 {profile.username}")
            display_profile_overview(profile)

            if profile.profile_info.get('Bio'):
                st.markdown("**Bio:**")
                st.markdown(profile.profile_info['Bio'])

    st.markdown("---")

    tab1, tab2, tab3 = st.tabs(["📊 Comparison", "🔍 Deep Dive", "🤖 LLM Analysis"])

    with tab1:
        with st.spinner("Generating statistical comparison..."):
            # Advanced statistical analysis
            st.subheader("📊 Advanced Statistical Analysis")

            all_stats = []
            for p in profiles:
                all_stats.extend(p.get("advanced_stats", []))

            if all_stats:
                stats_df = pd.DataFrame(all_stats)
                st.dataframe(stats_df, use_container_width=True)
                with st.expander("📋 Statistical Insights"):
                    st.markdown("""
                    **Understanding the metrics:**
                    - **Standard Deviation**: Lower values indicate more consistent rating patterns
                    - **Skewness**: Negative = tends to rate higher, Positive = tends to rate lower
                    - **Kurtosis**: Higher values = more extreme ratings (very high or very low)
                    - **IQR**: Interquartile range showing rating spread
                    - **Review Rate**: Percentage of movies that have written reviews
                    """)

            # Multi-profile rating distribution chart
            st.subheader("⭐ Rating Distribution Comparison")
            fig = go.Figure()
            colors = ['#ff6b6b', '#4ecdc4', '#45b7d1', '#96ceb4', '#ffeaa7', '#dda0dd']
            for i, profile in enumerate(profiles):
                ratings = profile.get("rating_distribution", {})
                if ratings:
                    all_ratings = sorted([float(k) for k in ratings.keys()])
                    fig.add_trace(go.Bar(
                        x=all_ratings,
                        y=[ratings.get(str(r), 0) for r in all_ratings],
                        name=profile['username'],
                        marker_color=colors[i % len(colors)],
                        opacity=0.7
                    ))
            fig.update_layout(
                title="Rating Distribution Comparison",
                xaxis_title="Rating",
                yaxis_title="Number of Movies",
                barmode='group',
                height=400,
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            st.plotly_chart(fig, use_container_width=True)

            # Pairwise comparisons for common movies (only for 2 profiles for now)
            if len(profiles) == 2:
                response = requests.get(f"http://127.0.0.1:8000/analysis/comparison?user1={profiles[0]['username']}&user2={profiles[1]['username']}")
                if response.status_code == 200:
                    comparison_data = response.json()
                    common_movies = comparison_data.get("common_movies", [])
                    compatibility = comparison_data.get("compatibility", {})
                else:
                    st.error(f"Failed to get comparison data: {response.text}")
                    common_movies = []
                    compatibility = {}

                # Enhanced compatibility metrics
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("🎬 Common Movies", len(common_movies))
                with col2:
                    avg_diff = compatibility.get('rating_agreement', {}).get('avg_difference', 0)
                    st.metric("📊 Avg Rating Diff", f"{avg_diff:.2f}" if avg_diff else "N/A")
                with col3:
                    pattern_sim = compatibility.get('pattern_similarity', 0)
                    st.metric("🔄 Pattern Similarity", f"{pattern_sim:.2f}")
                with col4:
                    if common_movies:
                        correlation = np.corrcoef(
                            [m[list(m.keys())[2]] for m in common_movies if len(m) > 2],
                            [m[list(m.keys())[3]] for m in common_movies if len(m) > 3]
                        )[0,1] if len(common_movies) > 1 else 0
                        st.metric("📈 Rating Correlation", f"{correlation:.3f}")

                # Enhanced common movies analysis
                if common_movies:
                    # Common movies scatter plot
                    st.subheader("🎯 Common Movies Rating Comparison")
                    common_chart = analyzer.create_common_movies_chart(common_movies)
                    if common_chart:
                        st.plotly_chart(common_chart, use_container_width=True)

                    # Enhanced common movies table with sorting and scrolling
                    st.subheader(f"🎬 Common Movies ({len(common_movies)} total)")

                    # Convert to DataFrame for better handling
                    df_common = pd.DataFrame(common_movies)

                    if not df_common.empty:
                        # Add sorting options
                        col1, col2, col3 = st.columns([2, 2, 1])

                        with col1:
                            sort_column = st.selectbox(
                                "Sort by:",
                                options=df_common.columns.tolist(),
                                index=0,
                                key="common_sort_col"
                            )

                        with col2:
                            sort_order = st.selectbox(
                                "Order:",
                                options=["Descending", "Ascending"],
                                index=0,
                                key="common_sort_order"
                            )

                        with col3:
                            show_all = st.checkbox("Show all", value=False, key="common_show_all")

                        # Apply sorting
                        ascending = sort_order == "Ascending"
                        df_sorted = df_common.sort_values(by=sort_column, ascending=ascending)

                        # Display count and filters
                        st.write(f"**Showing {'all' if show_all else 'top 20'} of {len(df_sorted)} common movies**")

                        # Show table with optional limiting
                        display_df = df_sorted if show_all else df_sorted.head(20)

                        # Use container with fixed height for scrolling
                        if len(display_df) > 10:
                            st.dataframe(
                                display_df,
                                use_container_width=True,
                                height=400  # Fixed height enables scrolling
                            )
                        else:
                            st.dataframe(display_df, use_container_width=True)

                        # Add download option
                        csv = df_sorted.to_csv(index=False)
                        st.download_button(
                            label="📥 Download all common movies as CSV",
                            data=csv,
                            file_name=f"common_movies_{profiles[0].username}_{profiles[1].username}.csv",
                            mime="text/csv"
                        )
            else:
                # Multi-profile summary statistics
                st.subheader("📊 Profile Statistics Summary")
                stats_data = []
                for profile in profiles:
                    enhanced_metrics = analyzer.get_enhanced_profile_metrics(profile)
                    stats_data.append({
                        "👤 Username": profile.username,
                        "🎬 Total Movies": enhanced_metrics.get('total_movies', 0),
                        "⭐ Avg Rating": f"{enhanced_metrics.get('avg_rating', 0):.2f}",
                        "📊 Std Dev": f"{enhanced_metrics.get('std_rating', 0):.2f}",
                        "🎯 Median": f"{enhanced_metrics.get('median_rating', 0):.1f}",
                        "✍️ Review Rate": f"{enhanced_metrics.get('review_rate', 0):.1f}%",
                        "⭐ 5-Star %": f"{enhanced_metrics.get('five_star_pct', 0):.1f}%",
                        "🎭 4+ Star %": f"{enhanced_metrics.get('four_plus_pct', 0):.1f}%",
                        "📅 Join Date": profile.join_date.strftime("%Y-%m-%d") if profile.join_date else "Unknown"
                    })

                stats_df = pd.DataFrame(stats_data)
                st.dataframe(stats_df, use_container_width=True)

    with tab2:
        st.header("🔍 Individual Profile Deep Dive")

        selected_profile_name = st.selectbox("Select profile to analyze", [p['username'] for p in profiles])
        profile_data = next(p for p in profiles if p['username'] == selected_profile_name)

        # Enhanced profile metrics
        enhanced_metrics = profile_data.get("enhanced_metrics", {})

        # Display enhanced metrics in columns
        col1, col2, col3, col4, col5 = st.columns(5)

        with col1:
            st.metric("🎬 Total Movies", enhanced_metrics.get('total_movies', 0))
        with col2:
            st.metric("⭐ Avg Rating", f"{enhanced_metrics.get('avg_rating', 0):.2f}")
        with col3:
            st.metric("📊 Std Dev", f"{enhanced_metrics.get('std_rating', 0):.2f}")
        with col4:
            st.metric("✍️ Review Rate", f"{enhanced_metrics.get('review_rate', 0):.1f}%")
        with col5:
            st.metric("🏆 5-Star Rate", f"{enhanced_metrics.get('five_star_pct', 0):.1f}%")

        # Tabs for different analyses
        sub_tab1, sub_tab2, sub_tab3, sub_tab4 = st.tabs(["🏆 Top Rated", "📅 Recent Activity", "📊 Rating Analysis", "📝 Reviews"])

        with sub_tab1:
            # Top rated movies with enhanced sorting
            if not profile.ratings.empty:
                ratings_df = profile.ratings.copy()
                ratings_df['Rating'] = pd.to_numeric(ratings_df['Rating'], errors='coerce')
                high_rated = ratings_df[ratings_df['Rating'] >= 4.0].copy()

                if not high_rated.empty:
                    # Add ranking
                    high_rated = high_rated.sort_values('Rating', ascending=False).reset_index(drop=True)
                    high_rated['Rank'] = range(1, len(high_rated) + 1)

                    # Reorder columns
                    columns = ['Rank', 'Name', 'Year', 'Rating']
                    available_columns = [col for col in columns if col in high_rated.columns]
                    high_rated_display = high_rated[available_columns]

                    create_sortable_table(high_rated_display, f"🏆 {profile.username}'s Top Rated Movies (4+ stars)", height=500)
                else:
                    st.info("No movies rated 4+ stars found")

        with sub_tab2:
            # Recent activity with enhanced display
            if not profile.diary.empty:
                diary_df = profile.diary.copy()
                diary_df['Date'] = pd.to_datetime(diary_df['Date'], errors='coerce')

                if not diary_df['Date'].isna().all():
                    diary_sorted = diary_df.sort_values('Date', ascending=False, na_position='last')

                    # Add relative date information
                    today = pd.Timestamp.now()
                    diary_sorted['Days Ago'] = (today - diary_sorted['Date']).dt.days

                    # Select relevant columns
                    display_columns = ['Name', 'Year', 'Date', 'Days Ago']
                    if 'Rating' in diary_sorted.columns:
                        display_columns.insert(-1, 'Rating')

                    available_columns = [col for col in display_columns if col in diary_sorted.columns]
                    recent_display = diary_sorted[available_columns].head(50)

                    create_sortable_table(recent_display, f"📅 {profile.username}'s Recent Activity", height=500)
                else:
                    st.info("No diary data with valid dates found")

        with sub_tab3:
            # Rating analysis
            if not profile.ratings.empty:
                ratings = pd.to_numeric(profile.ratings['Rating'], errors='coerce').dropna()

                # Rating distribution chart
                fig = px.histogram(
                    x=ratings,
                    nbins=20,
                    title=f"{profile.username}'s Rating Distribution",
                    labels={'x': 'Rating', 'y': 'Count'}
                )
                fig.update_layout(height=300)
                st.plotly_chart(fig, use_container_width=True)

                # Rating statistics
                col1, col2 = st.columns(2)

                with col1:
                    st.subheader("📊 Rating Statistics")
                    st.write(f"**Mean:** {ratings.mean():.2f}")
                    st.write(f"**Median:** {ratings.median():.2f}")
                    st.write(f"**Mode:** {ratings.mode().iloc[0] if not ratings.mode().empty else 'N/A':.1f}")
                    st.write(f"**Standard Deviation:** {ratings.std():.2f}")
                    st.write(f"**Skewness:** {stats.skew(ratings):.2f}")
                    st.write(f"**Kurtosis:** {stats.kurtosis(ratings):.2f}")

                with col2:
                    st.subheader("🎯 Rating Breakdown")
                    rating_counts = ratings.value_counts().sort_index()
                    for rating in sorted(rating_counts.index):
                        count = rating_counts[rating]
                        percentage = (count / len(ratings)) * 100
                        st.write(f"**{rating}★:** {count} movies ({percentage:.1f}%)")

        with sub_tab4:
            # Reviews analysis
            if not profile.reviews.empty:
                reviews_df = profile.reviews.copy()

                # Add review length if review text is available
                if 'Review' in reviews_df.columns:
                    reviews_df['Review Length'] = reviews_df['Review'].str.len()
                    reviews_df = reviews_df.sort_values('Review Length', ascending=False)

                # Select relevant columns for display
                display_columns = ['Name', 'Year']
                if 'Rating' in reviews_df.columns:
                    display_columns.append('Rating')
                if 'Review Length' in reviews_df.columns:
                    display_columns.append('Review Length')
                if 'Date' in reviews_df.columns:
                    display_columns.append('Date')

                available_columns = [col for col in display_columns if col in reviews_df.columns]
                reviews_display = reviews_df[available_columns]

                create_sortable_table(reviews_display, f"📝 {profile.username}'s Reviews", height=500)
            else:
                st.info("No reviews found for this profile")

    with tab3:
        st.header("🤖 LLM-Powered Deep Analysis")

        # For now, LLM analysis works best with 2 profiles
        if len(profiles) == 2:
            if st.button("🚀 Generate LLM Comparison", type="primary"):
                with st.spinner("Performing deep LLM analysis... This may take a few minutes."):
                    response = requests.get(f"http://127.0.0.1:8000/analysis/llm_comparison?user1={profiles[0]['username']}&user2={profiles[1]['username']}")
                    if response.status_code == 200:
                        llm_result = response.json().get("analysis")
                        st.success("LLM analysis completed!")
                        if llm_result and llm_result != "LLM analysis not available":
                            st.markdown("### Analysis Results")
                            st.markdown(llm_result)
                        else:
                            st.error("LLM analysis not available")
                    else:
                        st.error(f"LLM analysis failed: {response.text}")
        else:
            st.info("🔍 LLM comparison analysis currently supports 2 profiles. Individual profile analysis available below.")

        st.markdown("---")
        st.subheader("🤖 AI Personality Analysis")

        selected_profile_name_llm = st.selectbox("Select profile for AI analysis", [p['username'] for p in profiles], key="llm_profile_select")

        if st.button(f"Generate AI Analysis for {selected_profile_name_llm}", key=f"individual_analysis_{selected_profile_name_llm}"):
            with st.spinner(f"Analyzing {selected_profile_name_llm}'s cinematic personality..."):
                response = requests.get(f"http://127.0.0.1:8000/analysis/llm_individual/{selected_profile_name_llm}")
                if response.status_code == 200:
                    individual_analysis = response.json().get("analysis")
                    if individual_analysis and individual_analysis != "LLM analysis not available":
                        st.markdown("### 🎭 AI Insights")
                        st.markdown(individual_analysis)
                    else:
                        st.error("Individual analysis not available")
                else:
                    st.error(f"Individual analysis failed: {response.text}")

if __name__ == "__main__":
    main()
