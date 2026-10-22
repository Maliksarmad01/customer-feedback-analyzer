import React from 'react';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { Activity, AlertCircle, ArrowDownToLine, ArrowRight, BarChart3, CheckCircle2, ChevronDown, CircleHelp, FileText, LayoutDashboard, LifeBuoy, LoaderCircle, MessageSquareText, Search, Send, ShieldCheck, Sparkles, Ticket, TrendingUp, X, Trash2, Check, RotateCcw, CircleCheck, History, RefreshCw, LogOut } from 'lucide-react';
import { api, setUnauthorizedHandler } from './api.js';
import { auth } from './auth.js';
import AuthPage from './AuthPage.jsx';

const NAV = [{ id: 'overview', label: 'Overview', icon: LayoutDashboard }, { id: 'analyze', label: 'Analyze feedback', icon: Sparkles }, { id: 'tickets', label: 'Ticket explorer', icon: Ticket }, { id: 'activity', label: 'Activity history', icon: History }, { id: 'analytics', label: 'Analytics', icon: BarChart3 }];
const catTone = { 'Bug Report': 'violet', 'Feature Request': 'blue', 'Billing Issue': 'amber', 'General Inquiry': 'green' };
const priTone = { Urgent: 'red', High: 'orange', Medium: 'blue', Low: 'green' };
const short = (s, n = 68) => !s ? '—' : s.length > n ? `${s.slice(0, n)}…` : s;
const normalizedStatus = status => String(status || 'open').toLowerCase();
const dateLabel = value => { if (!value) return '—'; const d = new Date(value); return Number.isNaN(d.getTime()) ? value : d.toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }); };
function Badge({ children, tone = 'neutral', dot = false }) { return <span className={`badge ${tone}`}>{dot && <i />}{children}</span>; }
function Heading({ eyebrow, title, description, actions }) { return <div className="page-heading"><div><div className="eyebrow">{eyebrow}</div><h1>{title}</h1><p>{description}</p></div>{actions && <div className="heading-actions">{actions}</div>}</div>; }
function Stat({ icon: Icon, label, value, note, tone }) { return <article className="stat-card"><div className={`stat-icon ${tone}`}><Icon size={19} /></div><div className="stat-label">{label}</div><div className="stat-value">{value}</div><div className="stat-note">{note}</div></article>; }
function Empty({ title, description, icon: Icon = MessageSquareText }) { return <div className="empty"><div><Icon size={23} /></div><strong>{title}</strong><p>{description}</p></div>; }

function Dashboard({ user, onLogout }) {
  const [page, setPage] = useState('overview');
  const [health, setHealth] = useState('checking');
  const [tickets, setTickets] = useState([]);
  const [total, setTotal] = useState(0);
  const [analytics, setAnalytics] = useState(null);
  const [activities, setActivities] = useState([]);
  const [activityTotal, setActivityTotal] = useState(0);
  const [activityLoading, setActivityLoading] = useState(false);
  const [activityFilter, setActivityFilter] = useState('All actions');
  const [activityQuery, setActivityQuery] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [toast, setToast] = useState('');
  const [query, setQuery] = useState('');
  const [priority, setPriority] = useState('All priorities');
  const [category, setCategory] = useState('All categories');
  const [statusFilter, setStatusFilter] = useState('All statuses');
  const [actionBusy, setActionBusy] = useState(null);
  const load = useCallback(async () => {
    setLoading(true); setError('');
    try {
      const [h, t, a] = await Promise.all([api.health(), api.tickets(), api.analytics()]);
      setHealth(h?.status === 'healthy' ? 'online' : 'online');
      const rows = Array.isArray(t) ? t : (t?.tickets || t?.items || []);
      setTickets(rows); setTotal(t?.total ?? rows.length); setAnalytics(a);
    } catch (e) { setHealth('offline'); setError(e.message || 'Could not load backend data.'); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { load(); }, [load]);
  const loadActivity = useCallback(async () => {
    setActivityLoading(true);
    try {
      const data = await api.activity(300, 0);
      setActivities(data?.activities || []);
      setActivityTotal(data?.total ?? (data?.activities || []).length);
    } catch (e) {
      setError(e.message || 'Could not load ticket activity history.');
    } finally { setActivityLoading(false); }
  }, []);
  useEffect(() => { if (page === 'activity') loadActivity(); }, [page, loadActivity]);
  const notify = message => { setToast(message); window.setTimeout(() => setToast(''), 3000); };
  const filtered = useMemo(() => tickets.filter(t => {
    const q = query.toLowerCase();
    const matches = String(t.message || '').toLowerCase().includes(q) || String(t.category || '').toLowerCase().includes(q) || String(t.product_feature || '').toLowerCase().includes(q);
    const status = normalizedStatus(t.status);
    return matches && (priority === 'All priorities' || t.priority === priority) && (category === 'All categories' || t.category === category) && (statusFilter === 'All statuses' || status === statusFilter.toLowerCase());
  }), [tickets, query, priority, category, statusFilter]);
  const exportFile = async format => { try { const blob = await api.exportFile(format); const url = URL.createObjectURL(blob); const a = document.createElement('a'); a.href = url; a.download = `customer-feedback-tickets.${format}`; document.body.appendChild(a); a.click(); a.remove(); URL.revokeObjectURL(url); } catch (e) { setError(e.message || 'Could not export tickets.'); } };
  const updateTicketStatus = async (ticket, action) => {
    if (!ticket?.id) return;
    const label = action === 'resolve' ? 'mark this ticket as resolved' : 'reopen this ticket';
    if (!window.confirm(`Are you sure you want to ${label}?`)) return;
    setActionBusy(`${ticket.id}:${action}`); setError('');
    try {
      let result;
      if (action === 'resolve') result = await api.resolveTicket(ticket.id);
      else result = await api.reopenTicket(ticket.id);
      if (action === 'resolve') notify(`Ticket #${ticket.id} marked as resolved.`);
      else notify(`Ticket #${ticket.id} reopened as new ticket #${result?.ticket?.id ?? 'created'}.`);
      await load();
      if (page === 'activity') await loadActivity();
    } catch (e) { setError(e.message || 'Could not update ticket status.'); }
    finally { setActionBusy(null); }
  };
  const removeTicket = async ticket => {
    if (!ticket?.id || !window.confirm(`Permanently delete ticket #${ticket.id}? This cannot be undone.`)) return;
    setActionBusy(`${ticket.id}:delete`); setError('');
    try { await api.deleteTicket(ticket.id); notify(`Ticket #${ticket.id} deleted; history retained.`); await load(); if (page === 'activity') await loadActivity(); }
    catch (e) { setError(e.message || 'Could not delete ticket.'); }
    finally { setActionBusy(null); }
  };
  const urgent = tickets.filter(t => t.priority === 'Urgent').length;
  const negative = tickets.filter(t => t.sentiment === 'Negative').length;
  return <div className="shell">
    <aside className="sidebar">
      <div className="brand"><div className="brand-mark"><Activity size={22} /></div><div><div className="brand-name">Feedback<span>IQ</span></div><div className="brand-caption">SUPPORT INTELLIGENCE</div></div></div>
      <div className="nav-label">WORKSPACE</div><nav>{NAV.map(({ id, label, icon: Icon }) => <button key={id} className={`nav-item ${page === id ? 'active' : ''}`} onClick={() => setPage(id)}><Icon size={18} /><span>{label}</span>{id === 'tickets' && total > 0 && <b>{total}</b>}</button>)}</nav>
      <div className="sidebar-bottom"><div className="help-card"><div className="help-icon"><LifeBuoy size={18} /></div><strong>Need a hand?</strong><p>Open the API docs to explore the backend endpoints.</p><button onClick={() => window.open('http://127.0.0.1:8000/docs', '_blank', 'noopener,noreferrer')}>Open API docs <ArrowRight size={14} /></button></div><div className="profile"><div className="avatar">{(user?.name || user?.email || 'F').trim().charAt(0).toUpperCase()}</div><div><strong>{user?.name || 'Signed in'}</strong><span>{user?.email || ''}</span></div><button className="icon-button" title="Log out" aria-label="Log out" onClick={onLogout}><LogOut size={17} /></button></div></div>
    </aside>
    <main className="main"><header className="topbar"><div className="breadcrumb">Workspace <span>/</span> <strong>{NAV.find(n => n.id === page)?.label}</strong></div><div className="top-actions"><span className={`api-state ${health}`}><i />API {health === 'online' ? 'connected' : health === 'offline' ? 'offline' : 'checking'}</span><button className="btn secondary small" onClick={load}><Activity size={15} /> Refresh</button></div></header>
      <div className="content">
        {error && <div className="error-banner"><AlertCircle size={19} /><div><strong>Backend connection issue</strong><p>{error}</p><small>Start FastAPI in your backend terminal, then refresh this page.</small></div><button className="icon-button" onClick={() => setError('')}><X size={17} /></button></div>}
        {page === 'overview' && <>
          <Heading eyebrow="YOUR SUPPORT, AT A GLANCE" title="Feedback overview" description="Turn incoming customer messages into actionable support insights." actions={<button className="btn primary" onClick={() => setPage('analyze')}><Sparkles size={16} /> Analyze feedback</button>} />
          <section className="welcome"><div className="welcome-symbol"><Sparkles size={24} /></div><div className="welcome-copy"><div className="welcome-kicker">CUSTOMER SIGNALS, SIMPLIFIED</div><h2>Understand every message.</h2><p>Classify feedback, spot urgent issues, and draft a helpful next reply — all in one workspace.</p></div><div className="welcome-art"><div>✓ <span><b>Fast insights</b><small>One message at a time</small></span></div><div>✦ <span><b>Clear priorities</b><small>Know what to handle first</small></span></div></div></section>
          <div className="section-head"><div><h2>Workspace metrics</h2><p>A snapshot of your saved support tickets</p></div><span className="live"><i /> Live from API</span></div>
          <div className="stats"><Stat icon={Ticket} label="Total tickets" value={loading ? '…' : total} note="Accepted messages saved" tone="purple" /><Stat icon={AlertCircle} label="Urgent priority" value={loading ? '…' : urgent} note="Needs prompt attention" tone="red" /><Stat icon={TrendingUp} label="Negative sentiment" value={loading ? '…' : negative} note="May need careful response" tone="amber" /><Stat icon={BarChart3} label="Categories tracked" value={Object.keys(analytics?.by_category || {}).length || 4} note="Intent groups supported" tone="blue" /></div>
          <div className="dashboard-grid"><section className="panel recent"><div className="panel-head"><div><h3>Recent tickets</h3><p>Latest analyzed customer messages</p></div><button className="text-btn" onClick={() => setPage('tickets')}>View all <ArrowRight size={14} /></button></div>{tickets.slice(0, 5).length ? <div className="recent-list">{tickets.slice(0, 5).map((t, i) => <div className="recent-row" key={t.id ?? i}><div className={`ticket-icon ${catTone[t.category] || 'neutral'}`}><MessageSquareText size={17} /></div><div className="recent-copy"><b>{short(t.message, 61)}</b><span>{t.category || 'Uncategorized'} · {dateLabel(t.created_at)}</span></div><Badge tone={priTone[t.priority] || 'neutral'} dot>{t.priority || 'Unassigned'}</Badge></div>)}</div> : <Empty title="No tickets yet" description="Analyze your first customer message to see it here." icon={Ticket} />}</section>
            <section className="panel breakdown"><div className="panel-head"><div><h3>Ticket breakdown</h3><p>Distribution by priority</p></div><div className="panel-mini-icon"><BarChart3 size={17} /></div></div><div className="bars">{['Urgent', 'High', 'Medium', 'Low'].map(k => { const data = analytics?.by_priority || {}; const count = Number(data[k]) || 0; const max = Math.max(1, ...Object.values(data).map(Number)); return <div className="bar-row" key={k}><div><span>{k}</span><b>{count}</b></div><div className="track"><i className={priTone[k]} style={{ width: `${count / max * 100}%` }} /></div></div> })}</div><div className="breakdown-foot"><span>● Based on saved tickets</span><button className="text-btn" onClick={() => setPage('analytics')}>Full analytics <ArrowRight size={14} /></button></div></section></div>
          <div className="quick-actions"><button onClick={() => setPage('analyze')}><span className="quick-icon purple"><Sparkles size={18} /></span><span><b>Analyze a message</b><small>Classify and prioritize new feedback</small></span><ArrowRight size={17} /></button><button onClick={() => setPage('tickets')}><span className="quick-icon blue"><FileText size={18} /></span><span><b>Explore tickets</b><small>Search, filter, and export records</small></span><ArrowRight size={17} /></button></div>
          <p className="disclaimer"><ShieldCheck size={14} /> Rule-based results should be reviewed before use in customer communications.</p>
        </>}
        {page === 'analyze' && <AnalyzePage onDone={async result => { await load(); notify(result.accepted ? 'Feedback analyzed and saved.' : 'Message was filtered.'); }} />}
        {page === 'tickets' && <><Heading eyebrow="TICKET WORKSPACE" title="Ticket explorer" description="Search analyzed messages, review classifications, and export records." actions={<><button className="btn secondary" onClick={() => exportFile('csv')}><ArrowDownToLine size={15} /> Export CSV</button><button className="btn secondary" onClick={() => exportFile('json')}><ArrowDownToLine size={15} /> Export JSON</button></>} /><section className="panel table-panel"><div className="table-toolbar"><div className="search"><Search size={16} /><input value={query} onChange={e => setQuery(e.target.value)} placeholder="Search messages, categories, features…" /></div><div className="select-wrap"><select value={category} onChange={e => setCategory(e.target.value)}><option>All categories</option><option>Bug Report</option><option>Feature Request</option><option>Billing Issue</option><option>General Inquiry</option></select><ChevronDown size={14} /></div><div className="select-wrap"><select value={priority} onChange={e => setPriority(e.target.value)}><option>All priorities</option><option>Urgent</option><option>High</option><option>Medium</option><option>Low</option></select><ChevronDown size={14} /></div><div className="select-wrap"><select value={statusFilter} onChange={e => setStatusFilter(e.target.value)}><option>All statuses</option><option>Open</option><option>Resolved</option></select><ChevronDown size={14} /></div></div><div className="table-meta"><span>{filtered.length} shown · {total} total records</span><span><CircleCheck size={14} /> Resolve completed tickets or delete unwanted records</span></div><div className="table-scroll"><table><thead><tr><th>Customer message</th><th>Category</th><th>Priority</th><th>Sentiment</th><th>Product / feature</th><th>Status</th><th>Created</th><th>Actions</th></tr></thead><tbody>{filtered.map((t, i) => <tr key={t.id ?? i}><td><div className="message-cell"><b>{short(t.message, 66)}</b><span>Ticket #{t.id ?? '—'}</span></div></td><td><Badge tone={catTone[t.category] || 'neutral'}>{t.category || '—'}</Badge></td><td><Badge tone={priTone[t.priority] || 'neutral'} dot>{t.priority || '—'}</Badge></td><td><span className={`sentiment ${String(t.sentiment || '').toLowerCase()}`}>{t.sentiment || '—'}</span></td><td>{t.product_feature || '—'}</td><td><Badge tone={normalizedStatus(t.status) === 'resolved' ? 'green' : 'blue'} dot>{normalizedStatus(t.status) === 'resolved' ? 'Resolved' : 'Open'}</Badge></td><td className="date-cell">{dateLabel(t.created_at)}</td><td><div className="ticket-actions">{normalizedStatus(t.status) === 'resolved' ? <button className="action-btn" title="Reopen ticket" disabled={actionBusy === `${t.id}:reopen`} onClick={() => updateTicketStatus(t, 'reopen')}><RotateCcw size={15} /><span>Reopen</span></button> : <button className="action-btn resolve" title="Mark resolved" disabled={actionBusy === `${t.id}:resolve`} onClick={() => updateTicketStatus(t, 'resolve')}><Check size={15} /><span>Resolve</span></button>}<button className="action-btn delete" title="Delete ticket permanently" disabled={actionBusy === `${t.id}:delete`} onClick={() => removeTicket(t)}><Trash2 size={15} /><span>Delete</span></button></div></td></tr>)}</tbody></table></div>{loading ? <div className="table-state"><LoaderCircle className="spin" /> Loading tickets…</div> : filtered.length === 0 ? <Empty title="No matching tickets" description="Change your search or filters, or analyze a new customer message." icon={Search} /> : null}</section><p className="disclaimer"><FileText size={14} /> Export downloads the backend's full export; table filters only change the visible list.</p></>}
        {page === 'activity' && <ActivityPage activities={activities} total={activityTotal} loading={activityLoading} query={activityQuery} setQuery={setActivityQuery} filter={activityFilter} setFilter={setActivityFilter} onRefresh={loadActivity} />}
        {page === 'analytics' && <AnalyticsPage analytics={analytics} tickets={tickets} loading={loading} />}
      </div><footer className="footer"><span>FeedbackIQ · Customer Feedback Analyzer</span><span><ShieldCheck size={14} /> Rule-based analysis · Local demo</span></footer>
    </main>{toast && <div className="toast"><CheckCircle2 size={18} />{toast}</div>}
  </div>;
}

function AnalyzePage({ onDone }) {
  const [message, setMessage] = useState(''); const [result, setResult] = useState(null); const [error, setError] = useState(''); const [busy, setBusy] = useState(false);
  const [importFile, setImportFile] = useState(null); const [importBusy, setImportBusy] = useState(false); const [importResult, setImportResult] = useState(null); const [importError, setImportError] = useState('');
  async function submit(e) { e.preventDefault(); setError(''); setResult(null); setBusy(true); try { const data = await api.analyze(message.trim()); setResult(data); await onDone(data); } catch (err) { setError(err.message || 'Analysis failed.'); } finally { setBusy(false); } }
  const accepted = result?.accepted;
  return <><Heading eyebrow="MESSAGE INTELLIGENCE" title="Analyze feedback" description="Classify intent, estimate sentiment, and draft a suggested reply from a customer message." />
    <section className="panel import-panel" style={{ marginTop: 0, marginBottom: 18, padding: 20, border: "1px solid #dcd5ff", boxShadow: "0 4px 18px rgba(112,87,232,.06)" }}>
      <div className="panel-head"><div><h3>Upload CSV or JSON file</h3><p>Choose a file from your computer and analyze up to 100 customer messages at once.</p></div><div className="panel-mini-icon"><FileText size={17} /></div></div>
      <div style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
        <input aria-label="Choose CSV or JSON file" type="file" accept=".csv,.json,text/csv,application/json" onChange={e => { setImportFile(e.target.files?.[0] || null); setImportResult(null); setImportError(''); }} style={{ flex: '1 1 260px', padding: 10, border: '1px solid #e7e6f0', borderRadius: 8, background: '#fdfdff', fontSize: 12 }} />
        <button className="btn primary" disabled={!importFile || importBusy} onClick={async () => { setImportError(''); setImportResult(null); setImportBusy(true); try { const data = await api.importFile(importFile); setImportResult(data); await onDone({ accepted: data.accepted_count > 0 }); } catch (err) { setImportError(err.message || 'Import failed.'); } finally { setImportBusy(false); } }}>{importBusy ? <LoaderCircle className="spin" size={16} /> : <ArrowDownToLine size={16} />} {importBusy ? 'Importing…' : 'Upload and analyze'}</button>
      </div>
      <p className="disclaimer"><ShieldCheck size={14} /> CSV files need a <code>message</code> column. JSON may be an array of message strings, an array of objects containing <code>message</code>, or an object with a <code>messages</code> array. Maximum 2 MB and 100 messages.</p>
      {importError && <div className="inline-error"><AlertCircle size={15} />{importError}</div>}
      {importResult && <div style={{ marginTop: 12, padding: 14, border: '1px solid #e5e1fa', borderRadius: 9, background: '#fbfaff' }}><strong style={{ fontSize: 12 }}>Import complete</strong><p style={{ fontSize: 11, color: '#77768b', margin: '7px 0' }}>Processed {importResult.total_submitted} messages · Saved {importResult.accepted_count} · Filtered {importResult.rejected_count}</p><span style={{ fontSize: 11, color: '#77768b' }}>Open Ticket explorer to review imported records.</span></div>}
    </section><div className="analyze-grid"><section className="panel input-panel"><div className="panel-head"><div><h3>Customer message</h3><p>What did your customer say?</p></div><div className="panel-mini-icon"><MessageSquareText size={17} /></div></div><form onSubmit={submit}><label htmlFor="message">Message content</label><textarea id="message" value={message} onChange={e => setMessage(e.target.value)} maxLength={5000} required placeholder="Example: The checkout page crashes whenever I try to pay. Please help me fix this urgently…" /><div className="textarea-meta"><span>Specific details can improve rule-based results.</span><span>{message.length}/5000</span></div>{error && <div className="inline-error"><AlertCircle size={15} />{error}</div>}<button className="btn primary submit" disabled={!message.trim() || busy}>{busy ? <LoaderCircle className="spin" size={16} /> : <Send size={16} />} {busy ? 'Analyzing…' : 'Analyze message'}</button></form><div className="examples"><span>TRY AN EXAMPLE</span><button type="button" onClick={() => setMessage('The checkout page crashes every time I click Pay. Please fix this urgently.')}>Bug report</button><button type="button" onClick={() => setMessage('I was charged twice for my subscription and need a refund.')}>Billing issue</button><button type="button" onClick={() => setMessage('It would be great if you added dark mode to the dashboard.')}>Feature request</button></div></section>
      <section className="panel result-panel"><div className="panel-head"><div><h3>Analysis results</h3><p>Classification and response suggestion</p></div><div className="result-icon"><Sparkles size={18} /></div></div>{!result ? <Empty title="Your results will appear here" description="Submit a message to see its category, priority, sentiment, product feature, and suggested reply." icon={Sparkles} /> : !accepted ? <div className="rejected"><div><AlertCircle size={22} /></div><h3>Message filtered</h3><p>This message was not saved as a support ticket.</p><section><span>FILTER REASON</span><b>{result.reason || 'Message did not pass filtering rules.'}</b></section></div> : <div className="result-content"><div className="success-line"><CheckCircle2 size={16} /> Analysis complete <span>Ticket #{result.ticket_id ?? 'saved'}</span></div><div className="result-metrics"><div><label>Category</label><Badge tone={catTone[result.category] || 'neutral'}>{result.category || '—'}</Badge></div><div><label>Priority</label><Badge tone={priTone[result.priority] || 'neutral'} dot>{result.priority || '—'}</Badge></div><div><label>Sentiment</label><Badge tone={result.sentiment === 'Negative' ? 'red' : result.sentiment === 'Positive' ? 'green' : 'blue'}>{result.sentiment || '—'}</Badge></div><div><label>Product / feature</label><b>{result.product_feature || 'Not identified'}</b></div></div><div className="reply-box"><div className="reply-head"><div><b>Suggested reply</b><small>Review before sending</small></div><button className="copy" onClick={async () => { try { await navigator.clipboard.writeText(result.suggested_reply || ''); } catch { setError('Clipboard access was blocked by the browser.'); } }}>Copy reply</button></div><p>{result.suggested_reply || 'No suggested reply was generated.'}</p></div><p className="disclaimer"><ShieldCheck size={14} /> This is a rule-based suggestion, not an automatically sent response.</p></div>}</section></div>
  </>;
}

function ActivityPage({ activities, total, loading, query, setQuery, filter, setFilter, onRefresh }) {
  const actionTone = { CREATED: 'blue', RESOLVED: 'green', REOPENED: 'violet', DELETED: 'red' };
  const actionIcon = { CREATED: Ticket, RESOLVED: CheckCircle2, REOPENED: RotateCcw, DELETED: Trash2 };
  const visible = activities.filter(item => {
    const action = String(item.action || '').toUpperCase();
    const q = query.trim().toLowerCase();
    const snapshotMessage = item.ticket_snapshot?.message || '';
    const matchesQuery = !q || String(item.ticket_id).includes(q) || String(item.related_ticket_id || '').includes(q) || snapshotMessage.toLowerCase().includes(q) || String(item.details || '').toLowerCase().includes(q) || action.toLowerCase().includes(q);
    return matchesQuery && (filter === 'All actions' || action === filter);
  });
  return <>
    <Heading eyebrow="AUDIT TRAIL" title="Activity history" description="A permanent timeline of ticket creation, resolution, reopening, and deletion." actions={<button className="btn secondary" onClick={onRefresh} disabled={loading}><RefreshCw size={15} /> Refresh history</button>} />
    <div className="activity-stats">
      <div className="activity-stat"><span>Total events</span><strong>{total}</strong></div>
      <div className="activity-stat"><span>Created</span><strong>{activities.filter(a => a.action === 'CREATED').length}</strong></div>
      <div className="activity-stat"><span>Resolved</span><strong>{activities.filter(a => a.action === 'RESOLVED').length}</strong></div>
      <div className="activity-stat"><span>Reopened</span><strong>{activities.filter(a => a.action === 'REOPENED').length}</strong></div>
      <div className="activity-stat"><span>Deleted</span><strong>{activities.filter(a => a.action === 'DELETED').length}</strong></div>
    </div>
    <section className="panel activity-panel">
      <div className="activity-toolbar">
        <div className="search"><Search size={16} /><input value={query} onChange={e => setQuery(e.target.value)} placeholder="Search ticket ID, message, or event…" /></div>
        <div className="select-wrap"><select value={filter} onChange={e => setFilter(e.target.value)}><option>All actions</option><option value="CREATED">Created</option><option value="RESOLVED">Resolved</option><option value="REOPENED">Reopened</option><option value="DELETED">Deleted</option></select><ChevronDown size={14} /></div>
      </div>
      <div className="table-meta"><span>{visible.length} shown · {total} total events</span><span>History remains available after a ticket is deleted</span></div>
      {loading ? <div className="table-state"><LoaderCircle className="spin" /> Loading activity history…</div> : visible.length === 0 ? <Empty title="No activity found" description="Ticket actions will appear here after you create, resolve, reopen, or delete tickets." icon={History} /> :
        <div className="table-scroll"><table className="activity-table"><thead><tr><th>Action</th><th>Ticket</th><th>Related ticket</th><th>Details</th><th>Previous status</th><th>New status</th><th>Recorded at</th></tr></thead><tbody>
          {visible.map(item => { const action = String(item.action || '').toUpperCase(); const Icon = actionIcon[action] || Activity; const snapshot = item.ticket_snapshot || {}; return <tr key={item.id}><td><span className={`activity-action ${actionTone[action] || 'neutral'}`}><Icon size={14} />{action.charAt(0) + action.slice(1).toLowerCase()}</span></td><td><div className="message-cell"><b>#{item.ticket_id}</b><span>{short(snapshot.message, 42)}</span></div></td><td>{item.related_ticket_id ? <Badge tone="violet">#{item.related_ticket_id}</Badge> : '—'}</td><td className="activity-details">{item.details || '—'}</td><td>{item.previous_status ? <Badge tone={item.previous_status === 'resolved' ? 'green' : 'blue'}>{item.previous_status}</Badge> : '—'}</td><td>{item.new_status ? <Badge tone={item.new_status === 'resolved' ? 'green' : 'blue'}>{item.new_status}</Badge> : '—'}</td><td className="date-cell">{dateLabel(item.created_at)}</td></tr> })}
        </tbody></table></div>}
    </section>
    <p className="disclaimer"><ShieldCheck size={14} /> The audit trail reflects actions recorded by the backend after activity logging was added. Earlier actions cannot be reconstructed automatically.</p>
  </>;
}

function AnalyticsPage({ analytics, tickets, loading }) {
  const groups = [{ title: 'Intent categories', subtitle: 'What customers are contacting you about', data: analytics?.by_category || {}, keys: ['Bug Report', 'Feature Request', 'Billing Issue', 'General Inquiry'], tones: catTone }, { title: 'Priority levels', subtitle: 'Which messages need attention first', data: analytics?.by_priority || {}, keys: ['Urgent', 'High', 'Medium', 'Low'], tones: priTone }, { title: 'Sentiment signals', subtitle: 'How messages are interpreted', data: analytics?.by_sentiment || {}, keys: ['Negative', 'Neutral', 'Positive'], tones: { Negative: 'red', Neutral: 'blue', Positive: 'green' } }];
  return <><Heading eyebrow="SUPPORT INSIGHTS" title="Analytics" description="Explore saved feedback by intent, priority, and sentiment." /><div className="analytics-top"><div className="analytics-total"><div className="stat-icon purple"><BarChart3 size={19} /></div><span>Total analyzed tickets</span><strong>{loading ? '…' : analytics?.total_tickets ?? tickets.length}</strong><small>Saved records in your workspace</small></div><div className="analytics-note"><div className="panel-mini-icon"><Activity size={18} /></div><div><b>How to read these insights</b><p>Counts come from the backend analytics endpoint. This version uses keyword rules, not trained ML confidence scores.</p></div></div></div><div className="analytics-grid">{groups.map(g => { const max = Math.max(1, ...g.keys.map(k => Number(g.data[k]) || 0)); return <section className="panel analytics-card" key={g.title}><div className="panel-head"><div><h3>{g.title}</h3><p>{g.subtitle}</p></div></div><div className="bars">{g.keys.map(k => <div className="bar-row" key={k}><div><span>{k}</span><b>{Number(g.data[k]) || 0}</b></div><div className="track"><i className={g.tones[k] || 'violet'} style={{ width: `${(Number(g.data[k]) || 0) / max * 100}%` }} /></div></div>)}</div></section> })}</div><div className="analytics-note bottom-note"><div className="panel-mini-icon"><ShieldCheck size={18} /></div><div><b>Keep improving your analyzer</b><p>Review the rules against real examples and add regression tests when you discover new message patterns.</p></div></div></>;
}


export default function App() {
  const [session, setSession] = useState(() => (auth.getToken() ? { user: auth.getUser() } : null));
  const [checking, setChecking] = useState(() => !!auth.getToken());
  const logout = useCallback(() => { auth.clear(); setSession(null); }, []);

  useEffect(() => { setUnauthorizedHandler(logout); }, [logout]);

  // Confirm a saved token is still valid before showing the dashboard.
  useEffect(() => {
    if (!auth.getToken()) { setChecking(false); return; }
    let cancelled = false;
    api.me()
      .then(user => { if (cancelled) return; auth.save({ access_token: auth.getToken(), user }); setSession({ user }); })
      .catch(e => { if (cancelled) return; if (!/Cannot connect/.test(e.message)) logout(); })
      .finally(() => { if (!cancelled) setChecking(false); });
    return () => { cancelled = true; };
  }, [logout]);

  if (checking) return <div className="auth-loading"><LoaderCircle className="spin" size={22} /> Checking your session…</div>;
  if (!session) return <AuthPage onAuthenticated={s => { auth.save(s); setSession({ user: s.user }); }} />;
  return <Dashboard user={session.user} onLogout={logout} />;
}
