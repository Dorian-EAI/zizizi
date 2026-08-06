import { existsSync, readFileSync, writeFileSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const sourceRoot = resolve(root, '..', 'zjrnew')
const designFile = join(sourceRoot, 'zjrnew.design')
const reportFile = join(root, 'DESIGN_PIXEL_AUDIT.md')
const strict = process.argv.includes('--strict')

const effectTokens = [
  'linear-gradient',
  'radial-gradient',
  'box-shadow',
  'backdrop-filter',
  '-webkit-backdrop-filter',
  'border-radius',
  'transition',
  'transform',
  'opacity',
  'filter:',
  'position:sticky',
  'position:fixed'
]
const ignoredClasses = new Set([
  'light',
  'phone',
  'no-scrollbar',
  'tag-span',
  'tag-p',
  'tag-h1',
  'tag-h2',
  'tag-h3',
  'tag-small',
  'tag-strong',
  'design-button',
  'design-detail-page',
  'design-canvas-page'
])

function readText(file) {
  return existsSync(file) ? readFileSync(file, 'utf8') : ''
}

function targetFor(source) {
  let name = String(source || '').split('/').pop().replace(/\.html$/i, '')
  if (name.startsWith('client-home-glass-neu')) name = 'client-home'
  else if (name === 'client-address') name = 'address'
  else if (name === 'client-order-detail') name = 'order-detail-client'
  else if (name === 'worker-order-detail') name = 'order-detail-worker'
  else if (name === 'client-order-tracking-2') name = 'client-order-tracking'
  return name
}

function classNames(markup) {
  const names = new Set()
  const pattern = /\bclass=(['"])(.*?)\1/gi
  let match
  while ((match = pattern.exec(markup))) {
    for (const name of match[2].split(/\s+/).filter(Boolean)) names.add(name)
  }
  return names
}

function extractDesignMarkup(html) {
  const main = html.match(/<main\b[^>]*>[\s\S]*?<\/main>/i)
  if (main) return main[0]
  const body = html.match(/<body\b[^>]*>([\s\S]*?)<\/body>/i)?.[1] || html
  const beforeBodyStyle = body.split(/<style\b/i)[0]
  const phone = beforeBodyStyle.match(/<div\b[^>]*\bclass=(['"])[^'"]*\bphone\b[^'"]*\1[^>]*>[\s\S]*<\/div>\s*$/i)
  return phone ? phone[0] : beforeBodyStyle
}

function styleBlocks(html) {
  const blocks = []
  const stylePattern = /<style\b[^>]*>([\s\S]*?)<\/style>/gi
  let match
  while ((match = stylePattern.exec(html))) {
    const css = match[1].trim()
    if (!css || css.includes('@theme inline') || css.includes('#semantic-token-fallback')) continue
    blocks.push(css)
  }
  if (/(?:^|\/)detail-page\.css(?:['"]|\?)/.test(html)) {
    blocks.push(readText(join(sourceRoot, 'assets', 'detail-page.css')))
  }
  return blocks.join('\n')
}

function readWxssWithImports(file, seen = new Set()) {
  if (!existsSync(file) || seen.has(file)) return ''
  seen.add(file)
  let css = readText(file)
  css = css.replace(/@import\s+(['"])(.*?)\1\s*;/g, (_, quote, target) => {
    const imported = resolve(dirname(file), target)
    return readWxssWithImports(imported, seen)
  })
  return css
}

function effectClasses(css) {
  const classes = new Set()
  const rulePattern = /([^{}]+)\{([^{}]*)\}/g
  let match
  while ((match = rulePattern.exec(css))) {
    const selector = match[1].trim()
    const body = match[2].replace(/\s+/g, '')
    const hasEffect = selector.includes(':active') ||
      selector.includes('::before') ||
      selector.includes('::after') ||
      effectTokens.some(token => body.includes(token.replace(/\s+/g, '')))
    if (!hasEffect) continue
    const classPattern = /\.([A-Za-z0-9_-]+)/g
    let classMatch
    while ((classMatch = classPattern.exec(selector))) classes.add(classMatch[1])
  }
  return classes
}

function escapedRegExp(value) {
  return String(value).replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

function hasRuntimeClassPrefix(targetWxml, prefix) {
  return new RegExp(`${escapedRegExp(prefix)}-\\s*\\{\\{`).test(targetWxml) ||
    new RegExp(`${escapedRegExp(prefix)}-\\{\\{`).test(targetWxml)
}

function coveredByRuntimeClass(name, targetWxml, targetClassSet, targetStyleSet) {
  if (name === 'tab-bar' || name === 'tab-item') {
    return targetWxml.includes('<tab-bar') && (targetStyleSet.has('tab-bar') || targetStyleSet.has('tab-item'))
  }
  if (name === 'green') {
    return targetWxml.includes('green') && (targetStyleSet.has('green') || targetStyleSet.has('text-green'))
  }
  if (name === 'level-tier-current') {
    return targetWxml.includes('level-tier-current') && targetStyleSet.has('level-tier-current')
  }
  if (name.startsWith('menu-icon-')) {
    return hasRuntimeClassPrefix(targetWxml, 'menu-icon') &&
      (targetClassSet.has('menu-icon') || targetClassSet.has('menu-icon-wrap') || targetClassSet.has('info-menu-icon')) &&
      targetStyleSet.has(name)
  }
  if (name.startsWith('benefit-icon-')) {
    return hasRuntimeClassPrefix(targetWxml, 'benefit-icon') &&
      targetClassSet.has('benefit-icon') &&
      targetStyleSet.has(name)
  }
  if (name.startsWith('level-tier-icon-')) {
    return hasRuntimeClassPrefix(targetWxml, 'level-tier-icon') &&
      targetClassSet.has('level-tier-icon') &&
      targetStyleSet.has(name)
  }
  if (name.startsWith('tl-dot-')) {
    return hasRuntimeClassPrefix(targetWxml, 'tl-dot') &&
      targetClassSet.has('tl-dot') &&
      targetStyleSet.has(name)
  }
  if (name.startsWith('tl-label-')) {
    return hasRuntimeClassPrefix(targetWxml, 'tl-label') &&
      targetClassSet.has('tl-label') &&
      targetStyleSet.has(name)
  }
  if (name.startsWith('bubble-')) {
    return hasRuntimeClassPrefix(targetWxml, 'bubble') &&
      targetClassSet.has('bubble') &&
      targetStyleSet.has(name)
  }
  return false
}

function sortedDiff(source, target, isCovered = () => false) {
  return [...source].filter(item => !target.has(item) && !ignoredClasses.has(item) && !isCovered(item)).sort()
}

function count(pattern, text) {
  return (text.match(pattern) || []).length
}

const design = JSON.parse(readText(designFile))
const appCss = readText(join(root, 'app.wxss'))
const componentCss = readWxssWithImports(join(root, 'components', 'tab-bar', 'index.wxss'))
const seenRoutes = new Set()
const rows = []

for (const node of design.data || []) {
  const source = node.devMetadata?.htmlSrc
  if (!source || !source.endsWith('.html')) continue
  const pageName = targetFor(source)
  const route = `pages/${pageName}/index`
  if (seenRoutes.has(route)) continue
  seenRoutes.add(route)

  const sourceHtml = readText(join(sourceRoot, source))
  const sourceMarkup = extractDesignMarkup(sourceHtml)
  const sourceCss = styleBlocks(sourceHtml)
  const targetWxml = readText(join(root, 'pages', pageName, 'index.wxml'))
  const targetCss = readWxssWithImports(join(root, 'pages', pageName, 'index.wxss')) + '\n' + appCss + '\n' + componentCss
  const sourceClassSet = classNames(sourceMarkup)
  const targetClassSet = classNames(targetWxml)
  const sourceEffectSet = effectClasses(sourceCss)
  const targetStyleSet = classNames(targetCss.replace(/\.([A-Za-z0-9_-]+)/g, ' class="$1"'))

  const isCovered = name => coveredByRuntimeClass(name, targetWxml, targetClassSet, targetStyleSet)
  const missingClasses = sortedDiff(sourceClassSet, targetClassSet, isCovered)
  const missingEffects = sortedDiff(new Set([...sourceEffectSet].filter(name => sourceClassSet.has(name))), targetStyleSet, isCovered)
  const warnings = []
  const sourceSvg = count(/<svg\b/gi, sourceMarkup)
  const targetImage = count(/<image\b/gi, targetWxml)

  if (missingClasses.length > 12) warnings.push(`结构类缺口 ${missingClasses.length}`)
  if (missingEffects.length > 6) warnings.push(`效果类缺口 ${missingEffects.length}`)
  if (sourceSvg > 0 && targetImage === 0) warnings.push(`源 SVG ${sourceSvg} 个，目标无 image`)
  if (sourceCss.includes('backdrop-filter') && !targetCss.includes('backdrop-filter')) warnings.push('缺少玻璃模糊')
  if (sourceCss.includes(':active') && !targetCss.includes(':active')) warnings.push('缺少按压态')
  if (sourceCss.includes('linear-gradient') && !targetCss.includes('linear-gradient')) warnings.push('缺少渐变')

  rows.push({
    id: node.id,
    title: node.title,
    route,
    source,
    warnings,
    missingClasses: missingClasses.slice(0, 10),
    missingEffects: missingEffects.slice(0, 10)
  })
}

const risky = rows.filter(row => row.warnings.length)
const lines = [
  '# zjrnew.design 像素复刻审计',
  '',
  '> 自动生成的预审报告。它检查源 HTML/CSS 与小程序 WXML/WXSS 的结构类、效果类、渐变、阴影、玻璃模糊、按压态和 SVG 图标迁移风险；最终像素验收仍以微信开发者工具截图 50% 叠加差分为准。',
  '',
  `- 设计目标页：${rows.length}`,
  `- 需人工复核页：${risky.length}`,
  `- 严格模式：${strict ? '开启' : '关闭'}`,
  '',
  '## 需人工复核',
  '',
  ...(risky.length ? risky.map(row => [
    `### ${row.id} — ${row.title}`,
    `- 目标：\`${row.route}\``,
    `- 源：\`${row.source}\``,
    `- 风险：${row.warnings.join('；')}`,
    row.missingClasses.length ? `- 结构类示例：${row.missingClasses.map(name => `\`${name}\``).join('、')}` : '',
    row.missingEffects.length ? `- 效果类示例：${row.missingEffects.map(name => `\`${name}\``).join('、')}` : ''
  ].filter(Boolean).join('\n')) : ['- 无命令行可识别风险']),
  '',
  '## 审计边界',
  '',
  '- 本脚本不接受设计基线，不替代 `tools/design-sync.mjs`。',
  '- 业务真实性仍按 PRD 与运行门禁执行；示例金额、示例记录和未开放能力不得为了视觉复刻被写入运行态。',
  '- 对首页和实时追踪的滚动中间态，还需要按 md 要求截取起点、中间态、终点三帧。'
]

writeFileSync(reportFile, lines.join('\n') + '\n', 'utf8')

console.log(`像素复刻审计：${rows.length} 页，需人工复核 ${risky.length} 页。报告：DESIGN_PIXEL_AUDIT.md`)
if (strict && risky.length) process.exitCode = 1
