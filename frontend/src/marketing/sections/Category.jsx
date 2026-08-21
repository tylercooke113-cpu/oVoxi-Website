import { Reveal } from '../components/Reveal';

export default function Category() {
  return (
    <section className="py-24 md:py-40 border-t border-ovx-line">
      <div className="max-w-[1440px] mx-auto px-6 md:px-[120px]">
        <div className="max-w-4xl">
          <Reveal delay={0}>
            <p
              className="font-display font-extrabold text-white leading-[0.95] tracking-[-0.02em]"
              style={{ fontSize: 'var(--fs-h1)' }}
            >
              Epidemic proved curation scales.<br />
              The majors proved AI pays.<br />
              oVoxi is the first catalog built for both.
            </p>
          </Reveal>
        </div>
      </div>
    </section>
  );
}
