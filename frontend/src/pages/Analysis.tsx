import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { profileApi } from '../services/api';
import { UserIcon } from '@heroicons/react/24/outline';
import LoadingSpinner from '../components/LoadingSpinner';
import ErrorMessage from '../components/ErrorMessage';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts';

const Analysis: React.FC = () => {
  const [selectedProfile, setSelectedProfile] = useState<string>('');
  
  // Get all profiles
  const { data: profiles, isLoading: loadingProfiles } = useQuery({
    queryKey: ['profiles'],
    queryFn: profileApi.getProfiles,
  });

  // Get analysis for selected profile
  const { data: analysis, isLoading: loadingAnalysis, error: analysisError } = useQuery({
    queryKey: ['analysis', selectedProfile],
    queryFn: () => profileApi.getAnalysis(selectedProfile),
    enabled: !!selectedProfile,
  });

  const COLORS = ['#0088FE', '#00C49F', '#FFBB28', '#FF8042', '#8884D8'];

  // Prepare rating distribution data for charts
  const ratingData = analysis?.rating_distribution 
    ? Object.entries(analysis.rating_distribution).map(([rating, count]) => ({
        rating: `${rating} stars`,
        count: count as number,
      }))
    : [];

  if (loadingProfiles) return <LoadingSpinner message="Loading profiles..." />;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-gray-900">Analysis</h1>
        <p className="mt-2 text-gray-600">
          Detailed analysis and insights from Letterboxd profiles
        </p>
      </div>

      {/* Profile Selection */}
      <div className="card">
        <h2 className="text-xl font-semibold text-gray-900 mb-4">
          Select Profile to Analyze
        </h2>
        {profiles && profiles.length > 0 ? (
          <select
            value={selectedProfile}
            onChange={(e) => setSelectedProfile(e.target.value)}
            className="block w-full border border-gray-300 rounded-md px-3 py-2 focus:ring-primary-500 focus:border-primary-500"
          >
            <option value="">Choose a profile...</option>
            {profiles.map((profile) => (
              <option key={profile.username} value={profile.username}>
                {profile.username} ({profile.total_films} movies, {profile.total_reviews} reviews)
              </option>
            ))}
          </select>
        ) : (
          <div className="text-center py-6">
            <UserIcon className="mx-auto h-12 w-12 text-gray-400" />
            <p className="mt-2 text-gray-500">No profiles available for analysis</p>
            <p className="text-sm text-gray-400">Upload data or scrape profiles first</p>
          </div>
        )}
      </div>

      {/* Analysis Results */}
      {selectedProfile && (
        <>
          {loadingAnalysis && (
            <LoadingSpinner message="Analyzing profile data..." />
          )}

          {analysisError && (
            <ErrorMessage message="Failed to load analysis data" />
          )}

          {analysis && (
            <div className="space-y-6">
              {/* Profile Summary */}
              <div className="card">
                <h2 className="text-xl font-semibold text-gray-900 mb-4">
                  Profile Summary: {analysis.username}
                </h2>
                <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
                  <div className="text-center">
                    <p className="text-3xl font-bold text-primary-600">{analysis.total_films}</p>
                    <p className="text-sm text-gray-600">Movies Watched</p>
                  </div>
                  <div className="text-center">
                    <p className="text-3xl font-bold text-green-600">{analysis.total_reviews}</p>
                    <p className="text-sm text-gray-600">Reviews Written</p>
                  </div>
                  <div className="text-center">
                    <p className="text-3xl font-bold text-yellow-600">{analysis.avg_rating.toFixed(1)}</p>
                    <p className="text-sm text-gray-600">Average Rating</p>
                  </div>
                  <div className="text-center">
                    <p className="text-3xl font-bold text-purple-600">
                      {analysis.join_date 
                        ? new Date(analysis.join_date).getFullYear()
                        : 'Unknown'
                      }
                    </p>
                    <p className="text-sm text-gray-600">Member Since</p>
                  </div>
                </div>
              </div>

              {/* Rating Distribution Chart */}
              {ratingData.length > 0 && (
                <div className="card">
                  <h2 className="text-xl font-semibold text-gray-900 mb-4">
                    Rating Distribution
                  </h2>
                  <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                    {/* Bar Chart */}
                    <div>
                      <h3 className="text-lg font-medium text-gray-700 mb-2">Bar Chart</h3>
                      <ResponsiveContainer width="100%" height={300}>
                        <BarChart data={ratingData}>
                          <CartesianGrid strokeDasharray="3 3" />
                          <XAxis dataKey="rating" />
                          <YAxis />
                          <Tooltip />
                          <Bar dataKey="count" fill="#3B82F6" />
                        </BarChart>
                      </ResponsiveContainer>
                    </div>

                    {/* Pie Chart */}
                    <div>
                      <h3 className="text-lg font-medium text-gray-700 mb-2">Distribution</h3>
                      <ResponsiveContainer width="100%" height={300}>
                        <PieChart>
                          <Pie
                            data={ratingData}
                            cx="50%"
                            cy="50%"
                            labelLine={false}
                            label={({ rating, percent }) => `${rating}: ${((percent || 0) * 100).toFixed(0)}%`}
                            outerRadius={80}
                            fill="#8884d8"
                            dataKey="count"
                          >
                            {ratingData.map((entry, index) => (
                              <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                            ))}
                          </Pie>
                          <Tooltip />
                        </PieChart>
                      </ResponsiveContainer>
                    </div>
                  </div>
                </div>
              )}

              {/* Enhanced Metrics */}
              {analysis.enhanced_metrics && (
                <div className="card">
                  <h2 className="text-xl font-semibold text-gray-900 mb-4">
                    Enhanced Metrics
                  </h2>
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {Object.entries(analysis.enhanced_metrics).map(([key, value]) => (
                      <div key={key} className="p-4 bg-gray-50 rounded-lg">
                        <p className="text-sm font-medium text-gray-600 capitalize">
                          {key.replace(/_/g, ' ')}
                        </p>
                        <p className="text-lg font-semibold text-gray-900">
                          {typeof value === 'number' ? value.toFixed(2) : String(value)}
                        </p>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Advanced Statistics */}
              {analysis.advanced_stats && analysis.advanced_stats.length > 0 && (
                <div className="card">
                  <h2 className="text-xl font-semibold text-gray-900 mb-4">
                    Advanced Statistics
                  </h2>
                  <div className="overflow-x-auto">
                    <table className="min-w-full divide-y divide-gray-200">
                      <thead className="bg-gray-50">
                        <tr>
                          {Object.keys(analysis.advanced_stats[0]).map((key) => (
                            <th key={key} className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                              {key.replace(/_/g, ' ')}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody className="bg-white divide-y divide-gray-200">
                        {analysis.advanced_stats.map((stat, index) => (
                          <tr key={index}>
                            {Object.values(stat).map((value, valueIndex) => (
                              <td key={valueIndex} className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                                {typeof value === 'number' ? value.toFixed(2) : String(value)}
                              </td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
};

export default Analysis;
