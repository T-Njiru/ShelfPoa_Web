import { useEffect, useMemo, useState } from "react";
import { useLocation } from "react-router-dom";
import { api } from "../services/api";
import * as store from "../services/recommendationStore";
import { agoLabel } from "../lib/format";
import { GhostButton, Pill, PrimaryButton, SectionLabel } from "../components/ui";

const TYPES = [
  { value: "sos", label: "SOS / shelf space" },
  { value: "copromo", label: "Co-promotion" },
  { value: "restock", label: "Restock priority" },
];
const TYPE_LABEL = Object.fromEntries(TYPES.map((t) => [t.value, t.label]));
const STATUS_KIND = { Pending: "warn", Seen: "neutral", Done: "ok", Declined: "warn", Draft: "neutral" };

const fieldCls = "w-full h-11 rounded-control bg-field px-4 text-[13px] text-white outline-none focus:ring-1 focus:ring-accent";
const labelCls = "block mb-2 text-[11px] leading-[14px] font-semibold uppercase tracking-wide text-muted";

const toIso = (ms) => (ms ? new Date(ms).toISOString() : new Date().toISOString());

export default function RecommendationMaker() {
  const prefill = useLocation().state ?? {}; // set by "Send recommendation" on the Recommendations page

  const [merchandisers, setMerchandisers] = useState([]); // [{ uid, name, email }]
  const [outlets, setOutlets] = useState([]);             // names
  const [outletIdByName, setOutletIdByName] = useState({});
  const [sent, setSent] = useState([]);
  const [drafts, setDrafts] = useState(store.listDrafts);

  const [draftId, setDraftId] = useState("");
  const [merchandiser, setMerchandiser] = useState(""); // uid
  const [outlet, setOutlet] = useState(prefill.outlet ?? "");
  const [sku, setSku] = useState(prefill.sku ?? "");
  const [type, setType] = useState(prefill.type ?? "sos");
  const [source, setSource] = useState(prefill.source ?? "");
  const [message, setMessage] = useState("");
  const [priority, setPriority] = useState("High");
  const [due, setDue] = useState("Next visit");
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    Promise.all([
      store.listMerchandisers().catch(() => []),
      store.listOutlets().catch(() => []),
      api.getForecasts(50).catch(() => []),
      api.getStockoutAlerts(50).catch(() => []),
    ]).then(([merch, fbOutlets, fc, so]) => {
      setMerchandisers(merch);
      setOutletIdByName(Object.fromEntries(fbOutlets.map((o) => [o.name, o.id])));
      const names = [
        ...fbOutlets.map((o) => o.name),
        ...fc.map((x) => x.branch_name),
        ...so.map((x) => x.branch_name),
      ].filter(Boolean);
      setOutlets([...new Set([prefill.outlet, ...names].filter(Boolean))].sort());
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Live status: Pending → Seen → Done / Declined as the merchandiser acts in the app
  useEffect(() => store.watchSent((rows) => setSent(rows.slice(0, 20)), () => setError("Couldn't load sent recommendations.")), []);

  const nameByUid = useMemo(
    () => Object.fromEntries(merchandisers.map((m) => [m.uid, m.name])),
    [merchandisers]
  );

  function resetForm() {
    setDraftId("");
    setMessage("");
    setSku("");
    setSource("");
  }

  async function sendNow() {
    setInfo("");
    if (!merchandiser || !outlet || !message.trim()) {
      setError("Pick a merchandiser and outlet, and write a message.");
      return;
    }
    setError("");
    setBusy(true);
    try {
      await store.send(merchandiser, {
        title: TYPE_LABEL[type],
        type,
        message,
        priority: priority.toLowerCase(),
        due,
        outletName: outlet,
        outletId: outletIdByName[outlet] ?? "",
        sku,
        basis: source,
        source: source ? "ml" : "manual",
      });
      if (draftId) {
        store.removeDraft(draftId);
        setDrafts(store.listDrafts());
      }
      setInfo(`Sent to ${nameByUid[merchandiser] ?? "merchandiser"}.`);
      resetForm();
    } catch (e) {
      setError(e.message || "Couldn't send.");
    } finally {
      setBusy(false);
    }
  }

  function saveDraft() {
    setInfo("");
    if (!message.trim()) {
      setError("Write a message before saving a draft.");
      return;
    }
    setError("");
    store.saveDraft({ id: draftId, merchandiser, outlet, sku, type, source, message, priority, due });
    setDrafts(store.listDrafts());
    setInfo("Draft saved on this browser.");
    resetForm();
  }

  function loadDraft(d) {
    setDraftId(d.id);
    setMerchandiser(d.merchandiser ?? "");
    setOutlet(d.outlet ?? "");
    setSku(d.sku ?? "");
    setType(d.type ?? "sos");
    setSource(d.source ?? "");
    setMessage(d.message ?? "");
    setPriority(d.priority ?? "High");
    setDue(d.due ?? "Next visit");
    setError("");
    setInfo("Draft loaded. Send it or save again.");
  }

  function deleteDraft(id) {
    store.removeDraft(id);
    setDrafts(store.listDrafts());
    if (id === draftId) resetForm();
  }

  return (
    <div className="grid grid-cols-[minmax(0,660px)_minmax(180px,1fr)] gap-7 items-start">
      <div className="rounded-card bg-card p-6">
        <h2 className="text-base font-bold mb-6">{draftId ? "Edit draft" : "New recommendation"}</h2>

        <label className={labelCls}>Merchandiser</label>
        <select className={`${fieldCls} mb-3.5`} value={merchandiser} onChange={(e) => setMerchandiser(e.target.value)}>
          <option value="">Select merchandiser…</option>
          {merchandisers.map((m) => (
            <option key={m.uid} value={m.uid}>{m.name}</option>
          ))}
        </select>
        {merchandisers.length === 0 && (
          <p className="text-[11px] text-muted -mt-2 mb-3.5">No merchandiser accounts yet. Invite one from the Users page.</p>
        )}

        <div className="grid grid-cols-2 gap-5">
          <div>
            <label className={labelCls}>Outlet</label>
            <select className={`${fieldCls} mb-3.5`} value={outlet} onChange={(e) => setOutlet(e.target.value)}>
              <option value="">Select outlet…</option>
              {outlets.map((o) => <option key={o}>{o}</option>)}
            </select>
          </div>
          <div>
            <label className={labelCls}>SKU (optional)</label>
            <select className={`${fieldCls} mb-3.5`} value={sku} onChange={(e) => setSku(e.target.value)}>
              <option value="">Any / not specific</option>
              {store.SKUS.map((s) => <option key={s}>{s}</option>)}
            </select>
          </div>
        </div>

        <label className={labelCls}>Recommendation type</label>
        <div className="flex gap-3 mb-3.5">
          {TYPES.map((t) => (
            <button
              key={t.value}
              type="button"
              onClick={() => setType(t.value)}
              className={`h-9 px-3 rounded-control text-xs font-semibold ${
                type === t.value ? "bg-accent text-ink" : "bg-field text-white hover:bg-track"
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>

        <label className={labelCls}>Suggested source (optional)</label>
        <select className={`${fieldCls} mb-3.5`} value={source} onChange={(e) => setSource(e.target.value)}>
          <option value="">None</option>
          {source && !source.startsWith("FP-Growth — co-promotion rule") && !source.startsWith("XGBoost — demand forecast") && (
            <option>{source}</option>
          )}
          {prefill.source && prefill.source !== source && <option>{prefill.source}</option>}
          <option>FP-Growth — co-promotion rule</option>
          <option>XGBoost — demand forecast</option>
        </select>

        <label className={labelCls}>Message</label>
        <textarea
          rows={5} style={{ height: 130 }}
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          maxLength={500}
          placeholder="e.g. Share-of-shelf is below target. Please request an extra facing on the middle shelf during your next visit."
          className="w-full rounded-control bg-field px-4 py-3 text-[13px] text-white placeholder:text-muted outline-none focus:ring-1 focus:ring-accent mb-5 resize-none block"
        />

        <div className="grid grid-cols-2 gap-5 mb-5">
          <select className={`${fieldCls} font-semibold ${priority === "High" ? "!text-warn" : ""}`} value={priority} onChange={(e) => setPriority(e.target.value)}>
            {["High", "Medium", "Low"].map((p) => <option key={p} value={p}>Priority: {p}</option>)}
          </select>
          <select className={fieldCls} value={due} onChange={(e) => setDue(e.target.value)}>
            {["Next visit", "Within 24 hours", "This week"].map((d) => <option key={d} value={d}>Due: {d}</option>)}
          </select>
        </div>

        {error && <p className="text-bad text-xs mb-3">{error}</p>}
        {info && <p className="text-ok text-xs mb-3">{info}</p>}

        <div className="grid grid-cols-2 gap-5">
          <PrimaryButton onClick={sendNow} disabled={busy} className="h-[46px] text-left px-4 text-[13px] disabled:opacity-60">
            {busy ? "Sending…" : "Send to merchandiser"}
          </PrimaryButton>
          <GhostButton onClick={saveDraft} disabled={busy} className="h-[46px] text-left px-4 text-[13px]">
            Save as draft
          </GhostButton>
        </div>
      </div>

      <div className="max-w-[208px] pt-[22px]">
        {drafts.length > 0 && (
          <>
            <SectionLabel>Drafts</SectionLabel>
            <div className="flex flex-col gap-3 mb-6">
              {drafts.map((d) => (
                <div key={d.id} className="rounded-card bg-card p-4">
                  <button type="button" onClick={() => loadDraft(d)} className="text-left w-full">
                    <div className="text-[13px] font-bold">{nameByUid[d.merchandiser] ?? "No merchandiser"}</div>
                    <div className="text-[11px] text-muted mt-1">{TYPE_LABEL[d.type]}</div>
                    <div className="text-[11px] text-muted">{d.outlet || "No outlet"}</div>
                  </button>
                  <div className="flex items-center gap-2 mt-3">
                    <Pill kind={STATUS_KIND.Draft}>Draft</Pill>
                    <span className="text-[10px] text-muted">{agoLabel(d.savedAt)}</span>
                    <button type="button" onClick={() => deleteDraft(d.id)} className="ml-auto text-[10px] text-muted hover:text-white">
                      Delete
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </>
        )}

        <SectionLabel>Recently sent</SectionLabel>
        <div className="flex flex-col gap-3">
          {sent.map((s) => {
            const label = store.STATUS_LABEL[s.status] ?? "Pending";
            return (
              <div key={`${s.merchandiserUid}-${s.id}`} className="rounded-card bg-card p-4">
                <div className="text-[13px] font-bold">{nameByUid[s.merchandiserUid] ?? "Unknown merchandiser"}</div>
                <div className="text-[11px] text-muted mt-1">{TYPE_LABEL[s.type] ?? s.title}</div>
                <div className="text-[11px] text-muted">
                  {s.outletName}{s.sku ? ` · ${s.sku}` : ""}
                </div>
                {s.merchandiserNote && (
                  <div className="text-[11px] text-white/70 mt-2 italic">“{s.merchandiserNote}”</div>
                )}
                <div className="flex items-center gap-2 mt-3">
                  <Pill kind={STATUS_KIND[label]}>{label}</Pill>
                  <span className="text-[10px] text-muted">{agoLabel(toIso(s.createdAt))}</span>
                </div>
              </div>
            );
          })}
          {!sent.length && <p className="text-xs text-muted">Nothing sent yet.</p>}
        </div>
      </div>
    </div>
  );
}
