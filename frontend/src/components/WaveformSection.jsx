import React, { useRef, useEffect } from 'react';

const WAVES = [
  { color: '#C2185B', opacity: 0.65, freq: 0.018, speed: 0.032 },
  { color: '#6A1B9A', opacity: 0.53, freq: 0.022, speed: 0.024 },
  { color: '#1565C0', opacity: 0.41, freq: 0.015, speed: 0.040 },
];

const TAGS = [
  { color: '#C2185B', label: 'Cleared' },
  { color: '#6A1B9A', label: 'Mastered' },
  { color: '#1565C0', label: 'AI-Ready' },
];

export default function WaveformSection() {
  const canvasRef = useRef(null);
  const mouseXRef = useRef(0.5);
  const rafRef = useRef(null);
  const timeRef = useRef(0);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');

    const resize = () => {
      canvas.width = canvas.offsetWidth;
      canvas.height = canvas.offsetHeight;
    };
    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(canvas);

    const draw = () => {
      const { width, height } = canvas;
      ctx.clearRect(0, 0, width, height);
      timeRef.current += 1;

      const mouseX = mouseXRef.current;
      const amplitude = 18 + (46 - 18) * mouseX;

      WAVES.forEach(({ color, opacity, freq, speed }) => {
        ctx.beginPath();
        ctx.strokeStyle = color;
        ctx.globalAlpha = opacity;
        ctx.lineWidth = 1.5;

        for (let x = 0; x <= width; x++) {
          const phase = timeRef.current * speed;
          const y = height / 2 + Math.sin(x * freq + phase) * amplitude;
          x === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
        }
        ctx.stroke();
      });

      ctx.globalAlpha = 1;
      rafRef.current = requestAnimationFrame(draw);
    };

    draw();
    return () => {
      cancelAnimationFrame(rafRef.current);
      ro.disconnect();
    };
  }, []);

  const handleMouseMove = (e) => {
    const rect = e.currentTarget.getBoundingClientRect();
    mouseXRef.current = (e.clientX - rect.left) / rect.width;
  };

  return (
    <section
      onMouseMove={handleMouseMove}
      style={{
        backgroundColor: '#000000',
        padding: '40px 32px',
        width: '100%',
        boxSizing: 'border-box',
      }}
    >
      <div style={{ display: 'flex', gap: '24px', marginBottom: '20px', alignItems: 'center' }}>
        {TAGS.map(({ color, label }) => (
          <div key={label} style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <div
              style={{
                width: 6,
                height: 6,
                borderRadius: '50%',
                backgroundColor: color,
                flexShrink: 0,
              }}
            />
            <span
              style={{
                fontFamily: "'DM Sans', system-ui, sans-serif",
                fontSize: '11px',
                letterSpacing: '0.18em',
                textTransform: 'uppercase',
                color: '#555',
              }}
            >
              {label}
            </span>
          </div>
        ))}
      </div>
      <canvas
        ref={canvasRef}
        style={{ display: 'block', width: '100%', height: '80px' }}
      />
    </section>
  );
}
