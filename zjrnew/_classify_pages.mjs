import { readFileSync } from 'fs';
import { readdirSync } from 'fs';

// Get list of pages in settle.design
const settlePath = 'c:\\Users\\12620\\Desktop\\zi\\zjrnew\\settle.design';
const settleData = JSON.parse(readFileSync(settlePath, 'utf-8'));
const settlePageIds = new Set(settleData.data.map(p => p.id));

// Get all pages in zjrnew
const zjrnewPath = 'c:\\Users\\12620\\Desktop\\zi\\zjrnew\\zjrnew.design';
const zjrnewData = JSON.parse(readFileSync(zjrnewPath, 'utf-8'));

const pagesDir = 'c:\\Users\\12620\\Desktop\\zi\\zjrnew\\pages';
const allHtmlFiles = readdirSync(pagesDir).filter(f => f.endsWith('.html'));

console.log('=== PAGE STATUS ===');
console.log(`Total HTML files: ${allHtmlFiles.length}`);
console.log(`Pages in settle.design: ${settlePageIds.size}`);
console.log(`Pages in zjrnew.design: ${zjrnewData.data.length}`);

// Classify pages
const settled = [];
const notSettled = [];
zjrnewData.data.forEach(p => {
  if (settlePageIds.has(p.id)) {
    settled.push(p.id);
  } else {
    notSettled.push(p.id);
  }
});

console.log(`\nSettled (in settle.design): ${settled.length}`);
console.log(`Not settled (need style fix): ${notSettled.length}`);

console.log('\n--- NOT SETTLED pages ---');
notSettled.sort().forEach(id => console.log(`  ${id}`));
