'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { UserButton, SignInButton, useAuth } from '@clerk/nextjs';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  HomeIcon, 
  FilmIcon, 
  ChartBarIcon, 
  UserGroupIcon,
  PlayIcon,
} from '@heroicons/react/24/outline';
import {
  HomeIcon as HomeIconSolid,
  FilmIcon as FilmIconSolid,
  ChartBarIcon as ChartBarIconSolid
} from '@heroicons/react/24/solid';

interface LayoutProps {
  children: React.ReactNode;
}

const Layout: React.FC<LayoutProps> = ({ children }) => {
  const pathname = usePathname();
  const { isSignedIn } = useAuth();
  const [isLoaded, setIsLoaded] = useState(false);
  const [currentTime, setCurrentTime] = useState(new Date());

  useEffect(() => {
    setIsLoaded(true);
    const timer = setInterval(() => setCurrentTime(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  const navigationItems = [
    {
      path: '/',
      label: 'Dashboard',
      icon: HomeIcon,
      activeIcon: HomeIconSolid,
      description: 'Overview & Analytics'
    },
    {
      path: '/profiles',
      label: 'Profiles',
      icon: UserGroupIcon,
      activeIcon: UserGroupIcon,
      description: 'Manage Profiles'
    },
    {
      path: '/scraper',
      label: 'Scraper',
      icon: FilmIcon,
      activeIcon: FilmIconSolid,
      description: 'Data Collection'
    },
    {
      path: '/analysis',
      label: 'Analysis',
      icon: ChartBarIcon,
      activeIcon: ChartBarIconSolid,
      description: 'Deep Insights'
    }
  ];

  const isActive = (path: string) => pathname === path;

  return (
    <motion.div 
      className="min-h-screen flex flex-col lg:flex-row"
      initial={{ opacity: 0 }}
      animate={{ opacity: isLoaded ? 1 : 0 }}
      transition={{ duration: 0.8, ease: "easeOut" }}
    >
      {/* Sidebar Navigation */}
      <motion.nav 
        className="w-full lg:w-80 bg-black/20 backdrop-blur-xl border-r border-white/10 flex-shrink-0"
        initial={{ x: -100, opacity: 0 }}
        animate={{ x: 0, opacity: 1 }}
        transition={{ duration: 0.6, delay: 0.2, ease: "easeOut" }}
      >
        <div className="p-6 h-full flex flex-col">
          {/* Logo & Branding */}
          <motion.div 
            className="flex items-center space-x-3 mb-8"
            whileHover={{ scale: 1.02 }}
            transition={{ type: "spring", stiffness: 300 }}
          >
            <div className="relative">
              <motion.div 
                className="w-12 h-12 bg-gradient-to-br from-cinema-400 to-cinema-600 rounded-xl flex items-center justify-center shadow-glow"
                animate={{ 
                  boxShadow: [
                    "0 0 20px rgba(229, 81, 0, 0.3)",
                    "0 0 30px rgba(229, 81, 0, 0.5)",
                    "0 0 20px rgba(229, 81, 0, 0.3)"
                  ]
                }}
                transition={{ duration: 3, repeat: Infinity }}
              >
                <PlayIcon className="w-6 h-6 text-white" />
              </motion.div>
            </div>
            <div>
              <h1 className="text-xl font-bold text-white text-glow">
                Spyboxd
              </h1>
              <p className="text-sm text-white/60 font-medium">
                User Analytics
              </p>
            </div>
          </motion.div>

          {/* System Status */}
          <motion.div 
            className="mb-8 p-4 rounded-xl bg-white/5 border border-white/10 backdrop-blur-sm"
            initial={{ y: 20, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            transition={{ delay: 0.4 }}
          >
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm text-white/70">System Status</span>
              <motion.div 
                className="w-2 h-2 bg-green-400 rounded-full"
                animate={{ scale: [1, 1.2, 1] }}
                transition={{ duration: 2, repeat: Infinity }}
              />
            </div>
            <div className="text-xs text-white/50">
              {currentTime.toLocaleTimeString()}
            </div>
          </motion.div>

          {/* Navigation Items */}
          <div className="space-y-2 flex-1">
            {navigationItems.map((item, index) => {
              const Icon = isActive(item.path) ? item.activeIcon : item.icon;
              return (
                <motion.div
                  key={item.path}
                  initial={{ x: -50, opacity: 0 }}
                  animate={{ x: 0, opacity: 1 }}
                  transition={{ delay: 0.3 + (index * 0.1) }}
                >
                  <Link href={item.path}>
                    <motion.div
                      className={`
                        relative group flex items-center space-x-4 p-4 rounded-xl transition-all duration-300
                        ${isActive(item.path) 
                          ? 'bg-cinema-500/20 text-cinema-400 border border-cinema-400/30' 
                          : 'text-white/70 hover:text-white hover:bg-white/10 border border-transparent hover:border-white/20'
                        }
                      `}
                      whileHover={{ 
                        scale: 1.02,
                        x: 5
                      }}
                      whileTap={{ scale: 0.98 }}
                      transition={{ type: "spring", stiffness: 400, damping: 17 }}
                    >
                      {/* Active indicator */}
                      {isActive(item.path) && (
                        <motion.div
                          className="absolute left-0 top-1/2 -translate-y-1/2 w-1 h-8 bg-cinema-500 rounded-r-full"
                          layoutId="activeIndicator"
                          transition={{ type: "spring", stiffness: 500, damping: 30 }}
                        />
                      )}
                      
                      <Icon className={`w-6 h-6 flex-shrink-0 ${isActive(item.path) ? 'text-cinema-400' : ''}`} />
                      <div className="flex-1">
                        <div className={`font-semibold ${isActive(item.path) ? 'text-cinema-300' : ''}`}>
                          {item.label}
                        </div>
                        <div className="text-xs text-white/50 group-hover:text-white/70 transition-colors">
                          {item.description}
                        </div>
                      </div>
                      
                      {/* Hover glow effect */}
                      <motion.div
                        className="absolute inset-0 bg-gradient-to-r from-cinema-500/0 via-cinema-500/5 to-cinema-500/0 rounded-xl opacity-0 group-hover:opacity-100 transition-opacity duration-300"
                        animate={{ 
                          backgroundPosition: ["0% 0%", "100% 0%"],
                        }}
                        transition={{ 
                          duration: 2, 
                          repeat: Infinity, 
                          ease: "linear",
                          repeatType: "reverse" 
                        }}
                      />
                    </motion.div>
                  </Link>
                </motion.div>
              );
            })}
          </div>
        </div>
      </motion.nav>

      {/* Main Content */}
      <main className="flex-1 flex flex-col min-h-screen lg:min-h-auto">
        {/* Top Header */}
        <motion.header 
          className="bg-black/10 backdrop-blur-md border-b border-white/10 px-6 py-4"
          initial={{ y: -50, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          transition={{ duration: 0.6, delay: 0.3 }}
        >
          <div className="flex items-center justify-between">
            <div>
              <motion.h2 
                className="text-2xl font-bold text-white text-glow"
                initial={{ x: -20, opacity: 0 }}
                animate={{ x: 0, opacity: 1 }}
                transition={{ delay: 0.5 }}
              >
                {navigationItems.find(item => isActive(item.path))?.label || 'Dashboard'}
              </motion.h2>
              <motion.p 
                className="text-white/60 text-sm mt-1"
                initial={{ x: -20, opacity: 0 }}
                animate={{ x: 0, opacity: 1 }}
                transition={{ delay: 0.6 }}
              >
                {navigationItems.find(item => isActive(item.path))?.description || 'Welcome to Spyboxd'}
              </motion.p>
            </div>
            
            <motion.div 
              className="flex items-center space-x-3"
              initial={{ x: 20, opacity: 0 }}
              animate={{ x: 0, opacity: 1 }}
              transition={{ delay: 0.7 }}
            >
              {isSignedIn ? (
                <UserButton
                  appearance={{
                    elements: {
                      avatarBox: 'w-9 h-9 ring-2 ring-cinema-500/40 hover:ring-cinema-400/70 transition-all',
                    },
                  }}
                />
              ) : (
                <SignInButton mode="modal">
                  <button className="px-4 py-1.5 rounded-lg text-sm font-medium bg-cinema-500 hover:bg-cinema-600 text-white transition-colors">
                    Sign in
                  </button>
                </SignInButton>
              )}
            </motion.div>
          </div>
        </motion.header>

        {/* Page Content with Animation */}
        <div className="flex-1 p-6">
          <AnimatePresence mode="wait">
            <motion.div
              key={pathname}
              initial={{ opacity: 0, y: 20, scale: 0.98 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: -20, scale: 1.02 }}
              transition={{ 
                duration: 0.4, 
                ease: [0.25, 0.46, 0.45, 0.94] 
              }}
            >
              {children}
            </motion.div>
          </AnimatePresence>
        </div>
      </main>
    </motion.div>
  );
};

export default Layout;
