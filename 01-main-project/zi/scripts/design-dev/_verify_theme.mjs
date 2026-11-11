import { readdirSync, readFileSync } from 'fs';

const pagesDir = 'c:\\Users\\12620\\Desktop\\zi\\zjrnew\\pages';
const allFiles = readdirSync(pagesDir).filter(f => f.endsWith('.html'));

let hasThemeVars = 0;
let clientCorrect = 0;
let workerCorrect = 0;
let clientWrong = [];
let workerWrong = [];

allFiles.forEach(f => {
  const html = readFileSync(`${pagesDir}/${f}`, 'utf-8');
  const hasVars = html.includes('id="theme-vars"');
  if (hasVars) hasThemeVars++;
  
  if (f.startsWith('client-')) {
    const hasTeal = html.includes('--brand: #0D9488;');
    if (hasTeal) {
      clientCorrect++;
    } else {
      clientWrong.push(f);
    }
  } else if (f.startsWith('worker-')) {
    const hasBlue = html.includes('--brand: #2D6CDF;');
    if (hasBlue) {
      workerCorrect++;
    } else {
      workerWrong.push(f);
    }
  }
});

console.log('=== THEME UNIFICATION VERIFICATION ===');
console.log(`Total pages: ${allFiles.length}`);
console.log(`Pages with id="theme-vars": ${hasThemeVars}`);
console.log(`Client with teal brand: ${clientCorrect}/90`);
console.log(`Worker with blue brand: ${workerCorrect}/39`);

if (clientWrong.length > 0) {
  console.log('\n--- Client pages with wrong brand ---');
  clientWrong.forEach(f => console.log(`  ${f}`));
}
if (workerWrong.length > 0) {
  console.log('\n--- Worker pages with wrong brand ---');
  workerWrong.forEach(f => console.log(`  ${f}`));
}

// Check a sample page for structure
console.log('\n=== SAMPLE: client-points.html (previously non-settled) ===');
const pointsHtml = readFileSync(`${pagesDir}/client-points.html`, 'utf-8');
const headMatch = pointsHtml.match(/<head>([\s\S]*?)<\/head>/);
if (headMatch) {
  const headContent = headMatch[1];
  const styleCount = (headContent.match(/<style/g) || []).length;
  console.log(`Head style tags: ${styleCount}`);
  console.log(`Has theme-vars id: ${headContent.includes('id="theme-vars"')}`);
  console.log(`Has @theme inline: ${headContent.includes('@theme inline')}`);
  console.log(`Has semantic-token-fallback: ${headContent.includes('#semantic-token-fallback')}`);
  console.log(`Has fonts.css link: ${headContent.includes('fonts.css')}`);
}
