import { spawnSync } from 'node:child_process'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const checks = [
  { name: '小程序运行完整性', script: 'tools/runtime-integrity.mjs' },
  { name: 'zjrnew.design 同步状态', script: 'tools/design-sync.mjs' }
]

let failed = false
for (const check of checks) {
  console.log(`\n[发布门禁] ${check.name}`)
  const result = spawnSync(process.execPath, [check.script], {
    cwd: root,
    stdio: 'inherit'
  })
  if (result.error) {
    console.error('[发布门禁] 无法执行：' + result.error.message)
    failed = true
  } else if (result.status !== 0) {
    console.error(`[发布门禁] 未通过：${check.name}（exit ${result.status}）`)
    failed = true
  }
}

if (failed) {
  console.error('\n发布门禁未通过，禁止上传体验版或正式版。')
  process.exitCode = 1
} else {
  console.log('\n发布门禁全部通过，可以进入微信开发者工具人工验收与上传步骤。')
}
