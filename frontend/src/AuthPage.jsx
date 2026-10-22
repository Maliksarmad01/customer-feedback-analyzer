import React, { useState } from 'react';
import { Activity, AlertCircle, ArrowRight, Check, Eye, EyeOff, LoaderCircle, Lock, Mail, ShieldCheck, User } from 'lucide-react';
import { api } from './api.js';

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function passwordChecks(pw) {
  return [
    { label: 'At least 8 characters', ok: pw.length >= 8 },
    { label: 'A letter and a number', ok: /[A-Za-z]/.test(pw) && /\d/.test(pw) }
  ];
}

function Field({ id, label, icon: Icon, error, right, ...input }) {
  return (
    <div className="auth-field">
      <label htmlFor={id}>{label}</label>
      <div className={`auth-input ${error ? 'invalid' : ''}`}>
        <Icon size={16} />
        <input id={id} aria-invalid={!!error} aria-describedby={error ? `${id}-error` : undefined} {...input} />
        {right}
      </div>
      {error && <small id={`${id}-error`} className="field-error">{error}</small>}
    </div>
  );
}

export default function AuthPage({ initialMode = 'login', onAuthenticated }) {
  const [mode, setMode] = useState(initialMode);
  const [form, setForm] = useState({ name: '', email: '', password: '', confirm: '' });
  const [touched, setTouched] = useState({});
  const [showPw, setShowPw] = useState(false);
  const [busy, setBusy] = useState(false);
  const [serverError, setServerError] = useState('');
  const signup = mode === 'signup';

  const set = key => e => setForm(f => ({ ...f, [key]: e.target.value }));
  const blur = key => () => setTouched(t => ({ ...t, [key]: true }));

  const errors = {};
  if (signup && !form.name.trim()) errors.name = 'Enter your name.';
  if (!form.email.trim()) errors.email = 'Enter your email address.';
  else if (!EMAIL_RE.test(form.email.trim())) errors.email = 'Enter a valid email, like name@company.com.';
  if (!form.password) errors.password = 'Enter your password.';
  else if (signup && passwordChecks(form.password).some(c => !c.ok)) errors.password = 'Use at least 8 characters with a letter and a number.';
  if (signup && form.confirm !== form.password) errors.confirm = 'Passwords do not match.';
  const shown = key => (touched[key] ? errors[key] : undefined);

  function switchMode(next) {
    setMode(next); setServerError(''); setTouched({}); setShowPw(false);
    setForm(f => ({ ...f, password: '', confirm: '' }));
  }

  async function submit(e) {
    e.preventDefault();
    setServerError('');
    if (Object.keys(errors).length) {
      setTouched({ name: true, email: true, password: true, confirm: true });
      return;
    }
    setBusy(true);
    try {
      const payload = { name: form.name.trim(), email: form.email.trim().toLowerCase(), password: form.password };
      const session = signup ? await api.signup(payload) : await api.login(payload);
      if (!session?.access_token) throw new Error('The server did not return an access token.');
      onAuthenticated(session);
    } catch (err) {
      setServerError(err.message || 'Something went wrong. Try again.');
    } finally {
      setBusy(false);
    }
  }

  const pwToggle = (
    <button type="button" className="icon-button" onClick={() => setShowPw(v => !v)} aria-label={showPw ? 'Hide password' : 'Show password'}>
      {showPw ? <EyeOff size={16} /> : <Eye size={16} />}
    </button>
  );

  return (
    <div className="auth-shell">
      <aside className="auth-side">
        <div className="brand">
          <div className="brand-mark"><Activity size={22} /></div>
          <div><div className="brand-name">Feedback<span>IQ</span></div><div className="brand-caption">SUPPORT INTELLIGENCE</div></div>
        </div>
        <div className="auth-pitch">
          <h2>Know what every customer is asking for.</h2>
          <p>Sign in to classify feedback, spot urgent tickets, and keep an audit trail of every ticket action.</p>
          <ul>
            <li><Check size={15} /> Tickets and activity history are saved to the shared workspace</li>
            <li><Check size={15} /> Every request to the API is checked for a valid login</li>
            <li><Check size={15} /> Passwords are hashed by the backend, never stored in plain text</li>
          </ul>
        </div>
        <p className="auth-side-foot"><ShieldCheck size={14} /> Rule-based analysis · Local demo</p>
      </aside>

      <main className="auth-main">
        <form className="auth-card" onSubmit={submit} noValidate aria-labelledby="auth-title">
          <h1 id="auth-title">{signup ? 'Create your account' : 'Log in to FeedbackIQ'}</h1>
          <p className="auth-sub">{signup ? 'It takes less than a minute.' : 'Welcome back. Enter your details to continue.'}</p>

          {serverError && <div className="inline-error" role="alert"><AlertCircle size={15} />{serverError}</div>}

          {signup && <Field id="name" label="Full name" icon={User} type="text" autoComplete="name" value={form.name} onChange={set('name')} onBlur={blur('name')} error={shown('name')} placeholder="Ayesha Khan" />}
          <Field id="email" label="Email" icon={Mail} type="email" autoComplete="email" value={form.email} onChange={set('email')} onBlur={blur('email')} error={shown('email')} placeholder="name@company.com" />
          <Field id="password" label="Password" icon={Lock} type={showPw ? 'text' : 'password'} autoComplete={signup ? 'new-password' : 'current-password'} value={form.password} onChange={set('password')} onBlur={blur('password')} error={shown('password')} placeholder={signup ? 'Create a password' : 'Your password'} right={pwToggle} />

          {signup && <>
            <ul className="pw-rules" aria-label="Password requirements">
              {passwordChecks(form.password).map(c => <li key={c.label} className={c.ok ? 'ok' : ''}><Check size={13} />{c.label}</li>)}
            </ul>
            <Field id="confirm" label="Confirm password" icon={Lock} type={showPw ? 'text' : 'password'} autoComplete="new-password" value={form.confirm} onChange={set('confirm')} onBlur={blur('confirm')} error={shown('confirm')} placeholder="Repeat your password" />
          </>}

          <button className="btn primary auth-submit" disabled={busy}>
            {busy ? <LoaderCircle className="spin" size={16} /> : null}
            {busy ? (signup ? 'Creating account…' : 'Logging in…') : (signup ? 'Create account' : 'Log in')}
            {!busy && <ArrowRight size={16} />}
          </button>

          <p className="auth-switch">
            {signup ? 'Already have an account?' : 'New to FeedbackIQ?'}{' '}
            <button type="button" className="text-btn" onClick={() => switchMode(signup ? 'login' : 'signup')}>{signup ? 'Log in' : 'Create an account'}</button>
          </p>
        </form>
      </main>
    </div>
  );
}
