import { readFileSync } from 'fs';
import { readdirSync } from 'fs';

const pagesDir = 'c:\\Users\\12620\\Desktop\\zi\\zjrnew\\pages';

// Check all pages for key style patterns
const files = readdirSync(pagesDir).filter(f => f.endsWith('.html'));

const patterns = {
  'has_theme_vars_id': f => readFileSync(`${pagesDir}/${f}`, 'utf-8').includes('id="theme-vars"'),
  'has_glass_neu_card': f => readFileSync(`${pagesDir}/${f}`, 'utf-8').includes('glass-neu-card'),
  'has_btn_neu_primary': f => readFileSync(`${pagesDir}/${f}`, 'utf-8').includes('btn-neu-primary'),
  'has_detail_page_css': f => readFileSync(`${pagesDir}/${f}`, 'utf-8').includes('detail-page.css'),
  'has_colors_and_type': f => readFileSync(`${pagesDir}/${f}`, 'utf-8').includes('colors_and_type.css'),
  'has_neu_out_sm': f => readFileSync(`${pagesDir}/${f}`, 'utf-8').includes('neu-out-sm'),
  'has_gradient_btn': f => {
    const c = readFileSync(`${pagesDir}/${f}`, 'utf-8');
    return c.includes('linear-gradient') && (c.includes('btn') || c.includes('button'));
  },
};

const results = {};
for (const [name, fn] of Object.entries(patterns)) {
  results[name] = [];
}

files.forEach(f => {
  for (const [name, fn] of Object.entries(patterns)) {
    if (fn(f)) results[name].push(f);
  }
});

console.log('=== STYLE PATTERN DISTRIBUTION ===');
for (const [name, list] of Object.entries(results)) {
  console.log(`\n${name}: ${list.length}/${files.length} pages`);
}

// Pages missing theme-vars id
const missingThemeVars = files.filter(f => !results.has_theme_vars_id.includes(f));
console.log(`\n--- Pages MISSING id="theme-vars" (${missingThemeVars.length}) ---`);
missingThemeVars.sort().forEach(f => console.log(`  ${f}`));
