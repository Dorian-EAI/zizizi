import { readFileSync } from 'fs';

// Compare a settled page vs a non-settled page of similar type
// Settled: client-coupon.html (in settle)
// Non-settled: client-points.html (not in settle)

const settled = readFileSync('c:\\Users\\12620\\Desktop\\zi\\zjrnew\\pages\\client-coupon.html', 'utf-8');
const nonSettled = readFileSync('c:\\Users\\12620\\Desktop\\zi\\zjrnew\\pages\\client-points.html', 'utf-8');

// Extract key structural elements to compare
function extractStructure(html) {
  const lines = [];
  const inBody = html.split('<body>')[1] || html;
  const bodyContent = inBody.split('</body>')[0] || inBody;
  // Get class names of top-level elements
  const topDivs = bodyContent.match(/<div[^>]*class="[^"]*"[^>]*>/g) || [];
  return topDivs.slice(0, 20);
}

console.log('=== SETTLED: client-coupon.html ===');
console.log(`File size: ${settled.length} chars`);
const settledDivs = extractStructure(settled);
settledDivs.forEach((d, i) => console.log(`  ${i}: ${d.substring(0, 100)}`));

console.log('\n=== NON-SETTLED: client-points.html ===');
console.log(`File size: ${nonSettled.length} chars`);
const nonSettledDivs = extractStructure(nonSettled);
nonSettledDivs.forEach((d, i) => console.log(`  ${i}: ${d.substring(0, 100)}`));

// Check for key style markers
function checkMarkers(html, name) {
  console.log(`\n--- ${name} markers ---`);
  console.log(`Has phone container: ${html.includes('class="phone"')}`);
  console.log(`Has status-bar: ${html.includes('status-bar')}`);
  console.log(`Has tab-bar: ${html.includes('tab-bar')}`);
  console.log(`Has hero-section: ${html.includes('hero') || html.includes('header-section')}`);
  console.log(`Has glass-card: ${html.includes('glass-card') || html.includes('neu-card')}`);
  console.log(`Has neu-out: ${html.includes('neu-out') || html.includes('neu-')}`);
  console.log(`Has btn-neu: ${html.includes('btn-neu')}`);
  console.log(`Has gradient background: ${html.includes('linear-gradient') || html.includes('radial-gradient')}`);
  console.log(`Uses colors_and_type.css: ${html.includes('colors_and_type.css')}`);
  console.log(`Uses detail-page.css: ${html.includes('detail-page.css')}`);
  console.log(`Has style tag with theme-vars: ${html.includes('id="theme-vars"')}`);
}

checkMarkers(settled, 'SETTLED (coupon)');
checkMarkers(nonSettled, 'NON-SETTLED (points)');
