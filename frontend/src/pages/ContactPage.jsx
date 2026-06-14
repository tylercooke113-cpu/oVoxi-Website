import React, { useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import axios from 'axios';
import { toast } from 'sonner';
import { Mail, Loader2, CheckCircle2 } from 'lucide-react';
import { PageHero } from '../components/PageHero';
import { Reveal } from '../components/Reveal';
import { Input } from '../components/ui/input';
import { Textarea } from '../components/ui/textarea';
import { Label } from '../components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../components/ui/select';
import { BRAND, INTEREST_OPTIONS } from '../content';

const API = `https://ovoxi-website-production.up.railway.app/api`;
const VALID = INTEREST_OPTIONS.map((o) => o.value);

const ContactPage = () => {
  const [params] = useSearchParams();
  const initialInterest = VALID.includes(params.get('interest')) ? params.get('interest') : '';

  const [form, setForm] = useState({
    name: '',
    email: '',
    company: '',
    interest: initialInterest,
    message: '',
  });
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState(false);

  const update = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }));

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!form.name || !form.email || !form.interest || !form.message) {
      toast.error('Please fill in all required fields.');
      return;
    }
    setSubmitting(true);
    try {
      await axios.post(`${API}/contact`, {
        name: form.name,
        email: form.email,
        company: form.company || null,
        interest: form.interest,
        message: form.message,
      });
      setDone(true);
      toast.success("Thanks — we've received your inquiry.");
    } catch (err) {
      toast.error('Something went wrong. Please try again or email us directly.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div data-testid="contact-page">
      <PageHero
        testid="contact-hero"
        label="Contact"
        title="Let's Build the Catalog Together"
        subtitle="Whether you're an AI platform, an enterprise buyer, an emerging artist, or an investor — tell us how you'd like to work with oVoxi."
      />

      <section className="bg-ink py-20 lg:py-28">
        <div className="mx-auto grid max-w-7xl grid-cols-1 gap-12 px-6 lg:grid-cols-5 lg:gap-16 lg:px-8">
          <Reveal className="lg:col-span-2">
            <h2 className="font-heading text-2xl font-semibold text-white">Reach out directly</h2>
            <p className="mt-4 text-base leading-relaxed text-slate-400">
              Prefer email? We typically respond within two business days.
            </p>
            <a
              href={`mailto:${BRAND.email}`}
              data-testid="contact-email-link"
              className="mt-6 inline-flex items-center gap-3 rounded-2xl border border-white/10 bg-white/[0.02] px-5 py-4 text-base text-white transition-all hover:border-electric/40"
            >
              <Mail size={18} className="text-cyan" />
              {BRAND.email}
            </a>
            <div className="mt-10 space-y-2 text-sm text-slate-500">
              <p>oVoxi · {BRAND.domain}</p>
            </div>
          </Reveal>

          <Reveal delay={0.12} className="lg:col-span-3">
            {done ? (
              <div
                data-testid="contact-success"
                className="flex h-full flex-col items-center justify-center rounded-2xl border border-electric/30 bg-white/[0.02] p-12 text-center"
              >
                <CheckCircle2 size={48} className="text-cyan" />
                <h3 className="mt-5 font-heading text-2xl font-semibold text-white">Inquiry received</h3>
                <p className="mt-3 max-w-md text-base text-slate-400">
                  Thanks, {form.name.split(' ')[0] || 'there'}. Our team will review your message and
                  follow up at ovoxi.ai@gmail.com.
                </p>
              </div>
            ) : (
              <form
                data-testid="contact-form"
                onSubmit={handleSubmit}
                className="rounded-2xl border border-white/10 bg-white/[0.02] p-8 md:p-10"
              >
                <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
                  <div className="space-y-2">
                    <Label htmlFor="name" className="text-slate-300">Name *</Label>
                    <Input
                      id="name"
                      data-testid="contact-name-input"
                      value={form.name}
                      onChange={update('name')}
                      placeholder="Your full name"
                      className="border-white/10 bg-ink text-white placeholder:text-slate-600 focus-visible:ring-electric"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="email" className="text-slate-300">Email *</Label>
                    <Input
                      id="email"
                      type="email"
                      data-testid="contact-email-input"
                      value={form.email}
                      onChange={update('email')}
                      placeholder="you@company.com"
                      className="border-white/10 bg-ink text-white placeholder:text-slate-600 focus-visible:ring-electric"
                    />
                  </div>
                </div>

                <div className="mt-6 grid grid-cols-1 gap-6 sm:grid-cols-2">
                  <div className="space-y-2">
                    <Label htmlFor="company" className="text-slate-300">Company</Label>
                    <Input
                      id="company"
                      data-testid="contact-company-input"
                      value={form.company}
                      onChange={update('company')}
                      placeholder="Company / project (optional)"
                      className="border-white/10 bg-ink text-white placeholder:text-slate-600 focus-visible:ring-electric"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label className="text-slate-300">I am a... *</Label>
                    <Select
                      value={form.interest}
                      onValueChange={(v) => setForm((f) => ({ ...f, interest: v }))}
                    >
                      <SelectTrigger
                        data-testid="contact-interest-select"
                        className="border-white/10 bg-ink text-white focus:ring-electric"
                      >
                        <SelectValue placeholder="Select one" />
                      </SelectTrigger>
                      <SelectContent className="border-white/10 bg-ink-2 text-white">
                        {INTEREST_OPTIONS.map((o) => (
                          <SelectItem key={o.value} value={o.value} data-testid={`interest-option-${o.value}`}>
                            {o.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                </div>

                <div className="mt-6 space-y-2">
                  <Label htmlFor="message" className="text-slate-300">Message *</Label>
                  <Textarea
                    id="message"
                    data-testid="contact-message-input"
                    value={form.message}
                    onChange={update('message')}
                    rows={5}
                    placeholder="Tell us about your catalog, licensing needs, or investment interest."
                    className="border-white/10 bg-ink text-white placeholder:text-slate-600 focus-visible:ring-electric"
                  />
                </div>

                <button
                  type="submit"
                  data-testid="contact-submit-button"
                  disabled={submitting}
                  className="mt-8 inline-flex w-full items-center justify-center gap-2 rounded-full bg-electric px-7 py-3.5 text-sm font-semibold text-white transition-all duration-300 hover:shadow-[0_0_28px_rgba(0,102,255,0.55)] disabled:opacity-60 sm:w-auto"
                >
                  {submitting && <Loader2 size={16} className="animate-spin" />}
                  {submitting ? 'Sending...' : 'Send Inquiry'}
                </button>
              </form>
            )}
          </Reveal>
        </div>
      </section>
    </div>
  );
};

export default ContactPage;
