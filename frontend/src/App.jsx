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
  const { token, user, loading, error, login, register, logout, clearError } = useAuth();

  const handleAuth = async (mode, data) => {
    if (mode === 'login') {
      return await login(data.username, data.password);
    } else {
      return await register(data.username, data.email, data.password);
    }
  };

  // Show loading spinner while validating stored token
  if (loading) {
    return (
      <div style={{
        minHeight: '100vh',
        background: 'var(--ink)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}>
        <div style={{
          fontSize: '16px',
          fontWeight: 500,
          color: 'var(--text3)',
          letterSpacing: '-0.3px',
        }}>
          nse<span style={{ color: 'var(--gold)' }}>arena</span>
        </div>
      </div>
    );
  }

  // Not authenticated — show login/register screen
  if (!token || !user) {
    return (
      <AuthScreen
        onAuth={handleAuth}
        error={error}
        clearError={clearError}
      />
    );
  }

  // Authenticated — show main app
  const renderScreen = () => {
    switch (activeScreen) {
      case 'dashboard':
        return <Dashboard token={token} user={user} />;
      case 'leaderboard':
        return <Leaderboard token={token} />;
      case 'ai-feed':
        return <AIFeed />;
      case 'scripts':
        return <ScriptEditor token={token} />;
      case 'profile':
        return <Profile token={token} user={user} />;
      default:
        return <Dashboard token={token} user={user} />;
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
      <main>
        {renderScreen()}
      </main>
    </div>
  );
}

export default App;
