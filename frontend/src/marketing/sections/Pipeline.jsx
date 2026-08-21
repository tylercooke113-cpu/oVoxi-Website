const steps = [
  { num: '01', label: 'Upload' },
  { num: '02', label: 'Gate' },
  { num: '03', label: 'Verify' },
  { num: '04', label: 'Enhance' },
  { num: '05', label: 'Catalog' },
];

export default function Pipeline() {
  return (
    <section className="py-24 md:py-40 border-t border-ovx-line">
      <div className="max-w-[1440px] mx-auto px-6 md:px-[120px]">
        <p className="font-jetmono text-[13px] uppercase tracking-[0.12em] bg-ovx-gradient bg-clip-text text-transparent mb-16">
          The pipeline
        </p>

        {/* Desktop: horizontal dots + hairlines above labels */}
        <div className="hidden md:block">
          <div className="grid grid-cols-5 mb-5">
            {steps.map((step, i) => (
              <div key={step.num} className="relative flex justify-center">
                {/* Left hairline (not on first) */}
                {i > 0 && (
                  <div className="absolute right-1/2 left-0 top-[3px] h-px bg-ovx-line" />
                )}
                {/* Right hairline (not on last) */}
                {i < steps.length - 1 && (
                  <div className="absolute left-1/2 right-0 top-[3px] h-px bg-ovx-line" />
                )}
                {/* Gradient dot */}
                <div
                  className="relative z-10 w-2 h-2 rounded-full shrink-0"
                  style={{ background: 'linear-gradient(135deg, #B44FD4 0%, #7B5EA7 50%, #6B7FD4 100%)' }}
                />
              </div>
            ))}
          </div>
          <div className="grid grid-cols-5">
            {steps.map((step) => (
              <div key={step.num} className="px-2 first:pl-0 last:pr-0">
                <span className="font-jetmono text-ovx-dim text-[13px] uppercase tracking-[0.12em] block">
                  {step.num}
                </span>
                <span className="font-body text-white text-base mt-1 block">
                  {step.label}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Mobile: vertical */}
        <div className="flex md:hidden flex-col">
          {steps.map((step, i) => (
            <div key={step.num} className="flex items-start gap-6">
              <div className="flex flex-col items-center shrink-0">
                <div
                  className="w-2 h-2 rounded-full mt-1"
                  style={{ background: 'linear-gradient(135deg, #B44FD4 0%, #7B5EA7 50%, #6B7FD4 100%)' }}
                />
                {i < steps.length - 1 && (
                  <div className="w-px flex-1 bg-ovx-line mt-2" style={{ minHeight: '44px' }} />
                )}
              </div>
              <div className="pb-10">
                <span className="font-jetmono text-ovx-dim text-[13px] uppercase tracking-[0.12em] block">
                  {step.num}
                </span>
                <span className="font-body text-white text-base mt-1 block">
                  {step.label}
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
