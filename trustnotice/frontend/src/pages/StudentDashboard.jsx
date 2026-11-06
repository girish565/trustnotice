import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, websocketUrl } from "../services/api";
import { Chip, Icon } from "../components/ui";

export default function StudentDashboard() {
  const [notifications, setNotifications] = useState([]);
  const [emergencies, setEmergencies] = useState([]);
  const [error, setError] = useState("");
  const refresh = useCallback(async () => {
    try {
      const [inbox, active] = await Promise.all([api.notifications(), api.emergencies()]);
      setNotifications(inbox);
      setEmergencies(active);
      window.dispatchEvent(new Event("tn-notifications-updated"));
    } catch (e) { setError(e.message); }
  }, []);
  useEffect(() => {
    refresh();
    if (!localStorage.getItem("tn_token")) return undefined;
    let socket, timer, stopped = false, delay = 1000;
    const connect = async () => {
      if (stopped) return;
      const after = localStorage.getItem("tn_last_notification") || "0";
      try {
        const { ticket } = await api.socketTicket();
        if (stopped) return;
        socket = new WebSocket(websocketUrl("/api/notifications/ws", { ticket, after }));
      } catch {
        if (!stopped) { timer = window.setTimeout(connect, delay); delay = Math.min(delay * 2, 15000); }
        return;
      }
      socket.onopen = () => { delay = 1000; };
      socket.onmessage = (event) => {
        try {
          const item = JSON.parse(event.data);
          localStorage.setItem("tn_last_notification", String(Math.max(Number(after), item.id || 0)));
        } catch { /* The persisted inbox remains the source of truth. */ }
        refresh();
      };
      socket.onclose = () => {
        if (!stopped) { timer = window.setTimeout(connect, delay); delay = Math.min(delay * 2, 15000); }
      };
      socket.onerror = () => socket.close();
    };
    connect();
    return () => { stopped = true; window.clearTimeout(timer); socket?.close(); };
  }, [refresh]);
  const markRead = async (id) => { try { await api.readNotification(id); await refresh(); } catch (e) { setError(e.message); } };
  const acknowledge = async (id) => { try { await api.acknowledgeNotification(id); await refresh(); } catch (e) { setError(e.message); } };
  const readAll = async () => { try { await api.readAllNotifications(); await refresh(); } catch (e) { setError(e.message); } };
  const download = async (noticeId) => {
    try {
      const url = await api.blobUrl(`/api/student/notices/${noticeId}/download`);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = noticeId;
      anchor.click();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (e) { setError(e.message); }
  };
  const critical = emergencies.filter((item) => item.is_active && item.priority === "critical");
  const unread = notifications.filter((item) => !item.read).length;
  return <div className="space-y-7">
    <section className="flex flex-wrap items-end justify-between gap-4">
      <div><p className="page-eyebrow">Official student portal</p><h1 className="page-title mt-2">Welcome to TRUSTNOTICE</h1><p className="mt-2 text-sm text-slate-400">Your trusted source for verified college announcements.</p></div>
      <Link to="/verify" className="btn-primary"><Icon name="verify" size={16} /> Verify a notice</Link>
    </section>
    <section className="grid gap-3 sm:grid-cols-3">
      {[["Verify a notice", "Authenticate an official document", "/verify", "verify"], ["Scan a QR code", "Check a notice in the registry", "/verify", "notices"], ["Notification history", `${unread} unread alert(s)`, "/student#notifications", "bell"]].map(([title, detail, href, icon]) => <Link key={title} to={href} className="card group flex items-center gap-3 !p-4 transition hover:-translate-y-0.5 hover:border-cyan-300/20">
        <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl border border-cyan-300/10 bg-cyan-300/[.06] text-cyan-200"><Icon name={icon} /></span><span className="min-w-0"><span className="block text-xs font-semibold group-hover:text-cyan-100">{title}</span><span className="mt-1 block truncate text-[10px] text-slate-500">{detail}</span></span><Icon name="arrow" size={15} className="ml-auto text-slate-600 transition group-hover:translate-x-1 group-hover:text-cyan-300" />
      </Link>)}
    </section>
    {critical.map((item) => <section key={item.id} className="relative overflow-hidden rounded-2xl border border-red-400/30 bg-gradient-to-br from-red-950/85 via-[#27172d] to-[#111f3b] p-5 shadow-xl shadow-red-950/20 md:p-6" role="alert">
      <div className="absolute -right-10 -top-14 h-48 w-48 rounded-full bg-red-500/10 blur-3xl" />
      <div className="relative flex items-start gap-4"><span className="pulse-ring grid h-11 w-11 shrink-0 place-items-center rounded-xl bg-red-500/15 text-red-200"><Icon name="emergency" size={22} /></span>
        <div className="min-w-0 flex-1"><div className="flex flex-wrap items-center gap-2"><p className="text-[10px] font-bold uppercase tracking-[.15em] text-red-200">Critical emergency alert</p><Chip ok={false} label="Action may be required" /></div>
          <h2 className="mt-2 text-xl font-bold text-white">{item.title}</h2><p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-red-50/80">{item.message}</p>
          <div className="mt-3 text-[10px] text-red-100/55">Issued {item.issue_date} · Notice ID {item.notice_id}</div>
          <button className="btn mt-4 border border-red-300/20 bg-red-500/15 !px-3 !py-2 text-xs text-red-100 hover:bg-red-500/25" onClick={() => download(item.notice_id)}>View signed notice <Icon name="arrow" size={14} /></button>
        </div></div>
    </section>)}
    {error && <p role="alert" className="rounded-xl border border-red-400/20 bg-red-400/5 px-4 py-3 text-xs text-red-300">{error}</p>}
    <section className="card" id="emergencies">
      <div className="mb-4 flex flex-wrap items-end justify-between gap-2"><div><h2 className="section-title">Latest official notices</h2><p className="mt-1 text-[11px] text-slate-500">Authenticated announcements sent to your profile</p></div><span className="text-[10px] text-slate-500">{emergencies.length} notice(s)</span></div>
      <div className="grid gap-3 lg:grid-cols-2">{emergencies.map((item) => <article key={item.id} className="rounded-xl border border-white/[.08] bg-black/[.12] p-4 transition hover:border-white/[.15]">
        <div className="flex flex-wrap items-center justify-between gap-2"><span className="text-[9px] font-bold uppercase tracking-widest text-slate-500">{item.category || "Official notice"}</span><span className={`rounded-full border px-2 py-1 text-[9px] font-bold uppercase priority-${item.priority}`}>{item.priority}</span></div>
        <h3 className="mt-3 text-sm font-bold text-slate-100">{item.title}</h3><p className="mt-2 line-clamp-3 whitespace-pre-wrap text-xs leading-5 text-slate-400">{item.message}</p>
        <div className="mt-4 flex flex-wrap items-center justify-between gap-2 border-t border-white/[.06] pt-3"><span className="font-mono text-[9px] text-slate-500">{item.notice_id}</span><Chip ok={item.status === "active"} label={item.status === "revoked" ? "REVOKED" : item.is_active ? "AUTHENTIC RECORD" : "EXPIRED"} /></div>
        <div className="mt-3 flex flex-wrap items-center justify-between gap-2 text-[10px] text-slate-500"><span>Issued by {item.institution_name || "Your institution"} · {item.issue_date}{item.expiry_date ? ` · expires ${item.expiry_date}` : ""}</span>{item.replacement_notice_id && <Link className="text-cyan-300" to={`/verify/${item.replacement_notice_id}`}>Updated notice →</Link>}</div>
        <div className="mt-3 flex flex-wrap gap-2"><Link className="btn-primary !px-3 !py-1.5 text-[10px]" to={`/verify/${item.notice_id}`}>Verify notice</Link><button className="btn-ghost !px-3 !py-1.5 text-[10px]" onClick={() => download(item.notice_id)}>Download signed notice{item.has_attachment ? " + attachment" : ""}</button></div>
      </article>)}</div>
      {!emergencies.length && <div className="rounded-xl border border-dashed border-white/10 px-4 py-8 text-center"><span className="mx-auto grid h-10 w-10 place-items-center rounded-xl bg-white/[.04] text-slate-500"><Icon name="notices" /></span><p className="mt-3 text-xs text-slate-400">No official notices have been delivered to this account yet.</p></div>}
    </section>
    <section className="card" id="notifications">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2"><div><h2 className="section-title">Notification centre</h2><p className="mt-1 text-[11px] text-slate-500">Delivery, reading and acknowledgement are tracked separately</p></div><button className="btn-ghost !py-1.5 text-[10px]" onClick={readAll}>Mark all as read</button></div>
      <div className="space-y-3">{notifications.map((item) => <article key={item.id} className={`rounded-xl border p-4 transition ${item.read ? "border-white/10 bg-black/[.08]" : "border-sky-400/20 bg-sky-950/15"}`}>
        <div className="flex flex-wrap items-center justify-between gap-2"><div className="flex items-center gap-2"><span className={`h-2 w-2 rounded-full ${item.read ? "bg-slate-600" : "bg-cyan-300"}`} /><h3 className="text-xs font-semibold">{item.title}</h3><span className={`rounded-full border px-2 py-0.5 text-[8px] font-bold uppercase priority-${item.priority || "normal"}`}>{item.priority || "normal"}</span></div><span className="text-[9px] text-slate-500">{item.created_at?.slice(0, 19).replace("T", " ")}</span></div>
        <p className="mt-2 whitespace-pre-wrap text-xs leading-5 text-slate-300">{item.message}</p>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          {!item.read && <button className="btn-ghost !px-3 !py-1.5 text-[9px]" onClick={() => markRead(item.id)}>Mark as read</button>}
          {item.kind === "emergency" && !item.acknowledged && <button className="btn-primary !px-3 !py-1.5 text-[9px]" onClick={() => acknowledge(item.id)}>Acknowledge alert</button>}
          {item.acknowledged && <span className="text-[9px] font-semibold text-emerald-300">Acknowledged</span>}
          <Link className="btn-ghost !px-3 !py-1.5 text-[9px]" to={`/verify/${item.notice_id}`}>View notice</Link>
        </div>
      </article>)}</div>
      {!notifications.length && <div className="rounded-xl border border-dashed border-white/10 px-4 py-8 text-center text-xs text-slate-500">Your notification history is empty.</div>}
    </section>
  </div>;
}
