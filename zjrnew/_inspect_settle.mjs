import { readFileSync } from 'fs';

const settlePath = 'c:\\Users\\12620\\Desktop\\zi\\zjrnew\\settle.design';
const content = readFileSync(settlePath, 'utf-8');
const data = JSON.parse(content);

console.log('=== SETTLE.DESIGN INFO ===');
console.log(`Total pages: ${data.data?.length || 'unknown'}`);
if (data.data) {
  data.data.forEach(p => {
    console.log(`\nPage: ${p.id} - ${p.title}`);
    console.log(`  Type: ${p.type}`);
    console.log(`  HTML: ${p.devMetadata?.htmlSrc || 'none'}`);
    console.log(`  Position: (${p.canvasData?.x}, ${p.canvasData?.y})`);
  });
}
