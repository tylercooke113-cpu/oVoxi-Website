// Full capability probe -- evaluated once at module load, not a React hook despite the filename.
// Returns false to skip the 3D canvas entirely.

function checkWebGL() {
  try {
    const c = document.createElement('canvas');
    const gl = c.getContext('webgl2') || c.getContext('webgl');
    if (!gl) return false;
    const ext = gl.getExtension('WEBGL_debug_renderer_info');
    if (ext) {
      const r = gl.getParameter(ext.UNMASKED_RENDERER_WEBGL).toLowerCase();
      if (r.includes('swiftshader') || r.includes('software') || r.includes('llvmpipe')) return false;
    }
    return true;
  } catch {
    return false;
  }
}

export const canRender3D = (() => {
  if (typeof window === 'undefined') return false;
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return false;
  if (typeof navigator !== 'undefined') {
    if (navigator.hardwareConcurrency != null && navigator.hardwareConcurrency < 4) return false;
    if (navigator.deviceMemory != null && navigator.deviceMemory < 4) return false;
  }
  return checkWebGL();
})();
