import { useEffect, useRef, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { api } from "../services/api";

const iconPaths = {
  dashboard: <><rect x="3" y="3" width="7" height="7" rx="1" /><rect x="14" y="3" width="7" height="5" rx="1" /><rect x="14" y="12" width="7" height="9" rx="1" /><rect x="3" y="14" width="7" height="7" rx="1" /></>,
  publish: <><path d="M12 5v14" /><path d="m5 12 7-7 7 7" /><path d="M4 20h16" /></>,
  notices: <><path d="M4 4h16v16H4z" /><path d="M8 8h8M8 12h8M8 16h5" /></>,
  verify: <><path d="m9 12 2 2 4-4" /><circle cx="12" cy="12" r="9" /></>,
  emergency: <><path d="m12 3 10 18H2L12 3Z" /><path d="M12 9v4M12 17h.01" /></>,
  history: <><path d="M3 12a9 9 0 1 0 3-6.7L3 8" /><path d="M3 3v5h5M12 7v5l3 2" /></>,
  analytics: <><path d="M4 19V5M4 19h17" /><path d="m7 15 4-4 3 2 5-6" /></>,
  settings: <><circle cx="12" cy="12" r="3" /><path d="m19.4 15 .1.1 1.4 1.1-1.4 2.4-1.7-.7a8 8 0 0 1-1.8 1l-.3 1.8h-2.8l-.3-1.8a8 8 0 0 1-1.8-1l-1.7.7-1.4-2.4 1.4-1.1A7 7 0 0 1 7 13l-1.8-.5v-2.8L7 9.2a8 8 0 0 1 .8-1.8L6.7 5.9l1.4-2.4 1.7.7a8 8 0 0 1 1.8-1l.3-1.8h2.8l.3 1.8a8 8 0 0 1 1.8 1l1.7-.7 1.4 2.4-1.4 1.1a7 7 0 0 1 .8 1.8l1.8.5v2.8l-1.8.5a8 8 0 0 1-.8 1.8Z" /></>,
  menu: <><path d="M4 6h16M4 12h16M4 18h16" /></>,
  close: <><path d="m6 6 12 12M18 6 6 18" /></>,
  logout: <><path d="M10 17l5-5-5-5M15 12H3" /><path d="M12 3h7a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-7" /></>,
  shield: <><path d="M12 22s8-4 8-11V5l-8-3-8 3v6c0 7 8 11 8 11Z" /><path d="m9 12 2 2 4-4" /></>,
  bell: <><path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9" /><path d="M10 21h4" /></>,
  arrow: <><path d="M5 12h14M13 6l6 6-6 6" /></>,
};

export function Icon({ name, size = 18, className = "" }) {
  return <svg aria-hidden="true" className={`shrink-0 ${className}`} width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">{iconPaths[name] || iconPaths.shield}</svg>;
}

export const STATUS = {
  GREEN: ["AUTHENTIC", "bg-emerald-500", "The file matches the registered notice and its signature is valid."],
  YELLOW: ["AUTHENTIC, DEGRADED", "bg-amber-500", "A genuine source was identified, but compression or resizing prevents complete verification."],
  RED: ["TAMPERED", "bg-red-600", "A registered notice was identified, but this content differs from it."],
  BLACK: ["UNVERIFIED", "bg-slate-600", "No reliable authentication evidence could be established. This does not by itself prove the notice is fake."],
};

export const Chip = ({ ok, label }) => <span className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-semibold ${ok === true ? "border-emerald-400/20 bg-emerald-400/10 text-emerald-300" : ok === false ? "border-red-400/20 bg-red-400/10 text-red-300" : "border-white/10 bg-white/5 text-slate-300"}`}><span className={`h-1.5 w-1.5 rounded-full ${ok === true ? "bg-emerald-400" : ok === false ? "bg-red-400" : "bg-slate-500"}`} />{label}</span>;

function NotificationBell() {
  const [unread, setUnread] = useState(0);
  const [unavailable, setUnavailable] = useState(false);
  useEffect(() => {
    const update = () => api.notifications().then((items) => { setUnread(items.filter((item) => !item.read).length); setUnavailable(false); }).catch(() => setUnavailable(true));
    update();
    const interval = window.setInterval(update, 30000);
    window.addEventListener("tn-notifications-updated", update);
    return () => { window.clearInterval(interval); window.removeEventListener("tn-notifications-updated", update); };
  }, []);
  return <Link to="/student#notifications" className="sidebar-link" title={unavailable ? "Notification count unavailable" : undefined}><Icon name="bell" /><span>Notifications</span>{unavailable ? <span className="ml-auto text-[9px] text-amber-300">Unavailable</span> : unread > 0 && <span className="ml-auto rounded-full bg-red-500 px-2 py-0.5 text-[10px] font-bold text-white">{unread}</span>}</Link>;
}

function TopbarNotificationBell() {
  const [unread, setUnread] = useState(0);
  const [unavailable, setUnavailable] = useState(false);
  const [notifications, setNotifications] = useState([]);
  const [error, setError] = useState("");
  const [open, setOpen] = useState(false);
  const container = useRef(null);
  useEffect(() => {
    const update = () => api.notifications().then((items) => {
      setNotifications(items);
      setUnread(items.filter((item) => !item.read).length);
      setUnavailable(false);
      setError("");
    }).catch((reason) => { setUnavailable(true); setError(reason.message); });
    update();
    const interval = window.setInterval(update, 30000);
    window.addEventListener("tn-notifications-updated", update);
    const closeOutside = (event) => { if (!container.current?.contains(event.target)) setOpen(false); };
    document.addEventListener("pointerdown", closeOutside);
    return () => { window.clearInterval(interval); window.removeEventListener("tn-notifications-updated", update); document.removeEventListener("pointerdown", closeOutside); };
  }, []);
  const markRead = async (id) => {
    try {
      await api.readNotification(id);
      setNotifications(await api.notifications());
      setUnread((items) => items.filter((item) => !item.read).length);
      window.dispatchEvent(new Event("tn-notifications-updated"));
    }
    catch (reason) { setError(reason.message); }
  };
  return <div className="relative" ref={container}>
    <button type="button" onClick={() => setOpen((value) => !value)} className="topbar-bell relative" aria-label={unavailable ? "Notification count unavailable" : `${unread} unread notifications`} aria-expanded={open} aria-haspopup="dialog">
      <Icon name="bell" />
      {unread > 0 && <span className="absolute -right-1 -top-1 min-w-4 rounded-full bg-red-500 px-1 text-center text-[8px] font-bold leading-4 text-white">{unread}</span>}
      {unavailable && <span className="absolute -right-1 -top-1 h-2 w-2 rounded-full bg-amber-400" />}
    </button>
    {open && <section className="notification-popover" role="dialog" aria-label="Recent notifications">
      <div className="flex items-center justify-between border-b border-white/[.08] px-4 py-3"><div><h2 className="text-sm font-bold text-white">Notifications</h2><p className="mt-0.5 text-[10px] text-slate-500">{unread} unread</p></div><Link to="/student#notifications" onClick={() => setOpen(false)} className="text-[10px] font-semibold text-cyan-300 hover:text-cyan-200">View all</Link></div>
      {error && <p role="alert" className="mx-3 mt-3 rounded-lg border border-amber-400/20 bg-amber-400/[.06] px-3 py-2 text-[10px] text-amber-200">{error}</p>}
      <div className="divide-y divide-white/[.06]">{notifications.slice(0, 5).map((item) => <article key={item.id} className="px-4 py-3">
        <div className="flex items-start gap-2"><span className={`mt-1 h-2 w-2 shrink-0 rounded-full ${item.read ? "bg-slate-600" : "bg-cyan-300"}`} /><div className="min-w-0 flex-1"><h3 className="truncate text-xs font-semibold text-slate-100">{item.title}</h3><p className="mt-1 line-clamp-2 text-[10px] leading-4 text-slate-400">{item.message}</p><div className="mt-2 flex items-center justify-between gap-2"><Link to={item.notice_id ? `/verify/${item.notice_id}` : "/student#notifications"} onClick={() => setOpen(false)} className="text-[10px] font-semibold text-cyan-300">View notice →</Link>{!item.read && <button type="button" onClick={() => markRead(item.id)} className="text-[9px] text-slate-400 hover:text-white">Mark read</button>}</div></div></div>
      </article>)}</div>
      {!notifications.length && !error && <p className="px-4 py-8 text-center text-xs text-slate-500">No notifications yet.</p>}
    </section>}
  </div>;
}

const adminItems = [
  ["Dashboard", "/admin", "dashboard"],
  ["Publish Notice", "/admin/new", "publish"],
  ["All Notices", "/admin#all-notices", "notices"],
  ["Verify Document", "/verify", "verify"],
  ["Emergency Alerts", "/admin/emergency", "emergency"],
  ["Verification History", "/admin#verification-history", "history"],
  ["Analytics", "/admin#analytics", "analytics"],
  ["Settings", "/admin#settings", "settings"],
];

export function Layout({ children }) {
  const { user, logout } = useAuth();
  const nav = useNavigate();
  const location = useLocation();
  const [collapsed, setCollapsed] = useState(() => localStorage.getItem("tn_sidebar_collapsed") === "true");
  const [mobileOpen, setMobileOpen] = useState(false);
  const signedIn = user?.role === "admin" || user?.role === "student";
  const items = user?.role === "student"
    ? [["Dashboard", "/student", "dashboard"], ["Emergency Alerts", "/student#emergencies", "emergency"], ["Verify Document", "/verify", "verify"], ["Notification History", "/student#notifications", "history"]]
    : adminItems;
  const isActive = (to) => {
    if (to === "notifications") return location.pathname === "/student";
    const [path, hash] = to.split("#");
    return location.pathname === path && (hash ? location.hash === `#${hash}` : !location.hash || location.pathname !== "/admin");
  };
  useEffect(() => { setMobileOpen(false); }, [location.pathname, location.hash]);
  const toggleCollapse = () => setCollapsed((value) => {
    localStorage.setItem("tn_sidebar_collapsed", String(!value));
    return !value;
  });
  const navLink = (label, to, icon) => {
    const actualTo = to === "notifications" ? "/student#notifications" : to;
    return <Link key={`${label}-${actualTo}`} to={actualTo} onClick={() => setMobileOpen(false)} title={collapsed ? label : undefined}
      className={`sidebar-link ${isActive(to) ? "sidebar-link-active" : ""}`}>
      <Icon name={icon} /><span className={collapsed ? "sidebar-label-collapsed" : ""}>{label}</span>
    </Link>;
  };
  const sidebar = <aside className={`sidebar ${collapsed ? "sidebar-collapsed" : ""} ${mobileOpen ? "sidebar-mobile-open" : ""}`}>
    <div className="sidebar-brand">
      <Link to={user?.role === "student" ? "/student" : "/admin"} className="brand-mark"><span className="brand-shield"><Icon name="shield" size={20} /></span><span className={collapsed ? "sidebar-label-collapsed" : ""}>TRUST<span className="text-cyan">NOTICE</span></span></Link>
      <button onClick={toggleCollapse} className="sidebar-collapse" aria-label="Collapse sidebar"><span>{collapsed ? "›" : "‹"}</span></button>
    </div>
    <div className="sidebar-caption">{user?.role === "student" ? "STUDENT PORTAL" : "WORKSPACE"}</div>
    <nav className="sidebar-nav">{items.map(([label, to, icon]) => navLink(label, to, icon))}{user?.role === "student" && <NotificationBell />}</nav>
    {!collapsed && <div className="sidebar-security"><div className="flex items-center gap-2 text-sm font-semibold"><Icon name="shield" className="text-emerald-400" /> Secure workspace</div><p className="mt-2 text-xs leading-5 text-slate-400">Signed records protected with Ed25519 verification.</p></div>}
    <div className="sidebar-user">
      <div className="user-avatar">{(user?.name || user?.email || "U").slice(0, 1).toUpperCase()}</div>
      {!collapsed && <div className="min-w-0 flex-1"><div className="truncate text-sm font-semibold">{user?.name || user?.email}</div><div className="text-xs capitalize text-slate-500">{user?.role}</div></div>}
      <button className="icon-button" title="Sign out" aria-label="Sign out" onClick={() => { logout(); nav("/"); }}><Icon name="logout" /></button>
    </div>
  </aside>;
  return <div className="app-shell">
    {signedIn ? <>
      {mobileOpen && <button className="sidebar-overlay" aria-label="Close navigation" onClick={() => setMobileOpen(false)} />}
      {sidebar}
      <div className={`app-main ${collapsed ? "app-main-collapsed" : ""}`}>
        <header className="app-topbar">
          <button className="mobile-menu icon-button" aria-label="Open navigation" onClick={() => setMobileOpen(true)}><Icon name="menu" /></button>
          <div className="hidden text-sm text-slate-400 sm:block">{user?.role === "admin" ? "Institutional security console" : "Student portal"} <span className="mx-2 text-slate-700">/</span><span className="text-slate-200">{user?.name || user?.email}</span></div>
          <div className="topbar-status"><span className="status-pulse" /> Systems operational</div>
          <Link to="/verify" className="topbar-verify"><Icon name="verify" size={16} /> Verify a document</Link>
          {user?.role === "student" && <TopbarNotificationBell />}
        </header>
        <main className="app-content fade">{children}</main>
      </div>
    </> : <div className="public-shell">
      <header className="public-header"><Link to="/" className="brand-mark"><span className="brand-shield"><Icon name="shield" size={20} /></span><span>TRUST<span className="text-cyan">NOTICE</span></span></Link><nav><Link to="/verify">Verify a notice</Link><Link to="/student/login">Student</Link><Link to="/admin/login" className="btn-primary !py-2 !px-4">Admin portal</Link></nav></header>
      <main className="public-content fade">{children}</main>
      <footer className="public-footer"><span>TRUSTNOTICE</span><span>Trust Every Notice. Verify Every Word.</span><span>Secure institutional communications</span></footer>
    </div>}
  </div>;
}
