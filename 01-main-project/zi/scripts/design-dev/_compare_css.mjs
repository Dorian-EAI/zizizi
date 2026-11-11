import { readFileSync } from 'fs';

// Compare CSS structure of settled vs non-settled
const settled = readFileSync('c:\\Users\\12620\\Desktop\\zi\\zjrnew\\pages\\client-coupon.html', 'utf-8');
const nonSettled = readFileSync('c:\\Users\\12620\\Desktop\\zi\\zjrnew\\pages\\client-points.html', 'utf-8');

// Extract the style section
function extractStyle(html) {
  const match = html.match(/<style[^>]*>([\s\S]*?)<\/style>/);
  return match ? match[1] : '';
}

const settledStyle = extractStyle(settled);
const nonSettledStyle = extractStyle(nonSettled);

console.log('=== SETTLED CSS length:', settledStyle.length, 'chars ===');
console.log('=== NON-SETTLED CSS length:', nonSettledStyle.length, 'chars ===');

// Check for key CSS classes
function checkCssClasses(css, name) {
  console.log(`\n--- ${name} CSS classes ---`);
  const classes = [
    'phone', 'glass-neu-card', 'glass-card', 'neu-card',
    'hero', 'header-section', 'top-bar', 'nav-bar',
    'btn-neu-primary', 'btn-neu-secondary', 'btn-primary',
    'tab-bar', 'segmented-tabs',
    'section-header', 'section-title',
    'list-item', 'cell', 'row',
    'neu-out', 'neu-in',
    'status-bar', 'safe-area'
  ];
  classes.forEach(c => {
    const found = css.includes('.' + c);
    if (found) console.log(`  ✓ .${c}`);
  });
}

checkCssClasses(settledStyle, 'SETTLED');
checkCssClasses(nonSettledStyle, 'NON-SETTLED');

// Check head section structure
function extractHead(html) {
  const match = html.match(/<head>([\s\S]*?)<\/head>/);
  return match ? match[1] : '';
}

console.log('\n=== SETTLED HEAD ===');
console.log(extractHead(settled).trim().substring(0, 500));
console.log('\n=== NON-SETTLED HEAD ===');
console.log(extractHead(nonSettled).trim().substring(0, 500));
