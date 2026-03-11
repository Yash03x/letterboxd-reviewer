import { ImageResponse } from 'next/og';
import { NextRequest } from 'next/server';

export const runtime = 'edge';

const API_URL = process.env.API_URL ?? 'http://localhost:8000';

interface Profile {
  username: string;
  total_films: number;
  avg_rating: number;
  total_reviews: number;
  profile_image_url?: string;
}

export async function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url);
  const username = searchParams.get('username') ?? 'unknown';

  let profile: Profile = { username, total_films: 0, avg_rating: 0, total_reviews: 0 };

  try {
    const res = await fetch(`${API_URL}/public/profile/${encodeURIComponent(username)}`);
    if (res.ok) profile = await res.json();
  } catch {
    // use defaults
  }

  const stats = [
    { label: 'Films', value: profile.total_films?.toLocaleString() ?? '0' },
    { label: 'Avg Rating', value: `${profile.avg_rating?.toFixed(1) ?? '0.0'}★` },
    { label: 'Reviews', value: profile.total_reviews?.toLocaleString() ?? '0' },
  ];

  return new ImageResponse(
    (
      <div
        style={{
          width: '1200px',
          height: '630px',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          background: 'linear-gradient(135deg, #0f172a 0%, #1e293b 50%, #334155 100%)',
          fontFamily: 'sans-serif',
          gap: '40px',
        }}
      >
        {/* Username */}
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '8px' }}>
          <div style={{ fontSize: '80px', fontWeight: 800, color: '#ffffff', letterSpacing: '-2px' }}>
            {profile.username}
          </div>
          <div style={{ fontSize: '28px', color: 'rgba(255,255,255,0.45)' }}>on Spyboxd</div>
        </div>

        {/* Stats row */}
        <div style={{ display: 'flex', gap: '40px' }}>
          {stats.map(({ label, value }) => (
            <div
              key={label}
              style={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                background: 'rgba(255,255,255,0.06)',
                border: '1px solid rgba(255,255,255,0.12)',
                borderRadius: '20px',
                padding: '28px 48px',
                gap: '10px',
              }}
            >
              <div style={{ fontSize: '52px', fontWeight: 700, color: '#f57c00' }}>{value}</div>
              <div style={{ fontSize: '20px', color: 'rgba(255,255,255,0.5)' }}>{label}</div>
            </div>
          ))}
        </div>

        {/* Brand */}
        <div style={{ fontSize: '22px', color: 'rgba(255,255,255,0.25)', marginTop: '8px' }}>
          spyboxd.com
        </div>
      </div>
    ),
    { width: 1200, height: 630 }
  );
}
