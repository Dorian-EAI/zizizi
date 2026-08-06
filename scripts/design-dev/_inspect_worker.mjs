import { readFileSync } from 'fs';

// Check worker settled pages for brand color override
const workerHome = readFileSync('c:\\Users\\12620\\Desktop\\zi\\zjrnew\\pages\\worker-home.html', 'utf-8');
const workerWallet = readFileSync('c:\\Users\\12620\\Desktop\\zi\\zjrnew\\pages\\worker-wallet.html', 'utf-8');

// Extract theme-vars from worker pages
function extractThemeVars(html) {
  const match = html.match(/<style[^>]*id="theme-vars"[^>]*>([\s\S]*?)<\/style>/);
  return match ? match[1] : 'NOT FOUND';
}

console.log('=== WORKER-HOME theme-vars (first 500 chars) ===');
const whVars = extractThemeVars(workerHome);
console.log(whVars.substring(0, 500));

console.log('\n=== WORKER-WALLET has theme-vars:', workerWallet.includes('id="theme-vars"'));
console.log('=== WORKER-HOME has theme-vars:', workerHome.includes('id="theme-vars"'));

// Check for worker-specific brand color
console.log('\nWorker home has blue brand:', workerHome.includes('#2D6CDF'));
console.log('Worker wallet has blue brand:', workerWallet.includes('#2D6CDF'));

// Check settled client page for comparison
const coupon = readFileSync('c:\\Users\\12620\\Desktop\\zi\\zjrnew\\pages\\client-coupon.html', 'utf-8');
const couponVars = extractThemeVars(coupon);
console.log('\n=== CLIENT-COUPON theme-vars (first 300 chars) ===');
console.log(couponVars.substring(0, 300));

// Check detail-page.css usage
console.log('\n=== detail-page.css usage ===');
console.log('worker-home:', workerHome.includes('detail-page.css'));
console.log('worker-wallet:', workerWallet.includes('detail-page.css'));
console.log('client-coupon:', coupon.includes('detail-page.css'));

// Check how many style tags each page has
function countStyles(html) {
  const matches = html.match(/<style/g);
  return matches ? matches.length : 0;
}
console.log('\nStyle tag counts:');
console.log('  worker-home:', countStyles(workerHome));
console.log('  worker-wallet:', countStyles(workerWallet));
console.log('  client-coupon:', countStyles(coupon));
