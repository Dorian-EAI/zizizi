import { readFileSync } from 'fs';

const report = JSON.parse(readFileSync('c:\\Users\\12620\\Desktop\\zi\\zjrnew\\validation-report.json', 'utf-8'));

console.log('=== REPAIR PLAN HINTS ===');
console.log(JSON.stringify(report.repairPlanHints, null, 2));

console.log('\n=== REPAIR ACTION TABLE ===');
if (report.repairActionTable) {
  report.repairActionTable.forEach((action, i) => {
    console.log(`${i+1}. errorClass: ${action.errorClass}`);
    console.log(`   owner: ${action.owner}`);
    console.log(`   requiredAction: ${action.requiredAction}`);
    console.log(`   affectedCount: ${action.affectedFiles?.length || 0}`);
    if (action.affectedFiles && action.affectedFiles.length <= 5) {
      console.log(`   files: ${action.affectedFiles.join(', ')}`);
    } else if (action.affectedFiles) {
      console.log(`   first 5 files: ${action.affectedFiles.slice(0, 5).join(', ')}`);
    }
    console.log('');
  });
}

console.log('=== RENDER BLOCKING vs SOFT ===');
console.log('renderBlockingErrorCount:', report.renderBlockingErrorCount);
console.log('softWarningCount:', report.softWarningCount);
console.log('errorCount:', report.errorCount);
console.log('warningCount:', report.warningCount);
