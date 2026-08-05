import { readFileSync } from 'fs';

const report = JSON.parse(readFileSync('c:\\Users\\12620\\Desktop\\zi\\zjrnew\\validation-report.json', 'utf-8'));

console.log('=== VALIDATION SUMMARY ===');
console.log('Success:', report.success);
console.log('Errors:', report.errorCount);
console.log('Warnings:', report.warningCount);
console.log('Keys:', Object.keys(report).join(', '));

if (report.errors && report.errors.length > 0) {
  console.log('\n--- ERRORS ---');
  report.errors.forEach((e, i) => {
    console.log(i+1 + '. ruleId: ' + (e.ruleId || 'N/A'));
    console.log('   msg: ' + JSON.stringify(e).substring(0, 200));
  });
}

// Check structure
console.log('\n--- REPORT STRUCTURE ---');
console.log('Has issues:', !!report.issues);
console.log('Has checks:', !!report.checks);
console.log('Has results:', !!report.results);

if (report.issues) {
  console.log('Issues count:', report.issues.length);
  const issueTypes = {};
  report.issues.forEach(iss => {
    const type = iss.severity + ':' + (iss.ruleId || iss.code || 'unknown');
    issueTypes[type] = (issueTypes[type] || 0) + 1;
  });
  console.log('Issue types:');
  Object.entries(issueTypes).sort().forEach(([type, count]) => {
    console.log('  ' + type + ': ' + count);
  });
}
