import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import json
import asyncio
from unified_analyzer import UnifiedLetterboxdAnalyzer, ProfileData
import os
import zipfile
import tempfile
import shutil
from datetime import datetime
import numpy as np
from scipy import stats
import seaborn as sns
import matplotlib.pyplot as plt

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

def create_multi_profile_rating_chart(profiles):
    """Create rating distribution comparison chart for multiple profiles"""
    if not profiles:
        return None
        
    fig = go.Figure()
    colors = ['#ff6b6b', '#4ecdc4', '#45b7d1', '#96ceb4', '#ffeaa7', '#dda0dd']
    
    for i, profile in enumerate(profiles):
        ratings = profile.ratings['Rating'].value_counts().sort_index()
        all_ratings = sorted(ratings.index)
        
        fig.add_trace(go.Bar(
            x=all_ratings,
            y=[ratings.get(r, 0) for r in all_ratings],
            name=profile.username,
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
    
    return fig

def create_advanced_statistics_section(profiles):
    """Create advanced statistical analysis section"""
    st.subheader("📊 Advanced Statistical Analysis")
    
    # Calculate comprehensive statistics
    stats_data = []
    for profile in profiles:
        if not profile.ratings.empty:
            ratings = pd.to_numeric(profile.ratings['Rating'], errors='coerce').dropna()
            
            # Calculate advanced metrics
            rating_std = ratings.std()
            rating_skew = stats.skew(ratings)
            rating_kurtosis = stats.kurtosis(ratings)
            rating_median = ratings.median()
            rating_mode = ratings.mode().iloc[0] if not ratings.mode().empty else 0
            
            # Rating distribution percentiles
            p25 = ratings.quantile(0.25)
            p75 = ratings.quantile(0.75)
            iqr = p75 - p25
            
            # Activity metrics
            total_reviews = len(profile.reviews)
            review_rate = (total_reviews / len(ratings) * 100) if len(ratings) > 0 else 0
            
            # Year span analysis
            if 'Year' in profile.ratings.columns:
                years = pd.to_numeric(profile.ratings['Year'], errors='coerce').dropna()
                year_span = years.max() - years.min() if len(years) > 0 else 0
                avg_year = years.mean() if len(years) > 0 else 0
            else:
                year_span = 0
                avg_year = 0
            
            stats_data.append({
                "👤 Username": profile.username,
                "🎬 Total Movies": len(ratings),
                "⭐ Avg Rating": f"{ratings.mean():.2f}",
                "📊 Std Dev": f"{rating_std:.2f}",
                "📈 Skewness": f"{rating_skew:.2f}",
                "📉 Kurtosis": f"{rating_kurtosis:.2f}",
                "🎯 Median": f"{rating_median:.1f}",
                "🏆 Mode": f"{rating_mode:.1f}",
                "📏 IQR": f"{iqr:.2f}",
                "✍️ Review Rate": f"{review_rate:.1f}%",
                "📅 Year Span": f"{int(year_span)}",
                "🗓️ Avg Year": f"{int(avg_year)}"
            })
    
    if stats_data:
        df_stats = pd.DataFrame(stats_data)
        st.dataframe(df_stats, use_container_width=True)
        
        # Statistical insights
        with st.expander("📋 Statistical Insights"):
            st.markdown("""
            **Understanding the metrics:**
            - **Standard Deviation**: Lower values indicate more consistent rating patterns
            - **Skewness**: Negative = tends to rate higher, Positive = tends to rate lower
            - **Kurtosis**: Higher values = more extreme ratings (very high or very low)
            - **IQR**: Interquartile range showing rating spread
            - **Review Rate**: Percentage of movies that have written reviews
            """)

def create_genre_heatmap(profiles):
    """Create genre preference heatmap"""
    if len(profiles) < 2:
        return None
    
    # This is a simplified version - would need genre data from analyzer
    st.subheader("🎭 Genre Preference Heatmap")
    st.info("Genre analysis requires additional data processing - coming soon!")

def create_rating_trend_chart(profiles):
    """Create rating trends over time"""
    st.subheader("📈 Rating Trends Over Time")
    
    fig = go.Figure()
    colors = ['#ff6b6b', '#4ecdc4', '#45b7d1', '#96ceb4', '#ffeaa7', '#dda0dd']
    
    for i, profile in enumerate(profiles):
        if not profile.diary.empty and 'Date' in profile.diary.columns:
            diary_df = profile.diary.copy()
            diary_df['Date'] = pd.to_datetime(diary_df['Date'], errors='coerce')
            diary_df = diary_df.dropna(subset=['Date'])
            
            if not diary_df.empty and 'Rating' in diary_df.columns:
                diary_df['Rating'] = pd.to_numeric(diary_df['Rating'], errors='coerce')
                diary_df = diary_df.dropna(subset=['Rating'])
                
                if not diary_df.empty:
                    # Calculate monthly averages
                    diary_df['YearMonth'] = diary_df['Date'].dt.to_period('M')
                    monthly_avg = diary_df.groupby('YearMonth')['Rating'].mean().reset_index()
                    monthly_avg['Date'] = monthly_avg['YearMonth'].dt.to_timestamp()
                    
                    fig.add_trace(go.Scatter(
                        x=monthly_avg['Date'],
                        y=monthly_avg['Rating'],
                        mode='lines+markers',
                        name=profile.username,
                        line=dict(color=colors[i % len(colors)], width=3),
                        marker=dict(size=6)
                    ))
    
    fig.update_layout(
        title="Rating Trends Over Time (Monthly Averages)",
        xaxis_title="Date",
        yaxis_title="Average Rating",
        height=400,
        hovermode='x unified'
    )
    
    if fig.data:
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No diary data with dates available for trend analysis")

def create_common_movies_enhanced_table(common_movies, profiles):
    """Create enhanced table for common movies with sorting and scrolling"""
    if not common_movies or len(profiles) != 2:
        return None
        
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
                index=0
            )
        
        with col2:
            sort_order = st.selectbox(
                "Order:",
                options=["Descending", "Ascending"],
                index=0
            )
        
        with col3:
            show_all = st.checkbox("Show all", value=False)
        
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
        
def create_common_movies_chart(common_movies):
    """Create chart showing rating differences for common movies"""
    if not common_movies or len(common_movies) < 2:
        return None
    
    df = pd.DataFrame(common_movies[:20])  # Top 20
    
    # For 2 profiles, create scatter plot
    if len(df.columns) == 5:  # movie, year, rating1, rating2, difference
        fig = px.scatter(
            df,
            x=df.columns[2],  # First user's rating
            y=df.columns[3],  # Second user's rating
            hover_data=['movie', 'year'],
            title="Rating Comparison for Common Movies",
            labels={
                df.columns[2]: f"{df.columns[2].replace('_rating', '')} Rating",
                df.columns[3]: f"{df.columns[3].replace('_rating', '')} Rating"
            }
        )
        
        # Add diagonal line for perfect agreement
        fig.add_trace(go.Scatter(
            x=[0.5, 5],
            y=[0.5, 5],
            mode='lines',
            line=dict(dash='dash', color='red'),
            name='Perfect Agreement',
            showlegend=True
        ))
        
        fig.update_layout(height=500)
        return fig
    
    return None

def create_enhanced_profile_metrics(profile):
    """Create enhanced metrics for a profile"""
    metrics = {}
    
    if not profile.ratings.empty:
        ratings = pd.to_numeric(profile.ratings['Rating'], errors='coerce').dropna()
        
        # Basic metrics
        metrics['total_movies'] = len(ratings)
        metrics['avg_rating'] = ratings.mean()
        metrics['median_rating'] = ratings.median()
        metrics['std_rating'] = ratings.std()
        
        # Advanced metrics
        metrics['rating_skew'] = stats.skew(ratings)
        metrics['rating_kurtosis'] = stats.kurtosis(ratings)
        
        # Rating distribution
        metrics['five_star_pct'] = (ratings == 5.0).sum() / len(ratings) * 100
        metrics['four_plus_pct'] = (ratings >= 4.0).sum() / len(ratings) * 100
        metrics['three_minus_pct'] = (ratings <= 3.0).sum() / len(ratings) * 100
        
        # Consistency metrics
        metrics['rating_variance'] = ratings.var()
        
        # Year analysis
        if 'Year' in profile.ratings.columns:
            years = pd.to_numeric(profile.ratings['Year'], errors='coerce').dropna()
            if len(years) > 0:
                metrics['oldest_movie'] = int(years.min())
                metrics['newest_movie'] = int(years.max())
                metrics['avg_movie_year'] = years.mean()
    
    # Review metrics
    metrics['total_reviews'] = len(profile.reviews)
    metrics['review_rate'] = (metrics['total_reviews'] / metrics.get('total_movies', 1)) * 100
    
    return metrics

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
        base_path = "/Users/mailyas/Downloads/letterboxd"
        
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
            A sophisticated system for analyzing and comparing up to 4 Letterboxd user profiles using LLM-powered insights
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
    st.markdown('<div class="upload-section">', unsafe_allow_html=True)
    st.header("📁 Profile Setup")
    
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
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Load profiles button
    if st.button("🔄 Load Profiles", type="primary"):
        with st.spinner("Loading profiles..."):
            try:
                analyzer = load_analyzer()
                profiles = []
                
                for i, config in enumerate(profile_configs):
                    if config is None:
                        continue
                    
                    source_type, data, username = config
                    
                    if source_type == "upload":
                        # Extract uploaded file
                        profile_path = extract_zip_file(data, st.session_state.temp_dir)
                        profile = analyzer.load_profile(profile_path, username)
                        profiles.append(profile)
                    
                    elif source_type == "local":
                        # Use local data
                        profile = analyzer.load_profile(data, username)
                        profiles.append(profile)
                
                if len(profiles) >= 2:
                    st.session_state.analyzer = analyzer
                    st.session_state.profiles = profiles
                    st.session_state.profiles_loaded = True
                    st.success(f"Successfully loaded {len(profiles)} profiles!")
                else:
                    st.error("Please configure at least 2 profiles to continue.")
                    
            except Exception as e:
                st.error(f"Error loading profiles: {str(e)}")
    
    # Main analysis content
    if 'profiles_loaded' not in st.session_state:
        st.info("� Please configure and load profiles to begin analysis.")
        return
    
    analyzer = st.session_state.analyzer
    profiles = st.session_state.profiles
    
    # Update analyzer with API key if provided
    if openai_key:
        analyzer.openai_enabled = True
        try:
            import openai
            openai.api_key = openai_key
        except ImportError:
            st.warning("OpenAI package not available. Install with: pip install openai")
    
    # Profile Overview Section
    st.markdown('<div class="comparison-section">', unsafe_allow_html=True)
    st.header("📊 Profile Overview")
    
    # Display profiles in a grid
    cols = st.columns(min(len(profiles), 2))
    for i, profile in enumerate(profiles):
        with cols[i % 2]:
            st.subheader(f"👤 {profile.username}")
            display_profile_overview(profile)
            
            if profile.profile_info.get('Bio'):
                st.markdown("**Bio:**")
                st.markdown(profile.profile_info['Bio'])
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Statistical Analysis Section
    st.markdown('<div class="comparison-section">', unsafe_allow_html=True)
    st.header("📈 Statistical Analysis")
    
    with st.spinner("Generating statistical comparison..."):
        # Advanced statistical analysis
        create_advanced_statistics_section(profiles)
        
        # Rating trends over time
        create_rating_trend_chart(profiles)
        
        # Multi-profile rating distribution chart
        st.subheader("⭐ Rating Distribution Comparison")
        rating_chart = create_multi_profile_rating_chart(profiles)
        if rating_chart:
            st.plotly_chart(rating_chart, use_container_width=True)
        
        # Pairwise comparisons for common movies (only for 2 profiles for now)
        if len(profiles) == 2:
            common_movies = analyzer.find_common_movies(profiles[0], profiles[1])
            compatibility = analyzer.calculate_compatibility(profiles[0], profiles[1])
            
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
                common_chart = create_common_movies_chart(common_movies)
                if common_chart:
                    st.plotly_chart(common_chart, use_container_width=True)
                
                # Enhanced common movies table with sorting and scrolling
                create_common_movies_enhanced_table(common_movies, profiles)
        
        else:
            # Multi-profile summary statistics
            st.subheader("📊 Profile Statistics Summary")
            stats_data = []
            for profile in profiles:
                enhanced_metrics = create_enhanced_profile_metrics(profile)
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
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    # LLM Analysis Section
    st.markdown('<div class="comparison-section">', unsafe_allow_html=True)
    st.header("🤖 LLM-Powered Deep Analysis")
    
    if analyzer.llm_available:
        # Show which LLM service is being used
        if hasattr(analyzer, 'local_llm') and analyzer.local_llm and analyzer.local_llm.available_service:
            st.info(f"🔧 Using local LLM: {analyzer.local_llm.available_service.upper()}")
        elif analyzer.openai_enabled:
            st.info("🌐 Using OpenAI API")
        
        # For now, LLM analysis works best with 2 profiles
        if len(profiles) == 2:
            if st.button("🚀 Generate LLM Analysis", type="primary"):
                with st.spinner("Performing deep LLM analysis... This may take a few minutes."):
                    try:
                        llm_result = analyzer.llm_analyze_profiles(profiles[0], profiles[1])
                        
                        st.success("LLM analysis completed!")
                        
                        if llm_result and llm_result != "LLM analysis not available":
                            st.markdown("### Analysis Results")
                            st.markdown(llm_result)
                        else:
                            st.error("LLM analysis not available")
                            
                    except Exception as e:
                        st.error(f"Error during LLM analysis: {str(e)}")
        else:
            st.info("🔍 LLM comparison analysis currently supports 2 profiles. Individual profile analysis available below.")
    
    else:
        st.warning("⚠️ No LLM service available. Please:")
        st.markdown("""
        - **For local LLM**: Start Ollama (`ollama serve`) or LM Studio server
        - **For cloud LLM**: Enter your OpenAI API key in the sidebar
        """)
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Individual Profile Deep Dive
    st.markdown('<div class="comparison-section">', unsafe_allow_html=True)
    st.header("🔍 Individual Profile Analysis")
    
    selected_profile_name = st.selectbox("Select profile to analyze", [p.username for p in profiles])
    profile = next(p for p in profiles if p.username == selected_profile_name)
    
    # Enhanced profile metrics
    enhanced_metrics = create_enhanced_profile_metrics(profile)
    
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
    tab1, tab2, tab3, tab4 = st.tabs(["🏆 Top Rated", "📅 Recent Activity", "📊 Rating Analysis", "📝 Reviews"])
    
    with tab1:
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
    
    with tab2:
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
    
    with tab3:
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
    
    with tab4:
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
    
    # LLM Individual Analysis
    if analyzer.llm_available:
        st.subheader("🤖 AI Personality Analysis")
        if st.button(f"Generate AI Analysis for {profile.username}", key=f"individual_analysis_{selected_profile_name}"):
            with st.spinner(f"Analyzing {profile.username}'s cinematic personality..."):
                try:
                    # Create a safer version of individual analysis
                    individual_analysis = generate_safe_individual_analysis(analyzer, profile)
                    if individual_analysis and individual_analysis != "LLM analysis not available":
                        st.markdown("### 🎭 AI Insights")
                        st.markdown(individual_analysis)
                    else:
                        st.error("Individual analysis not available")
                except Exception as e:
                    st.error(f"Error during individual analysis: {str(e)}")
                    # Show debug information
                    with st.expander("Debug Information"):
                        st.code(str(e))

def generate_safe_individual_analysis(analyzer, profile):
    """Generate a safer version of individual analysis that handles missing data"""
    try:
        if not analyzer.llm_available:
            return "LLM analysis not available"
        
        # Safely get basic statistics
        total_movies = len(profile.ratings) if not profile.ratings.empty else 0
        avg_rating = profile.ratings['Rating'].mean() if not profile.ratings.empty else 0
        total_reviews = len(profile.reviews) if not profile.reviews.empty else 0
        
        # Safely get genre preferences (simplified version)
        genre_analysis = "Genre analysis requires additional processing"
        
        # Get top and low rated movies safely
        top_movies = []
        low_movies = []
        
        if not profile.ratings.empty:
            ratings_numeric = pd.to_numeric(profile.ratings['Rating'], errors='coerce')
            profile.ratings['Rating_Numeric'] = ratings_numeric
            
            high_rated = profile.ratings[profile.ratings['Rating_Numeric'] >= 4.5]
            if not high_rated.empty:
                top_movies = high_rated.head(5).apply(
                    lambda x: f"{x.get('Name', 'Unknown')} ({x.get('Year', 'N/A')}) - {x.get('Rating', 'N/A')}★", 
                    axis=1
                ).tolist()
            
            low_rated = profile.ratings[profile.ratings['Rating_Numeric'] <= 2.0]
            if not low_rated.empty:
                low_movies = low_rated.head(3).apply(
                    lambda x: f"{x.get('Name', 'Unknown')} ({x.get('Year', 'N/A')}) - {x.get('Rating', 'N/A')}★", 
                    axis=1
                ).tolist()
        
        # Create a simplified but comprehensive prompt
        prompt = f"""Analyze this Letterboxd user's movie preferences and provide personality insights.

USER PROFILE: {profile.username}

CORE STATISTICS:
• Total movies rated: {total_movies}
• Average rating: {avg_rating:.2f}★
• Total reviews written: {total_reviews}
• Join date: {profile.join_date.strftime('%B %Y') if profile.join_date else 'Unknown'}

TOP RATED MOVIES (4.5+ stars):
{chr(10).join(['• ' + movie for movie in top_movies]) if top_movies else '• No highly rated movies found'}

MOVIES THEY DISLIKED (≤2 stars):
{chr(10).join(['• ' + movie for movie in low_movies]) if low_movies else '• No strongly disliked movies found'}

ANALYSIS REQUEST:
Provide a detailed personality analysis covering:

1. **Movie Taste Profile**: What do their preferences reveal about their personality?
2. **Critical Style**: Are they harsh, generous, or balanced in their ratings?
3. **Viewing Patterns**: What can you infer about their lifestyle and preferences?
4. **Personality Traits**: What psychological traits emerge from their movie choices?
5. **Recommendations**: Suggest 3-5 specific movies they might enjoy and explain why.

Be specific, insightful, and avoid generic observations. Use their actual ratings as evidence."""

        # Use available LLM service
        if hasattr(analyzer, 'local_llm') and analyzer.local_llm and analyzer.local_llm.available_service:
            return analyzer.local_llm.generate_response(prompt, 2000)
        elif analyzer.openai_enabled:
            try:
                import openai
                response = openai.ChatCompletion.create(
                    model="gpt-3.5-turbo",  # Use more reliable model
                    messages=[
                        {"role": "system", "content": "You are an expert film critic and personality analyst. Provide detailed, specific insights based on movie preferences."},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=2000,
                    temperature=0.8
                )
                return response.choices[0].message.content
            except Exception as e:
                return f"OpenAI error: {str(e)}"
        else:
            return "No LLM service available"
            
    except Exception as e:
        return f"Error generating analysis: {str(e)}"
    
    st.markdown('</div>', unsafe_allow_html=True)

if __name__ == "__main__":
    main()
