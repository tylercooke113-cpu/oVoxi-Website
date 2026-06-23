import React, { useRef, useEffect } from 'react';

const PARTICLE_COUNT = 55;
const COLORS = ['#C2185B', '#6A1B9A', '#1565C0', '#ffffff'];
const CONNECTION_DIST = 80;

function randomBetween(min, max) {
  return min + Math.random() * (max - min);
}

function initParticles() {
  return Array.from({ length: PARTICLE_COUNT }, () => ({
    x: Math.random(),
    y: Math.random(),
    vx: randomBetween(-0.0006, 0.0006),
    vy: randomBetween(-0.0006, 0.0006),
    radius: randomBetween(0.5, 2),
    color: COLORS[Math.floor(Math.random() * COLORS.length)],
    opacity: randomBetween(0.2, 0.7),
  }));
}

export default function ParticleHero() {
  const canvasRef = useRef(null);
  const mouseRef = useRef({ x: 0.5, y: 0.5 });
  const rafRef = useRef(null);
  const particlesRef = useRef(initParticles());

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

      const mx = mouseRef.current.x;
      const particles = particlesRef.current;

      particles.forEach((p) => {
        p.vx += 0.0003 * (mx - 0.5);
        p.vy += 0.0003 * (mouseRef.current.y - 0.5);
        p.x += p.vx;
        p.y += p.vy;
        if (p.x < 0) p.x = 1;
        if (p.x > 1) p.x = 0;
        if (p.y < 0) p.y = 1;
        if (p.y > 1) p.y = 0;
      });

      for (let i = 0; i < particles.length; i++) {
        for (let j = i + 1; j < particles.length; j++) {
          const dx = (particles[i].x - particles[j].x) * width;
          const dy = (particles[i].y - particles[j].y) * height;
          const dist = Math.sqrt(dx * dx + dy * dy);
          if (dist < CONNECTION_DIST) {
            ctx.beginPath();
            ctx.strokeStyle = '#6A1B9A';
            ctx.globalAlpha = (1 - dist / CONNECTION_DIST) * 0.25;
            ctx.lineWidth = 0.5;
            ctx.moveTo(particles[i].x * width, particles[i].y * height);
            ctx.lineTo(particles[j].x * width, particles[j].y * height);
            ctx.stroke();
          }
        }
      }

      particles.forEach((p) => {
        ctx.beginPath();
        ctx.globalAlpha = p.opacity;
        ctx.fillStyle = p.color;
        ctx.arc(p.x * width, p.y * height, p.radius, 0, Math.PI * 2);
        ctx.fill();
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
    mouseRef.current = {
      x: (e.clientX - rect.left) / rect.width,
      y: (e.clientY - rect.top) / rect.height,
    };
  };

  return (
    <div
      onMouseMove={handleMouseMove}
      style={{
        position: 'relative',
        backgroundColor: '#000000',
        overflow: 'hidden',
        width: '100%',
      }}
    >
      <canvas
        ref={canvasRef}
        style={{
          position: 'absolute',
          inset: 0,
          width: '100%',
          height: '100%',
          zIndex: 0,
        }}
      />
      <div
        style={{
          position: 'relative',
          zIndex: 1,
          padding: '48px 32px 40px',
        }}
      >
        <p
          style={{
            fontFamily: "'DM Sans', system-ui, sans-serif",
            fontSize: '11px',
            letterSpacing: '0.2em',
            textTransform: 'uppercase',
            color: '#6A1B9A',
            margin: '0 0 16px',
          }}
        >
          For Emerging Artists
        </p>
        <h1
          style={{
            fontFamily: "'Syne', system-ui, sans-serif",
            fontWeight: 800,
            fontSize: '38px',
            color: '#ffffff',
            lineHeight: 1.05,
            margin: '0 0 16px',
          }}
        >
          Turn Your Music Into Licensing Revenue.
        </h1>
        <p
          style={{
            fontFamily: "'DM Sans', system-ui, sans-serif",
            fontWeight: 300,
            fontSize: '14px',
            color: '#666',
            maxWidth: '440px',
            lineHeight: 1.65,
            margin: 0,
          }}
        >
          oVoxi is the only catalog company built exclusively for emerging artists. We prepare your music for AI platforms — and pay you when it licenses.
        </p>
      </div>
    </div>
  );
}
