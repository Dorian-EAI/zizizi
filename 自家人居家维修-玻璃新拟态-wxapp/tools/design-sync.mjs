import { createHash } from 'node:crypto'
import { existsSync, readFileSync, statSync, writeFileSync } from 'node:fs'
import { dirname, join, relative, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const sourceRoot = resolve(root, '..', 'zjrnew')
const designFile = join(sourceRoot, 'zjrnew.design')
const canonicalStyleFile = resolve(root, '..', 'docs', 'design', '样式规范详尽文档.md')
const stateFile = join(root, 'design-sync.state.json')
const reportFile = join(root, 'DESIGN_SYNC_REPORT.md')
const accept = process.argv.includes('--accept')
const design = JSON.parse(readFileSync(designFile, 'utf8'))

const sha = file => createHash('sha256').update(readFileSync(file)).digest('hex').slice(0, 12)
function fnv1a(text) {
  let value = 0x811c9dc5
  for (let index = 0; index < text.length; index += 1) {
    value ^= text.charCodeAt(index)
    value = Math.imul(value, 0x01000193) >>> 0
  }
  return `fnv1a-${value.toString(16).padStart(8, '0')}`
}
function targetFor(source) {
  const name = source.split('/').pop().replace(/\.html$/, '')
  if (name.startsWith('client-home-glass-neu')) return 'client-home'
  if (name === 'client-address') return 'address'
  if (name === 'client-order-detail') return 'order-detail-client'
  if (name === 'worker-order-detail') return 'order-detail-worker'
  if (name === 'client-order-tracking-2') return 'client-order-tracking'
  return name
}

const nodes = design.data.map(node => {
  const source = node.devMetadata?.htmlSrc
  const sourceFile = source && join(sourceRoot, source)
  const target = source ? `pages/${targetFor(source)}` : ''
  const targetDir = join(root, target)
  const snapshot = node.canvasData?.layoutSnapshot || {}
  const actualHash = sourceFile && existsSync(sourceFile) ? fnv1a(readFileSync(sourceFile, 'utf8')) : ''
  const complete = target && ['index.js', 'index.json', 'index.wxml', 'index.wxss']
    .every(name => existsSync(join(targetDir, name)) && statSync(join(targetDir, name)).size > 0)
  return {
    id: node.id, title: node.title, source, target, complete,
    width: snapshot.viewportWidth, height: snapshot.contentHeight,
    expectedHash: snapshot.sourceHash, actualHash,
    interactions: node.devMetadata?.interactions || []
  }
})

const globalSources = [canonicalStyleFile, join(sourceRoot, '小程序动画与布局实现规范.md'), join(sourceRoot, 'colors_and_type.css')]
const tracked = [designFile, ...new Set(nodes.map(node => join(sourceRoot, node.source))), ...globalSources]
const current = Object.fromEntries(tracked.map(file => [relative(sourceRoot, file).replaceAll('\\', '/'), sha(file)]))
const previous = existsSync(stateFile) ? JSON.parse(readFileSync(stateFile, 'utf8')).files || {} : {}
const changed = Object.keys(current).filter(file => current[file] !== previous[file])
const designSources = new Set(['zjrnew.design', ...nodes.map(node => node.source)])
const canonicalStyleKey = relative(sourceRoot, canonicalStyleFile).replaceAll('\\', '/')
function sourceRole(file) {
  if (file === 'zjrnew.design') return '已登记页面的具体画面来源'
  if (designSources.has(file)) return '画布登记渲染源'
  if (file === canonicalStyleKey) return '样式规范事实源（需与评审画布一致）'
  if (file === '小程序动画与布局实现规范.md') return '小程序特殊动效与布局实现规范'
  return '视觉实现参考（需同时符合样式规范与评审画布）'
}
const staleSnapshots = nodes.filter(node => node.expectedHash !== node.actualHash)
const missing = nodes.filter(node => !node.complete)
const invalidInteractions = nodes.flatMap(node => node.interactions
  .filter(link => !nodes.some(candidate => candidate.id === link.targetPageId))
  .map(link => `${node.id}:${link.domId} → ${link.targetPageId}`))
const uniqueTargets = new Set(nodes.map(node => node.target))

const cssSource = readFileSync(join(sourceRoot, 'colors_and_type.css'), 'utf8')
const cssTarget = readFileSync(join(root, 'app.wxss'), 'utf8')
const tokenNames = ['brand', 'brand-dark', 'brand-mid', 'accent', 'background', 'text-1', 'text-2', 'neu-light', 'neu-dark']
const token = (css, name) => css.match(new RegExp(`--${name}\\s*:\\s*([^;]+);`))?.[1].trim().toLowerCase()
const tokenDiffs = tokenNames.filter(name => token(cssSource, name) !== token(cssTarget, name))

const lines = [
  '# zjrnew.design 强一致性报告', '',
  '> 自动生成的视觉同步报告；适用产品规则 v6.2。  ',
  '> 业务规则以 PRD 为准；交互与样式规范定义体验和视觉系统，评审后的 `../zjrnew/zjrnew.design` 表达已登记页面的具体画面。  ',
  '> “通过”只表示画布节点、登记渲染源、目标四件套与辅助视觉令牌一致，不表示路由、按钮、接口或完整用户任务可用。', '',
  `- 设计节点：${nodes.length}`,
  `- 小程序目标页面：${uniqueTargets.size}`,
  `- 节点映射完整：${nodes.length - missing.length}/${nodes.length}`,
  `- 画布快照哈希异常：${staleSnapshots.length}`,
  `- 无效交互目标：${invalidInteractions.length}`,
  `- 核心令牌差异：${tokenDiffs.length}`,
  `- 基线后变更文件：${changed.length}`,
  '- 功能可用性：本报告不评估，须按 PRD 与交互文档单独验收', '',
  '## 检测到的源变更（未验收 / 未接受基线）', '',
  '> 下列文件相对已接受基线发生变化。本报告只检测，不代表已完成视觉迁移，也不会自动接受新基线。', '',
  ...(changed.length ? changed.map(file => `- \`${file}\` — ${sourceRole(file)}`) : ['- 无']), '',
  '## 设计节点映射', '',
  '| Design ID | 标题 | HTML 源 | 画布 | 小程序目标 | 校验 |', '|---|---|---|---:|---|---|',
  ...nodes.map(node => `| \`${node.id}\` | ${node.title} | \`${node.source}\` | ${node.width}×${node.height} | \`${node.target}\` | ${node.complete && node.expectedHash === node.actualHash ? '通过' : '异常'} |`),
  '', '## 强校验异常', '',
  ...(staleSnapshots.length ? staleSnapshots.map(node => `- 快照过期：\`${node.id}\` 期望 ${node.expectedHash}，实际 ${node.actualHash}`) : ['- `.design` sourceHash 与 HTML 全部一致']),
  ...(missing.length ? missing.map(node => `- 页面缺失：\`${node.id}\` → \`${node.target}\``) : []),
  ...(invalidInteractions.length ? invalidInteractions.map(item => `- 交互目标无效：${item}`) : []),
  ...(tokenDiffs.length ? tokenDiffs.map(name => `- 令牌差异：\`--${name}\``) : []), '',
  '## 报告边界', '',
  '- 业务规则唯一事实源：`../PRD_v6.0.md`（正文 v6.2）。',
  '- 入口、操作与异常恢复以 `../docs/design/功能与交互文档.md` 为准；Token、组件、布局规则与动效边界以 `../docs/design/样式规范详尽文档.md` 为准。',
  '- 评审后的 `../zjrnew/zjrnew.design` 表达已登记页面的具体几何与画面；若与上级规范冲突，暂停同步并先完成评审和源文件修订。',
  '- `../zjrnew/小程序动画与布局实现规范.md`、HTML/CSS 与小程序代码是特殊动效、布局或运行实现，不得自行反向修改规范或画布。',
  '- `.design` 的交互元数据只用于视觉热点和页面映射；按钮权限、状态迁移、支付与资金结果仍以 PRD 和服务端契约为准。',
  '- `page-worker-recharge` 是历史视觉节点：v6.2 不开放师傅收入钱包充值，节点“通过”不代表可注册入口或支付动作。',
  '- 首页与实时追踪的两个节点是同一页面的滚动状态，不是两条产品路由。',
  '- 正式发布还必须验证双角色切换、双端四项 Tab、稳定入口、订单多轴状态、AI/订单聊天/人工客服分流、权限、支付、位置和资金闭环。', ''
]
writeFileSync(reportFile, lines.join('\n'), 'utf8')

const failed = staleSnapshots.length || missing.length || invalidInteractions.length || tokenDiffs.length
if (accept && !failed) {
  writeFileSync(stateFile, `${JSON.stringify({ version: 2, authority: 'zjrnew/zjrnew.design', acceptedAt: new Date().toISOString(), files: current }, null, 2)}\n`, 'utf8')
  console.log(`已确认 .design 基线：${nodes.length} 个设计节点，${uniqueTargets.size} 个目标页面`)
} else {
  console.log(`设计节点 ${nodes.length}，缺失 ${missing.length}，快照异常 ${staleSnapshots.length}，交互异常 ${invalidInteractions.length}，变更 ${changed.length}`)
  if (!accept && changed.length) console.log('检测到未验收源变更；未接受新基线。')
}
if (failed || (!accept && changed.length)) process.exitCode = 1
