import { readFileSync, readdirSync } from 'fs';

const designPath = 'c:\\Users\\12620\\Desktop\\zi\\zjrnew\\zjrnew.design';
const data = JSON.parse(readFileSync(designPath, 'utf-8'));

const pagesDir = 'c:\\Users\\12620\\Desktop\\zi\\zjrnew\\pages';
const htmlFiles = readdirSync(pagesDir).filter(f => f.endsWith('.html'));

// Check htmlSrc for each page
const htmlSrcSet = new Set();
data.data.forEach(p => {
  const src = p.devMetadata?.htmlSrc;
  if (src) htmlSrcSet.add(src);
});

console.log('=== HTML SRC CHECK ===');
console.log('Pages in .design:', data.data.length);
console.log('Pages with htmlSrc:', htmlSrcSet.size);
console.log('HTML files in pages/:', htmlFiles.length);

// Check which HTML files are NOT referenced
const htmlFileSet = new Set(htmlFiles.map(f => 'pages/' + f));
const notReferenced = htmlFiles.filter(f => !htmlSrcSet.has('pages/' + f));
const notInPages = [...htmlSrcSet].filter(src => !htmlFileSet.has(src));

console.log('\nHTML files NOT referenced in .design:', notReferenced.length);
if (notReferenced.length > 0) {
  notReferenced.slice(0, 10).forEach(f => console.log('  ' + f));
  if (notReferenced.length > 10) console.log('  ... and ' + (notReferenced.length - 10) + ' more');
}

console.log('\nDesign pages whose HTML file is MISSING:', notInPages.length);
if (notInPages.length > 0) {
  notInPages.slice(0, 10).forEach(f => console.log('  ' + f));
}

// Check a few sample htmlSrc values
console.log('\nSample htmlSrc values:');
data.data.slice(0, 5).forEach(p => {
  console.log('  ' + p.id + ' -> ' + (p.devMetadata?.htmlSrc || 'NONE'));
});
