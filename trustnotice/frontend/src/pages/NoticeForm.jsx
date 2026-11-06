import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { api, apiUrl } from "../services/api";
import { Icon } from "../components/ui";

export default function NoticeForm() {
  const { id } = useParams();
  const [values, setValues] = useState({ title: "", department: "", category: "exam", issue_date: new Date().toISOString().slice(0, 10), expiry_date: "", description: "" });
  const [file, setFile] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [done, setDone] = useState(null);
  const [qr, setQr] = useState(null);
  useEffect(() => {
    if (!id) return;
    api.notice(id).then((notice) => setValues({ title: notice.title, department: notice.department, category: notice.category, issue_date: notice.issue_date, expiry_date: notice.expiry_date, description: notice.description || "" })).catch((reason) => setError(reason.message));
  }, [id]);
  const set = (key) => (event) => setValues({ ...values, [key]: event.target.value });
  const submit = async (event) => {
    event.preventDefault();
    if (!file) return setError("Please choose a PDF or image.");
    setBusy(true);
    setError("");
    try {
      const body = { ...values, file };
      const result = id ? await api.newVersion(id, body) : await api.create(body);
      setDone(result);
      setQr(`/api/notices/${result.notice_id}/qr`);
    } catch (reason) { setError(reason.message); }
    setBusy(false);
  };
  const download = async () => {
    const url = await api.blobUrl(done.download || `/api/notices/${done.notice_id}/download`);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = done.notice_id;
    anchor.click();
  };
  if (done) return <section className="card mx-auto max-w-2xl space-y-5 text-center">
    <span className="mx-auto grid h-14 w-14 place-items-center rounded-2xl border border-emerald-400/20 bg-emerald-400/10 text-emerald-300"><Icon name="shield" size={29} /></span>
    <div><p className="page-eyebrow">Cryptographic issue complete</p><h1 className="page-title mt-2 text-emerald-200">Notice authenticated</h1><p className="mt-2 text-sm text-slate-400">Your document has been registered and signed by the institution.</p></div>
    <div className="rounded-xl border border-white/[.07] bg-black/[.12] p-4 text-left text-xs"><div className="text-[9px] font-bold uppercase tracking-widest text-slate-500">Registry record</div><div className="mt-2">ID: <b className="break-all font-mono">{done.notice_id}</b>{done.version && ` · version ${done.version}`}</div><div className="mt-2 break-all text-[10px] text-slate-400">SHA-256: {done.sha256}</div></div>
    <img src={apiUrl(qr)} className="mx-auto h-40 w-40 rounded-xl bg-white p-2" alt="Notice registry QR code" />
    <div className="flex flex-wrap justify-center gap-3"><button className="btn-primary" onClick={download}><Icon name="arrow" size={15} /> Download authenticated notice</button><Link className="btn-ghost" to="/admin">Dashboard</Link></div>
  </section>;
  return <div className="space-y-6">
    <section><p className="page-eyebrow">Institutional document registry</p><h1 className="page-title mt-2">{id ? `Issue corrected version` : "Publish a notice"}</h1><p className="mt-2 text-sm text-slate-400">{id ? `Create a signed replacement for ${id}.` : "Register and authenticate an official institutional notice."}</p></section>
    <form onSubmit={submit} className="grid items-start gap-5 xl:grid-cols-[minmax(0,1.4fr)_minmax(260px,.6fr)]">
      <div className="card space-y-4">
        <div className="flex items-start gap-3 border-b border-white/[.07] pb-4"><span className="grid h-10 w-10 place-items-center rounded-xl border border-cyan-400/15 bg-cyan-400/[.06] text-cyan-200"><Icon name="publish" /></span><div><h2 className="section-title">Notice details</h2><p className="mt-1 text-[11px] text-slate-500">Complete the details exactly as they should appear in the official record.</p></div></div>
        <label className="block text-xs font-medium text-slate-300">Notice title<input className="input mt-1.5" placeholder="Enter an official title" value={values.title} onChange={set("title")} required /></label>
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="text-xs font-medium text-slate-300">Department<input className="input mt-1.5" placeholder="Issuing department" value={values.department} onChange={set("department")} required /></label>
          <label className="text-xs font-medium text-slate-300">Category<select className="input mt-1.5" value={values.category} onChange={set("category")}>{["exam", "holiday", "academic", "event", "general"].map((category) => <option key={category}>{category}</option>)}</select></label>
          <label className="text-xs font-medium text-slate-300">Issue date<input type="date" className="input mt-1.5" value={values.issue_date} onChange={set("issue_date")} required /></label>
          <label className="text-xs font-medium text-slate-300">Expiry date<input type="date" className="input mt-1.5" value={values.expiry_date} onChange={set("expiry_date")} required /></label>
        </div>
        <label className="block text-xs font-medium text-slate-300">Description<textarea className="input mt-1.5 min-h-24 resize-y" rows="3" placeholder="Optional notice summary" value={values.description} onChange={set("description")} /></label>
        <label className="block text-xs font-medium text-slate-300">Notice document<input type="file" className="input mt-1.5 file:mr-3 file:rounded-md file:border-0 file:bg-blue-500/15 file:px-3 file:py-1.5 file:text-xs file:font-semibold file:text-blue-200" accept=".pdf,.png,.jpg,.jpeg" onChange={(event) => setFile(event.target.files[0])} required /><span className="mt-1 block text-[10px] text-slate-500">Accepted formats: PDF or image.</span></label>
        {error && <p role="alert" className="rounded-lg border border-red-400/20 bg-red-400/[.06] px-3 py-2 text-xs text-red-300">{error}</p>}
        <button className="btn-primary w-full sm:w-auto" disabled={busy}>{busy ? <><span className="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white" /> Signing &amp; watermarking…</> : <><Icon name="shield" size={15} /> Sign, watermark &amp; generate QR</>}</button>
      </div>
      <aside className="card space-y-4">
        <span className="grid h-10 w-10 place-items-center rounded-xl border border-emerald-400/15 bg-emerald-400/[.06] text-emerald-300"><Icon name="shield" /></span>
        <div><h2 className="section-title">Protected by TRUSTNOTICE</h2><p className="mt-1 text-xs leading-5 text-slate-400">Publishing creates a verifiable registry record without changing the existing signing workflow.</p></div>
        {[["SHA-256", "Integrity fingerprint"], ["Ed25519", "Issuer digital signature"], ["DWT + DCT", "Invisible watermark"], ["QR code", "Registry record locator"]].map(([label, detail]) => <div key={label} className="flex items-center gap-3 rounded-lg border border-white/[.06] bg-white/[.02] p-3"><Icon name="verify" size={15} className="text-emerald-300" /><div><b className="block text-xs">{label}</b><span className="text-[10px] text-slate-500">{detail}</span></div></div>)}
      </aside>
    </form>
  </div>;
}
