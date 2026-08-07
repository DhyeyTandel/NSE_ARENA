// App.jsx
import { useState } from 'react';
import { useAuth } from './hooks/useAuth';
import { NavBar } from './components/NavBar';
import { AuthScreen } from './screens/AuthScreen';
import { Dashboard } from './screens/Dashboard';
import { Leaderboard } from './screens/Leaderboard';
import { AIFeed } from './screens/AIFeed';
import { Profile } from './screens/Profile';
import { ScriptEditor } from './screens/ScriptEditor';

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
        minHeight: '100vh', background: 'var(--paper)',
        display: 'flex', flexDirection: 'column',
        alignItems: 'center', justifyContent: 'center', gap: '16px',
      }}>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: '8px' }}>
          <span style={{
            width: '7px', height: '7px', borderRadius: '999px',
            background: 'var(--accent)', display: 'inline-block',
          }} />
          <span style={{
            fontFamily: '"Newsreader", Georgia, serif',
            fontSize: '21px', fontWeight: 500, letterSpacing: '-0.02em',
          }}>NSE Arena</span>
        </div>
        <div style={{
          width: '24px', height: '24px',
          border: '2px solid var(--faint)',
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
        return <Leaderboard />;
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
    <div style={{ minHeight: '100vh', background: 'var(--paper)', color: 'var(--ink)' }}>
      <NavBar
        activeScreen={activeScreen}
        onNavigate={setActiveScreen}
        user={user}
        onLogout={logout}
      />
      <main>{renderScreen()}</main>
    </div>
  );
}

export default App;
