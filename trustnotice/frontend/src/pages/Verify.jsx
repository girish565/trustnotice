import { useState, useRef, useEffect } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { api, apiUrl } from "../services/api";
import { STATUS, Chip, Icon } from "../components/ui";

const STEPS = ["Validating file", "Extracting content", "Hashing document", "Finding registry record", "Checking watermark", "Verifying Ed25519 signature", "Comparing notice content", "Preparing verification report"];
const outcomes = {
  AUTHENTIC: ["Document successfully authenticated by TRUSTNOTICE.", "border-emerald-400/20 bg-gradient-to-br from-emerald-950/80 to-[#111f3b]", "text-emerald-200", "shield"],
  "AUTHENTIC, DEGRADED": ["A registered authentic source was found; byte integrity changed during re-encoding.", "border-amber-400/20 bg-gradient-to-br from-amber-950/55 to-[#111f3b]", "text-amber-200", "shield"],
  TAMPERED: ["The document differs from its signed institutional record.", "border-red-400/25 bg-gradient-to-br from-red-950/70 to-[#111f3b]", "text-red-200", "emergency"],
  REVOKED: ["This notice has been revoked by its issuing administrator.", "border-red-400/25 bg-gradient-to-br from-red-950/70 to-[#111f3b]", "text-red-200", "emergency"],
  "UNKNOWN ISSUER": ["No trusted signing key could authenticate this issuer.", "border-amber-400/25 bg-gradient-to-br from-amber-950/55 to-[#111f3b]", "text-amber-200", "emergency"],
  "SIGNATURE INVALID": ["The registered document signature could not be validated.", "border-red-400/25 bg-gradient-to-br from-red-950/70 to-[#111f3b]", "text-red-200", "emergency"],
  "EXPIRED NOTICE": ["This authentic notice has passed its validity date.", "border-amber-400/25 bg-gradient-to-br from-amber-950/55 to-[#111f3b]", "text-amber-200", "history"],
  "VERIFICATION INCONCLUSIVE": ["Available evidence is insufficient to confirm this document.", "border-slate-400/20 bg-gradient-to-br from-slate-900 to-[#111f3b]", "text-slate-200", "history"],
};

function getOutcome(report) {
  if (report.validity === "REVOKED") return "REVOKED";
  if (report.validity === "EXPIRED") return "EXPIRED NOTICE";
  if (report.status === "RED") return "TAMPERED";
  if (report.signature_valid === false && report.reasons?.some((reason) => /signature/i.test(reason))) return "SIGNATURE INVALID";
  if (report.status === "BLACK" && report.reasons?.some((reason) => /key unknown|unknown.*key|issuer/i.test(reason))) return "UNKNOWN ISSUER";
  if (report.status === "GREEN") return report.signature_valid ? "AUTHENTIC" : "SIGNATURE INVALID";
  if (report.status === "YELLOW") return report.signature_valid ? "AUTHENTIC, DEGRADED" : "SIGNATURE INVALID";
  return "VERIFICATION INCONCLUSIVE";
}

function CheckRow({ title, detail, state }) {
  return <div className="flex items-center gap-3 border-b border-white/[.06] py-3 last:border-0">
    <span className={`grid h-8 w-8 shrink-0 place-items-center rounded-lg ${state === true ? "bg-emerald-400/10 text-emerald-300" : state === false ? "bg-red-400/10 text-red-300" : "bg-slate-400/[.08] text-slate-400"}`}>
      {state === true ? <Icon name="verify" size={16} /> : state === false ? <Icon name="emergency" size={16} /> : <span className="text-sm">—</span>}
    </span>
    <div className="min-w-0 flex-1"><div className="text-xs font-semibold">{title}</div><div className="mt-1 text-[10px] text-slate-500">{detail}</div></div>
    <Chip ok={state} label={state === true ? "PASS" : state === false ? "REVIEW" : "NOT CONFIRMED"} />
  </div>;
}

function Report({ r, preview, noticeId }) {
  const [scale, setScale] = useState(1);
  const outcome = getOutcome(r);
  const [summary, panel, textColor, icon] = outcomes[outcome] || outcomes["VERIFICATION INCONCLUSIVE"];
  const statusValidity = r.validity === "REVOKED" ? false : r.validity === "VALID" ? true : null;
  return <div className="fade space-y-4">
    <section className={`relative overflow-hidden rounded-2xl border p-5 md:p-7 ${panel}`}>
      <div className="absolute -right-10 -top-20 h-56 w-56 rounded-full bg-white/[.025] blur-3xl" />
      <div className="relative flex items-start gap-4"><span className={`grid h-12 w-12 shrink-0 place-items-center rounded-2xl border border-white/10 bg-white/[.04] ${textColor}`}><Icon name={icon} size={25} /></span>
        <div className="min-w-0 flex-1"><p className="page-eyebrow">TRUSTNOTICE verification result</p><h2 className={`mt-2 font-display text-2xl font-extrabold tracking-tight md:text-3xl ${textColor}`}>{outcome === "AUTHENTIC" ? "AUTHENTIC NOTICE" : outcome}</h2><p className="mt-2 max-w-2xl text-sm leading-6 text-slate-300">{summary}</p>
          <div className="mt-4 flex flex-wrap gap-2"><Chip ok={r.signature_valid} label={r.signature_valid ? "Ed25519 signature valid" : "Signature not confirmed"} /><Chip ok={statusValidity} label={r.validity || "Registry status unknown"} /></div>
        </div>
      </div>
    </section>
    <section className="grid gap-4 xl:grid-cols-[1.05fr_.95fr]">
      <div className="card">
        <div className="mb-2"><h3 className="section-title">Authentication checks</h3><p className="mt-1 text-[10px] text-slate-500">The QR locates a record; it is not proof of authenticity.</p></div>
        <CheckRow title="SHA-256 content integrity" detail={r.exact_hash_match ? "Uploaded bytes match the signed hash." : r.content_similarity != null ? `Content similarity ${(r.content_similarity * 100).toFixed(1)}%; exact hash did not match.` : "Exact hash match was not established."} state={r.exact_hash_match ? true : r.status === "RED" ? false : null} />
        <CheckRow title="Ed25519 digital signature" detail={r.signature_valid ? "The registry manifest signature is valid." : "A valid issuer signature was not established."} state={r.signature_valid === true ? true : r.signature_valid === false && r.notice_id ? false : null} />
        <CheckRow title="QR registry locator" detail={r.qr_detected ? (r.qr_matches_notice ? `QR points to ${r.qr_notice_id || r.notice_id}.` : "A QR code was found but did not match the selected record.") : "No readable QR code detected; watermark or provided notice ID may locate the record."} state={r.qr_matches_notice ? true : r.qr_detected ? false : null} />
        <CheckRow title="Invisible watermark" detail={r.watermark_detected ? "A registered watermark reference was recovered." : "No registered watermark reference recovered. This alone does not mean fake."} state={r.watermark_detected ? true : null} />
        <CheckRow title="Revocation status" detail={r.validity === "REVOKED" ? "This record was revoked." : r.validity === "VALID" ? "No revocation is recorded." : `Registry validity: ${r.validity || "not confirmed"}.`} state={statusValidity} />
        {r.notice_id && <div className="mt-4 rounded-xl border border-white/[.07] bg-black/[.12] p-3 text-xs">
          <div className="text-[9px] font-bold uppercase tracking-widest text-slate-500">Registry record</div>
          <div className="mt-2 grid gap-2 sm:grid-cols-2"><div><span className="text-slate-500">Notice ID </span><b className="break-all font-mono">{r.notice_id}</b></div><div><span className="text-slate-500">Title </span><b>{r.notice?.title || r.title || "—"}</b></div><div><span className="text-slate-500">Issued </span><b>{r.notice?.issue_date || "—"}</b></div><div><span className="text-slate-500">Department </span><b>{r.notice?.department || "—"}</b></div></div>
          {r.validity === "REVOKED" && r.replacement_notice_id && <Link className="mt-3 inline-flex items-center gap-2 text-cyan-300 hover:text-cyan-200" to={`/verify/${r.replacement_notice_id}`}>View replacement notice <Icon name="arrow" size={14} /></Link>}
        </div>}
      </div>
      <div className="card">
        <div className="mb-3"><h3 className="section-title">Verification details</h3><p className="mt-1 text-[10px] text-slate-500">Evidence from this verification response</p></div>
        {r.reasons?.length > 0 && <ul className="mb-4 space-y-2">{r.reasons.map((reason, index) => <li key={index} className="flex gap-2 text-xs leading-5 text-slate-300"><span className="mt-1 text-cyan-300">•</span>{reason}</li>)}</ul>}
        {r.changes?.length > 0 && <><h4 className="mb-2 text-xs font-semibold">Detected modifications</h4><ul className="space-y-2">{r.changes.map((change, index) => <li key={index} className="rounded-lg bg-red-400/[.05] p-2 text-[10px]"><span className="text-slate-500 line-through">{change.original || "∅"}</span><span className="mx-2 text-slate-600">→</span><span className="text-red-300">{change.uploaded || "∅"}</span></li>)}</ul></>}
        {r.content_similarity != null && <div className="mt-4"><div className="flex justify-between text-[10px]"><span className="text-slate-500">Content similarity</span><span>{(r.content_similarity * 100).toFixed(1)}%</span></div><div className="mt-2 h-1.5 overflow-hidden rounded-full bg-white/10"><div className={`h-full rounded-full ${r.status === "RED" ? "bg-red-400" : "bg-emerald-400"}`} style={{ width: `${Math.min(100, r.content_similarity * 100)}%` }} /></div></div>}
      </div>
    </section>
    {noticeId && <div className="grid gap-4 md:grid-cols-2">
      <div className="card"><h3 className="mb-3 section-title">Uploaded document</h3>{preview ? <img src={preview} className="max-h-[28rem] w-full rounded-xl object-contain" alt="Uploaded notice" /> : <p className="text-xs text-slate-500">PDF preview is not available in the browser.</p>}</div>
      <div className="card"><h3 className="mb-3 section-title">Registered official copy{r.suspicious_regions?.length ? " · differences marked" : ""}</h3>
        {r.notice?.is_pdf ? <iframe title="Official notice PDF" src={apiUrl(`/api/verify/${noticeId}/original`)} className="h-[28rem] w-full rounded-xl bg-white" /> :
          <div className="relative"><img src={apiUrl(`/api/verify/${noticeId}/original`)} className="w-full rounded-xl" onLoad={(e) => setScale(e.target.clientWidth / 1024)} alt="Official copy" />
            {(r.suspicious_regions || []).map(([x, y, w, h], index) => <div key={index} className="absolute border-2 border-red-500" style={{ left: x * scale, top: y * scale, width: w * scale, height: h * scale }} />)}</div>}
      </div>
    </div>}
  </div>;
}

export default function Verify() {
  const { noticeId } = useParams();
  const nav = useNavigate();
  const input = useRef();
  const qrIn = useRef();
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [busy, setBusy] = useState(false);
  const [step, setStep] = useState(0);
  const [res, setRes] = useState(null);
  const [err, setErr] = useState("");
  const [rec, setRec] = useState(null);
  const [drag, setDrag] = useState(false);
  useEffect(() => {
    setRes(null);
    if (noticeId) api.record(noticeId).then(setRec).catch((e) => setErr(e.message));
    else setRec(null);
  }, [noticeId]);
  useEffect(() => () => { if (preview) URL.revokeObjectURL(preview); }, [preview]);
  const pick = (picked) => {
    if (!picked) return;
    if (!/\.(pdf|png|jpe?g)$/i.test(picked.name)) { setErr("Only PDF, PNG or JPG files are supported."); return; }
    setErr(""); setRes(null); setFile(picked); setPreview(picked.type.startsWith("image") ? URL.createObjectURL(picked) : null);
  };
  const run = async () => {
    if (!file) return;
    setBusy(true); setErr(""); setStep(0);
    const timer = setInterval(() => setStep((current) => Math.min(current + 1, STEPS.length - 1)), 450);
    try { setRes(await api.verifyUpload(file, noticeId)); }
    catch (e) { setErr(e.message); }
    clearInterval(timer); setBusy(false);
  };
  const scanQr = async (picked) => {
    if (!picked) return;
    setErr("");
    try { const result = await api.verifyQr(picked); nav(`/verify/${result.notice_id}`); }
    catch (e) { setErr(e.message); }
  };
  const recordRevoked = rec?.validity === "REVOKED" || rec?.status === "revoked";
  return <div className="mx-auto max-w-5xl space-y-6">
    <section className="flex flex-wrap items-end justify-between gap-3">
      <div><p className="page-eyebrow">Document authenticity check</p><h1 className="page-title mt-2">Verify a notice</h1><p className="mt-2 text-sm text-slate-400">A QR code only locates a record. TRUSTNOTICE validates the signature and document content.</p></div>
      <span className="inline-flex items-center gap-2 rounded-full border border-emerald-400/15 bg-emerald-400/[.05] px-3 py-2 text-[10px] font-semibold text-emerald-200"><Icon name="shield" size={15} /> Cryptographic verification</span>
    </section>
    {rec && <section className={`rounded-2xl border p-4 ${recordRevoked ? "border-red-400/25 bg-red-950/25" : "border-white/10 bg-[#111f3b]/70"}`}>
      <div className="flex flex-wrap items-start justify-between gap-3"><div><div className="text-[9px] font-bold uppercase tracking-widest text-slate-500">Registry lookup</div><h2 className="mt-1 text-sm font-bold">{rec.title}</h2><p className="mt-1 font-mono text-[10px] text-slate-500">{rec.notice_id} · v{rec.version}</p></div>
        <div className="flex gap-2"><Chip ok={rec.signature_valid} label={rec.signature_valid ? "signature valid" : "signature invalid"} /><Chip ok={!recordRevoked} label={recordRevoked ? "REVOKED" : rec.validity || rec.status} /></div>
      </div>
      {recordRevoked && <div className="mt-3 rounded-lg bg-red-400/[.07] p-3 text-xs text-red-200"><b>NOTICE REVOKED.</b> {rec.revocation_reason || "Do not rely on this notice."}{rec.replacement_notice_id && <Link className="ml-2 underline" to={`/verify/${rec.replacement_notice_id}`}>View replacement notice</Link>}</div>}
    </section>}
    <section className="card">
      <div className="mb-4"><h2 className="section-title">Upload a document to authenticate</h2><p className="mt-1 text-[10px] text-slate-500">PDF, PNG or JPG · maximum 10 MB</p></div>
      <div onDragOver={(event) => { event.preventDefault(); setDrag(true); }} onDragLeave={() => setDrag(false)} onDrop={(event) => { event.preventDefault(); setDrag(false); pick(event.dataTransfer.files[0]); }} onClick={() => input.current?.click()}
        className={`cursor-pointer rounded-2xl border border-dashed p-6 text-center transition md:p-10 ${drag ? "border-cyan-300/60 bg-cyan-300/[.06]" : "border-white/15 bg-black/[.12] hover:border-white/25 hover:bg-white/[.02]"}`}>
        <input ref={input} type="file" hidden accept=".pdf,.png,.jpg,.jpeg" onClick={(event) => event.stopPropagation()} onChange={(event) => pick(event.target.files[0])} />
        {preview ? <img src={preview} className="mx-auto max-h-64 rounded-xl object-contain" alt="Document preview" /> : <div className="mx-auto grid h-14 w-14 place-items-center rounded-2xl border border-cyan-300/15 bg-cyan-300/[.05] text-cyan-200"><Icon name="notices" size={26} /></div>}
        <p className="mt-4 text-sm font-semibold">{file ? file.name : "Drop your notice here or browse files"}</p><p className="mt-1 text-[10px] text-slate-500">Encrypted in transit · content checked against the signed record</p>
      </div>
      <div className="mt-4 flex flex-wrap gap-2">
        <button className="btn-primary" disabled={!file || busy} onClick={run}>{busy ? <><span className="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white" /> Verifying…</> : <><Icon name="verify" size={16} /> Verify document</>}</button>
        <button className="btn-ghost" onClick={() => qrIn.current?.click()}><Icon name="notices" size={16} /> Scan QR from file</button>
        <input ref={qrIn} type="file" hidden accept=".pdf,.png,.jpg,.jpeg" onChange={(event) => scanQr(event.target.files[0])} />
      </div>
    </section>
    {busy && <section className="card"><div className="flex items-center justify-between"><span className="text-xs font-semibold text-cyan-200">{STEPS[step]}…</span><span className="text-[10px] text-slate-500">{Math.round((step + 1) / STEPS.length * 100)}%</span></div><div className="mt-3 h-1.5 overflow-hidden rounded-full bg-white/10"><div className="h-full rounded-full bg-gradient-to-r from-blue-500 to-cyan-300 transition-all duration-300" style={{ width: `${((step + 1) / STEPS.length) * 100}%` }} /></div></section>}
    {err && <div role="alert" className="rounded-xl border border-red-400/20 bg-red-400/[.05] px-4 py-3 text-xs text-red-300">{err}</div>}
    {res && <Report r={res} preview={preview} noticeId={res.notice_id} />}
  </div>;
}
