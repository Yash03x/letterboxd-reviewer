import React, { useState, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { 
  PlusIcon, 
  MagnifyingGlassIcon,
  UserCircleIcon,
  TrashIcon,
  ArrowPathIcon,
  ExclamationTriangleIcon,
  CheckCircleIcon
} from '@heroicons/react/24/outline';
import { 
  Users, 
  UserPlus
} from 'lucide-react';
import { profileApi, scraperApi } from '../services/api';
import LoadingSpinner from '../components/LoadingSpinner';
import ErrorMessage from '../components/ErrorMessage';
import toast, { Toaster } from 'react-hot-toast';

const ProfileManager: React.FC = () => {
  const [searchTerm, setSearchTerm] = useState('');
  const [isAddingProfile, setIsAddingProfile] = useState(false);
  const [newProfileUsername, setNewProfileUsername] = useState('');
  const [filterStatus, setFilterStatus] = useState<string>('all');
  const [deletingProfile, setDeletingProfile] = useState<string | null>(null);
  const [scrapingProfile, setScrapingProfile] = useState<string | null>(null);
  const pollIntervals = useRef<Map<string, NodeJS.Timeout>>(new Map());
  const pollTimeouts = useRef<Map<string, NodeJS.Timeout>>(new Map());

  const queryClient = useQueryClient();

  // Fetch profiles
  const { data: profiles, isLoading, error } = useQuery({
    queryKey: ['profiles'],
    queryFn: profileApi.getProfiles,
    refetchInterval: 30000, // Auto-refresh every 30 seconds
  });

  // Add profile mutation
  const addProfileMutation = useMutation({
    mutationFn: profileApi.createProfile,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['profiles'] });
      setIsAddingProfile(false);
      setNewProfileUsername('');
      toast.success('Profile added successfully!');
    },
    onError: (error: Error) => {
      toast.error(`Failed to add profile: ${error.message}`);
    },
  });

  // Delete profile mutation
  const deleteProfileMutation = useMutation({
    mutationFn: async (username: string) => {
      setDeletingProfile(username);
      const result = await profileApi.deleteProfile(username);
      return result;
    },
    onSuccess: (data, username) => {
      queryClient.invalidateQueries({ queryKey: ['profiles'] });
      toast.success('Profile deleted successfully!');
      setDeletingProfile(null);
    },
    onError: (error: Error) => {
      console.error('❌ Delete mutation error:', error);
      toast.error(`Failed to delete profile: ${error.message}`);
      setDeletingProfile(null);
    },
  });

  // Start scraping mutation with proper status polling
  const startScrapingMutation = useMutation({
    mutationFn: async (username: string) => {
      setScrapingProfile(username);
      const result = await scraperApi.scrapeProfile(username);
      return { ...result, username };
    },
    onSuccess: (data, username) => {
      queryClient.invalidateQueries({ queryKey: ['profiles'] });
      toast.success(`Started scraping for @${data.username}`);
      
      // Start polling for status instead of immediately setting to null
      pollScrapingStatus(data.username);
    },
    onError: (error: Error) => {
      console.error('❌ Scraping mutation error:', error);
      toast.error(`Failed to start scraping: ${error.message}`);
      setScrapingProfile(null);
    },
  });

  const profilesArray = Array.isArray(profiles) ? profiles : [];

  // Filter profiles based on search and status
  const filteredProfiles = profilesArray.filter(profile => {
    const matchesSearch = profile.username.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesFilter = filterStatus === 'all' || 
      (filterStatus === 'active' && profile.scraping_status === 'completed') ||
      (filterStatus === 'pending' && profile.scraping_status === 'pending') ||
      (filterStatus === 'updating' && profile.scraping_status === 'in_progress');
    
    return matchesSearch && matchesFilter;
  });

  const handleAddProfile = () => {
    if (newProfileUsername.trim()) {
      addProfileMutation.mutate(newProfileUsername.trim());
    }
  };

  const handleDeleteProfile = (username: string) => {
    if (window.confirm(`Are you sure you want to delete ${username}? This cannot be undone.`)) {
      deleteProfileMutation.mutate(username);
    }
  };

  // Cleanup function to stop polling for a specific user
  const stopPolling = (username: string) => {
    const interval = pollIntervals.current.get(username);
    const timeout = pollTimeouts.current.get(username);
    
    if (interval) {
      clearInterval(interval);
      pollIntervals.current.delete(username);
    }
    
    if (timeout) {
      clearTimeout(timeout);
      pollTimeouts.current.delete(username);
    }
  };

  // Poll scraping status until completion
  const pollScrapingStatus = async (username: string) => {
    // Clear any existing polling for this user
    stopPolling(username);
    
    const pollInterval = setInterval(async () => {
      try {
        const status = await scraperApi.getStatus(username);
        console.log(`🔄 Polling status for ${username}:`, status);
        
        // Update profiles to get latest status
        queryClient.invalidateQueries({ queryKey: ['profiles'] });
        
        // If completed, stop polling and clear loading state
        if (status.status === 'completed') {
          setScrapingProfile(null);
          toast.success(`✅ Scraping completed for @${username}`);
          stopPolling(username);
        } 
        // If failed/error, stop polling and clear loading state
        else if (status.status === 'failed' || status.status === 'error') {
          setScrapingProfile(null);
          toast.error(`❌ Scraping failed for @${username}: ${status.error_message || 'Unknown error'}`);
          stopPolling(username);
        }
        // Otherwise continue polling (in_progress, queued, etc.)
      } catch (error) {
        console.error('Error polling status:', error);
        // On error, stop polling after a few attempts to avoid infinite polling
        setScrapingProfile(null);
        stopPolling(username);
      }
    }, 3000); // Poll every 3 seconds
    
    // Store the interval reference
    pollIntervals.current.set(username, pollInterval);
    
    // Safety timeout to prevent infinite polling (max 10 minutes)
    const pollTimeout = setTimeout(() => {
      console.log('⏰ Polling timeout reached for', username);
      if (scrapingProfile === username) {
        setScrapingProfile(null);
      }
      stopPolling(username);
    }, 10 * 60 * 1000); // 10 minutes timeout
    
    // Store the timeout reference
    pollTimeouts.current.set(username, pollTimeout);
  };

  const handleStartScraping = (username: string) => {
    console.log('🎯 Starting scraping for:', username);
    console.log('📊 Current scrapingProfile state before:', scrapingProfile);
    startScrapingMutation.mutate(username);
  };

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      // Clear all polling intervals and timeouts on unmount
      pollIntervals.current.forEach((interval) => clearInterval(interval));
      pollTimeouts.current.forEach((timeout) => clearTimeout(timeout));
    };
  }, []);

  if (isLoading) return <LoadingSpinner />;
  if (error) return <ErrorMessage message="Failed to load profiles" />;

  return (
    <motion.div 
      className="space-y-8"
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.6 }}
    >
      <Toaster 
        position="top-right"
        toastOptions={{
          className: 'bg-noir-800 text-white border border-cinema-400/20',
          duration: 4000,
        }}
      />

      {/* Header */}
      <motion.div 
        className="flex items-center justify-between"
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 }}
      >
        <div>
          <div className="flex items-center space-x-3 mb-2">
            <h1 className="text-4xl font-bold text-white text-glow">
              Profile Manager
            </h1>
            {scrapingProfile && (
              <motion.div
                className="flex items-center space-x-2 px-3 py-1.5 bg-cinema-500/20 border border-cinema-400/30 rounded-lg"
                initial={{ opacity: 0, scale: 0.8 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.8 }}
              >
                <ArrowPathIcon className="w-4 h-4 text-cinema-400 animate-spin" />
                <span className="text-sm text-cinema-300">
                  @{scrapingProfile} scraping...
                </span>
              </motion.div>
            )}
          </div>
          <p className="text-white/60">
            {scrapingProfile 
              ? "Background scraping in progress - safe to add more profiles"
              : "Manage and monitor your Letterboxd profiles"
            }
          </p>
        </div>
        
        <motion.button 
          onClick={() => setIsAddingProfile(true)}
          className="btn-primary flex items-center space-x-2 relative group"
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.95 }}
          title={scrapingProfile ? "Safe to add profiles during scraping" : "Add a new Letterboxd profile"}
        >
          <UserPlus className="w-5 h-5" />
          <span>Add Profile</span>
          {scrapingProfile && (
            <motion.div
              className="w-2 h-2 bg-cinema-400 rounded-full animate-pulse ml-1"
              initial={{ scale: 0 }}
              animate={{ scale: 1 }}
              transition={{ duration: 0.3 }}
            />
          )}
          
          {/* Enhanced tooltip */}
          <div className="absolute bottom-full left-1/2 transform -translate-x-1/2 mb-2 px-3 py-2 bg-noir-900 text-white text-sm rounded-lg opacity-0 group-hover:opacity-100 transition-opacity duration-200 pointer-events-none whitespace-nowrap z-50 border border-cinema-400/20">
            {scrapingProfile 
              ? "✅ Safe to add - scraping runs in background" 
              : "Add a new Letterboxd profile to analyze"
            }
            <div className="absolute top-full left-1/2 transform -translate-x-1/2 w-0 h-0 border-l-4 border-r-4 border-t-4 border-transparent border-t-noir-900"></div>
          </div>
        </motion.button>
      </motion.div>

      {/* Controls */}
      <motion.div 
        className="flex flex-col sm:flex-row gap-4 items-center justify-between"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.4 }}
      >
        <div className="flex items-center space-x-4 flex-1">
          {/* Search */}
          <div className="relative flex-1 max-w-md">
            <MagnifyingGlassIcon className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-white/40" />
            <input
              type="text"
              placeholder="Search profiles..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="input-field pl-10 w-full"
            />
          </div>

          {/* Filter */}
          <select
            value={filterStatus}
            onChange={(e) => setFilterStatus(e.target.value)}
            className="input-field"
          >
            <option value="all">All Profiles</option>
            <option value="active">Active</option>
            <option value="pending">Pending</option>
            <option value="updating">Updating</option>
          </select>
        </div>

        <div className="text-white/60 text-sm">
          {filteredProfiles.length} of {profilesArray.length} profiles
        </div>
      </motion.div>

      {/* Add Profile Modal */}
      <AnimatePresence>
        {isAddingProfile && (
          <motion.div
            className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-[100]"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            style={{ isolation: 'isolate' }}
          >
            <motion.div
              className="card-cinema w-full max-w-md relative z-50"
              initial={{ scale: 0.9, y: 20 }}
              animate={{ scale: 1, y: 0 }}
              exit={{ scale: 0.9, y: 20 }}
            >
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-xl font-bold text-white">Add New Profile</h3>
                {scrapingProfile && (
                  <motion.div
                    className="flex items-center space-x-1 text-sm text-green-400"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                  >
                    <CheckCircleIcon className="w-4 h-4" />
                    <span>Safe to add</span>
                  </motion.div>
                )}
              </div>
              
              {scrapingProfile && (
                <motion.div
                  className="mb-4 p-3 bg-cinema-500/10 border border-cinema-400/20 rounded-lg"
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: 'auto' }}
                >
                  <div className="flex items-center space-x-2 text-sm text-cinema-200">
                    <ArrowPathIcon className="w-4 h-4 text-cinema-400 animate-spin flex-shrink-0" />
                    <span>
                      <strong>@{scrapingProfile}</strong> is scraping in the background. 
                      Adding new profiles is safe and won't interfere.
                    </span>
                  </div>
                </motion.div>
              )}
              
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-white/80 mb-2">
                    Letterboxd Username
                  </label>
                  <input
                    type="text"
                    placeholder="e.g., username"
                    value={newProfileUsername}
                    onChange={(e) => setNewProfileUsername(e.target.value)}
                    className="input-field w-full"
                    onKeyDown={(e) => e.key === 'Enter' && handleAddProfile()}
                    autoFocus
                  />
                </div>
                
                <div className="flex space-x-3">
                  <button
                    onClick={handleAddProfile}
                    disabled={!newProfileUsername.trim() || addProfileMutation.isPending}
                    className="btn-primary flex-1 flex items-center justify-center space-x-2"
                  >
                    {addProfileMutation.isPending ? (
                      <ArrowPathIcon className="w-4 h-4 animate-spin" />
                    ) : (
                      <PlusIcon className="w-4 h-4" />
                    )}
                    <span>Add Profile</span>
                  </button>
                  
                  <button
                    onClick={() => {
                      setIsAddingProfile(false);
                      setNewProfileUsername('');
                    }}
                    className="btn-secondary"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Profiles Grid */}
      <motion.div 
        className="space-y-6"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.6 }}
      >
        <AnimatePresence mode="popLayout">
          {filteredProfiles.length > 0 ? (
            <motion.div 
              className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6"
              layout
            >
              {filteredProfiles.map((profile) => (
                <div
                  key={profile.username}
                  className="card-cinema relative"
                  style={{ 
                    pointerEvents: 'auto',
                    isolation: 'isolate'
                  }}
                >
                  {/* Profile Header */}
                  <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center space-x-3">
                      <motion.div 
                        className="w-12 h-12 bg-gradient-to-br from-cinema-400 to-cinema-600 rounded-full flex items-center justify-center shadow-glow"
                        whileHover={{ rotate: 360, scale: 1.1 }}
                        transition={{ duration: 0.6, ease: "easeInOut" }}
                      >
                        <UserCircleIcon className="w-6 h-6 text-white" />
                      </motion.div>
                      
                      <div>
                        <h3 className="text-lg font-bold text-white group-hover:text-cinema-300 transition-colors">
                          @{profile.username}
                        </h3>
                        <div className={`inline-flex items-center px-2 py-1 rounded-lg text-xs font-medium border ${
                          (profile.scraping_status === 'completed' && scrapingProfile !== profile.username)
                            ? 'bg-green-500/20 text-green-400 border-green-500/30'
                            : (profile.scraping_status === 'in_progress' || scrapingProfile === profile.username)
                            ? 'bg-cinema-500/20 text-cinema-400 border-cinema-500/30'
                            : profile.scraping_status === 'error'
                            ? 'bg-red-500/20 text-red-400 border-red-500/30'
                            : 'bg-gray-500/20 text-gray-400 border-gray-500/30'
                        }`}>
                          {(profile.scraping_status === 'completed' && scrapingProfile !== profile.username) && <CheckCircleIcon className="w-3 h-3 mr-1" />}
                          {(profile.scraping_status === 'in_progress' || scrapingProfile === profile.username) && <ArrowPathIcon className="w-3 h-3 mr-1 animate-spin" />}
                          {profile.scraping_status === 'error' && <ExclamationTriangleIcon className="w-3 h-3 mr-1" />}
                          {scrapingProfile === profile.username ? '🔄 scraping...' : (profile.scraping_status || 'pending')}
                        </div>
                      </div>
                    </div>

                    {/* Actions Menu */}
                    <div className="flex items-center space-x-2">
                      <button
                        onClick={(e) => {
                          e.preventDefault();
                          e.stopPropagation();
                          handleStartScraping(profile.username);
                        }}
                        disabled={profile.scraping_status === 'in_progress' || scrapingProfile === profile.username}
                        className={`p-3 rounded-lg transition-colors disabled:opacity-50 ${
                          (profile.scraping_status === 'in_progress' || scrapingProfile === profile.username)
                            ? 'bg-cinema-500/30 cursor-not-allowed border border-cinema-400/50' 
                            : 'bg-white/10 hover:bg-cinema-500/20 border border-transparent hover:border-cinema-400/30'
                        }`}
                        title="Start scraping"
                        style={{ 
                          pointerEvents: 'auto',
                          zIndex: 10,
                          position: 'relative'
                        }}
                      >
                        <ArrowPathIcon className={`w-4 h-4 text-white ${
                          profile.scraping_status === 'in_progress' || scrapingProfile === profile.username 
                            ? 'animate-spin' 
                            : ''
                        }`} />
                      </button>
                      
                      <button
                        onClick={(e) => {
                          e.preventDefault();
                          e.stopPropagation();
                          handleDeleteProfile(profile.username);
                        }}
                        disabled={deletingProfile === profile.username}
                        className={`p-3 rounded-lg transition-colors disabled:opacity-50 ${
                          deletingProfile === profile.username 
                            ? 'bg-red-500/20 cursor-not-allowed' 
                            : 'bg-red-500/20 hover:bg-red-500/30'
                        }`}
                        title="Delete profile"
                        style={{ 
                          pointerEvents: 'auto',
                          zIndex: 10,
                          position: 'relative'
                        }}
                      >
                        <TrashIcon className={`w-4 h-4 text-red-400 ${deletingProfile === profile.username ? 'animate-pulse' : ''}`} />
                      </button>
                    </div>
                  </div>

                  {/* Stats */}
                  <div className="grid grid-cols-2 gap-3 mb-4">
                    <div className="text-center">
                      <div className="text-xl font-bold text-white">
                        {profile.total_films?.toLocaleString() || '0'}
                      </div>
                      <div className="text-xs text-white/60">Movies</div>
                    </div>
                    
                    <div className="text-center">
                      <div className="text-xl font-bold text-cinema-400">
                        {profile.avg_rating?.toFixed(1) || '0.0'}
                      </div>
                      <div className="text-xs text-white/60">Avg Rating</div>
                    </div>
                    
                    <div className="text-center">
                      <div className="text-xl font-bold text-green-400">
                        {profile.rated_films?.toLocaleString() || '0'}
                      </div>
                      <div className="text-xs text-white/60">Rated</div>
                    </div>
                    
                    <div className="text-center">
                      <div className="text-xl font-bold text-white">
                        {profile.total_reviews?.toLocaleString() || '0'}
                      </div>
                      <div className="text-xs text-white/60">Reviews</div>
                    </div>
                  </div>

                  {/* Last Updated */}
                  {profile.last_scraped_at && (
                    <div className="text-xs text-white/50 text-center">
                      Updated {new Date(profile.last_scraped_at).toLocaleDateString()}
                    </div>
                  )}

                  {/* Hover Animation Overlay */}
                  <motion.div
                    className="absolute inset-0 bg-gradient-to-br from-cinema-500/0 via-cinema-500/5 to-cinema-600/0 opacity-0 group-hover:opacity-100 transition-opacity duration-500 rounded-2xl"
                    animate={{
                      background: [
                        'linear-gradient(135deg, rgba(245,124,0,0) 0%, rgba(229,81,0,0.05) 50%, rgba(196,65,0,0) 100%)',
                        'linear-gradient(225deg, rgba(245,124,0,0) 0%, rgba(229,81,0,0.05) 50%, rgba(196,65,0,0) 100%)',
                        'linear-gradient(135deg, rgba(245,124,0,0) 0%, rgba(229,81,0,0.05) 50%, rgba(196,65,0,0) 100%)',
                      ],
                    }}
                    transition={{ duration: 3, repeat: Infinity, ease: 'linear' }}
                  />
                </div>
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
                <Users className="w-12 h-12 text-cinema-400" />
              </motion.div>
              
              <h3 className="text-xl font-bold text-white mb-3">
                {searchTerm ? 'No profiles match your search' : 'No profiles yet'}
              </h3>
              <p className="text-white/60 mb-8 max-w-md mx-auto">
                {searchTerm 
                  ? `No profiles found matching "${searchTerm}". Try adjusting your search or filters.`
                  : 'Add your first Letterboxd profile to get started with analysis and tracking.'
                }
              </p>
              
              {!searchTerm && (
                <motion.button 
                  onClick={() => setIsAddingProfile(true)}
                  className="btn-primary flex items-center space-x-2 mx-auto"
                  whileHover={{ scale: 1.05 }}
                  whileTap={{ scale: 0.95 }}
                >
                  <UserPlus className="w-5 h-5" />
                  <span>Add First Profile</span>
                </motion.button>
              )}
            </motion.div>
          )}
        </AnimatePresence>
      </motion.div>
    </motion.div>
  );
};

export default ProfileManager;