import { readFileSync } from 'fs';
import { readdirSync } from 'fs';

const pagesDir = 'c:\\Users\\12620\\Desktop\\zi\\zjrnew\\pages';
const files = readdirSync(pagesDir).filter(f => f.endsWith('.html'));

const clientPages = files.filter(f => f.startsWith('client-'));
const workerPages = files.filter(f => f.startsWith('worker-'));

console.log('=== PAGE COUNT ===');
console.log(`Total: ${files.length}`);
console.log(`Client: ${clientPages.length}`);
console.log(`Worker: ${workerPages.length}`);

// Verify settle.design pages classification
const settlePath = 'c:\\Users\\12620\\Desktop\\zi\\zjrnew\\settle.design';
const settleData = JSON.parse(readFileSync(settlePath, 'utf-8'));
const settledClient = settleData.data.filter(p => p.id.startsWith('page-client-'));
const settledWorker = settleData.data.filter(p => p.id.startsWith('page-worker-'));

console.log(`\nSettled client: ${settledClient.length}`);
console.log(`Settled worker: ${settledWorker.length}`);

// Check a worker settled page's theme vars for the exact worker color values
const workerHome = readFileSync(`${pagesDir}/worker-home.html`, 'utf-8');
const match = workerHome.match(/<style[^>]*id="theme-vars"[^>]*>([\s\S]*?)<\/style>/);
const workerTheme = match ? match[1] : '';

// Extract just the brand/accent variables
const brandVars = workerTheme.split('\n').filter(l => 
  l.includes('--brand') || l.includes('--accent') || l.includes('--primary') || l.includes('--ring')
);
console.log('\n=== WORKER BRAND VARS ===');
brandVars.forEach(l => console.log(l.trim()));
