import { useState } from 'react';
import axios from 'axios';

export default function Login() {
  const [email, setEmail] = useState('');
  const [status, setStatus] = useState({ type: '', message: '' });
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!email) return;

    setIsLoading(true);
    setStatus({ type: '', message: '' });

    try {
      const res = await axios.post('http://localhost:5000/api/auth/request-link', { email });
      setStatus({ type: 'success', message: res.data.message });
      setEmail('');
    } catch (err) {
      // The backend returns {error: 'Mail incorrecte'} if not found
      setStatus({ 
        type: 'error', 
        message: err.response?.data?.error || 'Une erreur est survenue'
      });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="auth-container">
      <div className="auth-card card">
        <div className="auth-logo" style={{textAlign: 'center', marginBottom: '2rem'}}>
          {/* Logo ISSAT Sousse */}
          <img src="https://issatso.rnu.tn/assets/images/logo.png" alt="Logo ISSAT Sousse" style={{maxWidth: '200px'}} 
               onError={(e) => {
                 e.target.onerror = null; 
                 // Fallback to text if image not found on that url
                 e.target.style.display = 'none';
                 e.target.insertAdjacentHTML('afterend', '<h2>ISSAT SOUSSE</h2>');
               }}/>
        </div>
        <h2 className="auth-title">Portail Enseignant</h2>
        <p className="auth-subtitle">Gestion des absences et indisponibilités</p>

        {status.message && (
          <div className={`alert alert-${status.type}`}>
            {status.message}
          </div>
        )}

        <form onSubmit={handleSubmit}>
          <div className="input-group">
            <label htmlFor="email" className="input-label">Adresse e-mail</label>
            <input 
              type="email" 
              id="email" 
              className="input-field" 
              placeholder="prenom.nom@issatso.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>
          
          <button type="submit" className="btn btn-primary" style={{width: '100%'}} disabled={isLoading}>
            {isLoading ? 'Vérification...' : 'Recevoir mon lien de connexion'}
          </button>
        </form>
      </div>
    </div>
  );
}
