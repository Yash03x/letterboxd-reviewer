import React, { useState, useRef } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { scraperApi, profileApi } from '../services/api';
import { 
  MagnifyingGlassIcon, 
  CheckCircleIcon, 
  XCircleIcon, 
  ClockIcon,
  TrashIcon
} from '@heroicons/react/24/outline';
import LoadingSpinner from '../components/LoadingSpinner';
import ErrorMessage from '../components/ErrorMessage';

interface ScrapingJob {
  username: string;
  status: 'pending' | 'queued' | 'in_progress' | 'completed' | 'failed' | 'error';
  progress: string;
  startTime?: string;
}

const Scraper: React.FC = () => {
  const [usernames, setUsernames] = useState<string[]>(['']);
  const [scrapingJobs, setScrapingJobs] = useState<ScrapingJob[]>([]);
  // Removed file input ref as ZIP upload is no longer supported
  const queryClient = useQueryClient();

  // Query for available scraped profiles
  const { data: availableData, isLoading: loadingAvailable } = useQuery({
    queryKey: ['available-profiles'],
    queryFn: scraperApi.getAvailable,
    refetchInterval: 5000, // Refresh every 5 seconds
  });

  // Mutation for starting scraping
  const scrapeMutation = useMutation({
    mutationFn: scraperApi.scrapeProfile,
    onSuccess: (data, username) => {
      setScrapingJobs(prev => [
        ...prev.filter(job => job.username !== username),
        {
          username,
          status: 'in_progress',
          progress: 'Starting scraper...',
          startTime: new Date().toISOString(),
        }
      ]);
      // Start polling for status
      pollStatus(username);
    },
    onError: (error, username) => {
      setScrapingJobs(prev => 
        prev.map(job => 
          job.username === username 
            ? { ...job, status: 'error', progress: 'Failed to start scraping' }
            : job
        )
      );
    },
  });

  // ZIP upload functionality removed - use scraping instead

  // Poll scraping status
  const pollStatus = async (username: string) => {
    const poll = async () => {
      try {
        const status = await scraperApi.getStatus(username);
        setScrapingJobs(prev => 
          prev.map(job => 
            job.username === username 
              ? { ...job, status: status.status, progress: status.progress_message || status.progress || 'Processing...' }
              : job
          )
        );

        if (status.status === 'completed' || status.status === 'error' || status.status === 'failed') {
          queryClient.invalidateQueries({ queryKey: ['available-profiles'] });
          queryClient.invalidateQueries({ queryKey: ['profiles'] });
          return; // Stop polling
        }

        // Continue polling if still in progress
        setTimeout(poll, 2000);
      } catch (error) {
        console.error('Polling error:', error);
        setTimeout(poll, 5000); // Retry after longer delay
      }
    };

    setTimeout(poll, 2000); // Start polling after 2 seconds
  };

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
                    <p className="text-sm text-white/60">{job.progress}</p>
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
