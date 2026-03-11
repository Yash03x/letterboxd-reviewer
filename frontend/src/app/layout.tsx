import type { Metadata } from 'next';
import Providers from './providers';
import '../index.css';

export const metadata: Metadata = {
  title: { default: 'Spyboxd', template: '%s | Spyboxd' },
  description: 'Letterboxd profile analytics and insights',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
