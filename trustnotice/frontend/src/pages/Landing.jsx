import { Link } from "react-router-dom";
import { useEffect, useState } from "react";
import { api } from "../services/api";
import { Icon } from "../components/ui";

const steps = [
  ["Issue", "An institution publishes a notice authenticated with a unique signed record."],
  ["Share", "Students receive the protected notice through existing communication channels."],
  ["Verify", "Check the document content, cryptographic signature, QR and watermark evidence."],
];
const features = [
  ["Ed25519 signatures", "Public-key signatures bind official notice manifests to their issuing key.", "shield"],
  ["SHA-256 integrity", "Cryptographic content hashes expose even small unauthorized changes.", "verify"],
  ["Invisible watermark", "A keyed DWT + DCT signal helps identify a source copy.", "history"],
  ["Secure QR locator", "QR codes lead to registry records; they never authenticate content alone.", "notices"],
  ["Document forensics", "Image and text comparisons help surface suspicious alterations.", "analytics"],
  ["Live emergency alerts", "Private student delivery, read receipts, acknowledgement and revocation.", "emergency"],
];
const faq = [
  ["Is a QR code proof that a notice is authentic?", "No. A QR code only helps locate the registry record. TRUSTNOTICE also checks the signature and document content."],
  ["What if an image was compressed or screenshotted?", "The system checks the source evidence available and may report degraded or inconclusive results rather than forcing a pass."],
  ["Does unverified mean fake?", "No. It means the available evidence was not enough to establish authenticity."],
];

export default function Landing() {
  const [stats, setStats] = useState(null);
  useEffect(() => { api.stats().then(setStats).catch(() => {}); }, []);
  return <div className="space-y-20 md:space-y-28">
    <section className="relative grid items-center gap-10 py-8 md:grid-cols-[1.15fr_.85fr] md:py-14">
      <div className="absolute -left-20 top-0 h-72 w-72 rounded-full bg-blue-500/[.08] blur-3xl" />
      <div className="relative">
        <div className="mb-5 inline-flex items-center gap-2 rounded-full border border-cyan-300/15 bg-cyan-300/[.045] px-3 py-1.5 text-[10px] font-semibold tracking-wide text-cyan-100"><span className="status-pulse" /> DOCUMENT TRUST, CRYPTOGRAPHICALLY VERIFIED</div>
        <h1 className="font-display text-4xl font-extrabold leading-[1.06] tracking-[-.05em] text-white sm:text-5xl lg:text-6xl">Trust Every Notice.<br /><span className="bg-gradient-to-r from-blue-400 to-cyan-200 bg-clip-text text-transparent">Verify Every Word.</span></h1>
        <p className="mt-6 max-w-xl text-base leading-7 text-slate-400">The secure verification platform for official college announcements. Authenticate signed records, inspect content integrity, and deliver trusted emergency updates.</p>
        <div className="mt-8 flex flex-wrap gap-3"><Link to="/verify" className="btn-primary !px-5 !py-3"><Icon name="verify" size={17} /> Verify a notice</Link><Link to="/student/login" className="btn-ghost !px-5 !py-3">Student portal <Icon name="arrow" size={15} /></Link></div>
        <div className="mt-8 flex flex-wrap items-center gap-x-6 gap-y-2 text-[10px] text-slate-500"><span className="inline-flex items-center gap-2"><Icon name="shield" size={14} className="text-emerald-400" /> Ed25519 signed</span><span className="inline-flex items-center gap-2"><Icon name="verify" size={14} className="text-cyan-300" /> SHA-256 integrity</span><span className="inline-flex items-center gap-2"><Icon name="history" size={14} className="text-blue-300" /> Tamper evidence</span></div>
      </div>
      <div className="relative mx-auto w-full max-w-[410px]">
        <div className="absolute inset-6 rounded-full bg-blue-600/10 blur-3xl" />
        <div className="relative rounded-[26px] border border-white/10 bg-gradient-to-br from-[#132447] to-[#0c162b] p-5 shadow-2xl shadow-black/30">
          <div className="flex items-center justify-between border-b border-white/[.08] pb-4"><div className="flex items-center gap-2"><span className="brand-shield"><Icon name="shield" /></span><div><div className="text-xs font-bold">Trust verification</div><div className="text-[9px] text-slate-500">NOTICE · TN-2026-0018</div></div></div><span className="rounded-full border border-emerald-400/20 bg-emerald-400/[.07] px-2.5 py-1 text-[9px] font-bold text-emerald-300">AUTHENTIC</span></div>
          <div className="mt-5 rounded-xl border border-white/[.07] bg-black/[.12] p-4"><div className="flex items-center gap-2 text-[9px] uppercase tracking-widest text-slate-500"><Icon name="notices" size={14} /> Official announcement</div><div className="mt-3 h-2 w-3/4 rounded bg-slate-500/25" /><div className="mt-2 h-2 w-full rounded bg-slate-500/15" /><div className="mt-2 h-2 w-5/6 rounded bg-slate-500/15" /><div className="mt-6 grid grid-cols-2 gap-2"><div className="rounded-lg bg-emerald-400/[.06] p-3"><div className="text-[9px] text-slate-500">SIGNATURE</div><div className="mt-1 flex items-center gap-1.5 text-[10px] font-semibold text-emerald-300"><Icon name="verify" size={13} /> Verified</div></div><div className="rounded-lg bg-cyan-400/[.05] p-3"><div className="text-[9px] text-slate-500">CONTENT HASH</div><div className="mt-1 flex items-center gap-1.5 text-[10px] font-semibold text-cyan-200"><Icon name="verify" size={13} /> Exact match</div></div></div></div>
          <div className="mt-4 flex items-center justify-between text-[9px] text-slate-500"><span>SHA-256 · Ed25519 · DWT+DCT</span><span>SECURE REGISTRY</span></div>
        </div>
        <div className="absolute -bottom-5 -left-7 hidden rounded-xl border border-white/10 bg-[#0d1830]/95 p-3 shadow-xl sm:block"><div className="flex items-center gap-2"><span className="grid h-7 w-7 place-items-center rounded-lg bg-emerald-400/10 text-emerald-300"><Icon name="shield" size={15} /></span><div><div className="text-[9px] font-semibold">Verified with trust</div><div className="text-[8px] text-slate-500">Key-backed document integrity</div></div></div></div>
      </div>
    </section>
    {stats && <section className="grid grid-cols-1 gap-3 rounded-2xl border border-white/[.07] bg-white/[.015] p-3 sm:grid-cols-3">
      {[["Official notices", stats.notices, "notices"], ["Verification attempts", stats.verifications, "verify"], ["Tampering flagged", stats.flagged, "emergency"]].map(([label, value, icon]) => <div key={label} className="flex items-center gap-3 rounded-xl px-4 py-3"><span className="metric-icon"><Icon name={icon} /></span><div><div className="font-display text-xl font-extrabold">{value}</div><div className="text-[10px] text-slate-500">{label}</div></div></div>)}
    </section>}
    <section>
      <div className="mb-7 max-w-xl"><p className="page-eyebrow">A verifiable chain of trust</p><h2 className="mt-2 font-display text-2xl font-bold tracking-tight sm:text-3xl">From official issue to confident decision.</h2><p className="mt-2 text-sm leading-6 text-slate-400">A clear workflow designed to counter forged, modified and outdated notices.</p></div>
      <div className="grid gap-3 md:grid-cols-3">{steps.map(([title, detail], index) => <article key={title} className="card group !p-5 transition hover:-translate-y-1 hover:border-cyan-300/15"><span className="font-display text-xs font-extrabold text-cyan-300/80">0{index + 1}</span><h3 className="mt-4 font-display text-base font-bold">{title}</h3><p className="mt-2 text-xs leading-5 text-slate-400">{detail}</p></article>)}</div>
    </section>
    <section>
      <div className="mb-7"><p className="page-eyebrow">Built for institutional trust</p><h2 className="mt-2 font-display text-2xl font-bold tracking-tight sm:text-3xl">More than a visual checkmark.</h2></div>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">{features.map(([title, detail, icon]) => <article key={title} className="card flex gap-3 !p-4"><span className="metric-icon"><Icon name={icon} size={17} /></span><div><h3 className="text-xs font-semibold">{title}</h3><p className="mt-1.5 text-[10px] leading-5 text-slate-500">{detail}</p></div></article>)}</div>
    </section>
    <section className="grid gap-6 md:grid-cols-[.8fr_1.2fr]">
      <div><p className="page-eyebrow">Trust by design</p><h2 className="mt-2 font-display text-2xl font-bold tracking-tight">Honest answers.<br />No false confidence.</h2><p className="mt-3 text-xs leading-6 text-slate-400">QR codes and watermarks locate a record. Authenticity comes from cryptographic signature validation together with a content check.</p></div>
      <div className="space-y-2">{faq.map(([question, answer]) => <details key={question} className="card group !p-4"><summary className="cursor-pointer list-none text-xs font-semibold marker:hidden">{question}<span className="float-right text-cyan-300 transition group-open:rotate-45">+</span></summary><p className="mt-3 border-t border-white/[.07] pt-3 text-[11px] leading-5 text-slate-400">{answer}</p></details>)}</div>
    </section>
    <section className="rounded-2xl border border-blue-400/15 bg-gradient-to-r from-blue-950/60 to-cyan-950/20 p-6 text-center md:p-9"><span className="page-eyebrow">TRUSTNOTICE · DOCUMENT AUTHENTICATION</span><h2 className="mt-3 font-display text-2xl font-extrabold">Have a notice you need to verify?</h2><p className="mt-2 text-xs text-slate-400">Check the record and content in seconds.</p><Link className="btn-primary mt-5" to="/verify">Start verification <Icon name="arrow" size={15} /></Link></section>
  </div>;
}
