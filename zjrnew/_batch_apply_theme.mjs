import { readdirSync } from 'fs';
import { execSync } from 'child_process';

const pagesDir = 'c:\\Users\\12620\\Desktop\\zi\\zjrnew\\pages';
const clientCss = 'c:\\Users\\12620\\Desktop\\zi\\zjrnew\\colors_and_type.css';
const workerCss = 'c:\\Users\\12620\\Desktop\\zi\\zjrnew\\colors_and_type_worker.css';
const toolPath = 'c:\\Users\\12620\\.trae-cn\\builtin\\design\\default\\skills\\solo-design\\shared-runtime\\deterministic-tooling\\apply-html-head-contract.mjs';

const allFiles = readdirSync(pagesDir).filter(f => f.endsWith('.html'));
const clientFiles = allFiles.filter(f => f.startsWith('client-')).map(f => `${pagesDir}\\${f}`);
const workerFiles = allFiles.filter(f => f.startsWith('worker-')).map(f => `${pagesDir}\\${f}`);

console.log(`Client pages: ${clientFiles.length}`);
console.log(`Worker pages: ${workerFiles.length}`);

// Batch size
const BATCH_SIZE = 8;

function processBatch(cssFile, files, label) {
  console.log(`\n=== Processing ${label} pages ===`);
  let successCount = 0;
  let failCount = 0;
  
  for (let i = 0; i < files.length; i += BATCH_SIZE) {
    const batch = files.slice(i, i + BATCH_SIZE);
    const args = [toolPath, `"${cssFile}"`, ...batch.map(f => `"${f}"`), '--replace-head'].join(' ');
    
    try {
      const result = execSync(`node ${args}`, { encoding: 'utf-8', stdio: ['pipe', 'pipe', 'pipe'] });
      const successMatch = result.match(/Success:\s*(\d+)/);
      const failMatch = result.match(/Failed:\s*(\d+)/);
      if (successMatch) successCount += parseInt(successMatch[1]);
      if (failMatch) failCount += parseInt(failMatch[1]);
      console.log(`  Batch ${Math.floor(i/BATCH_SIZE)+1}/${Math.ceil(files.length/BATCH_SIZE)}: ${batch.length} files done`);
    } catch(e) {
      console.log(`  Batch ${Math.floor(i/BATCH_SIZE)+1} FAILED: ${e.message}`);
      failCount += batch.length;
    }
  }
  
  console.log(`  Total: ${successCount} success, ${failCount} failed`);
  return { success: successCount, fail: failCount };
}

const clientResult = processBatch(clientCss, clientFiles, 'client');
const workerResult = processBatch(workerCss, workerFiles, 'worker');

console.log('\n=== FINAL SUMMARY ===');
console.log(`Client: ${clientResult.success}/${clientFiles.length} success, ${clientResult.fail} failed`);
console.log(`Worker: ${workerResult.success}/${workerFiles.length} success, ${workerResult.fail} failed`);
