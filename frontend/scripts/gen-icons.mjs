#!/usr/bin/env node
// One-shot icon generator — run once, commit outputs, never run at build time.
// Usage: node scripts/gen-icons.mjs
import sharp from 'sharp';
import pngToIco from 'png-to-ico';
import { writeFileSync, unlinkSync } from 'fs';
import { fileURLToPath } from 'url';
import path from 'path';
import os from 'os';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PUBLIC = path.resolve(__dirname, '..', 'public');
const SOURCE = path.join(PUBLIC, 'brand', 'icon-source.png');
const LOGO = path.join(PUBLIC, 'logo.png');
const WHITE = { r: 255, g: 255, b: 255 };

async function buildIconBuffer(size) {
  // Trim the near-white border from icon-source.png
  const trimmed = await sharp(SOURCE)
    .trim({ threshold: 10 })
    .toBuffer();

  const { width: tw, height: th } = await sharp(trimmed).metadata();
  const sq = Math.max(tw, th);

  // Letterbox to square so the mark stays centred — flush to buffer before next extend
  const squared = await sharp(trimmed)
    .extend({
      top: Math.floor((sq - th) / 2),
      bottom: Math.ceil((sq - th) / 2),
      left: Math.floor((sq - tw) / 2),
      right: Math.ceil((sq - tw) / 2),
      background: WHITE,
    })
    .toBuffer();

  // Re-add ~8% breathing room on each side (pad ≈ 0.095 × sq keeps the ratio exact)
  // Flush again before resize — sharp reorders resize before extend without an intermediate toBuffer
  const pad = Math.round(sq * 0.095);
  const padded = await sharp(squared)
    .extend({ top: pad, bottom: pad, left: pad, right: pad, background: WHITE })
    .toBuffer();

  return sharp(padded)
    .resize(size, size, { fit: 'fill' })
    .png()
    .toBuffer();
}

async function buildOgImage() {
  const { width: lw, height: lh } = await sharp(LOGO).metadata();

  // Fit the wordmark into 65% of each OG dimension so there is generous margin
  const maxW = Math.round(1200 * 0.65);
  const maxH = Math.round(630 * 0.65);
  const scale = Math.min(maxW / lw, maxH / lh);
  const logoW = Math.round(lw * scale);
  const logoH = Math.round(lh * scale);

  const logoResized = await sharp(LOGO).resize(logoW, logoH).png().toBuffer();

  await sharp({
    create: {
      width: 1200,
      height: 630,
      channels: 3,
      background: { r: 0x0b, g: 0x0b, b: 0x0f },
    },
  })
    .composite([{
      input: logoResized,
      left: Math.round((1200 - logoW) / 2),
      top: Math.round((630 - logoH) / 2),
    }])
    .png()
    .toFile(path.join(PUBLIC, 'og-image.png'));

  console.log('  og-image.png        1200×630');
}

async function main() {
  console.log('Generating icon set from', SOURCE);

  // pngToIco expects file paths, not buffers — write temp files
  const tmpDir = os.tmpdir();
  const tmpPaths = [];
  for (const size of [16, 32, 48]) {
    const buf = await buildIconBuffer(size);
    const p = path.join(tmpDir, `ovoxi-ico-${size}.png`);
    writeFileSync(p, buf);
    tmpPaths.push(p);
  }
  const icoBuffer = await pngToIco(tmpPaths);
  writeFileSync(path.join(PUBLIC, 'favicon.ico'), icoBuffer);
  tmpPaths.forEach(p => unlinkSync(p));
  console.log('  favicon.ico         16+32+48');

  const sizes = [
    { name: 'favicon-32.png',        size: 32  },
    { name: 'favicon-96.png',        size: 96  },
    { name: 'apple-touch-icon.png',  size: 180 },
    { name: 'icon-192.png',          size: 192 },
    { name: 'icon-512.png',          size: 512 },
  ];

  for (const { name, size } of sizes) {
    const buf = await buildIconBuffer(size);
    writeFileSync(path.join(PUBLIC, name), buf);
    console.log(`  ${name.padEnd(24)} ${size}×${size}`);
  }

  await buildOgImage();
  console.log('Done.');
}

main().catch(err => { console.error(err); process.exit(1); });
