import React from 'react';
import { motion } from 'framer-motion';
import { Bar } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  Tooltip,
  Legend,
  ChartOptions,
} from 'chart.js';

ChartJS.register(CategoryScale, LinearScale, BarElement, Tooltip, Legend);

interface RatingDistributionChartProps {
  data: Record<string, number>;
  title?: string;
  globalAverage?: number;
}

const RatingDistributionChart: React.FC<RatingDistributionChartProps> = ({ 
  data, 
  title = "Rating Distribution",
  globalAverage 
}) => {
  const ratings = Object.keys(data).sort((a, b) => parseFloat(b) - parseFloat(a));
  const values = ratings.map(rating => data[rating]);

  // Sort ratings in descending order (5.0 to 0.5)
  const sortedRatings = ratings.map((rating, index) => ({
    rating,
    value: values[index]
  })).sort((a, b) => parseFloat(b.rating) - parseFloat(a.rating));

  const chartData = {
    labels: sortedRatings.map(item => `${item.rating} ⭐`),
    datasets: [
      {
        label: 'Number of Ratings',
        data: sortedRatings.map(item => item.value),
        backgroundColor: [
          '#f59e0b', // 5.0 stars - amber
          '#f97316', // 4.5 stars - orange  
          '#ea580c', // 4.0 stars - orange-600
          '#dc2626', // 3.5 stars - red-600
          '#b91c1c', // 3.0 stars - red-700
          '#991b1b', // 2.5 stars - red-800
          '#7f1d1d', // 2.0 stars - red-900
          '#451a03', // 1.5 stars - orange-950
          '#292524', // 1.0 stars - stone-800
          '#1c1917', // 0.5 stars - stone-900
        ].slice(0, sortedRatings.length),
        borderColor: [
          '#d97706', '#ea580c', '#c2410c', '#b91c1c', '#991b1b', 
          '#7f1d1d', '#65a30d', '#365314', '#1f2937', '#111827'
        ].slice(0, sortedRatings.length),
        borderWidth: 1,
        borderRadius: 6,
        borderSkipped: false,
      },
    ],
  };

  const options: ChartOptions<'bar'> = {
    responsive: true,
    maintainAspectRatio: false,
    indexAxis: 'y' as const, // Horizontal bars
    plugins: {
      legend: {
        display: false, // Hide legend for cleaner look
      },
      tooltip: {
        backgroundColor: 'rgba(15, 23, 42, 0.95)',
        titleColor: '#f8fafc',
        bodyColor: '#f8fafc',
        borderColor: '#f59e0b',
        borderWidth: 1,
        cornerRadius: 8,
        padding: 12,
        displayColors: false,
        callbacks: {
          title: (context) => `${context[0].label}`,
          label: (context) => {
            const total = context.dataset.data.reduce((sum: number, val) => sum + (val as number), 0);
            const percentage = total > 0 ? ((context.raw as number) / total * 100).toFixed(1) : '0.0';
            return `${context.raw} ratings (${percentage}%)`;
          },
        },
      },
    },
    scales: {
      x: {
        beginAtZero: true,
        grid: {
          color: 'rgba(248, 250, 252, 0.1)',
        },
        ticks: {
          color: '#94a3b8',
          font: {
            size: 12,
          },
          callback: function(value) {
            // Format large numbers with k suffix
            const num = value as number;
            return num >= 1000 ? (num/1000).toFixed(1) + 'k' : num.toString();
          },
        },
      },
      y: {
        grid: {
          display: false,
        },
        ticks: {
          color: '#f8fafc',
          font: {
            size: 13,
            weight: 'bold',
          },
        },
      },
    },
    animation: {
      duration: 1500,
      easing: 'easeOutQuart',
    },
  };

  const totalRatings = values.reduce((sum, val) => sum + val, 0);
  const averageRating = globalAverage ?? 0;

  return (
    <motion.div 
      className="card-cinema h-80"
      initial={{ opacity: 0, scale: 0.9 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.6, delay: 0.2 }}
    >
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-lg font-semibold text-white">{title}</h3>
          <p className="text-white/60 text-sm">How users rate movies (star ratings)</p>
        </div>
        
        <div className="flex items-center space-x-6">
          <motion.div 
            className="text-center"
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.4 }}
          >
            <div className="text-xl font-bold text-cinema-400">{averageRating.toFixed(1)}</div>
            <div className="text-xs text-white/60">Avg Rating</div>
          </motion.div>
          
          <motion.div 
            className="text-center"
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.5 }}
          >
            <div className="text-xl font-bold text-white">{totalRatings.toLocaleString()}</div>
            <div className="text-xs text-white/60">Total Ratings</div>
          </motion.div>
        </div>
      </div>
      
      <div className="relative h-60">
        {totalRatings > 0 ? (
          <motion.div 
            className="h-full"
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 1, delay: 0.3 }}
          >
            <Bar data={chartData} options={options} />
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
                <span className="text-2xl">📊</span>
              </div>
              <p className="text-white/60">No rating data available</p>
            </div>
          </motion.div>
        )}
      </div>
    </motion.div>
  );
};

export default RatingDistributionChart;