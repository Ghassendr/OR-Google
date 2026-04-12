import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import axios from 'axios';

export default function Verify() {
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token');
  const navigate = useNavigate();
  const [status, setStatus] = useState('Vérification en cours...');
  const [error, setError] = useState(false);

  useEffect(() => {
    if (!token) {
      setStatus('Lien invalide.');
      setError(true);
      return;
    }

    const verifyToken = async () => {
      try {
        await axios.post('http://localhost:5000/api/auth/verify', 
          { token }, 
          { withCredentials: true }
        );
        setStatus('Authentification réussie. Redirection...');
        setTimeout(() => {
          navigate('/dashboard');
        }, 1000);
      } catch (err) {
        setError(true);
        setStatus(err.response?.data?.error || 'Lien invalide ou expiré.');
      }
    };

    verifyToken();
  }, [token, navigate]);

  return (
    <div className="auth-container">
      <div className="auth-card card" style={{textAlign: 'center'}}>
        <h2 className="auth-title">Vérification</h2>
        <div style={{marginTop: '2rem', marginBottom: '2rem'}}>
          {error ? (
            <div className="alert alert-error">{status}</div>
          ) : (
            <p style={{color: 'var(--primary-color)', fontWeight: 500}}>{status}</p>
          )}
        </div>
        {error && (
          <button className="btn btn-outline" onClick={() => navigate('/login')}>
            Retour à l'accueil
          </button>
        )}
      </div>
    </div>
  );
}
