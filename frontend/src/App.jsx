import { useEffect, useState } from 'react';
import { listTickets, submitTicket } from './api.js';

export default function App() {
  const [tickets, setTickets] = useState([]);
  const [title, setTitle] = useState('');
  const [message, setMessage] = useState('');
  const [category, setCategory] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  async function refresh() {
    try {
      const data = await listTickets();
      setTickets(data);
    } catch (e) {
      setError(String(e));
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  async function onSubmit(e) {
    e.preventDefault();
    setError(null);
    if (!title.trim() || !message.trim()) return;
    setLoading(true);
    try {
      await submitTicket({
        title: title.trim(),
        message: message.trim(),
        category: category.trim() || null,
      });
      setTitle('');
      setMessage('');
      setCategory('');
      await refresh();
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="container">
      <header>
        <h1>Ticket Analyzer</h1>
        <p className="subtitle">
          Submit a ticket and we will analyze its sentiment using a tiny
          Hugging Face model.
        </p>
      </header>

      <section className="card">
        <h2>New ticket</h2>
        <form onSubmit={onSubmit}>
          <label>
            Title
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Short summary"
              required
            />
          </label>
          <label>
            Message
            <textarea
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              placeholder="Describe the issue..."
              rows={4}
              required
            />
          </label>
          <label>
            Category (optional)
            <input
              type="text"
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              placeholder="e.g. lab, billing"
            />
          </label>
          <button type="submit" disabled={loading}>
            {loading ? 'Submitting...' : 'Submit ticket'}
          </button>
        </form>
        {error && <p className="error">{error}</p>}
      </section>

      <section className="card">
        <h2>Tickets ({tickets.length})</h2>
        {tickets.length === 0 ? (
          <p className="empty">No tickets yet.</p>
        ) : (
          <ul className="ticket-list">
            {tickets.map((t) => (
              <li key={t.id} className={`ticket ${t.sentiment === 'POSITIVE' ? 'pos' : 'neg'}`}>
                <div className="ticket-head">
                  <strong>#{t.id}</strong>
                  <span className="sentiment">
                    {t.sentiment} ({(t.confidence * 100).toFixed(1)}%)
                  </span>
                </div>
                <div className="ticket-title">{t.title}</div>
                <div className="ticket-message">{t.message}</div>
                <div className="ticket-meta">
                  {t.category && <span className="badge">{t.category}</span>}
                  <span className="time">{new Date(t.created_at).toLocaleString()}</span>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}