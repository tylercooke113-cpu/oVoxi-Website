import React, { useRef, useEffect } from 'react';

// Custom animated canvas: an AI "network" of drifting nodes connected by
// glowing lines, with a reactive audio waveform along the lower third.
// Pure canvas + requestAnimationFrame — no external dependency.
export const HeroCanvas = () => {
  const canvasRef = useRef(null);
  const rafRef = useRef(null);
  const mouseRef = useRef({ x: null, y: null });

  useEffect(() => {
    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    const mouse = mouseRef.current;
    let width = 0;
    let height = 0;
    let dpr = Math.min(window.devicePixelRatio || 1, 2);
    let nodes = [];
    let t = 0;

    const NODE_COUNT = window.innerWidth < 768 ? 28 : 56;
    const LINK_DIST = window.innerWidth < 768 ? 140 : 180;

    const resize = () => {
      width = canvas.clientWidth;
      height = canvas.clientHeight;
      dpr = Math.min(window.devicePixelRatio || 1, 2);
      canvas.width = width * dpr;
      canvas.height = height * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };

    const initNodes = () => {
      nodes = Array.from({ length: NODE_COUNT }, () => ({
        x: Math.random() * width,
        y: Math.random() * height,
        vx: (Math.random() - 0.5) * 0.28,
        vy: (Math.random() - 0.5) * 0.28,
        r: Math.random() * 1.8 + 0.8,
      }));
    };

    const draw = () => {
      t += 0.012;
      ctx.clearRect(0, 0, width, height);

      if (mouse.x !== null && mouse.y !== null) {
        const cursorGlow = ctx.createRadialGradient(
          mouse.x, mouse.y, 0,
          mouse.x, mouse.y, 180
        );
        cursorGlow.addColorStop(0, 'rgba(180, 79, 212, 0.15)');
        cursorGlow.addColorStop(0.5, 'rgba(107, 127, 212, 0.07)');
        cursorGlow.addColorStop(1, 'rgba(79, 195, 247, 0)');
        ctx.fillStyle = cursorGlow;
        ctx.fillRect(0, 0, width, height);
      }

      // Links
      for (let i = 0; i < nodes.length; i++) {
        const a = nodes[i];
        a.x += a.vx;
        a.y += a.vy;
        if (a.x < 0 || a.x > width) a.vx *= -1;
        if (a.y < 0 || a.y > height) a.vy *= -1;

        for (let j = i + 1; j < nodes.length; j++) {
          const b = nodes[j];
          const dx = a.x - b.x;
          const dy = a.y - b.y;
          const dist = Math.hypot(dx, dy);
          if (dist < LINK_DIST) {
            const op = (1 - dist / LINK_DIST) * 0.35;
            ctx.strokeStyle = `rgba(155, 89, 212, ${op})`;
            ctx.lineWidth = 1;
            ctx.beginPath();
            ctx.moveTo(a.x, a.y);
            ctx.lineTo(b.x, b.y);
            ctx.stroke();
          }
        }
      }

      // Nodes
      for (const n of nodes) {
        ctx.beginPath();
        ctx.arc(n.x, n.y, n.r, 0, Math.PI * 2);
        ctx.fillStyle = 'rgba(180, 79, 212, 0.9)';
        ctx.shadowBlur = 8;
        ctx.shadowColor = 'rgba(155, 89, 212, 0.8)';
        ctx.fill();
        ctx.shadowBlur = 0;
      }

      // Waveform along lower portion
      const baseY = height * 0.72;
      const layers = [
        { amp: 26, speed: 1.0, color: 'rgba(180, 79, 212, 0.55)', freq: 0.014 },
        { amp: 18, speed: 1.6, color: 'rgba(107, 127, 212, 0.35)', freq: 0.022 },
      ];
      layers.forEach((l, li) => {
        ctx.beginPath();
        for (let x = 0; x <= width; x += 6) {
          const y =
            baseY +
            Math.sin(x * l.freq + t * l.speed + li) *
              l.amp *
              (0.5 + 0.5 * Math.sin(x * 0.004 + t));
          if (x === 0) ctx.moveTo(x, y);
          else ctx.lineTo(x, y);
        }
        ctx.strokeStyle = l.color;
        ctx.lineWidth = 2;
        ctx.stroke();
      });

      rafRef.current = requestAnimationFrame(draw);
    };

    const onMouseMove = (e) => {
      const rect = canvas.getBoundingClientRect();
      mouse.x = e.clientX - rect.left;
      mouse.y = e.clientY - rect.top;
    };

    const onMouseLeave = () => {
      mouse.x = null;
      mouse.y = null;
    };

    resize();
    initNodes();
    draw();

    const onResize = () => {
      resize();
      initNodes();
    };
    window.addEventListener('resize', onResize);
    window.addEventListener('mousemove', onMouseMove);
    window.addEventListener('mouseleave', onMouseLeave);
    return () => {
      cancelAnimationFrame(rafRef.current);
      window.removeEventListener('resize', onResize);
      window.removeEventListener('mousemove', onMouseMove);
      window.removeEventListener('mouseleave', onMouseLeave);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      data-testid="hero-canvas"
      className="absolute inset-0 h-full w-full"
      aria-hidden="true"
    />
  );
};
