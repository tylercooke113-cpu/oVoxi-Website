import { Reveal } from '../components/Reveal';

const stats = [
  { value: '$500M',  label: 'RIAA suits against Suno and Udio, 2024' },
  { value: '2 of 3', label: 'majors now license AI platforms' },
  { value: '$0.005', label: 'per generation, the settlement template' },
  { value: '0',      label: 'independent artist seats at that table' },
];

export default function Reckoning() {
  return (
    <section className="py-24 md:py-40 border-t border-ovx-line">
      <div className="max-w-[1440px] mx-auto px-6 md:px-[120px]">
        <Reveal delay={0}>
          <p className="font-jetmono text-[13px] uppercase tracking-[0.12em] bg-ovx-gradient bg-clip-text text-transparent mb-16">
            What already happened
          </p>
        </Reveal>
        <div className="divide-y divide-ovx-line">
          {stats.map(({ value, label }, i) => (
            <Reveal key={value} delay={i * 0.08} className="flex flex-col sm:flex-row sm:items-baseline gap-3 sm:gap-16 py-10 first:pt-0 last:pb-0">
              <span
                className="font-jetmono text-white shrink-0 sm:w-56"
                style={{ fontSize: 'var(--fs-data)' }}
              >
                {value}
              </span>
              <span className="font-body text-ovx-dim" style={{ fontSize: 'var(--fs-lead)' }}>
                {label}
              </span>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
}
