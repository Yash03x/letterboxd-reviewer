'use client';

import React, { useState, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useSearchParams, useRouter } from 'next/navigation';
import {
  PlusIcon,
  MagnifyingGlassIcon,
  UserCircleIcon,
  TrashIcon,
  ArrowPathIcon,
  ExclamationTriangleIcon,
  CheckCircleIcon,
  XCircleIcon,
  ClockIcon,
  StopIcon,
} from '@heroicons/react/24/outline';
import { Users, UserPlus } from 'lucide-react';
import { profileApi, scraperApi, type ScrapeQueueJob } from '../services/api';
import LoadingSpinner from '../components/LoadingSpinner';
import ErrorMessage from '../components/ErrorMessage';
import toast, { Toaster } from 'react-hot-toast';

interface ScrapingJob {
  username: string;
  status: 'pending' | 'queued' | 'in_progress' | 'completed' | 'failed' | 'error';
  progress: string;
  progressPercentage?: number;
  jobId?: number;
  startTime?: string;
}

interface ScrapeProgressEvent {
  id: number;
  status: 'pending' | 'queued' | 'in_progress' | 'completed' | 'failed' | 'error';
  progress_message?: string;
  progress_percentage?: number;
  started_at?: string;
  error_message?: string;
  done?: boolean;
  timeout?: boolean;
}

const ProfileManager: React.FC = () => {
  const searchParams = useSearchParams();
  const router = useRouter();

  const [searchTerm, setSearchTerm] = useState('');
  const [isAddingProfile, setIsAddingProfile] = useState(false);
  const [newProfileUsername, setNewProfileUsername] = useState('');
  const [filterStatus, setFilterStatus] = useState<string>('all');
  const [deletingProfile, setDeletingProfile] = useState<string | null>(null);
  const [scrapingProfile, setScrapingProfile] = useState<string | null>(null);
  const [showOnlyStale, setShowOnlyStale] = useState(false);
  const [scrapingJobs, setScrapingJobs] = useState<ScrapingJob[]>([]);

  const pollIntervals = useRef<Map<string, NodeJS.Timeout>>(new Map());
  const pollTimeouts = useRef<Map<string, NodeJS.Timeout>>(new Map());
  const progressStreams = useRef<Map<string, EventSource>>(new Map());
  const fallbackPollTimers = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map());
  const subscribedUsernames = useRef<Set<string>>(new Set());

  const queryClient = useQueryClient();

  // Open add modal if ?add=true is in URL
  useEffect(() => {
    if (searchParams.get('add') === 'true') {
      setIsAddingProfile(true);
      router.replace('/profiles');
    }
  }, [searchParams, router]);

  const { data: profiles, isLoading, error } = useQuery({
    queryKey: ['profiles'],
    queryFn: profileApi.getProfiles,
    refetchInterval: 30000,
  });

  const { data: jobsData, isLoading: loadingJobs } = useQuery({
    queryKey: ['scrape-jobs', showOnlyStale],
    queryFn: () => scraperApi.getJobs(100, showOnlyStale),
    refetchInterval: 5000,
  });

  const invalidateScrapeQueries = () => {
    queryClient.invalidateQueries({ queryKey: ['scrape-jobs'] });
    queryClient.invalidateQueries({ queryKey: ['profiles'] });
  };

  // ── SSE / progress tracking ──────────────────────────────────────────────

  const stopTracking = (username: string) => {
    const activeStream = progressStreams.current.get(username);
    if (activeStream) {
      activeStream.close();
      progressStreams.current.delete(username);
    }
    const timer = fallbackPollTimers.current.get(username);
    if (timer) {
      clearTimeout(timer);
      fallbackPollTimers.current.delete(username);
    }
    subscribedUsernames.current.delete(username);
  };

  const handleTerminalStatus = (status: string, username: string) => {
    if (status === 'completed' || status === 'error' || status === 'failed') {
      stopTracking(username);
      invalidateScrapeQueries();
      return true;
    }
    return false;
  };

  const startFallbackPolling = (username: string) => {
    const poll = async () => {
      try {
        const status = await scraperApi.getStatus(username);
        setScrapingJobs(prev =>
          prev.map(job =>
            job.username === username
              ? {
                  ...job,
                  status: status.status,
                  progressPercentage: status.progress_percentage,
                  progress: status.progress_message || status.progress || 'Processing...',
                }
              : job
          )
        );
        if (handleTerminalStatus(status.status, username)) return;
        const timer = setTimeout(poll, 3000);
        fallbackPollTimers.current.set(username, timer);
      } catch {
        const timer = setTimeout(poll, 5000);
        fallbackPollTimers.current.set(username, timer);
      }
    };
    const timer = setTimeout(poll, 1500);
    fallbackPollTimers.current.set(username, timer);
  };

  const subscribeToProgress = (username: string, jobId: number) => {
    stopTracking(username);
    const streamUrl = scraperApi.getProgressStreamUrl(jobId);
    const eventSource = new EventSource(streamUrl);
    progressStreams.current.set(username, eventSource);

    eventSource.onmessage = (event: MessageEvent<string>) => {
      try {
        const progress = JSON.parse(event.data) as ScrapeProgressEvent;
        setScrapingJobs(prev =>
          prev.map(job =>
            job.username === username
              ? {
                  ...job,
                  status: progress.status,
                  progressPercentage: progress.progress_percentage,
                  progress: progress.progress_message || progress.error_message || 'Processing...',
                }
              : job
          )
        );
        if (progress.done || handleTerminalStatus(progress.status, username)) {
          stopTracking(username);
        }
      } catch {
        // ignore malformed SSE
      }
    };

    eventSource.onerror = () => {
      eventSource.close();
      progressStreams.current.delete(username);
      startFallbackPolling(username);
    };
  };

  // Auto-subscribe to active jobs (e.g. started from another page)
  useEffect(() => {
    if (!jobsData?.jobs) return;
    jobsData.jobs
      .filter(j => j.status === 'in_progress' || j.status === 'queued')
      .forEach(job => {
        if (subscribedUsernames.current.has(job.username)) return;
        subscribedUsernames.current.add(job.username);
        setScrapingJobs(prev => [
          ...prev.filter(sj => sj.username !== job.username),
          {
            username: job.username,
            status: job.status,
            progress: job.progress_message || 'Processing...',
            progressPercentage: job.progress_percentage ?? 0,
            jobId: job.id,
            startTime: job.queued_at ?? undefined,
          },
        ]);
        subscribeToProgress(job.username, job.id);
      });
  }, [jobsData]);

  // Restore scraping badge on mount if a profile is still in_progress
  useEffect(() => {
    if (!profiles) return;
    const profilesArr = Array.isArray(profiles) ? profiles : [];
    const inProgress = profilesArr.find(p => p.scraping_status === 'in_progress');
    if (inProgress && !scrapingProfile && !pollIntervals.current.has(inProgress.username)) {
      setScrapingProfile(inProgress.username);
      pollScrapingStatus(inProgress.username);
    }
  }, [profiles]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      pollIntervals.current.forEach(i => clearInterval(i));
      pollTimeouts.current.forEach(t => clearTimeout(t));
      progressStreams.current.forEach(s => s.close());
      fallbackPollTimers.current.forEach(t => clearTimeout(t));
      subscribedUsernames.current.clear();
    };
  }, []);

  // ── Mutations ────────────────────────────────────────────────────────────

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

  const deleteProfileMutation = useMutation({
    mutationFn: async (username: string) => {
      setDeletingProfile(username);
      return profileApi.deleteProfile(username);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['profiles'] });
      toast.success('Profile deleted successfully!');
      setDeletingProfile(null);
    },
    onError: (error: Error) => {
      toast.error(`Failed to delete profile: ${error.message}`);
      setDeletingProfile(null);
    },
  });

  const startScrapingMutation = useMutation({
    mutationFn: async (username: string) => {
      setScrapingProfile(username);
      const result = await scraperApi.scrapeProfile(username);
      return { ...result, username };
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['profiles'] });
      toast.success(`Started scraping for @${data.username}`);
      pollScrapingStatus(data.username);
    },
    onError: (error: Error) => {
      toast.error(`Failed to start scraping: ${error.message}`);
      setScrapingProfile(null);
    },
  });

  const retryMutation = useMutation({
    mutationFn: scraperApi.retryJob,
    onSuccess: (data) => {
      const username = data.job.username;
      setScrapingJobs(prev => [
        ...prev.filter(job => job.username !== username),
        {
          username,
          status: 'queued',
          progress: data.job.progress_message || 'Queued for retry...',
          progressPercentage: data.job.progress_percentage ?? 0,
          jobId: data.job.id,
          startTime: new Date().toISOString(),
        },
      ]);
      subscribeToProgress(username, data.job.id);
      invalidateScrapeQueries();
    },
    onError: () => invalidateScrapeQueries(),
  });

  const cancelMutation = useMutation({
    mutationFn: scraperApi.cancelJob,
    onSuccess: () => invalidateScrapeQueries(),
  });

  const resetStaleMutation = useMutation({
    mutationFn: scraperApi.resetStaleJobs,
    onSuccess: () => invalidateScrapeQueries(),
  });

  // ── Polling (profile card status) ───────────────────────────────────────

  const stopPolling = (username: string) => {
    const interval = pollIntervals.current.get(username);
    const timeout = pollTimeouts.current.get(username);
    if (interval) { clearInterval(interval); pollIntervals.current.delete(username); }
    if (timeout) { clearTimeout(timeout); pollTimeouts.current.delete(username); }
  };

  const pollScrapingStatus = (username: string) => {
    stopPolling(username);
    const pollInterval = setInterval(async () => {
      try {
        const status = await scraperApi.getStatus(username);
        queryClient.invalidateQueries({ queryKey: ['profiles'] });
        if (status.status === 'completed') {
          setScrapingProfile(null);
          toast.success(`✅ Scraping completed for @${username}`);
          stopPolling(username);
        } else if (status.status === 'failed' || status.status === 'error') {
          setScrapingProfile(null);
          toast.error(`❌ Scraping failed for @${username}: ${status.error_message || 'Unknown error'}`);
          stopPolling(username);
        }
      } catch {
        setScrapingProfile(null);
        stopPolling(username);
      }
    }, 3000);
    pollIntervals.current.set(username, pollInterval);
    const pollTimeout = setTimeout(() => {
      setScrapingProfile(null);
      stopPolling(username);
    }, 10 * 60 * 1000);
    pollTimeouts.current.set(username, pollTimeout);
  };

  // ── Helpers ──────────────────────────────────────────────────────────────

  const profilesArray = Array.isArray(profiles) ? profiles : [];

  const filteredProfiles = profilesArray.filter(profile => {
    const matchesSearch = profile.username.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesFilter =
      filterStatus === 'all' ||
      (filterStatus === 'active' && profile.scraping_status === 'completed') ||
      (filterStatus === 'pending' && profile.scraping_status === 'pending') ||
      (filterStatus === 'updating' && profile.scraping_status === 'in_progress');
    return matchesSearch && matchesFilter;
  });

  const formatAge = (seconds?: number | null) => {
    if (seconds == null) return 'n/a';
    if (seconds < 60) return `${seconds}s`;
    const minutes = Math.floor(seconds / 60);
    const remSeconds = seconds % 60;
    if (minutes < 60) return `${minutes}m ${remSeconds}s`;
    const hours = Math.floor(minutes / 60);
    return `${hours}h ${Math.floor(minutes % 60)}m`;
  };

  const statusLabelClass = (job: ScrapeQueueJob) => {
    if (job.is_stale) return 'bg-red-500/20 text-red-300 border border-red-400/40';
    if (job.status === 'in_progress') return 'bg-blue-500/20 text-blue-300 border border-blue-400/40';
    if (job.status === 'queued') return 'bg-amber-500/20 text-amber-300 border border-amber-400/40';
    if (job.status === 'completed') return 'bg-green-500/20 text-green-300 border border-green-400/40';
    if (job.status === 'failed' || job.status === 'error') return 'bg-red-500/20 text-red-300 border border-red-400/40';
    return 'bg-white/10 text-white/70 border border-white/20';
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed': return <CheckCircleIcon className="h-5 w-5 text-green-500" />;
      case 'error':
      case 'failed': return <XCircleIcon className="h-5 w-5 text-red-500" />;
      case 'in_progress': return <div className="h-5 w-5 animate-spin rounded-full border-b-2 border-blue-500" />;
      default: return <ClockIcon className="h-5 w-5 text-gray-400" />;
    }
  };

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
            <h1 className="text-4xl font-bold text-white text-glow">Profiles</h1>
            {scrapingProfile && (
              <motion.div
                className="flex items-center space-x-2 px-3 py-1.5 bg-cinema-500/20 border border-cinema-400/30 rounded-lg"
                initial={{ opacity: 0, scale: 0.8 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.8 }}
              >
                <ArrowPathIcon className="w-4 h-4 text-cinema-400 animate-spin" />
                <span className="text-sm text-cinema-300">@{scrapingProfile} scraping...</span>
              </motion.div>
            )}
          </div>
          <p className="text-white/60">
            {scrapingProfile
              ? 'Background scraping in progress — safe to add more profiles'
              : 'Manage and monitor your Letterboxd profiles'}
          </p>
        </div>

        <motion.button
          onClick={() => setIsAddingProfile(true)}
          className="btn-primary flex items-center space-x-2 relative group"
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.95 }}
        >
          <UserPlus className="w-5 h-5" />
          <span>Add Profile</span>
          {scrapingProfile && (
            <motion.div
              className="w-2 h-2 bg-cinema-400 rounded-full animate-pulse ml-1"
              initial={{ scale: 0 }}
              animate={{ scale: 1 }}
            />
          )}
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
          <div className="relative flex-1 max-w-md">
            <MagnifyingGlassIcon className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-white/40" />
            <input
              type="text"
              placeholder="Search profiles..."
              value={searchTerm}
              onChange={e => setSearchTerm(e.target.value)}
              className="input-field pl-10 w-full"
            />
          </div>
          <select
            value={filterStatus}
            onChange={e => setFilterStatus(e.target.value)}
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
              </div>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-white/80 mb-2">
                    Letterboxd Username
                  </label>
                  <input
                    type="text"
                    placeholder="e.g., username"
                    value={newProfileUsername}
                    onChange={e => setNewProfileUsername(e.target.value)}
                    className="input-field w-full"
                    onKeyDown={e => e.key === 'Enter' && addProfileMutation.mutate(newProfileUsername.trim())}
                    autoFocus
                  />
                </div>
                <div className="flex space-x-3">
                  <button
                    onClick={() => addProfileMutation.mutate(newProfileUsername.trim())}
                    disabled={!newProfileUsername.trim() || addProfileMutation.isPending}
                    className="btn-primary flex-1 flex items-center justify-center space-x-2"
                  >
                    {addProfileMutation.isPending
                      ? <ArrowPathIcon className="w-4 h-4 animate-spin" />
                      : <PlusIcon className="w-4 h-4" />}
                    <span>Add Profile</span>
                  </button>
                  <button
                    onClick={() => { setIsAddingProfile(false); setNewProfileUsername(''); }}
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
            <motion.div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6" layout>
              {filteredProfiles.map(profile => (
                <div key={profile.username} className="card-cinema relative" style={{ isolation: 'isolate' }}>
                  <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center space-x-3">
                      <motion.div
                        className="w-12 h-12 bg-gradient-to-br from-cinema-400 to-cinema-600 rounded-full flex items-center justify-center shadow-glow"
                        whileHover={{ rotate: 360, scale: 1.1 }}
                        transition={{ duration: 0.6, ease: 'easeInOut' }}
                      >
                        <UserCircleIcon className="w-6 h-6 text-white" />
                      </motion.div>
                      <div>
                        <h3 className="text-lg font-bold text-white">@{profile.username}</h3>
                        <div className={`inline-flex items-center px-2 py-1 rounded-lg text-xs font-medium border ${
                          profile.scraping_status === 'completed' && scrapingProfile !== profile.username
                            ? 'bg-green-500/20 text-green-400 border-green-500/30'
                            : profile.scraping_status === 'in_progress' || scrapingProfile === profile.username
                            ? 'bg-cinema-500/20 text-cinema-400 border-cinema-500/30'
                            : profile.scraping_status === 'error'
                            ? 'bg-red-500/20 text-red-400 border-red-500/30'
                            : 'bg-gray-500/20 text-gray-400 border-gray-500/30'
                        }`}>
                          {profile.scraping_status === 'completed' && scrapingProfile !== profile.username && <CheckCircleIcon className="w-3 h-3 mr-1" />}
                          {(profile.scraping_status === 'in_progress' || scrapingProfile === profile.username) && <ArrowPathIcon className="w-3 h-3 mr-1 animate-spin" />}
                          {profile.scraping_status === 'error' && <ExclamationTriangleIcon className="w-3 h-3 mr-1" />}
                          {scrapingProfile === profile.username ? '🔄 scraping...' : (profile.scraping_status || 'pending')}
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center space-x-2">
                      <button
                        onClick={() => startScrapingMutation.mutate(profile.username)}
                        disabled={profile.scraping_status === 'in_progress' || scrapingProfile === profile.username}
                        className={`p-3 rounded-lg transition-colors disabled:opacity-50 ${
                          profile.scraping_status === 'in_progress' || scrapingProfile === profile.username
                            ? 'bg-cinema-500/30 cursor-not-allowed border border-cinema-400/50'
                            : 'bg-white/10 hover:bg-cinema-500/20 border border-transparent hover:border-cinema-400/30'
                        }`}
                        title="Re-scrape profile"
                        style={{ pointerEvents: 'auto', zIndex: 10, position: 'relative' }}
                      >
                        <ArrowPathIcon className={`w-4 h-4 text-white ${
                          profile.scraping_status === 'in_progress' || scrapingProfile === profile.username ? 'animate-spin' : ''
                        }`} />
                      </button>
                      <button
                        onClick={() => {
                          if (window.confirm(`Delete ${profile.username}? This cannot be undone.`)) {
                            deleteProfileMutation.mutate(profile.username);
                          }
                        }}
                        disabled={deletingProfile === profile.username}
                        className="p-3 rounded-lg bg-red-500/20 hover:bg-red-500/30 transition-colors disabled:opacity-50"
                        title="Delete profile"
                        style={{ pointerEvents: 'auto', zIndex: 10, position: 'relative' }}
                      >
                        <TrashIcon className={`w-4 h-4 text-red-400 ${deletingProfile === profile.username ? 'animate-pulse' : ''}`} />
                      </button>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-3 mb-4">
                    <div className="text-center">
                      <div className="text-xl font-bold text-white">{profile.total_films?.toLocaleString() || '0'}</div>
                      <div className="text-xs text-white/60">Movies</div>
                    </div>
                    <div className="text-center">
                      <div className="text-xl font-bold text-cinema-400">{profile.avg_rating?.toFixed(1) || '0.0'}</div>
                      <div className="text-xs text-white/60">Avg Rating</div>
                    </div>
                    <div className="text-center">
                      <div className="text-xl font-bold text-green-400">{profile.rated_films?.toLocaleString() || '0'}</div>
                      <div className="text-xs text-white/60">Rated</div>
                    </div>
                    <div className="text-center">
                      <div className="text-xl font-bold text-white">{profile.total_reviews?.toLocaleString() || '0'}</div>
                      <div className="text-xs text-white/60">Reviews</div>
                    </div>
                  </div>

                  {profile.last_scraped_at && (
                    <div className="text-xs text-white/50 text-center">
                      Updated {new Date(profile.last_scraped_at).toLocaleDateString()}
                    </div>
                  )}

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
                  boxShadow: ['0 0 20px rgba(229,81,0,0.3)', '0 0 40px rgba(229,81,0,0.5)', '0 0 20px rgba(229,81,0,0.3)'],
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
                  ? `No profiles found matching "${searchTerm}".`
                  : 'Add your first Letterboxd profile to get started.'}
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

      {/* Scraping Progress (SSE-tracked active jobs) */}
      {scrapingJobs.length > 0 && (
        <div className="card-cinema">
          <h2 className="text-2xl font-bold text-white mb-6">Scraping Progress</h2>
          <div className="space-y-3">
            {scrapingJobs.map(job => (
              <div key={job.username} className="flex items-center justify-between p-4 bg-noir-800/50 border border-cinema-400/20 rounded-lg">
                <div className="flex items-center space-x-3">
                  {getStatusIcon(job.status)}
                  <div>
                    <p className="font-medium text-white">{job.username}</p>
                    <p className="text-sm text-white/60">
                      {job.progress}
                      {typeof job.progressPercentage === 'number' ? ` (${Math.round(job.progressPercentage)}%)` : ''}
                    </p>
                  </div>
                </div>
                <div className="text-sm text-white/50">
                  {job.startTime && new Date(job.startTime).toLocaleTimeString()}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Queue Monitor */}
      <div className="card-cinema">
        <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
          <div>
            <h2 className="text-2xl font-bold text-white">Queue Monitor</h2>
            <p className="text-sm text-white/60">Running, queued, stale and failed jobs</p>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowOnlyStale(prev => !prev)}
              className={`px-3 py-2 text-sm rounded-lg border transition-colors ${
                showOnlyStale
                  ? 'bg-red-500/20 border-red-400/40 text-red-300'
                  : 'bg-white/5 border-white/20 text-white/70'
              }`}
            >
              {showOnlyStale ? 'Showing Stale Only' : 'Show Stale Only'}
            </button>
            <button
              onClick={() => resetStaleMutation.mutate(undefined)}
              disabled={resetStaleMutation.isPending}
              className="btn-secondary flex items-center space-x-2"
            >
              <ExclamationTriangleIcon className="h-4 w-4" />
              <span>{resetStaleMutation.isPending ? 'Resetting…' : 'Reset Stale Jobs'}</span>
            </button>
          </div>
        </div>

        {jobsData?.counts && (
          <div className="grid grid-cols-2 md:grid-cols-6 gap-3 mb-5">
            <div className="p-3 rounded-lg bg-white/5 border border-white/10 text-white/80 text-sm">Total: {jobsData.counts.total}</div>
            <div className="p-3 rounded-lg bg-amber-500/10 border border-amber-400/30 text-amber-200 text-sm">Queued: {jobsData.counts.queued}</div>
            <div className="p-3 rounded-lg bg-blue-500/10 border border-blue-400/30 text-blue-200 text-sm">Running: {jobsData.counts.in_progress}</div>
            <div className="p-3 rounded-lg bg-red-500/10 border border-red-400/30 text-red-200 text-sm">Stale: {jobsData.counts.stale}</div>
            <div className="p-3 rounded-lg bg-green-500/10 border border-green-400/30 text-green-200 text-sm">Completed: {jobsData.counts.completed}</div>
            <div className="p-3 rounded-lg bg-red-500/10 border border-red-400/30 text-red-200 text-sm">Failed: {jobsData.counts.failed}</div>
          </div>
        )}

        {loadingJobs ? (
          <LoadingSpinner size="sm" message="Loading queue..." />
        ) : jobsData?.jobs?.length ? (
          <div className="space-y-3">
            {jobsData.jobs.map(job => (
              <div key={job.id} className="p-4 bg-noir-800/50 border border-cinema-400/20 rounded-lg">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="text-white font-semibold">{job.username}</span>
                      <span className={`px-2 py-0.5 text-xs rounded-full ${statusLabelClass(job)}`}>
                        {job.is_stale ? 'stale' : job.status}
                      </span>
                      <span className="text-xs text-white/40">job #{job.id}</span>
                    </div>
                    <p className="text-sm text-white/70">
                      {job.status === 'failed'
                        ? (job.error_message || job.progress_message || 'Job failed')
                        : (job.progress_message || job.error_message || 'No progress message')}
                      {typeof job.progress_percentage === 'number' ? ` (${Math.round(job.progress_percentage)}%)` : ''}
                    </p>
                    <p className="text-xs text-white/40">
                      Age: {formatAge(job.age_seconds)}{job.retry_count ? ` • Retries: ${job.retry_count}` : ''}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    {(job.status === 'failed' || job.status === 'completed' || job.is_stale) && (
                      <button
                        onClick={() => retryMutation.mutate(job.id)}
                        disabled={retryMutation.isPending}
                        className="btn-secondary flex items-center gap-1"
                      >
                        <ArrowPathIcon className="h-4 w-4" />
                        <span>Retry</span>
                      </button>
                    )}
                    {(job.status === 'queued' || job.status === 'in_progress') && (
                      <button
                        onClick={() => cancelMutation.mutate(job.id)}
                        disabled={cancelMutation.isPending}
                        className="px-3 py-2 rounded-lg bg-red-500/20 border border-red-400/40 text-red-300 hover:bg-red-500/30 transition-colors flex items-center gap-1"
                      >
                        <StopIcon className="h-4 w-4" />
                        <span>{job.is_stale ? 'Unlock' : 'Cancel'}</span>
                      </button>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-white/60 text-sm">No jobs to display.</p>
        )}
      </div>
    </motion.div>
  );
};

export default ProfileManager;
