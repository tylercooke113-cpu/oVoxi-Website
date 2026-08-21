import { Reveal } from '../components/Reveal';

export default function Gate() {
  return (
    <section className="relative min-h-screen flex flex-col items-center justify-center py-24 md:py-40 border-t border-ovx-line overflow-hidden">
      {/* Static gate plane: vertical cyan line, replaced by WebGL in Phase 6 */}
      <div
        aria-hidden="true"
        className="absolute inset-y-0 left-1/2 -translate-x-px w-px pointer-events-none"
        style={{
          background: 'linear-gradient(to bottom, transparent 0%, #4FC3F7 15%, #4FC3F7 85%, transparent 100%)',
          opacity: 0.4,
        }}
      />
      <div className="relative max-w-[1440px] mx-auto px-6 md:px-[120px] w-full text-center">
        <Reveal delay={0}>
          <p
            className="font-display font-extrabold text-white leading-[0.95] tracking-[-0.02em] mb-16"
            style={{ fontSize: 'var(--fs-h1)' }}
          >
            Every track passes<br />through the gate.
          </p>
        </Reveal>
        <Reveal delay={0.12}>
          <p className="font-jetmono text-[13px] uppercase tracking-[0.12em] text-ovx-faint">
            Cleared&nbsp;&nbsp;&#183;&nbsp;&nbsp;Needs Docs&nbsp;&nbsp;&#183;&nbsp;&nbsp;Conflict
          </p>
        </Reveal>
      </div>
    </section>
  );
}
