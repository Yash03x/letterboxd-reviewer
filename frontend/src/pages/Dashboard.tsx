import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { motion, AnimatePresence } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import { profileApi, scraperApi, dashboardApi } from '../services/api';
import { 
  ArrowPathIcon,
  PlusIcon,
  ChartBarIcon,
  FilmIcon
} from '@heroicons/react/24/outline';
import { 
  Users, 
  Film, 
  Star, 
  MessageCircle, 
  Activity,
  Award,
  Calendar
} from 'lucide-react';
import LoadingSpinner from '../components/LoadingSpinner';
import ErrorMessage from '../components/ErrorMessage';
import StatsCard from '../components/Charts/StatsCard';
import ProfileCard from '../components/ProfileCard';
import RatingDistributionChart from '../components/Charts/RatingDistributionChart';
import ActivityChart from '../components/Charts/ActivityChart';

const Dashboard: React.FC = () => {
  const [refreshingProfile, setRefreshingProfile] = useState<string | null>(null);
  const [deletingProfile, setDeletingProfile] = useState<string | null>(null);
  const navigate = useNavigate();
  
  const { data: profiles, isLoading, error, refetch } = useQuery({
    queryKey: ['profiles'],
    queryFn: profileApi.getProfiles,
    refetchInterval: 30000, // Auto-refresh every 30 seconds
  });

  const { data: analytics, isLoading: analyticsLoading } = useQuery({
    queryKey: ['dashboard-analytics'],
    queryFn: dashboardApi.getAnalytics,
    refetchInterval: 30000, // Auto-refresh every 30 seconds
  });

  // Handle profile refresh
  const handleRefreshProfile = async (username: string) => {
    setRefreshingProfile(username);
    try {
      await scraperApi.scrapeProfile(username);
      refetch();
    } catch (error) {
      console.error('Failed to refresh profile:', error);
    } finally {
      setRefreshingProfile(null);
    }
  };

  // Handle profile deletion
  const handleDeleteProfile = async (username: string) => {
    if (window.confirm(`Are you sure you want to delete ${username}? This cannot be undone.`)) {
      setDeletingProfile(username);
      try {
        await profileApi.deleteProfile(username);
        refetch();
      } catch (error) {
        console.error('Failed to delete profile:', error);
      } finally {
        setDeletingProfile(null);
      }
    }
  };

  // Handle start scraping
  const handleStartScraping = async (username: string) => {
    try {
      await scraperApi.scrapeProfile(username);
      refetch();
    } catch (error) {
      console.error('Failed to start scraping:', error);
    }
  };

  // Handle manual refresh all
  const handleRefreshAll = () => {
    refetch();
  };

  if (isLoading || analyticsLoading) return <LoadingSpinner />;
  if (error) return <ErrorMessage message="Failed to load profiles" />;

  // Ensure profiles is an array
  const profilesArray = Array.isArray(profiles) ? profiles : [];
  
  const totalProfiles = profilesArray.length;
  
  // Use analytics data if available, otherwise fall back to profile summation
  const totalMovies = analytics?.unique_movies_count || profilesArray.reduce((sum, profile) => sum + (profile.total_films || 0), 0);
  const totalReviews = profilesArray.reduce((sum, profile) => sum + (profile.total_reviews || 0), 0);
  const avgRating = profilesArray.length 
    ? profilesArray.reduce((sum, profile) => sum + (profile.avg_rating || 0), 0) / profilesArray.length 
    : 0;

  // Calculate additional metrics
  const activeProfiles = profilesArray.filter(p => p.scraping_status === 'completed').length;
  const completionRate = totalProfiles > 0 ? (activeProfiles / totalProfiles) * 100 : 0;
  
  // Use analytics data for real rating distribution
  const aggregateRatingDistribution = analytics?.rating_distribution || {};
  
  // Use analytics data for real activity data  
  const aggregateActivityData = analytics?.activity_data || [];

  return (
    <motion.div 
      className="space-y-8"
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.6 }}
    >
      {/* Header with Actions */}
      <motion.div 
        className="flex items-center justify-between"
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 }}
      >
        <div>
          <h1 className="text-4xl font-bold text-white text-glow mb-2">
            Dashboard
          </h1>
          <p className="text-white/60">
            Real-time insights from your Letterboxd community
          </p>
        </div>
        
        <motion.div 
          className="flex space-x-4"
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.3 }}
        >
          <motion.button 
            onClick={handleRefreshAll}
            className="btn-secondary flex items-center space-x-2"
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
          >
            <ArrowPathIcon className="w-5 h-5" />
            <span>Refresh All</span>
          </motion.button>
          
          <motion.button 
            onClick={() => navigate('/profiles')}
            className="btn-primary flex items-center space-x-2"
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
          >
            <PlusIcon className="w-5 h-5" />
            <span>Add Profile</span>
          </motion.button>
        </motion.div>
      </motion.div>

      {/* System Overview Stats */}
      <motion.div 
        className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.4 }}
      >
        <StatsCard
          title="Total Profiles"
          value={totalProfiles}
          subtitle="Active community members"
          icon={Users}
          trend={{ value: 12.5, isPositive: true }}
          delay={0}
        />
        
        <StatsCard
          title="Movies Tracked"
          value={totalMovies}
          subtitle="Across all profiles"
          icon={Film}
          trend={{ value: 8.3, isPositive: true }}
          gradient="from-blue-500/20 to-blue-600/10"
          delay={0.1}
        />
        
        <StatsCard
          title="Total Reviews"
          value={totalReviews}
          subtitle="Community insights"
          icon={MessageCircle}
          trend={{ value: 15.2, isPositive: true }}
          gradient="from-purple-500/20 to-purple-600/10"
          delay={0.2}
        />
        
        <StatsCard
          title="Average Rating"
          value={avgRating.toFixed(1)}
          subtitle={`${completionRate.toFixed(0)}% completion rate`}
          icon={Star}
          trend={{ value: 2.1, isPositive: true }}
          gradient="from-yellow-500/20 to-yellow-600/10"
          delay={0.3}
        />
      </motion.div>

      {/* Charts Section */}
      <motion.div 
        className="grid grid-cols-1 xl:grid-cols-2 gap-8"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.6 }}
      >
        <RatingDistributionChart data={aggregateRatingDistribution} />
        <ActivityChart data={aggregateActivityData} />
      </motion.div>

      {/* Additional Metrics Row */}
      <motion.div 
        className="grid grid-cols-1 md:grid-cols-3 gap-6"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.8 }}
      >
        <StatsCard
          title="Active Scrapers"
          value={profilesArray.filter(p => p.scraping_status === 'in_progress').length}
          subtitle="Currently updating"
          icon={Activity}
          gradient="from-green-500/20 to-green-600/10"
          delay={0}
        />
        
        <StatsCard
          title="Top Reviewer"
          value={profilesArray.length > 0 ? 
            profilesArray.reduce((prev, current) => 
              (current.total_reviews || 0) > (prev.total_reviews || 0) ? current : prev
            ).username : 'N/A'
          }
          subtitle="Most active reviewer"
          icon={Award}
          gradient="from-pink-500/20 to-pink-600/10"
          delay={0.1}
        />
        
        <StatsCard
          title="Last Update"
          value={profilesArray.length > 0 ? 
            new Date(Math.max(...profilesArray
              .filter(p => p.last_scraped_at)
              .map(p => new Date(p.last_scraped_at!).getTime())
            )).toLocaleDateString() : 'Never'
          }
          subtitle="Most recent data sync"
          icon={Calendar}
          gradient="from-indigo-500/20 to-indigo-600/10"
          delay={0.2}
        />
      </motion.div>

      {/* Profiles Grid */}
      <motion.div 
        className="space-y-6"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 1.0 }}
      >
        <div className="flex items-center justify-between">
          <h2 className="text-2xl font-bold text-white">
            Community Profiles
          </h2>
          <span className="text-white/60 text-sm">
            {profilesArray.length} {profilesArray.length === 1 ? 'profile' : 'profiles'} loaded
          </span>
        </div>

        <AnimatePresence mode="popLayout">
          {profilesArray.length > 0 ? (
            <motion.div 
              className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6"
              layout
            >
              {profilesArray.map((profile, index) => (
                <ProfileCard
                  key={profile.username}
                  profile={profile}
                  index={index}
                  onRefresh={handleRefreshProfile}
                  onDelete={handleDeleteProfile}
                  onStartScraping={handleStartScraping}
                  isRefreshing={refreshingProfile === profile.username}
                  isDeleting={deletingProfile === profile.username}
                />
              ))}
            </motion.div>
          ) : (
            <motion.div 
              className="card-cinema text-center py-16"
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: 0.3 }}
            >
              <motion.div 
                className="w-24 h-24 bg-cinema-500/20 rounded-full flex items-center justify-center mb-6 mx-auto"
                animate={{ 
                  scale: [1, 1.05, 1],
                  boxShadow: [
                    "0 0 20px rgba(229, 81, 0, 0.3)",
                    "0 0 40px rgba(229, 81, 0, 0.5)",
                    "0 0 20px rgba(229, 81, 0, 0.3)"
                  ]
                }}
                transition={{ duration: 2, repeat: Infinity }}
              >
                <FilmIcon className="w-12 h-12 text-cinema-400" />
              </motion.div>
              
              <h3 className="text-xl font-bold text-white mb-3">
                No profiles loaded yet
              </h3>
              <p className="text-white/60 mb-8 max-w-md mx-auto">
                Start building your Letterboxd community by adding profiles for analysis and tracking.
              </p>
              
              <div className="flex justify-center space-x-4">
                <motion.button 
                  onClick={() => navigate('/profiles')}
                  className="btn-primary flex items-center space-x-2"
                  whileHover={{ scale: 1.05 }}
                  whileTap={{ scale: 0.95 }}
                >
                  <PlusIcon className="w-5 h-5" />
                  <span>Add First Profile</span>
                </motion.button>
                
                <motion.button 
                  className="btn-secondary flex items-center space-x-2"
                  whileHover={{ scale: 1.05 }}
                  whileTap={{ scale: 0.95 }}
                >
                  <ChartBarIcon className="w-5 h-5" />
                  <span>View Analytics</span>
                </motion.button>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </motion.div>
    </motion.div>
  );
};

export default Dashboard;
