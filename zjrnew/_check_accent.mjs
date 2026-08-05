import { readFileSync } from 'fs';
import { readdirSync } from 'fs';

const pagesDir = 'c:\\Users\\12620\\Desktop\\zi\\zjrnew\\pages';

// Check all worker pages that are in settle.design
const settlePath = 'c:\\Users\\12620\\Desktop\\zi\\zjrnew\\settle.design';
const settleData = JSON.parse(readFileSync(settlePath, 'utf-8'));
const workerSettled = settleData.data.filter(p => p.id.startsWith('page-worker-'));

console.log('=== WORKER SETTLED PAGES ACCENT COLOR ===');
workerSettled.forEach(p => {
  const htmlFile = p.devMetadata?.htmlSrc;
  if (!htmlFile) return;
  const fullPath = `c:\\Users\\12620\\Desktop\\zi\\zjrnew\\${htmlFile}`;
  try {
    const html = readFileSync(fullPath, 'utf-8');
    const match = html.match(/--accent:\s*([^;]+);/);
    const accent = match ? match[1].trim() : 'not found';
    console.log(`  ${p.id}: --accent = ${accent}`);
  } catch(e) {
    console.log(`  ${p.id}: FILE NOT FOUND`);
  }
});

// Also check the style spec doc for worker accent
console.log('\n=== STYLE SPEC - WORKER ACCENT ===');
const specPath = 'c:\\Users\\12620\\Desktop\\zi\\docs\\design\\样式规范详尽文档.md';
const spec = readFileSync(specPath, 'utf-8');
const accentSection = spec.match(/师傅端颜色覆盖[\s\S]*?---/);
if (accentSection) {
  const lines = accentSection[0].split('\n').filter(l => l.includes('accent') || l.includes('强调'));
  lines.forEach(l => console.log(`  ${l.trim()}`));
}
