import axios from 'axios';

// Create axios instance with base configuration
const api = axios.create({
  baseURL: process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000',
  timeout: 30000, // 30 seconds for long operations like scraping
  headers: {
    'Content-Type': 'application/json',
  },
});

// Types for API responses
export interface ProfileInfo {
  username: string;
  total_films: number;   // All films discovered
  rated_films: number;   // Films with ratings
  liked_films: number;   // Films that are liked
  avg_rating: number;
  total_reviews: number;
  join_date: string | null;
  last_scraped_at?: string | null;
  scraping_status?: string;
}

export interface ProfileAnalysis {
  username: string;
  total_films: number;
  rated_films: number;
  liked_films: number;
  avg_rating: number;
  total_reviews: number;
  join_date: string | null;
  enhanced_metrics: any;
  advanced_stats: any[];
  rating_distribution: Record<string, number>;
}

export interface ScrapingStatus {
  id?: number;
  status: 'pending' | 'queued' | 'in_progress' | 'completed' | 'failed' | 'error';
  progress_message?: string;
  progress_percentage?: number;
  started_at?: string;
  error_message?: string;
  // Legacy fields for backward compatibility
  progress?: string;
  start_time?: string;
  end_time?: string;
}

export interface AvailableProfile {
  username: string;
  scraped_at: string;
}

// Profile API endpoints
export const profileApi = {
  // Get all profiles
  getProfiles: async (): Promise<ProfileInfo[]> => {
    const response = await api.get('/profiles/');
    return response.data.profiles || [];
  },

  // Get profile analysis
  getAnalysis: async (username: string): Promise<ProfileAnalysis> => {
    const response = await api.get(`/profiles/${username}/analysis`);
    return response.data;
  },

  // Upload ZIP files
  uploadFiles: async (files: FileList): Promise<{ message: string }> => {
    const formData = new FormData();
    Array.from(files).forEach((file, index) => {
      formData.append(`files`, file);
    });
    
    const response = await api.post('/upload/', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  },

  // Create profile
  createProfile: async (username: string): Promise<{ message: string; profile: any }> => {
    const response = await api.post('/profiles/create', { username });
    return response.data;
  },

  // Delete profile
  deleteProfile: async (username: string): Promise<{ message: string }> => {
    const response = await api.delete(`/profiles/${username}`);
    return response.data;
  },
};

// Scraper API endpoints
export const scraperApi = {
  // Start scraping a profile
  scrapeProfile: async (username: string): Promise<{ message: string }> => {
    const response = await api.post(`/scrape/profile/${username}`);
    return response.data;
  },

  // Get scraping status
  getStatus: async (username: string): Promise<ScrapingStatus> => {
    const response = await api.get(`/scrape/status/${username}`);
    return response.data;
  },

  // Get available scraped profiles
  getAvailable: async (): Promise<{ available_profiles: AvailableProfile[] }> => {
    const response = await api.get('/scrape/available');
    return response.data;
  },

  // Clear scraped data
  clearData: async (username: string): Promise<{ message: string }> => {
    const response = await api.delete(`/scrape/${username}`);
    return response.data;
  },
};

// Analysis API endpoints
export const analysisApi = {
  // Get comparative analysis
  getComparative: async (usernames: string[]): Promise<any> => {
    const params = new URLSearchParams();
    usernames.forEach(username => params.append('usernames', username));
    const response = await api.get(`/analysis/comparative?${params}`);
    return response.data;
  },

  // Get recommendations
  getRecommendations: async (username: string): Promise<any> => {
    const response = await api.get(`/analysis/recommendations/${username}`);
    return response.data;
  },
};

export interface SystemStats {
  total_profiles: number;
  total_movies_tracked: number;
  total_reviews: number;
  active_scraping_jobs: number;
  global_avg_rating: number;
  last_updated: string;
}

export interface TopMovie {
  title: string;
  year: number;
  average_rating: number;
  total_ratings: number;
}

export interface ActivityData {
  month: string;
  movies_watched: number;
  average_rating: number | null;
}

export interface DashboardAnalytics {
  system_stats: SystemStats;
  top_rated_movies: TopMovie[];
  rating_distribution: Record<string, number>;
  activity_data: ActivityData[];
  timestamp: string;
}

// Dashboard API endpoints
export const dashboardApi = {
  // Get dashboard analytics
  getAnalytics: async (): Promise<DashboardAnalytics> => {
    const response = await api.get('/api/dashboard/analytics');
    return response.data;
  },
};

export default api;
