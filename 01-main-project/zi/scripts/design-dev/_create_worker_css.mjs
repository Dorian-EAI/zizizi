import { readFileSync, writeFileSync } from 'fs';

// Read client CSS
const clientCss = readFileSync('c:\\Users\\12620\\Desktop\\zi\\zjrnew\\colors_and_type.css', 'utf-8');

// Create worker CSS by replacing brand colors
let workerCss = clientCss
  // Brand comment
  .replace('/* Brand - Client (Teal) */', '/* Brand - Worker (Blue) */')
  // Brand main
  .replace('--brand: #0D9488;', '--brand: #2D6CDF;')
  .replace('--brand-dark: #0A7A70;', '--brand-dark: #2456B8;')
  .replace('--brand-mid: #14B8A6;', '--brand-mid: #5A8EE8;')
  .replace('--brand-light: #CCFBF1;', '--brand-light: #DCE8FB;')
  .replace('--brand-glow: rgba(13, 148, 136, 0.24);', '--brand-glow: rgba(45, 108, 223, 0.18);')
  .replace('--brand-subtle: rgba(13, 148, 136, 0.10);', '--brand-subtle: rgba(45, 108, 223, 0.08);')
  // Primary & ring
  .replace('--primary: #0D9488;', '--primary: #2D6CDF;')
  .replace('--ring: #0D9488;', '--ring: #2D6CDF;');

// Write worker CSS
writeFileSync('c:\\Users\\12620\\Desktop\\zi\\zjrnew\\colors_and_type_worker.css', workerCss, 'utf-8');

// Verify
const verifyMatch = workerCss.match(/--brand:\s*([^;]+);/);
console.log('Worker CSS created successfully');
console.log(`Brand color: ${verifyMatch ? verifyMatch[1].trim() : 'not found'}`);
console.log(`File size: ${workerCss.length} chars`);
