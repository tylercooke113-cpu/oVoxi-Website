import React, { useCallback, useEffect, useRef, useState } from 'react';
import axios from 'axios';
import { useParams, Link } from 'react-router-dom';
import { Loader2, CheckCircle2, AlertCircle } from 'lucide-react';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Checkbox } from '../components/ui/checkbox';

const API = 'https://ovoxi-website-production.up.railway.app/api';

const CHECKBOX_CLASS =
  'mt-0.5 rounded-[3px] border-white/30 data-[state=checked]:border-electric data-[state=checked]:bg-electric data-[state=checked]:text-white focus-visible:ring-electric';
const FIELD_CLASS =
  'border-white/10 bg-ink text-white placeholder:text-slate-600 focus-visible:ring-electric';

const SIDE_LABEL = { writers: 'Writer', publishers: 'Publisher', master_owners: 'Master owner' };
const fmtPct = (bp) => (bp / 100).toFixed(2).replace(/\.?0+$/, '');
const fmtDate = (iso) => { try { return new Date(iso).toLocaleDateString(); } catch { return ''; } };

const detailMessage = (err, fallback) => {
  const d = err?.response?.data?.detail;
  if (typeof d === 'string') return d.replace(/^Value error, /, '');
  return fallback;
};

// Render the structured blocks the backend sends (never raw HTML).
const DocBlocks = ({ blocks }) => (
  <>
    {(blocks || []).map((b, i) => {
      if (b.type === 'title') return <h3 key={i} className="mt-4 text-center font-heading text-base font-semibold text-white">{b.text}</h3>;
      if (b.type === 'heading') return <h4 key={i} className="mt-4 font-heading text-sm font-semibold text-white">{b.text}</h4>;
      if (b.type === 'item') return <p key={i} className="ml-4 text-xs leading-relaxed text-slate-400">{b.text}</p>;
      if (b.type === 'signature') return <p key={i} className="mt-3 text-xs italic text-slate-500">[Signature block]</p>;
      return <p key={i} className="text-xs leading-relaxed text-slate-400">{b.text}</p>;
    })}
  </>
);

const Centered = ({ icon: Icon, color, title, children }) => (
  <div className="flex min-h-screen items-center justify-center bg-ink px-6">
    <div className="max-w-md rounded-2xl border border-white/10 bg-white/[0.02] p-10 text-center">
      {Icon && <Icon size={48} className={`mx-auto ${color}`} />}
      <h2 className="mt-5 font-heading text-2xl font-semibold text-white">{title}</h2>
      {children && <div className="mt-3 text-sm leading-relaxed text-slate-400">{children}</div>}
    </div>
  </div>
);

const CosignPage = () => {
  const { token } = useParams();
  const [loading, setLoading] = useState(true);
  const [fatal, setFatal] = useState(null);      // {kind, message, date}
  const [data, setData] = useState(null);
  const [docBlocks, setDocBlocks] = useState([]);
  const [docHash, setDocHash] = useState('');
  const [showAgreement, setShowAgreement] = useState(false);

  const [entityType, setEntityType] = useState('individual');
  const [legalName, setLegalName] = useState('');
  const [signerName, setSignerName] = useState('');
  const [signerTitle, setSignerTitle] = useState('');
  const [adult, setAdult] = useState(false);
  const [agree, setAgree] = useState(false);
  const [typed, setTyped] = useState('');

  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState('');
  const [result, setResult] = useState(null);    // 'signed' | 'declined'
  const [declineOpen, setDeclineOpen] = useState(false);
  const [declineReason, setDeclineReason] = useState('');

  // Load the request and the rendered documents.
  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const { data: d } = await axios.get(`${API}/cosign/${token}`);
        if (!active) return;
        setData(d);
        setDocBlocks(d.consent_blocks);
        setDocHash(d.text_sha256);
        setLegalName((d.interests?.[0]?.legal_name) || '');
        setLoading(false);
      } catch (err) {
        if (!active) return;
        const status = err.response?.status;
        if (status === 409) {
          const det = err.response?.data?.detail || {};
          setFatal({ kind: det.status || 'used', date: det.date });
        } else {
          setFatal({ kind: 'invalid', message: detailMessage(err, 'This link is not valid.') });
        }
        setLoading(false);
      }
    })();
    return () => { active = false; };
  }, [token]);

  // Re-render the document (new hash) whenever the signer's name or entity changes, so
  // the signer always signs exactly the text shown. Debounced.
  const previewTimer = useRef(null);
  const refreshPreview = useCallback(() => {
    if (!data) return;
    clearTimeout(previewTimer.current);
    previewTimer.current = setTimeout(async () => {
      try {
        const { data: p } = await axios.post(`${API}/cosign/${token}/preview`, {
          entity_type: entityType,
          legal_name: legalName,
          signer_name: entityType === 'company' ? signerName : null,
          signer_title: entityType === 'company' ? signerTitle : null,
        });
        setDocBlocks(p.consent_blocks);
        setDocHash(p.text_sha256);
      } catch { /* keep the previous hash; sign will surface any mismatch */ }
    }, 400);
  }, [data, token, entityType, legalName, signerName, signerTitle]);

  useEffect(() => { refreshPreview(); return () => clearTimeout(previewTimer.current); }, [refreshPreview]);

  const expectedSignature = entityType === 'company' ? signerName : legalName;
  const canSign = adult && agree && typed.trim() && expectedSignature.trim()
    && (entityType === 'individual' || (signerName.trim() && signerTitle.trim()))
    && !submitting;

  const sign = async () => {
    setSubmitting(true);
    setFormError('');
    try {
      await axios.post(`${API}/cosign/${token}/sign`, {
        entity_type: entityType,
        legal_name: legalName.trim(),
        signer_name: entityType === 'company' ? signerName.trim() : null,
        signer_title: entityType === 'company' ? signerTitle.trim() : null,
        typed_signature: typed.trim(),
        adult_confirmed: adult,
        text_sha256: docHash,
      });
      setResult('signed');
    } catch (err) {
      const status = err.response?.status;
      if (status === 409 && typeof err.response?.data?.detail === 'object') {
        setFatal({ kind: err.response.data.detail.status || 'used', date: err.response.data.detail.date });
      } else {
        setFormError(detailMessage(err, 'Could not sign. Please try again.'));
      }
    } finally {
      setSubmitting(false);
    }
  };

  const decline = async () => {
    setSubmitting(true);
    setFormError('');
    try {
      await axios.post(`${API}/cosign/${token}/decline`, { reason: declineReason.trim() || null });
      setResult('declined');
    } catch (err) {
      setFormError(detailMessage(err, 'Could not record your response. Please try again.'));
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-ink">
        <Loader2 size={28} className="animate-spin text-electric" />
      </div>
    );
  }

  if (fatal) {
    if (fatal.kind === 'signed') {
      return <Centered icon={CheckCircle2} color="text-cyan" title="Already signed">
        This consent was signed{fatal.date ? ` on ${fmtDate(fatal.date)}` : ''}.</Centered>;
    }
    if (fatal.kind === 'declined') {
      return <Centered icon={AlertCircle} color="text-amber-400" title="Already declined">
        This consent was declined{fatal.date ? ` on ${fmtDate(fatal.date)}` : ''}.</Centered>;
    }
    return <Centered icon={AlertCircle} color="text-red-400" title="Link not valid">
      {fatal.message || 'This link has expired or is not valid. Ask the artist to resend it.'}</Centered>;
  }

  if (result === 'signed') {
    return <Centered icon={CheckCircle2} color="text-cyan" title="Signed">
      A copy is on its way to your email. We'll keep an OVOXI Wallet for your share. Create an account with this
      email to see it and get paid.</Centered>;
  }
  if (result === 'declined') {
    return <Centered icon={AlertCircle} color="text-amber-400" title="Response recorded">
      You declined to sign. The artist has been notified.</Centered>;
  }

  return (
    <div className="min-h-screen bg-ink px-6 py-16">
      <div className="mx-auto max-w-2xl space-y-6">
        <header>
          <p className="text-xs uppercase tracking-[0.18em] text-electric">Co-owner Consent</p>
          <h1 className="mt-1 font-heading text-3xl font-semibold text-white">Sign as a rights holder</h1>
        </header>

        {/* Song card */}
        <div className="rounded-2xl border border-white/10 bg-white/[0.02] p-6">
          <p className="font-heading text-lg font-semibold text-white">{data.track_title}</p>
          <p className="mt-1 text-sm text-slate-400">Uploaded by {data.uploader_name}</p>
          <ul className="mt-3 space-y-1 text-sm text-slate-300">
            {(data.interests || []).map((it, i) => (
              <li key={i}>
                {SIDE_LABEL[it.side] || it.side}{it.role ? '' : ''}, {fmtPct(it.share_bp)}%
              </li>
            ))}
          </ul>
          {data.uses?.length > 0 && (
            <p className="mt-3 text-xs text-slate-500">Uses: {data.uses.join(', ')}</p>
          )}
        </div>

        {/* Plain-English summary */}
        <ul className="list-disc space-y-1.5 rounded-2xl border border-white/10 bg-white/[0.02] p-6 pl-10 text-sm text-slate-300 marker:text-slate-600">
          <li>You keep ownership of your share. You're letting OVOXI license this song for the uses above.</li>
          <li>You're paid your share of OVOXI's revenue share for this song, as set out in the documents below.</li>
          <li>You can end this after 12 months with 60 days' notice.</li>
        </ul>

        {/* Documents */}
        <div className="rounded-2xl border border-white/10 bg-white/[0.02] p-6">
          <div className="max-h-80 overflow-y-auto rounded-lg border border-white/10 bg-ink p-4">
            <DocBlocks blocks={docBlocks} />
          </div>
          <button
            type="button"
            onClick={() => setShowAgreement((s) => !s)}
            className="mt-4 text-sm text-cyan hover:underline"
          >
            {showAgreement ? 'Hide' : 'Show'} the Artist Agreement (incorporated by reference)
          </button>
          {showAgreement && (
            <div className="mt-3 max-h-80 overflow-y-auto rounded-lg border border-white/10 bg-ink p-4">
              <DocBlocks blocks={data.agreement_blocks} />
            </div>
          )}
          <p className="mt-4 text-xs text-slate-500">
            See our <Link to="/privacy" className="text-cyan hover:underline">Privacy Policy</Link>.
          </p>
        </div>

        {/* Form */}
        {!declineOpen ? (
          <div className="space-y-5 rounded-2xl border border-white/10 bg-white/[0.02] p-6">
            <div className="space-y-2">
              <Label className="text-slate-300">Are you signing as an individual or a company?</Label>
              <div className="inline-flex rounded-full border border-white/10 p-1">
                {[['individual', 'Individual'], ['company', 'Company']].map(([v, l]) => (
                  <button
                    key={v}
                    type="button"
                    aria-pressed={entityType === v}
                    onClick={() => setEntityType(v)}
                    className={`rounded-full px-5 py-1.5 text-sm transition-colors ${
                      entityType === v ? 'bg-gradient-brand text-white' : 'text-slate-300 hover:text-white'}`}
                  >
                    {l}
                  </button>
                ))}
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="cosign-legal-name" className="text-slate-300">
                {entityType === 'company' ? 'Company legal name' : 'Your legal name'}
              </Label>
              <Input id="cosign-legal-name" value={legalName} maxLength={120}
                onChange={(e) => setLegalName(e.target.value)} className={FIELD_CLASS} />
            </div>

            {entityType === 'company' && (
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="cosign-signer-name" className="text-slate-300">Signer name</Label>
                  <Input id="cosign-signer-name" value={signerName} maxLength={120}
                    onChange={(e) => setSignerName(e.target.value)} className={FIELD_CLASS} />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="cosign-signer-title" className="text-slate-300">Signer title</Label>
                  <Input id="cosign-signer-title" value={signerTitle} maxLength={120}
                    onChange={(e) => setSignerTitle(e.target.value)} className={FIELD_CLASS} />
                </div>
              </div>
            )}

            <label htmlFor="cosign-adult" className="flex cursor-pointer items-start gap-3 text-sm text-slate-300">
              <Checkbox id="cosign-adult" checked={adult} onCheckedChange={(v) => setAdult(v === true)} className={CHECKBOX_CLASS} />
              I am 18 or older.
            </label>
            <label htmlFor="cosign-agree" className="flex cursor-pointer items-start gap-3 text-sm text-slate-300">
              <Checkbox id="cosign-agree" checked={agree} onCheckedChange={(v) => setAgree(v === true)} className={CHECKBOX_CLASS} />
              I have read and agree to the Co-owner Consent and the Artist Agreement terms it incorporates.
            </label>

            <div className="space-y-2">
              <Label htmlFor="cosign-typed" className="text-slate-300">
                Type your full name to sign{expectedSignature.trim() ? ` (${expectedSignature.trim()})` : ''}
              </Label>
              <Input id="cosign-typed" value={typed} maxLength={120}
                onChange={(e) => setTyped(e.target.value)} placeholder="Type your full name" className={FIELD_CLASS} />
            </div>

            <div aria-live="polite">
              {formError && <p className="text-sm text-red-400">{formError}</p>}
            </div>

            <div className="flex flex-wrap items-center gap-4">
              <button
                type="button"
                onClick={sign}
                disabled={!canSign}
                className="inline-flex items-center justify-center gap-2 rounded-full bg-gradient-brand px-7 py-3 text-sm font-semibold text-white transition-all duration-300 hover:shadow-[0_0_28px_rgba(194,24,91,0.55)] disabled:cursor-not-allowed disabled:opacity-60"
              >
                {submitting ? <Loader2 size={16} className="animate-spin" /> : null}
                Sign
              </button>
              <button type="button" onClick={() => setDeclineOpen(true)} className="text-sm text-slate-400 hover:text-white">
                I don't agree / this isn't mine
              </button>
            </div>
          </div>
        ) : (
          <div className="space-y-4 rounded-2xl border border-white/10 bg-white/[0.02] p-6">
            <Label htmlFor="cosign-decline" className="text-slate-300">Decline to sign (optional reason)</Label>
            <Input id="cosign-decline" value={declineReason} maxLength={500}
              onChange={(e) => setDeclineReason(e.target.value)} placeholder="Reason (optional)" className={FIELD_CLASS} />
            <div aria-live="polite">
              {formError && <p className="text-sm text-red-400">{formError}</p>}
            </div>
            <div className="flex flex-wrap items-center gap-4">
              <button type="button" onClick={decline} disabled={submitting}
                className="inline-flex items-center gap-2 rounded-full border border-red-400/40 px-6 py-2.5 text-sm text-red-300 hover:bg-red-400/10 disabled:opacity-60">
                {submitting ? <Loader2 size={16} className="animate-spin" /> : null}
                Decline
              </button>
              <button type="button" onClick={() => setDeclineOpen(false)} className="text-sm text-slate-400 hover:text-white">
                Back
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default CosignPage;
