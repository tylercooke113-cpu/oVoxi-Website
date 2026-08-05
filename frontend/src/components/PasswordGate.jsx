import { useState, useEffect, useRef } from "react";

const CORRECT_PASSWORD = "oVoxi999**";
const SESSION_KEY = "ovoxi_access_granted";

export default function PasswordGate({ onUnlock }) {
  const [input, setInput] = useState("");
  const [status, setStatus] = useState("idle"); // idle | error | success
  const [visible, setVisible] = useState(true);
  const inputRef = useRef(null);
  const canvasRef = useRef(null);
  const animFrameRef = useRef(null);

  // Particle grid canvas effect
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");

    const resize = () => {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
    };
    resize();
    window.addEventListener("resize", resize);

    const particles = Array.from({ length: 80 }, () => ({
      x: Math.random() * window.innerWidth,
      y: Math.random() * window.innerHeight,
      vx: (Math.random() - 0.5) * 0.4,
      vy: (Math.random() - 0.5) * 0.4,
      r: Math.random() * 1.5 + 0.5,
      hue: Math.random() > 0.5 ? 336 : 277, // magenta or purple
    }));

    let t = 0;
    const draw = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);

      // Grid lines
      ctx.lineWidth = 0.4;
      const spacing = 60;
      const cols = Math.ceil(canvas.width / spacing) + 1;
      const rows = Math.ceil(canvas.height / spacing) + 1;
      for (let c = 0; c < cols; c++) {
        const x = c * spacing;
        const alpha = 0.06 + 0.04 * Math.sin(t * 0.01 + c * 0.3);
        ctx.strokeStyle = `rgba(194, 24, 91, ${alpha})`;
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, canvas.height);
        ctx.stroke();
      }
      for (let r = 0; r < rows; r++) {
        const y = r * spacing;
        const alpha = 0.06 + 0.04 * Math.sin(t * 0.01 + r * 0.3);
        ctx.strokeStyle = `rgba(106, 27, 154, ${alpha})`;
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(canvas.width, y);
        ctx.stroke();
      }

      // Particles and connecting lines
      particles.forEach((p, i) => {
        p.x += p.vx;
        p.y += p.vy;
        if (p.x < 0) p.x = canvas.width;
        if (p.x > canvas.width) p.x = 0;
        if (p.y < 0) p.y = canvas.height;
        if (p.y > canvas.height) p.y = 0;

        const glow = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, p.r * 4);
        glow.addColorStop(0, `hsla(${p.hue}, 100%, 70%, 0.9)`);
        glow.addColorStop(1, `hsla(${p.hue}, 100%, 70%, 0)`);
        ctx.fillStyle = glow;
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.r * 4, 0, Math.PI * 2);
        ctx.fill();

        for (let j = i + 1; j < particles.length; j++) {
          const dx = particles[j].x - p.x;
          const dy = particles[j].y - p.y;
          const dist = Math.sqrt(dx * dx + dy * dy);
          if (dist < 120) {
            const alpha = (1 - dist / 120) * 0.15;
            ctx.strokeStyle = `hsla(${p.hue}, 100%, 70%, ${alpha})`;
            ctx.lineWidth = 0.5;
            ctx.beginPath();
            ctx.moveTo(p.x, p.y);
            ctx.lineTo(particles[j].x, particles[j].y);
            ctx.stroke();
          }
        }
      });

      t++;
      animFrameRef.current = requestAnimationFrame(draw);
    };

    animFrameRef.current = requestAnimationFrame(draw);
    return () => {
      cancelAnimationFrame(animFrameRef.current);
      window.removeEventListener("resize", resize);
    };
  }, []);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (input === CORRECT_PASSWORD) {
      setStatus("success");
      sessionStorage.setItem(SESSION_KEY, "1");
      setTimeout(() => {
        setVisible(false);
        setTimeout(onUnlock, 600);
      }, 400);
    } else {
      setStatus("error");
      setTimeout(() => setStatus("idle"), 1200);
      setInput("");
    }
  };

  return (
    <div
      className="password-gate-overlay"
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 9999,
        background: "#000000",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        opacity: visible ? 1 : 0,
        transition: "opacity 0.6s ease",
        overflow: "hidden",
      }}
    >
      {/* Particle canvas */}
      <canvas
        ref={canvasRef}
        style={{ position: "absolute", inset: 0, pointerEvents: "none" }}
      />

      {/* Scanlines */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          pointerEvents: "none",
          backgroundImage:
            "repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(0,0,0,0.18) 2px, rgba(0,0,0,0.18) 4px)",
          animation: "scanlineScroll 8s linear infinite",
          zIndex: 1,
        }}
      />

      {/* Center card */}
      <div
        style={{
          position: "relative",
          zIndex: 2,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: "28px",
          padding: "0 24px",
          width: "100%",
          maxWidth: "440px",
        }}
      >
        {/* RESTRICTED ACCESS label */}
        <div
          style={{
            fontFamily: "'Kode Mono', monospace",
            fontSize: "11px",
            fontVariant: "small-caps",
            letterSpacing: "0.35em",
            color: "#6A1B9A",
            textShadow: "0 0 12px rgba(106, 27, 154, 0.7)",
            textTransform: "uppercase",
            opacity: 0.9,
          }}
        >
          Restricted Access
        </div>

        {/* Divider line */}
        <div
          style={{
            width: "100%",
            height: "1px",
            background:
              "linear-gradient(90deg, transparent, rgba(194,24,91,0.4), rgba(106,27,154,0.4), transparent)",
          }}
        />

        {/* Form */}
        <form
          onSubmit={handleSubmit}
          style={{
            width: "100%",
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            gap: "24px",
          }}
        >
          {/* Input */}
          <input
            ref={inputRef}
            type="password"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="ENTER ACCESS CODE"
            autoComplete="off"
            spellCheck={false}
            style={{
              width: "100%",
              background: "transparent",
              border: "none",
              borderBottom: "1.5px solid rgba(106, 27, 154, 0.7)",
              boxShadow: "0 4px 16px -4px rgba(106, 27, 154, 0.35)",
              outline: "none",
              color: "#ffffff",
              fontFamily: "'Kode Mono', monospace",
              fontSize: "13px",
              letterSpacing: "0.2em",
              textAlign: "center",
              padding: "12px 0",
              caretColor: "#6A1B9A",
              transition: "border-color 0.2s, box-shadow 0.2s",
            }}
            onFocus={(e) => {
              e.target.style.borderBottomColor = "#6A1B9A";
              e.target.style.boxShadow = "0 4px 20px -4px rgba(106, 27, 154, 0.6)";
            }}
            onBlur={(e) => {
              e.target.style.borderBottomColor = "rgba(106, 27, 154, 0.7)";
              e.target.style.boxShadow = "0 4px 16px -4px rgba(106, 27, 154, 0.35)";
            }}
          />

          {/* Error message */}
          <div
            style={{
              height: "18px",
              fontFamily: "'Kode Mono', monospace",
              fontSize: "11px",
              letterSpacing: "0.25em",
              color: "#ff2d55",
              textShadow: "0 0 10px rgba(255, 45, 85, 0.8)",
              textTransform: "uppercase",
              animation: status === "error" ? "shake 0.4s ease" : "none",
              opacity: status === "error" ? 1 : 0,
              transition: "opacity 0.2s",
            }}
          >
            Access Denied
          </div>

          {/* Submit button */}
          <button
            type="submit"
            className="auth-btn"
            style={{
              background: "transparent",
              border: "1px solid rgba(106, 27, 154, 0.6)",
              color: "#6A1B9A",
              fontFamily: "'Kode Mono', monospace",
              fontSize: "11px",
              letterSpacing: "0.35em",
              textTransform: "uppercase",
              padding: "12px 40px",
              cursor: "pointer",
              boxShadow:
                "0 0 18px rgba(106, 27, 154, 0.2), inset 0 0 18px rgba(106, 27, 154, 0.04)",
              transition: "box-shadow 0.2s, border-color 0.2s, color 0.2s",
              animation: "btnPulse 2.5s ease-in-out infinite",
              outline: "none",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.boxShadow =
                "0 0 32px rgba(106, 27, 154, 0.6), inset 0 0 24px rgba(106, 27, 154, 0.1)";
              e.currentTarget.style.borderColor = "#6A1B9A";
              e.currentTarget.style.color = "#ffffff";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.boxShadow =
                "0 0 18px rgba(106, 27, 154, 0.2), inset 0 0 18px rgba(106, 27, 154, 0.04)";
              e.currentTarget.style.borderColor = "rgba(106, 27, 154, 0.6)";
              e.currentTarget.style.color = "#6A1B9A";
            }}
          >
            Authenticate
          </button>
        </form>
      </div>
    </div>
  );
}
