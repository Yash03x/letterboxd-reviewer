import { Suspense } from 'react';
import ProfileManager from '../../../views/ProfileManager';

export default function ProfilesPage() {
  return (
    <Suspense>
      <ProfileManager />
    </Suspense>
  );
}
