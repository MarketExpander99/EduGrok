import React, { useState, useEffect } from 'react';

const StarlinkMode = () => {
  const [online, setOnline] = useState(navigator.onLine);

  useEffect(() => {
    const handleOnline = () => setOnline(true);
    const handleOffline = () => setOnline(false);
    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);
    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, []);

  return (
    <div className="starlink-mode">
      {online ? 'Online' : 'Offline - Starlink Backup Mode Active'}
    </div>
  );
};

export default StarlinkMode;