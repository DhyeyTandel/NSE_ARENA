// App.jsx
import { lazy, Suspense, useState } from 'react';
import { useAuth } from './hooks/useAuth';
import { NavBar } from './components/NavBar';
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
      <div style={{
        minHeight: '100vh', background: 'var(--canvas)',
        display: 'flex', flexDirection: 'column',
        alignItems: 'center', justifyContent: 'center', gap: 'var(--s4)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--s2)', fontWeight: 600, fontSize: '16px' }}>
          <span className="nav-mark" aria-hidden="true">N</span>
          NSE Arena
        </div>
        <div style={{
          width: '24px', height: '24px',
          border: '2px solid var(--border)',
          borderTopColor: 'var(--accent)',
          borderRadius: '50%',
          animation: 'spin 0.8s linear infinite',
        }} />
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
    <div style={{ minHeight: '100vh', background: 'var(--canvas)', color: 'var(--text)' }}>
      <NavBar
        activeScreen={activeScreen}
        onNavigate={setActiveScreen}
        user={user}
        onLogout={logout}
      />
      <main>
        <Suspense fallback={null}>{renderScreen()}</Suspense>
      </main>
    </div>
  );
}

export default App;
