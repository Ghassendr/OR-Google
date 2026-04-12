import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';

const DAYS = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi'];
const SLOTS = [
  { id: 'S1', label: 'S1' },
  { id: 'S2', label: 'S2' },
  { id: 'S3', label: 'S3' },
  { id: 'S4', label: 'S4' },
];

export default function Dashboard() {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState({ type: '', message: '' });
  const [selections, setSelections] = useState(new Set());

  const navigate = useNavigate();

  useEffect(() => {
    const fetchUser = async () => {
      try {
        const res = await axios.get('http://localhost:5000/api/auth/me', { withCredentials: true });
        setUser(res.data.user);

        const initialSelections = new Set();
        if (res.data.declarations) {
          res.data.declarations.forEach(decl => {
            if (decl.seance) initialSelections.add(`${decl.jour}|${decl.seance}`);
          });
        }
        setSelections(initialSelections);
      } catch (err) {
        navigate('/login');
      } finally {
        setLoading(false);
      }
    };
    fetchUser();
  }, [navigate]);

  const toggleSlot = (day, slotId) => {
    const key = `${day}|${slotId}`;
    const newSet = new Set(selections);
    if (newSet.has(key)) newSet.delete(key);
    else newSet.add(key);
    setSelections(newSet);
  };

  const selectDayAll = (day) => {
    const newSet = new Set(selections);
    const allSelected = SLOTS.every(slot => newSet.has(`${day}|${slot.id}`));
    if (allSelected) SLOTS.forEach(slot => newSet.delete(`${day}|${slot.id}`));
    else SLOTS.forEach(slot => newSet.add(`${day}|${slot.id}`));
    setSelections(newSet);
  };

  const selectSlotAll = (slotId) => {
    const newSet = new Set(selections);
    const allSelected = DAYS.every(day => newSet.has(`${day}|${slotId}`));
    if (allSelected) DAYS.forEach(day => newSet.delete(`${day}|${slotId}`));
    else DAYS.forEach(day => newSet.add(`${day}|${slotId}`));
    setSelections(newSet);
  };

  const clearAll = () => setSelections(new Set());

  const handleSubmit = async () => {
    setSaving(true);
    setStatus({ type: '', message: '' });
    const formattedSelections = Array.from(selections).map(key => {
      const [jour, slot_name] = key.split('|');
      return { jour, slot_name };
    });
    try {
      await axios.post('http://localhost:5000/api/declarations', { selections: formattedSelections }, { withCredentials: true });
      setStatus({ type: 'success', message: 'Indisponibilités enregistrées avec succès.' });
    } catch (err) {
      setStatus({ type: 'error', message: 'Erreur lors de la sauvegarde.' });
    } finally {
      setSaving(false);
      setTimeout(() => setStatus({ type: '', message: '' }), 5000);
    }
  };

  const handleLogout = async () => {
    await axios.post('http://localhost:5000/api/auth/logout', {}, { withCredentials: true });
    navigate('/login');
  };

  if (loading) return (
    <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      Chargement...
    </div>
  );

  return (
    <div className="container">
      {/* Header */}
      <div className="dashboard-header">
        <div style={{ display: 'flex', gap: '20px', alignItems: 'center' }}>
          <img
            src="https://issatso.rnu.tn/assets/images/logo.png"
            alt="ISSAT Logo"
            style={{ maxWidth: '110px' }}
            onError={(e) => { e.target.style.display = 'none'; }}
          />
          <div>
            <h1 style={{ fontSize: '1.3rem', marginBottom: '4px' }}>{user?.full_name}</h1>
            <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>
              {user?.grade} &nbsp;|&nbsp; Charge à surveiller : <strong>{user?.rest_charger}</strong> séance(s)
            </p>
          </div>
        </div>
        <button onClick={handleLogout} className="btn btn-outline" style={{ padding: '0.4rem 1rem', minWidth: 'auto', fontSize: '0.9rem' }}>
          Déconnexion
        </button>
      </div>

      {status.message && (
        <div className={`alert alert-${status.type}`}>{status.message}</div>
      )}

      {/* Card */}
      <div className="card" style={{ marginTop: 0, padding: '1.5rem', overflowX: 'auto' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
          <h3 style={{ fontSize: '1rem', color: 'var(--primary-dark)' }}>
            Cocher les séances d'indisponibilité (S1 → S4)
          </h3>
          <button className="action-chip clear" onClick={clearAll}>Effacer tout</button>
        </div>

        {/* Grid */}
        <div className="schedule-grid" style={{ minWidth: '700px' }}>

          {/* Row 1: header - corner + day names */}
          <div className="schedule-header" style={{ fontSize: '0.75rem', color: 'rgba(255,255,255,0.8)', flexDirection: 'column', gap: '4px' }}>
            <span>Séances</span>
            <span>↓ &nbsp; Jours →</span>
          </div>
          {DAYS.map(day => (
            <div key={day} className="schedule-header" style={{ flexDirection: 'column', gap: '6px' }}>
              <span style={{ fontWeight: 700, fontSize: '0.9rem' }}>{day}</span>
              <button
                onClick={() => selectDayAll(day)}
                style={{
                  background: SLOTS.every(s => selections.has(`${day}|${s.id}`)) ? 'rgba(255,255,255,0.9)' : 'rgba(255,255,255,0.15)',
                  color: SLOTS.every(s => selections.has(`${day}|${s.id}`)) ? 'var(--primary-dark)' : 'white',
                  border: '1px solid rgba(255,255,255,0.5)',
                  borderRadius: '4px',
                  fontSize: '0.7rem',
                  padding: '2px 8px',
                  cursor: 'pointer',
                  fontWeight: 600,
                  transition: 'all 0.15s'
                }}
              >
                Tous
              </button>
            </div>
          ))}

          {/* Rows: one per slot */}
          {SLOTS.map(slot => (
            <>
              {/* Slot label + select all row button */}
              <div key={`time-${slot.id}`} className="schedule-time" style={{ flexDirection: 'column', gap: '6px', padding: '0.75rem 0.5rem' }}>
                <span style={{ fontSize: '1rem', fontWeight: 700, color: 'var(--primary-dark)' }}>{slot.label}</span>
                <button
                  onClick={() => selectSlotAll(slot.id)}
                  style={{
                    background: DAYS.every(d => selections.has(`${d}|${slot.id}`)) ? 'var(--primary-color)' : 'transparent',
                    color: DAYS.every(d => selections.has(`${d}|${slot.id}`)) ? 'white' : 'var(--primary-color)',
                    border: '1px solid var(--primary-color)',
                    borderRadius: '4px',
                    fontSize: '0.7rem',
                    padding: '2px 8px',
                    cursor: 'pointer',
                    fontWeight: 600,
                    transition: 'all 0.15s'
                  }}
                >
                  Tous
                </button>
              </div>

              {/* Cells for this slot across all days */}
              {DAYS.map(day => {
                const key = `${day}|${slot.id}`;
                const isSelected = selections.has(key);
                return (
                  <div
                    key={key}
                    className={`schedule-cell ${isSelected ? 'unavailable' : 'available'}`}
                    onClick={() => toggleSlot(day, slot.id)}
                    data-day={day}
                    style={{ minHeight: '70px', fontSize: '0.85rem' }}
                  >
                    {isSelected ? '✕ Absent' : '—'}
                  </div>
                );
              })}
            </>
          ))}
        </div>

        <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
          <button className="btn btn-primary" onClick={handleSubmit} disabled={saving}>
            {saving ? 'Enregistrement...' : '✓ Valider mon emploi du temps'}
          </button>
        </div>
      </div>
    </div>
  );
}
