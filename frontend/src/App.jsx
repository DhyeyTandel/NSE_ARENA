// App.jsx
import { lazy, Suspense, useState } from 'react';
import { useAuth } from './hooks/useAuth';
import { NavBar } from './components/NavBar';
import { Logo } from './components/Logo';
import { AuthScreen } from './screens/AuthScreen';
import { Dashboard } from './screens/Dashboard';
import { Leaderboard } from './screens/Leaderboard';
import { AIFeed } from './screens/AIFeed';
import { Profile } from './screens/Profile';
import './components/NavBar.css';

// Lazy: pulls in the locally bundled Monaco editor only when opened.
const ScriptEditor = lazy(() =>
  import('./screens/ScriptEditor').then(m => ({ default: m.ScriptEditor })));

function App() {
  const [activeScreen, setActiveScreen] = useState('dashboard');
  const { authenticated, user, loading, error, login, register, logout, clearError } = useAuth();

  const handleAuth = async (mode, data) => {
    if (mode === 'login') {
      return await login(data.username, data.password);
    } else {
      return await register(data.username, data.email, data.password);
    }
  };

  if (loading) {
    return (
      <div className="boot" role="status" aria-label="Loading">
        <Logo size={36} variant="full" />
        <span className="spinner" aria-hidden="true" />
      </div>
    );
  }

  if (!authenticated || !user) {
    return <AuthScreen onAuth={handleAuth} error={error} clearError={clearError} />;
  }

  const renderScreen = () => {
    switch (activeScreen) {
      case 'dashboard':
        return <Dashboard authenticated={authenticated} user={user} />;
      case 'leaderboard':
        return <Leaderboard authenticated={authenticated} user={user} />;
      case 'ai-feed':
        return <AIFeed />;
      case 'scripts':
        return <ScriptEditor authenticated={authenticated} />;
      case 'profile':
        return <Profile authenticated={authenticated} user={user} />;
      default:
        return <Dashboard authenticated={authenticated} user={user} />;
    }
  };

  return (
    <div className="app-shell">
      <NavBar
        activeScreen={activeScreen}
        onNavigate={setActiveScreen}
        user={user}
        onLogout={logout}
      />
      <main>
        <Suspense fallback={<div className="page"><span className="skel skel--block" style={{ '--h': '320px' }} /></div>}>{renderScreen()}</Suspense>
      </main>
    </div>
  );
}

export default App;
