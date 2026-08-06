import { readFileSync } from 'fs';

// Extract theme-vars from a settled client page
const coupon = readFileSync('c:\\Users\\12620\\Desktop\\zi\\zjrnew\\pages\\client-coupon.html', 'utf-8');
const match = coupon.match(/<style[^>]*id="theme-vars"[^>]*>([\s\S]*?)<\/style>/);
const settledTheme = match ? match[1] : '';

// Read colors_and_type.css
const cssFile = readFileSync('c:\\Users\\12620\\Desktop\\zi\\zjrnew\\colors_and_type.css', 'utf-8');

// Compare the :root variable section
function extractRootVars(css) {
  const match = css.match(/:root\s*\{([\s\S]*?)\}/);
  return match ? match[1] : '';
}

const settledVars = extractRootVars(settledTheme);
const cssVars = extractRootVars(cssFile);

// Normalize for comparison - remove whitespace and comments
function normalize(str) {
  return str
    .replace(/\/\*[\s\S]*?\*\//g, '')  // remove comments
    .replace(/\s+/g, ' ')               // collapse whitespace
    .trim();
}

const normSettled = normalize(settledVars);
const normCss = normalize(cssVars);

console.log('=== COMPARISON ===');
console.log(`Settled vars length: ${settledVars.length}`);
console.log(`CSS file vars length: ${cssVars.length}`);
console.log(`Match: ${normSettled === normCss}`);

if (normSettled !== normCss) {
  // Find differences
  const settledLines = settledVars.split('\n').filter(l => l.trim() && !l.trim().startsWith('/*'));
  const cssLines = cssVars.split('\n').filter(l => l.trim() && !l.trim().startsWith('/*'));
  
  console.log(`\nSettled has ${settledLines.length} variable lines`);
  console.log(`CSS file has ${cssLines.length} variable lines`);
  
  // Check what's in settled but not in css
  const settledSet = new Set(settledLines.map(l => l.trim()));
  const cssSet = new Set(cssLines.map(l => l.trim()));
  
  const onlyInSettled = [...settledSet].filter(x => !cssSet.has(x));
  const onlyInCss = [...cssSet].filter(x => !settledSet.has(x));
  
  if (onlyInSettled.length > 0) {
    console.log('\n--- Only in settled page ---');
    onlyInSettled.forEach(l => console.log(`  ${l}`));
  }
  if (onlyInCss.length > 0) {
    console.log('\n--- Only in CSS file ---');
    onlyInCss.forEach(l => console.log(`  ${l}`));
  }
}

// Check if colors_and_type.css has the @theme section and component styles
console.log('\n=== CSS FILE SECTIONS ===');
console.log('Has @theme inline:', cssFile.includes('@theme inline'));
console.log('Has #semantic-token-fallback:', cssFile.includes('#semantic-token-fallback'));
console.log('Has .tab-bar:', cssFile.includes('.tab-bar'));
console.log('Has .btn-neu-primary:', cssFile.includes('.btn-neu-primary'));
console.log('Has .btn-neu-secondary:', cssFile.includes('.btn-neu-secondary'));
console.log('Has glass bg:', cssFile.includes('--glass-bg'));
console.log('Has neu-out-sm:', cssFile.includes('--neu-out-sm'));
