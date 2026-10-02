import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { Loader2, Check, X } from 'lucide-react';
import { Checkbox } from '../components/ui/checkbox';
import { errorMessage } from '../sync/api';
import { agreementApi, openAgreementPdf, formatSignedDate } from './agreementApi';
import AgreementDoc from './AgreementDoc';

const CHECKBOX_CLASS =
  'mt-0.5 rounded-[3px] border-white/30 data-[state=checked]:border-electric data-[state=checked]:bg-electric data-[state=checked]:text-white focus-visible:ring-electric';

const EMPTY_FIELDS = {
  legal_name: '', artist_name: '', company_name: '', signer_title: '',
  address_line1: '', address_line2: '', city: '', region: '', postal_code: '',
  country: 'United States',
};

const collapse = (s) => (s || '').trim().replace(/\s+/g, ' ');

export default function AgreementModal({ open, onClose, onSigned, getToken, prefill, previousSigned }) {
  const navigate = useNavigate();

  const [step, setStep] = useState(1);
  const [entity, setEntity] = useState('individual');
  const [fields, setFields] = useState(EMPTY_FIELDS);
  const [adult, setAdult] = useState(false);
  const [email, setEmail] = useState('');
  const [prefilled, setPrefilled] = useState({});

  const [blocks, setBlocks] = useState([]);
  const [textSha256, setTextSha256] = useState('');
  const [scrolledEnd, setScrolledEnd] = useState(false);
  const [step2Msg, setStep2Msg] = useState('');

  const [typedSig, setTypedSig] = useState('');
  const [consentElectronic, setConsentElectronic] = useState(false);
  const [agreed, setAgreed] = useState(false);

  const [signedAgreement, setSignedAgreement] = useState(null);
  const [busy, setBusy] = useState(false);
  const [err1, setErr1] = useState('');
  const [err3, setErr3] = useState('');

  const docRef = useRef(null);
  const firstFieldRef = useRef(null);
  const openerRef = useRef(null);
  const wasOpen = useRef(false);
  const initRef = useRef(false);

  const setField = (k, v) => setFields((f) => ({ ...f, [k]: v }));

  // Prefill once from status.prefill. Entered details then survive close and reopen.
  useEffect(() => {
    if (prefill && !initRef.current) {
      initRef.current = true;
      setEntity(prefill.entity_type === 'company' ? 'company' : 'individual');
      setFields((f) => ({
        ...f,
        legal_name: prefill.legal_name || '',
        artist_name: prefill.artist_name || '',
        company_name: prefill.company_name || '',
        signer_title: prefill.signer_title || '',
        address_line1: prefill.address_line1 || '',
        address_line2: prefill.address_line2 || '',
        city: prefill.city || '',
        region: prefill.region || '',
        postal_code: prefill.postal_code || '',
        country: prefill.country || 'United States',
      }));
      setEmail(prefill.email || '');
      setPrefilled({
        legal_name: !!prefill.legal_name,
        artist_name: !!prefill.artist_name,
        email: !!prefill.email,
      });
    }
  }, [prefill]);

  // On open: reset to step 1, clear step 2 and 3 scratch, keep step 1 details. Restore focus on close.
  useEffect(() => {
    if (open && !wasOpen.current) {
      openerRef.current = document.activeElement;
      setStep(1);
      setScrolledEnd(false);
      setStep2Msg('');
      setTypedSig('');
      setConsentElectronic(false);
      setAgreed(false);
      setErr1('');
      setErr3('');
      setTimeout(() => firstFieldRef.current?.focus(), 50);
    }
    if (!open && wasOpen.current && openerRef.current?.focus) {
      openerRef.current.focus();
    }
    wasOpen.current = open;
  }, [open]);

  useEffect(() => {
    if (!open) return undefined;
    const onKey = (e) => { if (e.key === 'Escape' && !busy) handleClose(); };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [open, busy]); // eslint-disable-line react-hooks/exhaustive-deps

  // Scroll gate: also unlock once if the agreement fits without scrolling.
  useEffect(() => {
    if (step === 2 && blocks.length) {
      const d = docRef.current;
      if (d && d.scrollHeight <= d.clientHeight + 8) setScrolledEnd(true);
    }
  }, [step, blocks]);

  const buildFields = () => ({
    entity_type: entity,
    legal_name: collapse(fields.legal_name),
    artist_name: collapse(fields.artist_name),
    company_name: entity === 'company' ? collapse(fields.company_name) : '',
    signer_title: entity === 'company' ? collapse(fields.signer_title) : '',
    address_line1: collapse(fields.address_line1),
    address_line2: collapse(fields.address_line2),
    city: collapse(fields.city),
    region: collapse(fields.region),
    postal_code: collapse(fields.postal_code),
    country: collapse(fields.country),
    adult_confirmed: adult,
  });

  const step1Error = () => {
    if (!collapse(fields.legal_name)) return 'Enter your full legal name.';
    if (entity === 'company' && (!collapse(fields.company_name) || !collapse(fields.signer_title)))
      return 'Enter the company name and your title.';
    if (!collapse(fields.address_line1) || !collapse(fields.city) || !collapse(fields.country))
      return 'Enter your street address, city and country.';
    if (!adult) return 'You must be 18 or older to sign.';
    return '';
  };

  const nameMatches = collapse(typedSig).toLowerCase() === collapse(fields.legal_name).toLowerCase();
  const liveNameError = collapse(typedSig) && !nameMatches
    ? 'Type your full legal name exactly as entered in step 1.' : '';
  const canSign = nameMatches && consentElectronic && agreed && !!collapse(typedSig);

  const handleClose = () => { if (!busy) onClose(); };

  const doPreview = async () => {
    const e = step1Error();
    setErr1(e);
    if (e) return;
    setBusy(true);
    try {
      const data = await agreementApi.preview(getToken, buildFields());
      setBlocks(data.blocks || []);
      setTextSha256(data.text_sha256);
      if (data.email) setEmail(data.email);
      setScrolledEnd(false);
      setStep2Msg('');
      setStep(2);
    } catch (err) {
      setErr1(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  const repreview = async (msg) => {
    try {
      const data = await agreementApi.preview(getToken, buildFields());
      setBlocks(data.blocks || []);
      setTextSha256(data.text_sha256);
      if (data.email) setEmail(data.email);
      setScrolledEnd(false);
      setStep2Msg(msg);
      setStep(2);
    } catch (err) {
      setErr3(errorMessage(err));
    }
  };

  const finishSigned = (agreement) => {
    setSignedAgreement(agreement);
    setStep(4);
    if (onSigned) onSigned(agreement);
  };

  const doSign = async () => {
    setBusy(true);
    setErr3('');
    try {
      const res = await agreementApi.sign(getToken, {
        fields: buildFields(),
        text_sha256: textSha256,
        typed_signature: collapse(typedSig),
        consent_electronic: true,
        agreed: true,
      });
      finishSigned(res.agreement);
    } catch (err) {
      const sc = err?.response?.status;
      const detail = String(err?.response?.data?.detail || '');
      if (sc === 409 && /already signed/i.test(detail)) {
        try {
          const s = await agreementApi.status(getToken);
          finishSigned(s.agreement);
        } catch {
          finishSigned(null);
        }
      } else if (sc === 409) {
        await repreview('The agreement was updated. Please review it again.');
      } else {
        setErr3(errorMessage(err));
      }
    } finally {
      setBusy(false);
    }
  };

  const onDocScroll = () => {
    const d = docRef.current;
    if (d && d.scrollTop + d.clientHeight >= d.scrollHeight - 8) setScrolledEnd(true);
  };

  if (!open) return null;

  const leftLabel = step === 1 ? 'Not now' : step === 4 ? 'Download PDF' : 'Back';
  const rightLabel = step === 3 ? (busy ? 'Signing...' : 'Sign agreement')
    : step === 4 ? 'Continue to upload' : 'Continue';
  const rightDisabled =
    (step === 1 && (!!step1Error() || busy)) ||
    (step === 2 && (!scrolledEnd || busy)) ||
    (step === 3 && (!canSign || busy));

  const onLeft = () => {
    if (step === 1) handleClose();
    else if (step === 4) openAgreementPdf(getToken);
    else if (!busy) setStep(step - 1);
  };
  const onRight = () => {
    if (step === 1) doPreview();
    else if (step === 2) setStep(3);
    else if (step === 3) doSign();
    else if (step === 4) { navigate('/upload'); onClose(); }
  };

  const legalLabel = entity === 'company' ? 'Your full legal name' : 'Full legal name';
  const doneDate = formatSignedDate(signedAgreement?.signed_at || new Date().toISOString());

  const labelCls = 'mb-1.5 block text-[13.5px] font-medium text-slate-300';
  const fromCls = 'ml-1.5 text-[12px] font-normal text-slate-500';
  const inputCls = 'w-full rounded-lg border border-white/10 bg-black px-3 py-2.5 text-sm text-white focus:border-electric/70 focus:outline-none';
  const readonlyCls = 'w-full rounded-lg border border-white/10 bg-[#08080a] px-3 py-2.5 text-sm text-slate-400';

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4 max-[640px]:p-0">
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="agreement-title"
        className="flex max-h-[calc(100vh-32px)] w-full max-w-[640px] flex-col overflow-hidden rounded-[18px] border border-white/10 bg-[#0A0A0C] max-[640px]:h-full max-[640px]:max-h-screen max-[640px]:rounded-none"
      >
        {/* Header */}
        <div className="flex items-start justify-between gap-2.5 px-[22px] pt-5">
          <h2 id="agreement-title" className="font-heading text-[22px] font-extrabold text-white">
            oVoxi Artist Agreement
          </h2>
          <button
            type="button"
            aria-label="Close"
            onClick={handleClose}
            disabled={busy}
            className="px-1.5 py-0.5 text-slate-400 hover:text-white disabled:opacity-40"
          >
            <X size={22} />
          </button>
        </div>

        {/* Progress */}
        {step !== 4 && (
          <div className="flex gap-1.5 px-[22px] pt-3.5">
            {[['1', 'YOUR DETAILS'], ['2', 'REVIEW'], ['3', 'SIGN']].map(([n, label], i) => {
              const idx = i + 1;
              const active = idx === step;
              const done = idx < step;
              return (
                <div key={n} className="flex-1">
                  <span className={`block h-[3px] rounded ${active || done ? 'bg-gradient-brand' : 'bg-[#1f2937]'}`} />
                  <span className={`mt-1.5 block text-[11.5px] tracking-[0.04em] ${active ? 'text-white' : 'text-slate-500'}`}>
                    {n} · {label}
                  </span>
                </div>
              );
            })}
          </div>
        )}

        {/* Body */}
        <div className="flex-1 overflow-auto px-[22px] py-[18px]">
          {step === 1 && (
            <>
              <p className="mb-[18px] text-[14.5px] leading-[1.5] text-slate-300">
                {previousSigned
                  ? "We've updated the oVoxi Artist Agreement. Review and sign the new version to keep uploading. Your tracks and opt-ins stay as they are."
                  : 'Before your first upload, sign the oVoxi Artist Agreement. You only do this once, and it covers every track you upload. It takes about two minutes.'}
              </p>
              <div className="mb-4 inline-flex overflow-hidden rounded-full border border-white/10">
                {[['individual', "I'm signing as myself"], ['company', 'For a company']].map(([val, label]) => (
                  <button
                    key={val}
                    type="button"
                    onClick={() => setEntity(val)}
                    className={`px-4 py-1.5 text-[13.5px] ${entity === val ? 'bg-electric/30 text-white' : 'text-slate-400'}`}
                  >
                    {label}
                  </button>
                ))}
              </div>

              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                <div className="mb-3.5">
                  <label className={labelCls} htmlFor="ag-legal">
                    {legalLabel}{prefilled.legal_name && <span className={fromCls}>from your account</span>}
                  </label>
                  <input id="ag-legal" ref={firstFieldRef} type="text" className={inputCls}
                    value={fields.legal_name} onChange={(e) => setField('legal_name', e.target.value)} />
                </div>
                <div className="mb-3.5">
                  <label className={labelCls} htmlFor="ag-artist">
                    Artist name{prefilled.artist_name && <span className={fromCls}>from your sync profile</span>}
                  </label>
                  <input id="ag-artist" type="text" className={inputCls}
                    value={fields.artist_name} onChange={(e) => setField('artist_name', e.target.value)} />
                </div>
              </div>

              {entity === 'company' && (
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                  <div className="mb-3.5">
                    <label className={labelCls} htmlFor="ag-company">Company name</label>
                    <input id="ag-company" type="text" className={inputCls} placeholder="Rivera Music LLC"
                      value={fields.company_name} onChange={(e) => setField('company_name', e.target.value)} />
                  </div>
                  <div className="mb-3.5">
                    <label className={labelCls} htmlFor="ag-title">Your title</label>
                    <input id="ag-title" type="text" className={inputCls} placeholder="Owner"
                      value={fields.signer_title} onChange={(e) => setField('signer_title', e.target.value)} />
                  </div>
                </div>
              )}

              <div className="mb-3.5">
                <label className={labelCls} htmlFor="ag-email">
                  Email{prefilled.email && <span className={fromCls}>from your account</span>}
                </label>
                <input id="ag-email" type="text" className={readonlyCls} value={email} readOnly />
                <p className="mt-1.5 text-[12px] text-slate-500">To change it, update your account email first.</p>
              </div>

              <div className="mb-3.5">
                <label className={labelCls} htmlFor="ag-a1">Street address</label>
                <input id="ag-a1" type="text" className={inputCls} placeholder="123 Main St"
                  value={fields.address_line1} onChange={(e) => setField('address_line1', e.target.value)} />
              </div>
              <div className="mb-3.5">
                <label className={labelCls} htmlFor="ag-a2">Apartment, suite (optional)</label>
                <input id="ag-a2" type="text" className={inputCls}
                  value={fields.address_line2} onChange={(e) => setField('address_line2', e.target.value)} />
              </div>
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                <div className="mb-3.5">
                  <label className={labelCls} htmlFor="ag-city">City</label>
                  <input id="ag-city" type="text" className={inputCls}
                    value={fields.city} onChange={(e) => setField('city', e.target.value)} />
                </div>
                <div className="mb-3.5">
                  <label className={labelCls} htmlFor="ag-region">State / region</label>
                  <input id="ag-region" type="text" className={inputCls}
                    value={fields.region} onChange={(e) => setField('region', e.target.value)} />
                </div>
              </div>
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                <div className="mb-3.5">
                  <label className={labelCls} htmlFor="ag-zip">Postal code</label>
                  <input id="ag-zip" type="text" className={inputCls}
                    value={fields.postal_code} onChange={(e) => setField('postal_code', e.target.value)} />
                </div>
                <div className="mb-3.5">
                  <label className={labelCls} htmlFor="ag-country">Country</label>
                  <input id="ag-country" type="text" className={inputCls}
                    value={fields.country} onChange={(e) => setField('country', e.target.value)} />
                </div>
              </div>

              <label className="my-2.5 flex cursor-pointer items-start gap-2.5 text-sm leading-[1.45] text-slate-300">
                <Checkbox checked={adult} onCheckedChange={(v) => setAdult(v === true)} className={CHECKBOX_CLASS} />
                <span>I am 18 or older.</span>
              </label>
              <div className="mt-2 min-h-[18px] text-[13px] text-red-400">{err1}</div>
            </>
          )}

          {step === 2 && (
            <>
              {step2Msg && <div className="mb-3 text-[13px] text-red-400">{step2Msg}</div>}
              <div className="mb-3.5 rounded-xl border border-cyan/25 bg-cyan/5 px-3.5 py-3">
                <h4 className="mb-1.5 text-[12px] font-medium uppercase tracking-[0.12em] text-cyan">The short version</h4>
                <ul className="list-disc pl-[18px] text-[13.5px] leading-[1.55] text-slate-300">
                  <li>You keep ownership of your music.</li>
                  <li>Each track is only used the ways you choose at upload: AI training, sync, or both.</li>
                  <li>You get 33% of net revenue from every license, paid monthly.</li>
                  <li>AI companies may not clone your voice or use your name as a prompt.</li>
                  <li>You can pull a track with 30 days' notice. Licenses already sold stay valid.</li>
                </ul>
                <p className="mt-1.5 text-[11.5px] text-slate-500">This summary is for convenience only. The agreement below is what you are signing.</p>
              </div>
              <div
                ref={docRef}
                onScroll={onDocScroll}
                tabIndex={0}
                aria-label="Agreement text"
                className="h-[340px] overflow-auto rounded-xl border border-white/10 bg-white px-6 py-[22px] font-serif text-[13.5px] leading-[1.55] text-[#111]"
              >
                <AgreementDoc blocks={blocks} />
              </div>
              <div className={`mt-2 text-[12.5px] ${scrolledEnd ? 'text-green-400' : 'text-slate-500'}`}>
                {scrolledEnd ? 'You reached the end. You can continue.' : 'Scroll to the end of the agreement to continue.'}
              </div>
            </>
          )}

          {step === 3 && (
            <>
              <div className="mb-3.5">
                <label className={labelCls} htmlFor="ag-sig">Type your full legal name to sign</label>
                <input id="ag-sig" type="text" autoComplete="off" className={inputCls} placeholder={collapse(fields.legal_name)}
                  value={typedSig} onChange={(e) => setTypedSig(e.target.value)} />
                <div className={`my-1.5 flex min-h-[52px] items-end border-b border-white/10 px-0.5 py-1.5 font-serif text-[28px] italic ${collapse(typedSig) ? 'text-white' : 'text-[#333]'}`}>
                  {collapse(typedSig) || 'Your signature'}
                </div>
                <div className="mt-1.5 text-[12px] text-slate-500">
                  Must match the legal name you entered: <b className="font-medium text-slate-300">{collapse(fields.legal_name)}</b>
                </div>
              </div>
              <label className="my-2.5 flex cursor-pointer items-start gap-2.5 text-sm leading-[1.45] text-slate-300">
                <Checkbox checked={consentElectronic} onCheckedChange={(v) => setConsentElectronic(v === true)} className={CHECKBOX_CLASS} />
                <span>I agree to sign electronically, and that my typed name is my legal signature.</span>
              </label>
              <label className="my-2.5 flex cursor-pointer items-start gap-2.5 text-sm leading-[1.45] text-slate-300">
                <Checkbox checked={agreed} onCheckedChange={(v) => setAgreed(v === true)} className={CHECKBOX_CLASS} />
                <span>I have read and agree to the oVoxi Artist Agreement.</span>
              </label>
              <div className="mt-2 min-h-[18px] text-[13px] text-red-400">{err3 || liveNameError}</div>
            </>
          )}

          {step === 4 && (
            <div className="py-4 text-center">
              <div className="mx-auto mb-3.5 flex h-14 w-14 items-center justify-center rounded-full bg-gradient-brand">
                <Check size={28} className="text-white" />
              </div>
              <h3 className="mb-1.5 font-heading text-[22px] font-extrabold text-white">You're signed</h3>
              <p className="my-1 text-sm text-slate-400">
                Signed {doneDate}. A copy is on its way to <b className="font-medium text-white">{email}</b>.
              </p>
              <p className="my-1 text-sm text-slate-400">You can download it any time from your Vault.</p>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex flex-wrap items-center justify-between gap-2.5 border-t border-white/10 px-[22px] pb-5 pt-3.5">
          <button
            type="button"
            onClick={onLeft}
            disabled={busy && step !== 4}
            className="rounded-full border border-white/10 px-4 py-2 text-sm text-slate-300 transition-colors hover:border-electric/50 hover:text-white disabled:opacity-40"
          >
            {leftLabel}
          </button>
          <button
            type="button"
            onClick={onRight}
            disabled={rightDisabled}
            className="inline-flex items-center gap-2 rounded-full bg-gradient-brand px-5 py-2.5 text-sm font-semibold text-white transition-all hover:shadow-[0_0_24px_rgba(180,79,212,0.6)] disabled:cursor-not-allowed disabled:opacity-40 disabled:shadow-none"
          >
            {busy && (step === 1 || step === 3) && <Loader2 size={16} className="animate-spin" />}
            {rightLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
