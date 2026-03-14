'use client';

import { useAuth } from '@clerk/nextjs';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { Toaster } from 'react-hot-toast';
import { setApiTokenProvider } from '../services/api';

function ApiAuthBridge() {
  const { getToken } = useAuth();

  useEffect(() => {
    setApiTokenProvider(async () => (await getToken()) ?? null);
    return () => {
      setApiTokenProvider(null);
    };
  }, [getToken]);

  return null;
}

export default function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            refetchOnWindowFocus: false,
            retry: 1,
            staleTime: 5 * 60 * 1000,
          },
        },
      })
  );

  return (
    <QueryClientProvider client={queryClient}>
      <ApiAuthBridge />
      {children}
      <Toaster />
    </QueryClientProvider>
  );
}
