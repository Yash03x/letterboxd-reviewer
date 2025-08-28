import React from 'react';
import { motion } from 'framer-motion';
import { Doughnut } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  ArcElement,
  Tooltip,
  Legend,
  ChartOptions,
} from 'chart.js';

ChartJS.register(ArcElement, Tooltip, Legend);

interface RatingDistributionChartProps {
  data: Record<string, number>;
  title?: string;
}

const RatingDistributionChart: React.FC<RatingDistributionChartProps> = ({ 
  data, 
  title = "Rating Distribution" 
}) => {
  const ratings = Object.keys(data).sort((a, b) => parseFloat(b) - parseFloat(a));
  const values = ratings.map(rating => data[rating]);
  
  // Cinema-inspired color palette
  const colors = [
    '#f57c00', // cinema-400
    '#e65100', // cinema-500
    '#c44100', // cinema-600
    '#992e00', // cinema-700
    '#7a1f00', // cinema-800
    '#5d1600', // cinema-900
    '#fde8d3', // cinema-100
    '#fbcd9a', // cinema-200
  ];

  const chartData = {
    labels: ratings.map(r => `${r} ⭐`),
    datasets: [
      {
        data: values,
        backgroundColor: colors.slice(0, ratings.length),
        borderColor: colors.slice(0, ratings.length).map(color => color + '40'),
        borderWidth: 2,
        hoverBorderWidth: 3,
        hoverBorderColor: '#ffffff80',
      },
    ],
  };

  const options: ChartOptions<'doughnut'> = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        position: 'right' as const,
        labels: {
          color: '#f8fafc',
          font: {
            family: 'Inter',
            size: 12,
          },
          padding: 15,
          usePointStyle: true,
          pointStyle: 'circle',
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
        displayColors: true,
        callbacks: {
          label: (context) => {
            const total = context.dataset.data.reduce((sum, val) => sum + (val as number), 0);
            const percentage = ((context.raw as number) / total * 100).toFixed(1);
            return `${context.label}: ${context.raw} movies (${percentage}%)`;
          },
        },
      },
    },
    cutout: '60%',
    animation: {
      animateRotate: true,
      animateScale: true,
      duration: 2000,
      easing: 'easeInOutQuart',
    },
  };

  const totalMovies = values.reduce((sum, val) => sum + val, 0);
  const averageRating = ratings.length > 0 
    ? ratings.reduce((sum, rating, index) => sum + parseFloat(rating) * values[index], 0) / totalMovies
    : 0;

  return (
    <motion.div 
      className="card-cinema h-80"
      initial={{ opacity: 0, scale: 0.9 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.6, delay: 0.2 }}
    >
      <div className="flex items-center justify-between mb-6">
        <div>
          <h3 className="text-lg font-semibold text-white">{title}</h3>
          <p className="text-white/60 text-sm">Distribution across ratings</p>
        </div>
        
        <motion.div 
          className="text-center"
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.4 }}
        >
          <div className="text-2xl font-bold text-cinema-400">{averageRating.toFixed(1)}</div>
          <div className="text-xs text-white/60">Avg Rating</div>
        </motion.div>
      </div>
      
      <div className="relative h-56">
        {totalMovies > 0 ? (
          <motion.div 
            className="h-full"
            initial={{ opacity: 0, rotate: -10 }}
            animate={{ opacity: 1, rotate: 0 }}
            transition={{ duration: 1, delay: 0.3 }}
          >
            <Doughnut data={chartData} options={options} />
            
            {/* Center text */}
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="text-center">
                <div className="text-2xl font-bold text-white">{totalMovies}</div>
                <div className="text-xs text-white/60">Movies</div>
              </div>
            </div>
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