import type { NextConfig } from 'next';

const nextConfig: NextConfig = {
  images: {
    remotePatterns: [
      { hostname: 'a.ltrbxd.com' },
      { hostname: 'image.tmdb.org' },
    ],
  },
};

export default nextConfig;
