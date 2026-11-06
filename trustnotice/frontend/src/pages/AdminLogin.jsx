import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { Icon } from "../components/ui";

export default function AdminLogin({ student = false }) {
  const { login } = useAuth();
  const nav = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const submit = async (event) => {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const current = await login(email, password);
      nav(current.role === "student" ? "/student" : "/admin");
    } catch (reason) { setError(reason.message); }
    setBusy(false);
  };
  return <div className="mx-auto grid max-w-4xl items-center gap-8 md:grid-cols-2">
    <div className="hidden md:block">
      <span className="brand-shield"><Icon name="shield" size={23} /></span>
      <p className="page-eyebrow mt-6">{student ? "TRUSTNOTICE STUDENT PORTAL" : "INSTITUTIONAL SECURITY"}</p>
      <h1 className="mt-3 font-display text-4xl font-extrabold leading-tight tracking-tight">{student ? "Official notices, with confidence." : "Protect the integrity of every notice."}</h1>
      <p className="mt-4 max-w-sm text-sm leading-6 text-slate-400">Trust Every Notice. Verify Every Word. Sign in to your secure TRUSTNOTICE workspace.</p>
      <div className="mt-7 space-y-3 text-xs text-slate-400">
        {[["Ed25519", "Digitally signed institutional records"], ["SHA-256", "Notice integrity verification"], ["Private", "Role-based access to your portal"]].map(([label, detail]) => <div key={label} className="flex items-center gap-3"><Icon name="verify" size={15} className="text-emerald-300" /><span><b className="text-slate-200">{label}</b> · {detail}</span></div>)}
      </div>
    </div>
    <form onSubmit={submit} className="card mx-auto w-full max-w-md space-y-5 !p-6 md:!p-7">
      <div><div className="brand-mark md:hidden"><span className="brand-shield"><Icon name="shield" size={18} /></span><span>TRUST<span className="text-cyan">NOTICE</span></span></div><p className="page-eyebrow mt-1">{student ? "STUDENT PORTAL" : "ADMINISTRATOR PORTAL"}</p><h2 className="mt-2 font-display text-2xl font-extrabold">{student ? "Student sign in" : "Administrator login"}</h2><p className="mt-1 text-xs text-slate-500">Enter your account credentials to continue securely.</p></div>
      <label className="block text-xs font-medium text-slate-300">Email address<input className="input mt-1.5" type="email" autoComplete="username" placeholder="you@institution.edu" value={email} onChange={(event) => setEmail(event.target.value)} required /></label>
      <label className="block text-xs font-medium text-slate-300">Password<input className="input mt-1.5" type="password" autoComplete="current-password" placeholder="Enter your password" value={password} onChange={(event) => setPassword(event.target.value)} required /></label>
      {error && <p role="alert" className="rounded-lg border border-red-400/20 bg-red-400/[.06] px-3 py-2 text-xs text-red-300">{error}</p>}
      <button className="btn-primary w-full !py-3" disabled={busy}>{busy ? <><span className="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white" /> Authenticating…</> : <>Sign in securely <Icon name="arrow" size={15} /></>}</button>
      <div className="flex items-center justify-between border-t border-white/[.07] pt-4 text-[10px] text-slate-500"><span className="inline-flex items-center gap-1.5"><Icon name="shield" size={13} className="text-emerald-400" /> Secure connection</span><Link className="text-cyan-300 hover:text-cyan-200" to={student ? "/admin/login" : "/student/login"}>{student ? "Administrator login" : "Student login"} →</Link></div>
    </form>
  </div>;
}
