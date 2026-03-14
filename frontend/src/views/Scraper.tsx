'use client';

import React, { useEffect, useRef, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { scraperApi, type ScrapeQueueJob } from '../services/api';
import {
  MagnifyingGlassIcon,
  CheckCircleIcon,
  XCircleIcon,
  ClockIcon,
  TrashIcon,
  ArrowPathIcon,
  ExclamationTriangleIcon,
  StopIcon,
} from '@heroicons/react/24/outline';
import LoadingSpinner from '../components/LoadingSpinner';

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

const Scraper: React.FC = () => {
  const [usernames, setUsernames] = useState<string[]>(['']);
  const [showOnlyStale, setShowOnlyStale] = useState(false);
  const [scrapingJobs, setScrapingJobs] = useState<ScrapingJob[]>([]);
  const progressStreams = useRef<Map<string, EventSource>>(new Map());
  const fallbackPollTimers = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map());
  const queryClient = useQueryClient();

  // Query for available scraped profiles
  const { data: availableData, isLoading: loadingAvailable } = useQuery({
    queryKey: ['available-profiles'],
    queryFn: scraperApi.getAvailable,
    refetchInterval: 5000, // Refresh every 5 seconds
  });

  const { data: jobsData, isLoading: loadingJobs } = useQuery({
    queryKey: ['scrape-jobs', showOnlyStale],
    queryFn: () => scraperApi.getJobs(100, showOnlyStale),
    refetchInterval: 5000,
  });

  const invalidateScrapeQueries = () => {
    queryClient.invalidateQueries({ queryKey: ['scrape-jobs'] });
    queryClient.invalidateQueries({ queryKey: ['available-profiles'] });
    queryClient.invalidateQueries({ queryKey: ['profiles'] });
  };

  const getErrorMessage = (error: unknown, fallback: string) => {
    const maybeError = error as { response?: { data?: { detail?: string } } };
    return maybeError?.response?.data?.detail || fallback;
  };

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
        setScrapingJobs((prev) =>
          prev.map((job) =>
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

        if (handleTerminalStatus(status.status, username)) {
          return;
        }

        const timer = setTimeout(poll, 3000);
        fallbackPollTimers.current.set(username, timer);
      } catch (error) {
        console.error('Fallback polling error:', error);
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

        setScrapingJobs((prev) =>
          prev.map((job) =>
            job.username === username
              ? {
                  ...job,
                  status: progress.status,
                  progressPercentage: progress.progress_percentage,
                  progress:
                    progress.progress_message ||
                    progress.error_message ||
                    'Processing...',
                }
              : job
          )
        );

        if (progress.done || handleTerminalStatus(progress.status, username)) {
          stopTracking(username);
        }
      } catch (error) {
        console.error('Invalid SSE payload:', error);
      }
    };

    eventSource.onerror = () => {
      eventSource.close();
      progressStreams.current.delete(username);
      startFallbackPolling(username);
    };
  };

  useEffect(() => {
    return () => {
      progressStreams.current.forEach((source) => source.close());
      fallbackPollTimers.current.forEach((timer) => clearTimeout(timer));
      progressStreams.current.clear();
      fallbackPollTimers.current.clear();
    };
  }, []);

  // Mutation for starting scraping
  const scrapeMutation = useMutation({
    mutationFn: scraperApi.scrapeProfile,
    onSuccess: (data, username) => {
      setScrapingJobs((prev) => [
        ...prev.filter((job) => job.username !== username),
        {
          username,
          status: 'queued',
          progress: 'Queued for worker...',
          progressPercentage: 0,
          jobId: data.job_id,
          startTime: new Date().toISOString(),
        },
      ]);

      subscribeToProgress(username, data.job_id);
      invalidateScrapeQueries();
    },
    onError: (error, username) => {
      setScrapingJobs((prev) => [
        ...prev.filter((job) => job.username !== username),
        {
          username,
          status: 'error',
          progress: getErrorMessage(error, 'Failed to start scraping'),
          startTime: new Date().toISOString(),
        },
      ]);
    },
  });

  const retryMutation = useMutation({
    mutationFn: scraperApi.retryJob,
    onSuccess: (data) => {
      const username = data.job.username;
      setScrapingJobs((prev) => [
        ...prev.filter((job) => job.username !== username),
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
    onError: (error) => {
      console.error('Retry enqueue error:', getErrorMessage(error, 'Failed to enqueue retry task'));
      invalidateScrapeQueries();
    },
  });

  const cancelMutation = useMutation({
    mutationFn: scraperApi.cancelJob,
    onSuccess: () => {
      invalidateScrapeQueries();
    },
  });

  const resetStaleMutation = useMutation({
    mutationFn: scraperApi.resetStaleJobs,
    onSuccess: () => {
      invalidateScrapeQueries();
    },
  });

  const handleAddUsername = () => {
    setUsernames([...usernames, '']);
  };

  const handleRemoveUsername = (index: number) => {
    setUsernames(usernames.filter((_, i) => i !== index));
  };

  const handleUsernameChange = (index: number, value: string) => {
    const newUsernames = [...usernames];
    newUsernames[index] = value;
    setUsernames(newUsernames);
  };

  const handleStartScraping = () => {
    const validUsernames = usernames.filter(u => u.trim());
    validUsernames.forEach(username => {
      scrapeMutation.mutate(username);
    });
  };

  const formatAge = (seconds?: number | null) => {
    if (seconds == null) {
      return 'n/a';
    }
    if (seconds < 60) {
      return `${seconds}s`;
    }
    const minutes = Math.floor(seconds / 60);
    const remSeconds = seconds % 60;
    if (minutes < 60) {
      return `${minutes}m ${remSeconds}s`;
    }
    const hours = Math.floor(minutes / 60);
    const remMinutes = minutes % 60;
    return `${hours}h ${remMinutes}m`;
  };

  const statusLabelClass = (job: ScrapeQueueJob) => {
    if (job.is_stale) {
      return 'bg-red-500/20 text-red-300 border border-red-400/40';
    }
    if (job.status === 'in_progress') {
      return 'bg-blue-500/20 text-blue-300 border border-blue-400/40';
    }
    if (job.status === 'queued') {
      return 'bg-amber-500/20 text-amber-300 border border-amber-400/40';
    }
    if (job.status === 'completed') {
      return 'bg-green-500/20 text-green-300 border border-green-400/40';
    }
    if (job.status === 'failed' || job.status === 'error') {
      return 'bg-red-500/20 text-red-300 border border-red-400/40';
    }
    return 'bg-white/10 text-white/70 border border-white/20';
  };

  // ZIP upload handler removed

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <CheckCircleIcon className="h-5 w-5 text-green-500" />;
      case 'error':
        return <XCircleIcon className="h-5 w-5 text-red-500" />;
      case 'in_progress':
        return <div className="h-5 w-5 animate-spin rounded-full border-b-2 border-blue-500" />;
      default:
        return <ClockIcon className="h-5 w-5 text-gray-400" />;
    }
  };

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-4xl font-bold text-white text-glow">Profile Scraper</h1>
        <p className="mt-2 text-white/70">
          Scrape Letterboxd profiles to analyze movie data
        </p>
      </div>

      {/* ZIP Upload removed - use Profiles page for ZIP uploads */}

      {/* Scraper Section */}
      <div className="card-cinema">
        <h2 className="text-2xl font-bold text-white mb-6">
          Scrape Profiles
        </h2>
        
        <div className="space-y-4">
          {usernames.map((username, index) => (
            <div key={index} className="flex items-center space-x-3">
              <input
                type="text"
                value={username}
                onChange={(e) => handleUsernameChange(index, e.target.value)}
                placeholder="Enter Letterboxd username"
                className="input-field flex-1"
              />
              {usernames.length > 1 && (
                <button
                  onClick={() => handleRemoveUsername(index)}
                  className="p-2 text-red-500 hover:text-red-700"
                >
                  <TrashIcon className="h-5 w-5" />
                </button>
              )}
            </div>
          ))}
          
          <div className="flex justify-between items-center">
            <button
              onClick={handleAddUsername}
              className="btn-secondary"
            >
              Add Another Username
            </button>
            
            <button
              onClick={handleStartScraping}
              disabled={scrapeMutation.isPending || !usernames.some(u => u.trim())}
              className="btn-primary flex items-center space-x-2"
            >
              <MagnifyingGlassIcon className="h-5 w-5" />
              <span>Start Scraping</span>
            </button>
          </div>
        </div>
      </div>

      {/* Scraping Progress */}
      {scrapingJobs.length > 0 && (
        <div className="card-cinema">
          <h2 className="text-2xl font-bold text-white mb-6">
            Scraping Progress
          </h2>
          <div className="space-y-3">
            {scrapingJobs.map((job) => (
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
            <p className="text-sm text-white/60">
              Running, queued, stale and failed jobs with quick recovery actions
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowOnlyStale((prev) => !prev)}
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
            {jobsData.jobs.map((job) => (
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
                      Age: {formatAge(job.age_seconds)} {job.retry_count ? `• Retries: ${job.retry_count}` : ''}
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

      {/* Available Profiles */}
      {availableData?.available_profiles && availableData.available_profiles.length > 0 && (
        <div className="card-cinema">
          <h2 className="text-2xl font-bold text-white mb-6">
            Available Scraped Profiles
          </h2>
          {loadingAvailable ? (
            <LoadingSpinner size="sm" message="Loading profiles..." />
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {availableData.available_profiles.map((profile) => (
                <div key={profile.username} className="p-4 bg-noir-800/50 border border-cinema-400/20 rounded-lg hover:border-cinema-400/40 transition-colors">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="font-medium text-white">{profile.username}</p>
                      <p className="text-sm text-white/60">
                        Scraped: {new Date(profile.scraped_at).toLocaleDateString()}
                      </p>
                    </div>
                    <CheckCircleIcon className="h-5 w-5 text-green-500" />
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default Scraper;
