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

  // Loading state — branded spinner
  if (loading) {
    return (
      <div style={{
        minHeight: '100vh',
        background: 'var(--ink)',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: '16px',
      }}>
        <div style={{
          width: '40px', height: '40px', borderRadius: '10px',
          background: 'linear-gradient(135deg, var(--gold) 0%, var(--gold-solid) 100%)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: '20px', fontWeight: 800, color: '#000',
          animation: 'glowPulse 1.5s ease-in-out infinite',
          boxShadow: 'var(--shadow-gold)',
        }}>
          N
        </div>
        <div style={{
          fontSize: '15px', fontWeight: 600, color: 'var(--text)',
          letterSpacing: '-0.3px',
        }}>
          NSE <span style={{ color: 'var(--gold)' }}>Arena</span>
        </div>
        <div style={{
          width: '24px', height: '24px',
          border: '2px solid var(--border2)',
          borderTopColor: 'var(--gold)',
          borderRadius: '50%',
          animation: 'spin 0.8s linear infinite',
        }} />
      </div>
    );
  }

  // Not authenticated
  if (!authenticated || !user) {
    return (
      <AuthScreen
        onAuth={handleAuth}
        error={error}
        clearError={clearError}
      />
    );
  }

  // Authenticated
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
    <div style={{
      minHeight: '100vh',
      background: 'var(--ink)',
      color: 'var(--text)',
    }}>
      <NavBar
        activeScreen={activeScreen}
        onNavigate={setActiveScreen}
        user={user}
        onLogout={logout}
      />
      <main style={{
        maxWidth: '1440px',
        margin: '0 auto',
      }}>
        {renderScreen()}
      </main>
    </div>
  );
}

export default App;
