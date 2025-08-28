import React from 'react';
import { motion } from 'framer-motion';
import { Line } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler,
  ChartOptions,
} from 'chart.js';

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler
);

interface ActivityData {
  month: string;
  movies_watched: number;
  average_rating: number | null;
}

interface ActivityChartProps {
  data: ActivityData[];
  title?: string;
}

const ActivityChart: React.FC<ActivityChartProps> = ({ 
  data, 
  title = "Watching Activity" 
}) => {
  const chartData = {
    labels: data.map(item => {
      const [year, month] = item.month.split('-');
      const date = new Date(parseInt(year), parseInt(month) - 1);
      return date.toLocaleDateString('en-US', { month: 'short', year: '2-digit' });
    }),
    datasets: [
      {
        label: 'Movies Watched',
        data: data.map(item => item.movies_watched),
        borderColor: '#f57c00',
        backgroundColor: 'rgba(245, 124, 0, 0.1)',
        borderWidth: 3,
        fill: true,
        tension: 0.4,
        pointBackgroundColor: '#f57c00',
        pointBorderColor: '#ffffff',
        pointBorderWidth: 2,
        pointRadius: 6,
        pointHoverRadius: 8,
        pointHoverBackgroundColor: '#e65100',
        pointHoverBorderColor: '#ffffff',
        pointHoverBorderWidth: 3,
      },
      {
        label: 'Average Rating',
        data: data.map(item => item.average_rating ? item.average_rating * 10 : null), // Scale to make visible
        borderColor: '#64748b',
        backgroundColor: 'rgba(100, 116, 139, 0.1)',
        borderWidth: 2,
        fill: false,
        tension: 0.4,
        pointBackgroundColor: '#64748b',
        pointBorderColor: '#ffffff',
        pointBorderWidth: 2,
        pointRadius: 4,
        pointHoverRadius: 6,
        borderDash: [5, 5],
        yAxisID: 'rating-axis',
      },
    ],
  };

  const options: ChartOptions<'line'> = {
    responsive: true,
    maintainAspectRatio: false,
    interaction: {
      intersect: false,
      mode: 'index' as const,
    },
    scales: {
      x: {
        grid: {
          color: 'rgba(255, 255, 255, 0.1)',
        },
        ticks: {
          color: '#cbd5e1',
          font: {
            family: 'Inter',
            size: 11,
          },
        },
      },
      y: {
        position: 'left' as const,
        grid: {
          color: 'rgba(255, 255, 255, 0.1)',
        },
        ticks: {
          color: '#cbd5e1',
          font: {
            family: 'Inter',
            size: 11,
          },
        },
        title: {
          display: true,
          text: 'Movies Watched',
          color: '#f57c00',
          font: {
            family: 'Inter',
            size: 12,
            weight: 'bold',
          },
        },
      },
      'rating-axis': {
        type: 'linear' as const,
        position: 'right' as const,
        grid: {
          drawOnChartArea: false,
        },
        ticks: {
          color: '#64748b',
          font: {
            family: 'Inter',
            size: 11,
          },
          callback: function(value) {
            return ((value as number) / 10).toFixed(1); // Convert back to rating scale
          },
        },
        title: {
          display: true,
          text: 'Avg Rating',
          color: '#64748b',
          font: {
            family: 'Inter',
            size: 12,
            weight: 'bold',
          },
        },
        min: 0,
        max: 50, // 5.0 rating * 10
      },
    },
    plugins: {
      legend: {
        display: true,
        position: 'top' as const,
        labels: {
          color: '#f8fafc',
          font: {
            family: 'Inter',
            size: 12,
          },
          padding: 20,
          usePointStyle: true,
        },
      },
      tooltip: {
        backgroundColor: 'rgba(15, 23, 42, 0.9)',
        titleColor: '#f8fafc',
        bodyColor: '#f8fafc',
        borderColor: '#f57c00',
        borderWidth: 1,
        cornerRadius: 8,
        padding: 12,
        callbacks: {
          label: (context) => {
            if (context.dataset.label === 'Average Rating') {
              const rating = (context.raw as number) / 10;
              return `${context.dataset.label}: ${rating.toFixed(1)} ⭐`;
            }
            return `${context.dataset.label}: ${context.raw}`;
          },
        },
      },
    },
    animation: {
      duration: 2000,
      easing: 'easeInOutQuart',
    },
  };

  const totalMovies = data.reduce((sum, item) => sum + item.movies_watched, 0);
  const avgMoviesPerMonth = data.length > 0 ? totalMovies / data.length : 0;

  return (
    <motion.div 
      className="card-cinema h-96"
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.6, delay: 0.1 }}
    >
      <div className="flex items-center justify-between mb-6">
        <div>
          <h3 className="text-lg font-semibold text-white">{title}</h3>
          <p className="text-white/60 text-sm">Monthly viewing patterns</p>
        </div>
        
        <motion.div 
          className="text-center"
          initial={{ opacity: 0, scale: 0.8 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: 0.4 }}
        >
          <div className="text-xl font-bold text-cinema-400">{avgMoviesPerMonth.toFixed(1)}</div>
          <div className="text-xs text-white/60">Avg/Month</div>
        </motion.div>
      </div>
      
      <div className="h-72">
        {data.length > 0 ? (
          <motion.div 
            className="h-full"
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 1, delay: 0.3 }}
          >
            <Line data={chartData} options={options} />
          </motion.div>
        ) : (
          <motion.div 
            className="h-full flex items-center justify-center"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.3 }}
          >
            <div className="text-center">
              <div className="w-16 h-16 bg-cinema-500/20 rounded-full flex items-center justify-center mb-3 mx-auto">
                <span className="text-2xl">📈</span>
              </div>
              <p className="text-white/60">No activity data available</p>
            </div>
          </motion.div>
        )}
      </div>
    </motion.div>
  );
};

export default ActivityChart;