import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../services/api";
import { Chip, Icon } from "../components/ui";

const dateKey = (value) => {
  const date = new Date(value);
  return Number.isNaN(date.valueOf()) ? "" : date.toISOString().slice(0, 10);
};
const shortDate = (value) => value ? new Date(value).toLocaleDateString(undefined, { month: "short", day: "numeric" }) : "—";

function ActivityChart({ logs }) {
  const points = useMemo(() => {
    const days = Array.from({ length: 7 }, (_, index) => {
      const date = new Date();
      date.setDate(date.getDate() - (6 - index));
      const key = date.toISOString().slice(0, 10);
      return { key, label: date.toLocaleDateString(undefined, { weekday: "short" }), count: 0 };
    });
    const counts = new Map(days.map((day) => [day.key, 0]));
    logs.forEach((log) => {
      const key = dateKey(log.at);
      if (counts.has(key)) counts.set(key, counts.get(key) + 1);
    });
    return days.map((day) => ({ ...day, count: counts.get(day.key) }));
  }, [logs]);
  const max = Math.max(1, ...points.map((point) => point.count));
  const coords = points.map((point, index) => `${42 + index * 64},${123 - point.count / max * 82}`).join(" ");
  const area = `42,126 ${coords} ${42 + (points.length - 1) * 64},126`;
  return <div className="card h-full">
    <div className="mb-5 flex items-start justify-between"><div><h2 className="section-title">Verification activity</h2><p className="mt-1 text-[11px] text-slate-500">Daily checks · last 7 days</p></div><span className="rounded-lg border border-cyan-400/15 bg-cyan-400/5 px-2 py-1 text-[10px] text-cyan-200">Live data</span></div>
    <svg viewBox="0 0 450 158" className="h-[180px] w-full" role="img" aria-label="Daily verification activity for the last seven days">
      <defs><linearGradient id="activity-fill" x1="0" x2="0" y1="0" y2="1"><stop offset="0%" stopColor="#22d3ee" stopOpacity=".22" /><stop offset="100%" stopColor="#22d3ee" stopOpacity="0" /></linearGradient></defs>
      {[38, 78, 118].map((y) => <line key={y} x1="35" y1={y} x2="430" y2={y} className="chart-grid" />)}
      <polygon points={area} className="chart-area" />
      <polyline points={coords} className="chart-line" />
      {points.map((point, index) => {
        const x = 42 + index * 64;
        const y = 123 - point.count / max * 82;
        return <g key={point.key}><circle cx={x} cy={y} r="4" className="activity-dot"><title>{point.count} checks</title></circle><text x={x} y="148" textAnchor="middle" className="chart-label">{point.label}</text></g>;
      })}
    </svg>
    {!logs.length && <p className="mt-2 text-center text-xs text-slate-500">Verification activity will appear here as documents are checked.</p>}
  </div>;
}

function VerificationSplit({ authentic, suspicious }) {
  const total = authentic + suspicious;
  const radius = 44;
  const circumference = 2 * Math.PI * radius;
  const safeAuthentic = total ? authentic / total : 0;
  return <div className="card">
    <h2 className="section-title">Verification outcomes</h2><p className="mt-1 text-[11px] text-slate-500">Authentic versus suspicious documents</p>
    <div className="mt-4 flex items-center justify-center gap-8">
      <div className="relative h-32 w-32">
        <svg viewBox="0 0 112 112" className="h-full w-full -rotate-90">
          <circle cx="56" cy="56" r={radius} fill="none" stroke="rgba(239,68,68,.72)" strokeWidth="12" />
          {total > 0 && <circle cx="56" cy="56" r={radius} fill="none" stroke="#10b981" strokeWidth="12" strokeDasharray={`${circumference * safeAuthentic} ${circumference}`} strokeLinecap="round" />}
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center"><b className="font-display text-2xl">{total}</b><span className="text-[9px] text-slate-500">CHECKS</span></div>
      </div>
      <div className="space-y-3 text-xs">
        <div className="flex items-center gap-2"><i className="h-2 w-2 rounded-full bg-emerald-400" /> <span className="text-slate-400">Authentic</span><b className="ml-auto">{authentic}</b></div>
        <div className="flex items-center gap-2"><i className="h-2 w-2 rounded-full bg-red-400" /> <span className="text-slate-400">Suspicious</span><b className="ml-auto">{suspicious}</b></div>
        {!total && <p className="max-w-28 text-[10px] leading-4 text-slate-500">No verification attempts recorded yet.</p>}
      </div>
    </div>
  </div>;
}

function PublicationBars({ notices }) {
  const points = useMemo(() => {
    const months = Array.from({ length: 6 }, (_, index) => {
      const date = new Date();
      date.setDate(1);
      date.setMonth(date.getMonth() - (5 - index));
      return { key: `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}`, label: date.toLocaleDateString(undefined, { month: "short" }), count: 0 };
    });
    const counts = new Map(months.map((month) => [month.key, 0]));
    notices.forEach((notice) => {
      const date = new Date(notice.issue_date);
      const key = Number.isNaN(date.valueOf()) ? "" : `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}`;
      if (counts.has(key)) counts.set(key, counts.get(key) + 1);
    });
    return months.map((month) => ({ ...month, count: counts.get(month.key) }));
  }, [notices]);
  const max = Math.max(1, ...points.map((point) => point.count));
  return <div className="card">
    <h2 className="section-title">Notice publication trend</h2><p className="mt-1 text-[11px] text-slate-500">Issued notices · last 6 months</p>
    <div className="mt-6 flex h-36 items-end justify-between gap-3 border-b border-white/10 px-2">
      {points.map((point) => <div key={point.key} className="flex h-full flex-1 flex-col items-center justify-end gap-2">
        <span className="text-[10px] text-slate-400">{point.count}</span>
        <div className="w-full max-w-9 rounded-t-md bg-gradient-to-t from-blue-600/50 to-cyan-400/80 transition-all" style={{ height: `${Math.max(point.count ? 10 : 4, point.count / max * 95)}%` }} title={`${point.count} notices`} />
      </div>)}
    </div>
    <div className="mt-2 flex justify-between px-2">{points.map((point) => <span className="flex-1 text-center text-[9px] text-slate-500" key={point.key}>{point.label}</span>)}</div>
    {!notices.length && <p className="mt-8 text-center text-xs text-slate-500">Published notice trends will appear here.</p>}
  </div>;
}

export default function Dashboard() {
  const [d, setD] = useState({});
  const [ns, setNs] = useState([]);
  const [logs, setLogs] = useState([]);
  const [keys, setKeys] = useState([]);
  const [emergencyStats, setEmergencyStats] = useState({});
  const [students, setStudents] = useState([]);
  const [audit, setAudit] = useState([]);
  const [student, setStudent] = useState({ name: "", email: "", password: "", student_id: "", department: "", academic_year: "", class_name: "" });
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(true);
  const load = () => Promise.all([api.dashboard(), api.notices(), api.logs(), api.keys(), api.emergencyAnalytics(), api.students(), api.audit()])
    .then(([a, b, c, k, e, s, trail]) => { setD(a); setNs(b); setLogs(c); setKeys(k); setEmergencyStats(e); setStudents(s); setAudit(trail); })
    .catch((e) => setErr(e.message)).finally(() => setLoading(false));
  useEffect(() => { load(); }, []);
  const revoke = async (id) => {
    const reason = prompt(`Revocation reason for ${id}:`);
    if (reason?.trim()) { try { await api.revoke(id, reason.trim()); load(); } catch (e) { setErr(e.message); } }
  };
  const revokeKey = async (id) => {
    if (confirm(`Revoke key ${id}? Every notice signed with it will stop verifying.`)) {
      try { await api.revokeKey(id); load(); } catch (e) { setErr(e.message); }
    }
  };
  const dl = async (id) => {
    try { const url = await api.blobUrl(`/api/notices/${id}/download`); const anchor = document.createElement("a"); anchor.href = url; anchor.download = id; anchor.click(); }
    catch (e) { setErr(e.message); }
  };
  const createStudent = async (event) => {
    event.preventDefault(); setErr("");
    try {
      await api.createStudent(student);
      setStudent({ name: "", email: "", password: "", student_id: "", department: "", academic_year: "", class_name: "" });
      load();
    } catch (e) { setErr(e.message); }
  };
  const activeEmergencies = ns.filter((notice) => notice.is_emergency && notice.status === "active");
  const stats = [
    ["Total notices published", d.total_notices, "notices", "#3b82f6", "rgba(37,99,235,.2)"],
    ["Total verifications", (d.verified || 0) + (d.suspicious || 0), "verify", "#22d3ee", "rgba(34,211,238,.18)"],
    ["Authentic notices", d.verified, "shield", "#10b981", "rgba(16,185,129,.16)"],
    ["Suspicious documents", d.suspicious, "emergency", "#f59e0b", "rgba(245,158,11,.16)"],
    ["Revoked notices", d.revoked, "history", "#f87171", "rgba(239,68,68,.16)"],
    ["Active emergency alerts", activeEmergencies.length, "bell", "#fb7185", "rgba(244,63,94,.16)"],
  ];
  return <div className="space-y-7">
    <section className="flex flex-wrap items-end justify-between gap-4">
      <div><p className="page-eyebrow">Institutional security overview</p><h1 className="page-title mt-2">Welcome Back, Administrator</h1><p className="mt-2 text-sm text-slate-400">Monitor institutional notices and document authenticity.</p></div>
      <div className="flex flex-wrap gap-2">
        <Link to="/admin/new" className="btn-primary"><Icon name="publish" size={16} /> Publish New Notice</Link>
        <Link to="/admin/emergency" className="btn-ghost !border-red-400/20 !text-red-200"><Icon name="emergency" size={16} /> Create Emergency Alert</Link>
      </div>
    </section>
    {err && <div role="alert" className="rounded-xl border border-red-400/20 bg-red-400/5 px-4 py-3 text-sm text-red-300">{err}</div>}
    {loading ? <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-6">{stats.map(([label]) => <div key={label} className="metric-card h-32 animate-pulse bg-slate-800/50" />)}</div> : <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-6">
      {stats.map(([label, value, icon, color, glow]) => <div key={label} className="metric-card" style={{ "--metric-color": color, "--metric-glow": glow }}>
        <div className="metric-icon"><Icon name={icon} /></div><div className="metric-value">{value ?? "—"}</div><div className="metric-label">{label}</div>
      </div>)}
    </section>}
    <section className="grid gap-4 xl:grid-cols-[1.4fr_.8fr]">
      <ActivityChart logs={logs} /><VerificationSplit authentic={d.verified || 0} suspicious={d.suspicious || 0} />
    </section>
    <section className="grid gap-4 xl:grid-cols-2">
      <div id="analytics"><PublicationBars notices={ns} /></div>
      <div className="card" id="activity">
        <div className="mb-4 flex items-start justify-between"><div><h2 className="section-title">Recent activity</h2><p className="mt-1 text-[11px] text-slate-500">Latest document verification events</p></div><Link to="/verify" className="text-xs font-semibold text-cyan-300 hover:text-cyan-200">Verify document →</Link></div>
        <div className="space-y-1">
          {logs.slice(0, 6).map((item, index) => <div key={`${item.notice_id}-${item.at}-${index}`} className="flex items-center gap-3 rounded-xl px-2 py-3 transition hover:bg-white/[.025]">
            <span className={`grid h-8 w-8 place-items-center rounded-lg ${item.status === "GREEN" || item.status === "YELLOW" ? "bg-emerald-400/10 text-emerald-300" : "bg-red-400/10 text-red-300"}`}><Icon name={item.status === "GREEN" || item.status === "YELLOW" ? "verify" : "emergency"} size={16} /></span>
            <div className="min-w-0 flex-1"><div className="truncate text-xs font-semibold">{item.notice_id || "Unidentified document"}</div><div className="mt-1 text-[10px] text-slate-500">{item.at ? new Date(item.at).toLocaleString() : "Recently"}</div></div>
            <Chip ok={item.status === "GREEN" || item.status === "YELLOW" ? true : item.status === "RED" ? false : null} label={item.status} />
          </div>)}
          {!logs.length && <div className="rounded-xl border border-dashed border-white/10 px-4 py-7 text-center text-xs text-slate-500">No verification activity recorded yet.</div>}
        </div>
      </div>
    </section>
    <section className="card" id="notices">
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3"><div><h2 className="section-title">Emergency communication history</h2><p className="mt-1 text-[11px] text-slate-500">Recipient delivery, read receipts, and current notice status</p></div><Link to="/admin/emergency" className="text-xs font-semibold text-cyan-300">Create alert →</Link></div>
      <div className="table-wrap"><table className="table-premium"><thead><tr><th>Alert</th><th>Priority</th><th>Published</th><th>Recipients</th><th>Delivery</th><th>Read status</th><th>Notice status</th><th>Actions</th></tr></thead><tbody>
        {ns.filter((notice) => notice.is_emergency).slice(0, 10).map((notice) => <tr key={notice.notice_id}>
          <td><div className="font-semibold text-slate-100">{notice.title}</div><div className="mt-1 font-mono text-[9px] text-slate-500">{notice.notice_id}</div></td>
          <td><span className={`rounded-full border px-2 py-1 text-[10px] font-bold uppercase priority-${notice.priority}`}>{notice.priority}</span></td>
          <td>{shortDate(notice.issue_date)}</td><td>{notice.recipient_count ?? "—"}</td>
          <td><Chip ok={notice.delivered_count === notice.recipient_count && notice.recipient_count > 0} label={notice.delivered_count === notice.recipient_count && notice.recipient_count > 0 ? "DELIVERED" : "PENDING"} /><div className="mt-1 text-[9px] text-slate-500">{notice.delivered_count ?? 0}/{notice.recipient_count ?? 0}</div></td><td><span className="text-xs">{notice.read_count ?? 0}/{notice.delivered_count ?? 0}</span><div className="text-[9px] text-slate-500">read / delivered</div></td>
          <td>{notice.status === "active" && <button className="text-[10px] font-semibold text-red-300 hover:text-red-200" onClick={() => revoke(notice.notice_id)}>Revoke</button>}</td>
        </tr>)}
      </tbody></table></div>
      {!ns.some((notice) => notice.is_emergency) && <p className="py-6 text-center text-xs text-slate-500">No emergency alerts have been published.</p>}
    </section>
    <section className="card" id="all-notices">
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3"><div><h2 className="section-title">All published notices</h2><p className="mt-1 text-[11px] text-slate-500">Signed records in your institutional registry</p></div><Link to="/admin/new" className="btn-ghost !px-3 !py-2 text-xs"><Icon name="publish" size={14} /> Publish Notice</Link></div>
      <div className="table-wrap"><table className="table-premium"><thead><tr><th>Notice ID</th><th>Title</th><th>Version</th><th>Status</th><th>Actions</th></tr></thead><tbody>
        {ns.map((notice) => <tr key={notice.notice_id}><td className="font-mono text-[10px]">{notice.notice_id}</td><td className="font-medium text-slate-100">{notice.title}{notice.is_emergency && <span className="ml-2 text-[9px] font-bold uppercase text-red-300">Emergency</span>}</td><td>v{notice.version}</td><td><Chip ok={notice.status === "active"} label={notice.status} />{notice.replacement_notice_id && <div className="mt-1 text-[9px] text-slate-500">Replacement: {notice.replacement_notice_id}</div>}</td>
          <td className="whitespace-nowrap"><button className="mr-3 text-[10px] text-cyan-300 hover:text-cyan-200" onClick={() => dl(notice.notice_id)}>Download</button>{!notice.is_emergency && <Link className="mr-3 text-[10px] text-slate-300 hover:text-white" to={`/admin/notices/${notice.notice_id}/new-version`}>Correct</Link>}{notice.status === "active" && <button className="text-[10px] text-red-300 hover:text-red-200" onClick={() => revoke(notice.notice_id)}>Revoke</button>}</td>
        </tr>)}
      </tbody></table></div>
      {!ns.length && <p className="py-6 text-center text-xs text-slate-500">No notices yet.</p>}
    </section>
    <section className="grid gap-4 xl:grid-cols-[1.2fr_.8fr]">
      <div className="card space-y-4">
        <div><h2 className="section-title">Provision student access</h2><p className="mt-1 text-[11px] text-slate-500">Student accounts are administered centrally; share initial passwords securely.</p></div>
        <form onSubmit={createStudent} className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {[["name", "Student name", "text"], ["email", "Email address", "email"], ["password", "Initial password (12+)", "password"], ["student_id", "Student ID", "text"], ["department", "Department", "text"], ["academic_year", "Academic year", "text"], ["class_name", "Class / cohort", "text"]].map(([key, label, type]) => <label key={key} className="text-[10px] font-medium text-slate-400">{label}<input className="input mt-1 !py-2.5 !text-xs" type={type} required minLength={key === "password" ? 12 : undefined} value={student[key]} onChange={(e) => setStudent({ ...student, [key]: e.target.value })} /></label>)}
          <button className="btn-primary self-end sm:col-span-2 lg:col-span-3"><Icon name="publish" size={15} /> Create student account</button>
        </form>
        <div className="table-wrap max-h-56"><table className="table-premium"><thead><tr><th>Name</th><th>Student ID</th><th>Department</th><th>Year / Class</th></tr></thead><tbody>{students.map((row) => <tr key={row.id}><td>{row.name}</td><td>{row.student_id}</td><td>{row.department}</td><td>{row.academic_year} · {row.class_name || "—"}</td></tr>)}</tbody></table></div>
      </div>
      <div className="card" id="settings">
        <div className="mb-4"><h2 className="section-title">Signing key status</h2><p className="mt-1 text-[11px] text-slate-500">Public registry keys · private material stays server-side</p></div>
        <div className="space-y-2">{keys.map((key) => <div key={key.key_id} className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-white/[.07] bg-white/[.02] px-3 py-3">
          <div className="min-w-0"><div className="truncate font-mono text-[10px] text-slate-300">{key.key_id}</div><div className="mt-1 text-[9px] text-slate-500">{key.current ? "Current signing key" : key.status}</div></div>
          <div className="flex items-center gap-2"><Chip ok={key.status === "active" ? true : key.status === "revoked" ? false : null} label={key.current ? "active" : key.status} />{!key.current && key.status !== "revoked" && <button className="text-[10px] text-red-300" onClick={() => revokeKey(key.key_id)}>Revoke</button>}</div>
        </div>)}</div>
        <p className="mt-4 text-[10px] leading-5 text-slate-500">Deploy a new Ed25519 key pair to rotate. Retired keys continue verifying earlier notices until explicitly revoked.</p>
      </div>
    </section>
    <section className="card" id="verification-history">
      <div className="mb-3"><h2 className="section-title">Verification history</h2><p className="mt-1 text-[11px] text-slate-500">Recent document checks and outcomes</p></div>
      <div className="table-wrap"><table className="table-premium"><thead><tr><th>Time</th><th>Notice</th><th>Outcome</th></tr></thead><tbody>{logs.slice(0, 20).map((row, index) => <tr key={`${row.at}-${index}`}><td>{row.at ? new Date(row.at).toLocaleString() : "—"}</td><td className="font-mono text-[10px]">{row.notice_id || "Unidentified"}</td><td><Chip ok={row.status === "GREEN" || row.status === "YELLOW" ? true : row.status === "RED" ? false : null} label={row.status} /></td></tr>)}</tbody></table></div>
    </section>
    <section className="card">
      <div className="mb-3"><h2 className="section-title">Administrative audit trail</h2><p className="mt-1 text-[11px] text-slate-500">Recorded administrative actions</p></div>
      <div className="table-wrap"><table className="table-premium"><thead><tr><th>Time</th><th>Actor</th><th>Action</th><th>Target</th></tr></thead><tbody>{audit.slice(0, 20).map((row, index) => <tr key={`${row.at}-${index}`}><td>{row.at ? new Date(row.at).toLocaleString() : "—"}</td><td>{row.actor}</td><td>{row.action}</td><td className="font-mono text-[10px]">{row.target}</td></tr>)}</tbody></table></div>
    </section>
  </div>;
}
