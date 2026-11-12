import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import axios from 'axios';
import { ButtonLink } from '../landing/parts';
import { LINKS } from '../landing/links';
import { BRAND } from '../content';

// /artists: the OVOXI session network (Plan 29 copy draft v2, section 3; Brief 32).
// Copy rules: no studio names, no sample pack, no artist pay or percentages,
// no prices or reply times. Applications go to the existing contact endpoint
// with interest "network" until Brief 33 adds structured storage and alerts.
const API = 'https://ovoxi-website-production.up.railway.app/api';
const WRAP = 'mx-auto max-w-[1240px] px-6';
const FIELD = 'w-full rounded-xl border border-[#3F3F46] bg-[#0B0B0E] px-3.5 py-3 text-base font-normal text-[#F4F4F6] placeholder:text-[#8B8B94] focus:outline-none focus-visible:ring-2 focus-visible:ring-cyan';
const LABEL = 'flex flex-col gap-2 text-[15px] font-medium';
const REQ = <span className="font-normal text-[#A1A1AA]"> (required)</span>;

export const ROLES = ['Artist', 'Producer', 'Songwriter', 'Session musician', 'Vocalist', 'Engineer'];
export const GENRES = ['Hip-hop', 'R&B', 'Pop', 'Rock', 'Electronic', 'Latin', 'Afrobeats', 'Country', 'Jazz', 'Classical', 'Reggaeton', 'Gospel'];
const AVAILABILITY = ['Weekdays', 'Weekends', 'Flexible'];

const STEPS = [
  ['Apply', 'Tell us what you play, write or produce, and where you are.'],
  ['Get matched', 'When a commission fits your sound, we reach out with the details.'],
  ['Record the session', 'Commercial studio, clear brief, one standard protocol.'],
  ['Sign in the room', 'Everyone on the track signs before the files leave the session.'],
];

const FAQ = [
  ['Does it cost anything to apply?', 'No.'],
  ['Do I need a PRO?', 'No. Add it if you have one.'],
  ['Where do sessions happen?', 'At commercial studios. We share the location when we match you.'],
  ['What are the terms?', 'Everything is set out in the agreement you sign before you record.'],
  ['I already have songs. Can I license them?', 'Yes. Sign in to your Vault and upload them. You keep ownership, streaming, sales and your PRO royalties. AI training for those songs is licensed only through OVOXI. Sync stays non-exclusive.'],
];

const EMPTY = {
  name: '', email: '', roles: [], genres: [], otherGenres: '', instruments: '',
  languages: '', city: '', links: '', pro: '', availability: '', website: '',
};

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

// The application as a labeled text message for the contact endpoint (max 4000 chars).
export function buildMessage(f) {
  const genres = [...f.genres, ...(f.otherGenres.trim() ? [`other: ${f.otherGenres.trim()}`] : [])];
  const lines = [
    'OVOXI network application',
    `Roles: ${f.roles.join(', ')}`,
    `Genres: ${genres.join(', ')}`,
    `Instruments: ${f.instruments.trim() || 'not given'}`,
    `Languages: ${f.languages.trim() || 'not given'}`,
    `City: ${f.city.trim()}`,
    `Links: ${f.links.trim() || 'not given'}`,
    `PRO and IPI: ${f.pro.trim() || 'not given'}`,
    `Availability: ${f.availability || 'not given'}`,
  ];
  return lines.join('\n').slice(0, 4000);
}

export function validate(f) {
  if (!f.name.trim() || !f.email.trim() || f.roles.length === 0
    || (f.genres.length === 0 && !f.otherGenres.trim()) || !f.city.trim()) {
    return 'Please fill in the fields marked required.';
  }
  if (!EMAIL_RE.test(f.email.trim())) return 'Please enter a valid email.';
  return '';
}

const Chip = ({ checked, onChange, label, type = 'checkbox', name }) => (
  <label className={`inline-flex min-h-[44px] cursor-pointer items-center gap-2.5 rounded-full border px-4 text-[15px] font-normal transition-colors ${checked ? 'border-[#B44FD4] bg-[#B44FD4]/10 text-white' : 'border-[#3F3F46] text-[#D4D4D8]'}`}>
    <input type={type} name={name} checked={checked} onChange={onChange} className="h-[18px] w-[18px] accent-[#8E44CC]" />
    {label}
  </label>
);

const ArtistsPage = () => {
  const [form, setForm] = useState(EMPTY);
  const [status, setStatus] = useState('idle'); // idle | sending | done
  const [error, setError] = useState('');

  const set = (key) => (e) => { setError(''); setForm((f) => ({ ...f, [key]: e.target.value })); };
  const toggle = (key, value) => () => {
    setError('');
    setForm((f) => ({ ...f, [key]: f[key].includes(value) ? f[key].filter((v) => v !== value) : [...f[key], value] }));
  };

  const submit = async (e) => {
    e.preventDefault();
    const problem = validate(form);
    if (problem) { setError(problem); return; }
    setStatus('sending');
    try {
      await axios.post(`${API}/contact`, {
        name: form.name.trim(),
        email: form.email.trim(),
        company: null,
        interest: 'network',
        message: buildMessage(form),
        website: form.website,
      });
      setStatus('done');
    } catch (err) {
      setStatus('idle');
      setError(`Something went wrong and your application wasn't sent. Please try again, or email ${BRAND.email}.`);
    }
  };

  const firstName = form.name.trim().split(' ')[0] || 'there';

  return (
    <div data-testid="artists-page" className="bg-ink pt-16 font-light text-[#F4F4F6]">
      {/* Hero */}
      <section className={`${WRAP} flex flex-col gap-7 pb-24 pt-20 sm:pt-24`}>
        <p className="m-0 text-sm font-medium uppercase tracking-[0.14em] text-[#C78BE0]">For artists, producers and session players</p>
        <h1 className="m-0 max-w-[14ch] font-heading text-[44px] font-extrabold leading-[0.98] sm:text-[72px] lg:text-[96px]">
          Record music for AI labs.
        </h1>
        <div className="flex flex-wrap items-end justify-between gap-8">
          <p className="m-0 max-w-[48ch] text-lg leading-relaxed text-[#A1A1AA] sm:text-[21px]">
            AI labs come to OVOXI for music that doesn&apos;t exist yet. We book artists, producers, writers, session
            players and vocalists to make it, in sessions at commercial studios.
          </p>
          <div className="flex flex-wrap gap-3">
            <a href="#apply" data-testid="artists-apply" className="inline-flex items-center rounded-full bg-[#8E44CC] px-7 py-4 text-base font-bold text-white transition-colors hover:bg-[#7D3AB6]">Apply to the network</a>
            <a href="#how" data-testid="artists-how" className="inline-flex items-center rounded-full border border-[#3F3F46] px-7 py-4 text-base font-bold text-[#F4F4F6] hover:bg-white/10">How it works</a>
          </div>
        </div>
      </section>

      {/* How it works */}
      <section id="how" className="scroll-mt-20 border-t border-[#1F1F23]">
        <ol className={`${WRAP} m-0 grid list-none grid-cols-1 gap-10 py-24 sm:grid-cols-2 lg:grid-cols-4 lg:gap-0`}>
          {STEPS.map(([title, text], i) => (
            <li key={title} className={`flex flex-col gap-3 lg:px-6 ${i === 0 ? 'lg:pl-0' : ''} ${i < STEPS.length - 1 ? 'lg:border-r lg:border-[#1F1F23]' : 'lg:pr-0'}`}>
              <span className="font-heading text-[56px] font-extrabold leading-none text-[#52525B]">{i + 1}</span>
              <h2 className="m-0 font-heading text-2xl font-bold">{title}</h2>
              <p className="m-0 text-base leading-relaxed text-[#A1A1AA]">{text}</p>
            </li>
          ))}
        </ol>
      </section>

      {/* Application */}
      <section id="apply" className="scroll-mt-20 border-t border-[#1F1F23] bg-[#0B0B0E]">
        <div className="mx-auto flex max-w-[880px] flex-col gap-10 px-6 py-24">
          <div className="flex flex-col gap-4">
            <p className="m-0 text-[13px] font-medium uppercase tracking-[0.12em] text-cyan">Apply</p>
            <h2 className="m-0 font-heading text-[36px] font-extrabold leading-tight sm:text-[48px]">Join the OVOXI network.</h2>
          </div>

          {status === 'done' ? (
            <div data-testid="artists-apply-success" role="status" className="flex flex-col gap-3 rounded-[20px] border border-[#27272A] bg-[#111114] p-10">
              <h3 className="m-0 text-2xl font-bold">Application received</h3>
              <p className="m-0 text-lg text-[#A1A1AA]">Thanks, {firstName}. We&apos;ll reach out if a session fits your sound.</p>
            </div>
          ) : (
            <form data-testid="artists-apply-form" noValidate onSubmit={submit} className="flex flex-col gap-8">
              <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
                <label className={LABEL}><span>Your name{REQ}</span>
                  <input className={FIELD} type="text" name="name" maxLength={120} placeholder="Legal name or artist name" value={form.name} onChange={set('name')} />
                </label>
                <label className={LABEL}><span>Email{REQ}</span>
                  <input className={FIELD} type="email" name="email" maxLength={254} value={form.email} onChange={set('email')} />
                </label>
              </div>

              <fieldset className="m-0 flex flex-col gap-3 border-0 p-0">
                <legend className="mb-3 text-[15px] font-medium">What do you do?{REQ}</legend>
                <div className="flex flex-wrap gap-2.5">
                  {ROLES.map((r) => <Chip key={r} label={r} checked={form.roles.includes(r)} onChange={toggle('roles', r)} />)}
                </div>
              </fieldset>

              <fieldset className="m-0 flex flex-col gap-3 border-0 p-0">
                <legend className="mb-3 text-[15px] font-medium">Genres{REQ}</legend>
                <div className="flex flex-wrap gap-2.5">
                  {GENRES.map((g) => <Chip key={g} label={g} checked={form.genres.includes(g)} onChange={toggle('genres', g)} />)}
                </div>
                <input className={FIELD} type="text" aria-label="Other genres" maxLength={200} placeholder="Add any genre we don't list" value={form.otherGenres} onChange={set('otherGenres')} />
              </fieldset>

              <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
                <label className={LABEL}>Instruments
                  <input className={FIELD} type="text" maxLength={300} value={form.instruments} onChange={set('instruments')} />
                </label>
                <label className={LABEL}>Languages you sing or write in
                  <input className={FIELD} type="text" maxLength={200} value={form.languages} onChange={set('languages')} />
                </label>
                <label className={LABEL}><span>City{REQ}</span>
                  <input className={FIELD} type="text" maxLength={120} value={form.city} onChange={set('city')} />
                </label>
                <label className={LABEL}>PRO and IPI
                  <input className={FIELD} type="text" maxLength={200} placeholder="Add them if you have them" value={form.pro} onChange={set('pro')} />
                </label>
              </div>

              <label className={LABEL}>Links
                <input className={FIELD} type="text" maxLength={600} placeholder="Spotify, Instagram, SoundCloud, portfolio" value={form.links} onChange={set('links')} />
              </label>

              <fieldset className="m-0 flex flex-col gap-3 border-0 p-0">
                <legend className="mb-3 text-[15px] font-medium">Availability</legend>
                <div className="flex flex-wrap gap-2.5">
                  {AVAILABILITY.map((a) => (
                    <Chip key={a} type="radio" name="availability" label={a} checked={form.availability === a}
                      onChange={() => { setError(''); setForm((f) => ({ ...f, availability: a })); }} />
                  ))}
                </div>
              </fieldset>

              {/* Honeypot: real people never see or fill this. */}
              <input type="text" name="website" tabIndex={-1} autoComplete="off" aria-hidden="true"
                className="absolute -left-[9999px] h-px w-px opacity-0" value={form.website} onChange={set('website')} />

              {error && <p data-testid="artists-apply-error" role="alert" className="m-0 text-[15px] font-normal text-[#FCA5A5]">{error}</p>}

              <div className="flex flex-col gap-4">
                <div>
                  <button type="submit" disabled={status === 'sending'} data-testid="artists-apply-submit"
                    className="min-h-[56px] rounded-full bg-[#8E44CC] px-8 text-[17px] font-bold text-white transition-colors hover:bg-[#7D3AB6] focus:outline-none focus-visible:ring-2 focus-visible:ring-cyan">
                    {status === 'sending' ? 'Sending...' : 'Apply'}
                  </button>
                </div>
                <p className="m-0 text-sm text-[#A1A1AA]">
                  See our <Link to="/privacy" className="text-cyan hover:underline">Privacy Policy</Link> for how we handle your details.
                </p>
              </div>
            </form>
          )}
        </div>
      </section>

      {/* FAQ */}
      <section id="faq" className="mx-auto flex max-w-[880px] flex-col px-6 py-24">
        <h2 className="m-0 mb-4 font-heading text-[36px] font-extrabold sm:text-[40px]">Straight answers</h2>
        {FAQ.map(([q, a], i) => (
          <details key={q} className={`border-t border-[#27272A] py-5 ${i === FAQ.length - 1 ? 'border-b' : ''}`}>
            <summary className="cursor-pointer text-[19px] font-bold">{q}</summary>
            <p className="m-0 mt-3 text-base leading-relaxed text-[#A1A1AA]">{a}</p>
          </details>
        ))}
      </section>

      {/* Already signed */}
      <section className="border-t border-[#1F1F23]">
        <div className={`${WRAP} flex flex-wrap items-center justify-between gap-4 py-12`}>
          <p className="m-0 text-[19px] font-normal text-[#D4D4D8]">Already signed with OVOXI?</p>
          <span className="flex flex-wrap items-center gap-4">
            <ButtonLink to={LINKS.signIn} kind="ghost" testid="artists-signin">Sign in to your Vault</ButtonLink>
            <Link to={LINKS.join} data-testid="artists-signup" className="font-bold text-cyan hover:underline">Create an account</Link>
          </span>
        </div>
      </section>
    </div>
  );
};

export default ArtistsPage;
