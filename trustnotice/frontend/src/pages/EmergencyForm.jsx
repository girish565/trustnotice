import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../services/api";
import { Icon } from "../components/ui";

const today = new Date().toISOString().slice(0, 10);
const categories = [
  ["college_holiday", "College Holiday"],
  ["examination_cancellation", "Examination Cancellation"],
  ["examination_postponement", "Examination Postponement"],
  ["emergency_closure", "Emergency Closure"],
  ["important_announcement", "Important Announcement"],
  ["fee_deadline", "Fee Deadline"],
  ["weather_emergency", "Weather Emergency"],
  ["other", "Other"],
];
export default function EmergencyForm() {
  const [values, setValues] = useState({
    title: "", description: "", category: "other", priority: "critical",
    audience: "all", department: "", academic_year: "", class_name: "",
    selected_student_ids: [], issue_date: today,
    expiry_date: "", replaces_notice_id: "",
  });
  const [attachment, setAttachment] = useState(null);
  const [notices, setNotices] = useState([]);
  const [students, setStudents] = useState([]);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const priorityOptions = [
    ["critical", "Critical", "Immediate attention required", "emergency"],
    ["high", "High", "Important time-sensitive update", "bell"],
    ["normal", "Normal", "General institutional update", "notices"],
  ];
  useEffect(() => {
    Promise.all([api.notices(), api.students()])
      .then(([noticeRows, studentRows]) => { setNotices(noticeRows); setStudents(studentRows); })
      .catch((e) => setError(e.message));
  }, []);
  const change = (key) => (event) => setValues({ ...values, [key]: event.target.value });
  const changeAudience = (event) => {
    const audience = event.target.value;
    setValues({ ...values, audience,
      department: ["department", "department_year"].includes(audience) ? values.department : "",
      academic_year: ["year", "department_year"].includes(audience) ? values.academic_year : "",
      class_name: audience === "class" ? values.class_name : "",
      selected_student_ids: audience === "selected" ? values.selected_student_ids : [] });
  };
  const toggleStudent = (studentId) => {
    const ids = new Set(values.selected_student_ids);
    if (ids.has(studentId)) ids.delete(studentId); else ids.add(studentId);
    setValues({ ...values, selected_student_ids: [...ids] });
  };
  const submit = async (event) => {
    event.preventDefault(); setBusy(true); setError("");
    try { setResult(await api.createEmergency({ ...values, expiry_date: values.expiry_date || null, attachment })); }
    catch (e) { setError(e.message); }
    setBusy(false);
  };
  if (result) return <section className="card mx-auto max-w-2xl space-y-4 text-center">
    <span className="mx-auto grid h-14 w-14 place-items-center rounded-2xl border border-emerald-400/20 bg-emerald-400/10 text-emerald-300"><Icon name="shield" size={27} /></span>
    <p className="page-eyebrow">Cryptographic issue complete</p>
    <h1 className="page-title text-emerald-200">Alert published securely</h1>
    <p className="text-sm text-slate-400">Notice ID <span className="font-mono text-slate-100">{result.notice_id}</span> · delivered to {result.recipient_count} student account(s)</p>
    {result.replacement_notice_id && <p>Replaced notice; new ID: {result.replacement_notice_id}</p>}
    <div className="flex flex-wrap justify-center gap-2"><Link className="btn-primary" to="/admin">View communication centre</Link><Link className="btn-ghost" to="/admin/emergency">Create another alert</Link></div>
  </section>;
  return <div className="space-y-7">
    <section className="flex flex-wrap items-end justify-between gap-4">
      <div><p className="page-eyebrow">Secure institutional communications</p><h1 className="page-title mt-2">Emergency Communication Centre</h1><p className="mt-2 max-w-2xl text-sm text-slate-400">Ensure every student receives critical institutional updates—signed, verifiable, and delivered to the right audience.</p></div>
      <Link to="/admin#notices" className="btn-ghost"><Icon name="history" size={16} /> Alert history</Link>
    </section>
    <form onSubmit={submit} className="grid items-start gap-5 xl:grid-cols-[minmax(0,1.45fr)_minmax(300px,.75fr)]">
      <div className="card space-y-5">
        <div className="flex items-start gap-3 border-b border-white/[.07] pb-4"><span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl border border-red-400/15 bg-red-400/10 text-red-300"><Icon name="emergency" size={19} /></span><div><h2 className="section-title">Create emergency alert</h2><p className="mt-1 text-[11px] text-slate-500">The final document is signed, watermarked, and QR-coded before delivery.</p></div></div>
        <label className="block text-xs font-medium text-slate-300">Alert title<input className="input mt-1.5" placeholder="e.g. Campus closed due to severe weather" value={values.title} onChange={change("title")} required maxLength={200} /></label>
        <label className="block text-xs font-medium text-slate-300">Description<textarea className="input mt-1.5 min-h-32 resize-y" rows="4" placeholder="Share clear instructions and relevant details with students…" value={values.description} onChange={change("description")} required maxLength={10000} /></label>
        <div>
          <div className="mb-2 text-xs font-semibold text-slate-300">Priority level</div>
          <div className="grid gap-2 sm:grid-cols-3">{priorityOptions.map(([value, label, detail, icon]) => <button key={value} type="button" onClick={() => setValues({ ...values, priority: value })} className={`rounded-xl border p-3 text-left transition ${values.priority === value ? `ring-1 priority-${value}` : "border-white/10 bg-white/[.02] hover:bg-white/[.05]"}`}>
            <div className={`mb-2 inline-flex h-8 w-8 items-center justify-center rounded-lg ${value === "critical" ? "bg-red-400/10 text-red-300" : value === "high" ? "bg-orange-400/10 text-orange-300" : "bg-blue-400/10 text-blue-300"}`}><Icon name={icon} size={16} /></div>
            <div className="text-xs font-bold uppercase">{label}</div><div className="mt-1 text-[9px] leading-4 text-slate-400">{detail}</div>
          </button>)}</div>
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="text-xs font-medium text-slate-300">Category<select className="input mt-1.5" value={values.category} onChange={change("category")} required>{categories.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
          <label className="text-xs font-medium text-slate-300">Target audience<select className="input mt-1.5" value={values.audience} onChange={changeAudience}>{[["all", "All students"], ["department", "Specific department"], ["year", "Academic year"], ["department_year", "Department + year"], ["class", "Specific class / cohort"], ["selected", "Selected students"]].map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select></label>
          {["department", "department_year"].includes(values.audience) && <label className="text-xs font-medium text-slate-300">Department<input className="input mt-1.5" value={values.department} onChange={change("department")} required /></label>}
          {["year", "department_year"].includes(values.audience) && <label className="text-xs font-medium text-slate-300">Academic year<input className="input mt-1.5" placeholder="e.g. 2026" value={values.academic_year} onChange={change("academic_year")} required /></label>}
          {values.audience === "class" && <label className="text-xs font-medium text-slate-300">Class / cohort<select className="input mt-1.5" value={values.class_name} onChange={change("class_name")} required><option value="">Select a class</option>{[...new Set(students.map((s) => s.class_name).filter(Boolean))].sort().map((name) => <option key={name}>{name}</option>)}</select></label>}
          <label className="text-xs font-medium text-slate-300">Issue date<input type="date" className="input mt-1.5" value={values.issue_date} onChange={change("issue_date")} required /></label>
          <label className="text-xs font-medium text-slate-300">Expiry date <span className="font-normal text-slate-500">(optional)</span><input type="date" className="input mt-1.5" value={values.expiry_date} onChange={change("expiry_date")} /></label>
        </div>
        {values.audience === "selected" && <fieldset className="rounded-xl border border-white/10 bg-black/10 p-4">
          <legend className="px-2 text-xs font-semibold">Select recipients ({values.selected_student_ids.length} selected)</legend>
          <div className="max-h-48 space-y-1 overflow-y-auto">{students.map((student) => <label key={student.id} className="flex cursor-pointer items-center gap-3 rounded-lg px-2 py-2 text-xs transition hover:bg-white/5">
            <input type="checkbox" checked={values.selected_student_ids.includes(student.id)} onChange={() => toggleStudent(student.id)} />
            <span className="text-slate-300">{student.name} · {student.student_id} · {student.department} · {student.class_name || "No class"}</span>
          </label>)}</div>
          {!students.length && <p className="text-xs text-amber-300">Create student profiles before selecting recipients.</p>}
        </fieldset>}
        <label className="block text-xs font-medium text-slate-300">Attachment <span className="font-normal text-slate-500">(optional · PDF, PNG or JPG)</span><input type="file" className="input mt-1.5" accept=".pdf,.png,.jpg,.jpeg" onChange={(e) => setAttachment(e.target.files?.[0] || null)} /></label>
        <label className="block text-xs font-medium text-slate-300">Replace existing emergency <span className="font-normal text-slate-500">(optional)</span><select className="input mt-1.5" value={values.replaces_notice_id} onChange={change("replaces_notice_id")}><option value="">Do not replace an existing notice</option>{notices.filter((n) => n.is_emergency && n.status === "active").map((n) => <option key={n.notice_id} value={n.notice_id}>{n.title} · {n.notice_id}</option>)}</select></label>
        {error && <p role="alert" className="rounded-xl border border-red-400/20 bg-red-400/5 px-3 py-2 text-xs text-red-300">{error}</p>}
        <button className="btn-primary w-full !py-3" disabled={busy}>{busy ? <><span className="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white" /> Signing & notifying…</> : <><Icon name="shield" size={16} /> Create Emergency Alert</>}</button>
      </div>
      <aside className="space-y-4 xl:sticky xl:top-20">
        <div className={`card overflow-hidden border ${values.priority === "critical" ? "border-red-400/20" : values.priority === "high" ? "border-orange-400/20" : "border-blue-400/20"}`}>
          <div className={`-mx-5 -mt-5 mb-4 flex items-center gap-2 px-5 py-3 text-[10px] font-bold uppercase tracking-[.13em] ${values.priority === "critical" ? "bg-red-500/10 text-red-200" : values.priority === "high" ? "bg-orange-500/10 text-orange-200" : "bg-blue-500/10 text-blue-200"}`}>
            <Icon name="emergency" size={15} /> Live student alert preview
          </div>
          <div className="flex items-start gap-3">
            <div className={`mt-0.5 grid h-9 w-9 shrink-0 place-items-center rounded-xl ${values.priority === "critical" ? "bg-red-500/15 text-red-300" : values.priority === "high" ? "bg-orange-500/15 text-orange-300" : "bg-blue-500/15 text-blue-300"}`}><Icon name={values.priority === "normal" ? "bell" : "emergency"} size={18} /></div>
            <div className="min-w-0"><span className={`rounded-full border px-2 py-1 text-[9px] font-bold uppercase priority-${values.priority}`}>{values.priority} priority</span>
              <h3 className="mt-3 break-words text-base font-bold text-white">{values.title || "Your alert title will appear here"}</h3>
              <p className="mt-2 whitespace-pre-wrap break-words text-xs leading-5 text-slate-300">{values.description || "A preview of your message appears here as you write it."}</p>
              <div className="mt-4 flex flex-wrap gap-2 text-[9px] text-slate-500"><span>{categories.find(([key]) => key === values.category)?.[1]}</span><span>·</span><span>{values.issue_date || "Issue date"}</span>{values.expiry_date && <><span>·</span><span>Expires {values.expiry_date}</span></>}</div>
            </div>
          </div>
          <div className="mt-4 flex items-center gap-2 border-t border-white/[.07] pt-3 text-[10px] text-slate-500"><Icon name="shield" size={14} className="text-emerald-400" />Signed, watermarked and delivered to intended recipients</div>
        </div>
        <div className="card">
          <h3 className="section-title">Secure publishing workflow</h3>
          <div className="mt-4 space-y-4">{[["01", "Audience validated", "Only matching student profiles receive the alert."], ["02", "Notice authenticated", "SHA-256, Ed25519 signature, QR and watermark."], ["03", "Delivery tracked", "Inbox delivery, reading and acknowledgement stay distinct."]].map(([number, title, detail]) => <div key={number} className="flex gap-3"><span className="font-display text-xs font-bold text-cyan-300">{number}</span><div><div className="text-xs font-semibold">{title}</div><p className="mt-1 text-[10px] leading-4 text-slate-500">{detail}</p></div></div>)}</div>
        </div>
      </aside>
    </form>
  </div>;
}
