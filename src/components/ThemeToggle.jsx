import { useState, useEffect } from 'react';

function ThemeToggle({ user }) {
  const [theme, setTheme] = useState(localStorage.getItem('theme') || user.unsafeMetadata?.theme || 'light');

  useEffect(() => {
    document.documentElement.classList.toggle('dark', theme === 'dark');
    localStorage.setItem('theme', theme);
    if (user) {
      user.update({
        unsafeMetadata: { ...user.unsafeMetadata, theme }
      }).catch(error => console.error('Error updating theme:', error));
    }
  }, [theme, user]);

  const toggleTheme = () => {
    setTheme(theme === 'light' ? 'dark' : 'light');
  };

  return (
    <button
      className="p-2 rounded hover:bg-blue-700"
      onClick={toggleTheme}
      aria-label={`Switch to ${theme === 'light' ? 'dark' : 'light'} mode`}
    >
      {theme === 'light' ? '🌙 Dark' : '☀️ Light'}
    </button>
  );
}

export default ThemeToggle;