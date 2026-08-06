import { createHash } from 'node:crypto'
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const designRoot = resolve(root, '..', 'zjrnew')
const designFile = join(designRoot, 'zjrnew.design')
const appFile = join(root, 'app.json')
const manifestFile = join(root, 'tools', 'design-pages.manifest.json')
const sharedStyleFile = join(root, 'styles', 'generated-detail-page.wxss')
const pageStyleDir = join(root, 'styles', 'generated-design-pages')
const write = process.argv.includes('--write')
const register = process.argv.includes('--register')
const forceView = process.argv.includes('--force-view')
const refreshGenerated = process.argv.includes('--refresh-generated')
const onlyArg = process.argv.find(item => item.startsWith('--only='))
const only = onlyArg
  ? new Set(onlyArg.slice('--only='.length).split(',').map(item => item.trim()).filter(Boolean))
  : null

function readJson(file) {
  return JSON.parse(readFileSync(file, 'utf8'))
}

function sha256(value) {
  return createHash('sha256').update(value).digest('hex')
}

function targetName(source) {
  let name = String(source || '').split('/').pop().replace(/\.html$/i, '')
  if (name.startsWith('client-home-glass-neu')) name = 'client-home'
  else if (name === 'client-address') name = 'address'
  else if (name === 'client-order-detail') name = 'order-detail-client'
  else if (name === 'worker-order-detail') name = 'order-detail-worker'
  else if (name === 'client-order-tracking-2') name = 'client-order-tracking'
  return name
}

function routeForSource(source) {
  return `pages/${targetName(source)}/index`
}

function addClass(attributes, names) {
  const additions = names.filter(Boolean)
  if (!additions.length) return attributes
  const match = attributes.match(/\sclass=(['"])(.*?)\1/i)
  if (match) {
    const value = [...new Set(match[2].split(/\s+/).concat(additions).filter(Boolean))].join(' ')
    return attributes.replace(match[0], ` class="${value}"`)
  }
  return `${attributes} class="${additions.join(' ')}"`
}

function pxToRpx(value) {
  return String(value).replace(/(-?\d*\.?\d+)px\b/gi, (_, raw) => {
    const converted = Number(raw) * 2
    return `${Number.isInteger(converted) ? converted : Number(converted.toFixed(4))}rpx`
  })
}

function decodeEntities(value) {
  const entities = {
    '&nbsp;': ' ', '&copy;': '©', '&reg;': '®', '&trade;': '™',
    '&middot;': '·', '&yen;': '¥', '&amp;': '&', '&lt;': '＜', '&gt;': '＞',
    '&quot;': '"', '&#39;': "'"
  }
  let result = value.replace(/&(nbsp|copy|reg|trade|middot|yen|amp|lt|gt|quot);|&#39;/g, token => entities[token] || token)
  result = result.replace(/&#(\d+);/g, (_, code) => String.fromCodePoint(Number(code)))
  return result
}

function dataUriForSvg(svg, color) {
  let normalized = svg
    .replace(/\s+/g, ' ')
    .replace(/>\s+</g, '><')
    .trim()
    .replace(/currentColor/g, color)
    .replace(/^<svg\b(?![^>]*\sxmlns=)/i, '<svg xmlns="http://www.w3.org/2000/svg"')
  normalized = normalized.replace(/^<svg\b([^>]*)>/i, (whole, attributes) => {
    let next = attributes
    if (!/\sfill=/.test(next)) next += ' fill="none"'
    if (!/\sstroke=/.test(next)) next += ` stroke="${color}"`
    if (!/\sstroke-width=/.test(next)) next += ' stroke-width="1.8"'
    if (!/\sstroke-linecap=/.test(next)) next += ' stroke-linecap="round"'
    if (!/\sstroke-linejoin=/.test(next)) next += ' stroke-linejoin="round"'
    return `<svg${next}>`
  })
  return `data:image/svg+xml;utf8,${encodeURIComponent(normalized)}`
}

function unitToRpx(value) {
  const raw = String(value || '').trim()
  if (!raw) return ''
  if (/^-?\d*\.?\d+$/.test(raw)) return pxToRpx(`${raw}px`)
  return pxToRpx(raw)
}

function iconColorForContext(context, worker) {
  const brand = worker ? '#2D6CDF' : '#0D9488'
  if (/\b(success|text-success)\b/i.test(context)) return '#5B8C5A'
  if (/\b(warning|pending)\b/i.test(context)) return '#D4944C'
  if (/\b(danger|text-danger|error)\b/i.test(context)) return '#C4533A'
  if (/\b(info)\b/i.test(context)) return '#5A8FAD'
  if (/\b(row-icon|empty-icon|upload-icon|inline-icon|media-placeholder|media-visual|service-glyph|play-icon|icon-action|top-action)\b/i.test(context)) return brand
  return '#2C2824'
}

function replaceInlineSvg(fragment, worker) {
  return fragment.replace(/<svg\b[\s\S]*?<\/svg>/gi, (svg, offset) => {
    const context = fragment.slice(Math.max(0, offset - 260), offset)
    const width = unitToRpx(svg.match(/(?<![A-Za-z0-9_-])width=(['"])(.*?)\1/i)?.[2])
    const height = unitToRpx(svg.match(/(?<![A-Za-z0-9_-])height=(['"])(.*?)\1/i)?.[2])
    const style = [width ? `width:${width}` : '', height ? `height:${height}` : ''].filter(Boolean).join(';')
    return `<img class="design-svg-icon" src="${dataUriForSvg(svg, iconColorForContext(context, worker))}"${style ? ` style="${style}"` : ''}>`
  })
}

function extractDivByClass(html, className) {
  const openRe = new RegExp(`<div\\b([^>]*\\bclass=(['"])[^'"]*\\b${className}\\b[^'"]*\\2[^>]*)>`, 'i')
  const open = openRe.exec(html)
  if (!open) return null

  const start = open.index
  const innerStart = start + open[0].length
  const tagRe = /<\/?div\b[^>]*>/gi
  tagRe.lastIndex = start
  let depth = 0
  let match
  while ((match = tagRe.exec(html))) {
    const tag = match[0]
    if (tag.startsWith('</')) depth -= 1
    else if (!/\/\s*>$/.test(tag)) depth += 1
    if (depth === 0) {
      return {
        tag: 'div',
        attributes: open[1],
        inner: html.slice(innerStart, match.index)
      }
    }
  }
  return null
}

function extractDesignRoot(html, node) {
  const main = html.match(/<main\b([^>]*)>([\s\S]*?)<\/main>/i)
  if (main) return { tag: 'main', attributes: main[1], inner: main[2] }

  const body = html.match(/<body\b[^>]*>([\s\S]*?)<\/body>/i)?.[1] || html
  const phoneRoot = extractDivByClass(body, 'phone')
  if (phoneRoot) return phoneRoot

  const beforeBodyStyle = body.split(/<style\b/i)[0]
  const phone = beforeBodyStyle.match(/<div\b([^>]*\bclass=(['"])[^'"]*\bphone\b[^'"]*\2[^>]*)>([\s\S]*?)<\/div>\s*$/i)
  if (phone) return { tag: 'div', attributes: phone[1], inner: phone[3] }

  throw new Error(`${node.devMetadata.htmlSrc} 缺少 <main> 或 .phone 画布根节点`)
}

const targetAliases = new Map([
  ['page-client-home', 'page-client-home-glass-neu-contrast-1'],
  ['page-client-notifications', 'page-client-notification'],
  ['page-client-auth-management', 'page-client-auth'],
  ['page-client-user-agreement', 'page-client-agreement'],
  ['page-client-privacy-policy', 'page-client-privacy']
])

function resolveTargetRoute(idToRoute, rawId) {
  return idToRoute.get(rawId) || idToRoute.get(targetAliases.get(rawId))
}

function convertHtml(html, node, idToRoute) {
  const designRootNode = extractDesignRoot(html, node)
  const worker = /<html\b[^>]*data-role=['"]worker['"]/i.test(html) || /\bworker-theme\b/.test(designRootNode.attributes)
  let fragment = `<${designRootNode.tag}${designRootNode.attributes}>${designRootNode.inner}</${designRootNode.tag}>`
    .replace(/<!--[\s\S]*?-->/g, '')
    .replace(/<script\b[\s\S]*?<\/script>/gi, '')
  fragment = replaceInlineSvg(fragment, worker)

  fragment = fragment.replace(/<([a-z][\w-]*)([^>]*)>/gi, (whole, rawTag, rawAttributes) => {
    const tag = rawTag.toLowerCase()
    if (tag === 'br') return '<text class="design-br">\n</text>'
    let attributes = (rawAttributes || '').replace(/\s*\/\s*$/, '')
    const target = attributes.match(/\sdata-target-page=(['"])(.*?)\1/i)
    const action = attributes.match(/\sdata-action=(['"])(.*?)\1/i)

    attributes = attributes
      .replace(/\s(?:aria-[\w-]+|role|tabindex|type)=(['"])[\s\S]*?\1/gi, '')
      .replace(/\s(?:disabled|checked|selected|readonly|required)\b(?:=(['"])[\s\S]*?\1)?/gi, '')
      .replace(/\sdata-target-page=(['"])[\s\S]*?\1/gi, '')
      .replace(/\sstyle=(['"])(.*?)\1/gi, (_, quote, style) => ` style=${quote}${pxToRpx(style)}${quote}`)

    if (target) {
      const [rawId, query = ''] = target[2].split('?')
      const route = resolveTargetRoute(idToRoute, rawId)
      if (!route) throw new Error(`${node.id} 的交互目标不存在：${target[2]}`)
      attributes += ` data-route="/${route}${query ? `?${query}` : ''}" bindtap="onNavigate"`
    } else if (action) {
      if (tag === 'input' || tag === 'textarea' || tag === 'select') attributes += ' bindchange="onAction"'
      else attributes += ' bindtap="onAction"'
    }

    const classNames = []
    let mapped = 'view'
    if (tag === 'main') {
      classNames.push('design-detail-page')
      if (worker) classNames.push('worker-theme')
    } else if (/\bclass=(['"])[^'"]*\bphone\b/i.test(attributes)) {
      classNames.push('design-canvas-page')
      if (worker) classNames.push('worker-theme')
    } else if (tag === 'button' || tag === 'a') {
      classNames.push('design-button')
    } else if (/^h[1-6]$/.test(tag) || ['p', 'span', 'strong', 'b', 'small', 'em', 'label'].includes(tag)) {
      mapped = tag === 'p' || /^h[1-6]$/.test(tag) ? 'view' : 'text'
      classNames.push(`tag-${tag}`)
    } else if (tag === 'input' || tag === 'textarea') {
      mapped = tag
    } else if (tag === 'img') {
      mapped = 'image'
      if (!/\smode=/.test(attributes)) attributes += ' mode="aspectFill"'
    } else if (tag === 'select') {
      mapped = 'view'
      classNames.push('design-select')
    } else if (tag === 'option') {
      mapped = 'text'
      classNames.push('design-option')
    }
    attributes = addClass(attributes, classNames)
    const selfClose = mapped === 'input' || mapped === 'image'
    return `<${mapped}${attributes}${selfClose ? ' /' : ''}>`
  })

  const closeMap = {
    view: 'view', text: 'text',
    main: 'view', header: 'view', footer: 'view', section: 'view', article: 'view', nav: 'view',
    form: 'view', div: 'view', ul: 'view', ol: 'view', li: 'view', button: 'view', a: 'view',
    p: 'view', h1: 'view', h2: 'view', h3: 'view', h4: 'view', h5: 'view', h6: 'view',
    span: 'text', strong: 'text', b: 'text', small: 'text', em: 'text', label: 'text', textarea: 'textarea',
    select: 'view', option: 'text', table: 'view', thead: 'view', tbody: 'view', tr: 'view', td: 'view', th: 'view'
  }
  fragment = fragment.replace(/<\/([a-z][\w-]*)>/gi, (_, rawTag) => `</${closeMap[rawTag.toLowerCase()] || 'view'}>`)
  fragment = fragment.replace(/<\/(?:input|img)>/gi, '')
  fragment = fragment.replace(
    /<text([^>]*\bclass=(['"])[^'"]*\b(?:row-icon|empty-icon|result-icon|inline-icon|upload-icon|map-pin)\b[^'"]*\2[^>]*)>\s*(<image\b[\s\S]*?\/>)\s*<\/text>/gi,
    '<view$1>$3</view>'
  )
  fragment = decodeEntities(fragment)
  return `<!-- AUTO-GENERATED DESIGN VIEW sourceHash=${node.canvasData.layoutSnapshot.sourceHash}; edit source HTML or generator bindings, then rerun. -->\n${fragment.trim()}\n`
}

function normalizeCssForWxss(css, rootClass) {
  return pxToRpx(css)
    .replace(/:root\s*\{/g, 'page {')
    .replace(/html\[data-role="worker"\]\s*\{/g, '.worker-theme {')
    .replace(/html,\s*body\s*\{/g, 'page {')
    .replace(/(?<![A-Za-z0-9_.-])body\s*\{/g, 'page {')
    .replace(/\.phone-page\b/g, rootClass)
    .replace(/\.phone\b/g, rootClass)
    .replace(/^\s*\*\s*\{/gm, 'view, text, image, input, textarea, .design-button, .design-select, .design-option {')
    .replace(/(?<![A-Za-z0-9_.-])button\.([A-Za-z0-9_-]+)/g, '.design-button.$1')
    .replace(/(?<![A-Za-z0-9_.-])button(?![A-Za-z0-9_-])/g, '.design-button')
    .replace(/(?<![A-Za-z0-9_.-])select(?![A-Za-z0-9_-])/g, '.design-select')
    .replace(/(?<![A-Za-z0-9_.-])svg(?![A-Za-z0-9_-])/g, '.design-svg-icon')
    .replace(/(?<![A-Za-z0-9_.-])small(?![A-Za-z0-9_-])/g, '.tag-small')
    .replace(/(?<![A-Za-z0-9_.-])strong(?![A-Za-z0-9_-])/g, '.tag-strong')
    .replace(/(?<![A-Za-z0-9_.-])h1(?![A-Za-z0-9_-])/g, '.tag-h1')
    .replace(/(?<![A-Za-z0-9_.-])h2(?![A-Za-z0-9_-])/g, '.tag-h2')
    .replace(/(?<![A-Za-z0-9_.-])h3(?![A-Za-z0-9_-])/g, '.tag-h3')
    .replace(/(?<![A-Za-z0-9_.-])p(?![A-Za-z0-9_-])/g, '.tag-p')
    .replace(/color-mix\(in srgb,\s*var\(--brand\)[^)]*\)/g, 'var(--brand-soft)')
    .replace(/color-mix\(in srgb,\s*var\(--accent\)[^)]*\)/g, 'var(--accent-soft)')
    .replace(/translate:\s*([^;\s]+)\s+([^;\s]+)\s*;/g, 'transform: translate($1, $2);')
    .replace(/@media \(max-width:[\s\S]*?\}\s*\}/g, '')
    .replace(/@media \(prefers-reduced-motion:[\s\S]*?\}\s*\}/g, '')
}

function extractPageCss(html) {
  const blocks = [...html.matchAll(/<style\b[^>]*>([\s\S]*?)<\/style>/gi)]
    .map(match => match[1].trim())
    .filter(css => css && !css.includes('@theme inline') && !css.includes('#semantic-token-fallback'))
  return blocks.length ? blocks[blocks.length - 1] : ''
}

function convertPageCss(css) {
  const value = normalizeCssForWxss(css, '.design-canvas-page')
  return `/* AUTO-GENERATED from zjrnew page-local CSS; do not hand edit. */\n${value.trim()}\n\n.design-canvas-page { width: 750rpx; min-height: 100vh; border-radius: 0; box-shadow: none; }\n.design-svg-icon { display: block; width: 44rpx; height: 44rpx; }\n`
}

function convertSharedCss(css) {
  let value = normalizeCssForWxss(css, '.design-detail-page')
    .replace(/^\s*\*\s*\{/gm, 'view, text, image, input, textarea, .design-button, .design-select, .design-option {')
    .replace(/\.design-detail-page\s*>\s*\*/g, '.design-detail-page > view, .design-detail-page > text, .design-detail-page > image')
    .replace(/\.hero\s*>\s*\*/g, '.hero > view, .hero > text, .hero > image')
    .replace(/(?<![A-Za-z0-9_.-])button\.list-row/g, '.design-button.list-row')
    .replace(/(?<![A-Za-z0-9_.-])button(?![A-Za-z0-9_-])/g, '.design-button')
    .replace(/(?<![A-Za-z0-9_.-])select(?![A-Za-z0-9_-])/g, '.design-select')
    .replace(/\.topbar h1/g, '.topbar .tag-h1')
    .replace(/\.hero h2/g, '.hero .tag-h2')
    .replace(/\.hero p/g, '.hero .tag-p')
    .replace(/\.progress-ring strong/g, '.progress-ring .tag-strong')
    .replace(/\.progress-ring small/g, '.progress-ring .tag-small')
    .replace(/\.section-title strong/g, '.section-title .tag-strong')
    .replace(/\.metric strong/g, '.metric .tag-strong')
    .replace(/\.metric span/g, '.metric .tag-span')
    .replace(/\.timeline-item strong/g, '.timeline-item .tag-strong')
    .replace(/\.timeline-item span/g, '.timeline-item .tag-span')
    .replace(/\.empty-state h3/g, '.empty-state .tag-h3')
    .replace(/\.empty-state p/g, '.empty-state .tag-p')
    .replace(/\.amount small/g, '.amount .tag-small')
    .replace(/\.field label/g, '.field .tag-label')

  value += `

page { display: block; min-height: 100%; padding: 0; background: var(--canvas); }
.design-detail-page { width: 750rpx; min-height: 100vh; border: 0; border-radius: 0; box-shadow: none; }
.design-detail-page .fixed-actions { position: fixed; padding-bottom: calc(44rpx + env(safe-area-inset-bottom)); }
.design-button { margin: 0; padding: 0; line-height: inherit; }
.design-select, .design-option { box-sizing: border-box; }
.design-svg-icon { display: block; width: 44rpx; height: 44rpx; }
.icon-button .design-svg-icon { width: 40rpx; height: 40rpx; }
.icon-action .design-svg-icon { width: 38rpx; height: 38rpx; }
.row-icon .design-svg-icon { width: 36rpx; height: 36rpx; }
.empty-icon .design-svg-icon, .result-icon .design-svg-icon { width: 72rpx; height: 72rpx; }
.card { -webkit-backdrop-filter: blur(28rpx) saturate(135%); }
.map-caption { -webkit-backdrop-filter: blur(16rpx); }
.upload-tile { min-height: 190rpx; }
`
  return `/* AUTO-GENERATED from zjrnew/assets/detail-page.css; do not hand edit. */\n${value.trim()}\n`
}

function generatedJs(node, route) {
  return `// AUTO-GENERATED PAGE CONTROLLER; remove this marker before adding page-specific business logic.\nconst { createDesignPage } = require('../../utils/design-page-runtime')\n\nPage(createDesignPage({\n  pageId: ${JSON.stringify(node.id)},\n  route: ${JSON.stringify(route)},\n  source: ${JSON.stringify(node.devMetadata.htmlSrc)},\n  sourceHash: ${JSON.stringify(node.canvasData.layoutSnapshot.sourceHash)},\n  title: ${JSON.stringify(node.title)}\n}))\n`
}

function generatedJson(node) {
  return `${JSON.stringify({ navigationStyle: 'custom', disableScroll: true, navigationBarTitleText: node.title }, null, 2)}\n`
}

function generatedWxss(node, detailPage, pageName) {
  if (!detailPage) {
    return `/* AUTO-GENERATED DESIGN STYLE ENTRY; page-specific overrides may follow this import. */\n@import "../../styles/generated-design-pages/${pageName}.wxss";\n`
  }
  return `/* AUTO-GENERATED DESIGN STYLE ENTRY; page-specific overrides may follow this import. */\n@import "../../styles/generated-detail-page.wxss";\n`
}

function mayOverwrite(file, marker) {
  return !existsSync(file) || forceView || readFileSync(file, 'utf8').startsWith(marker)
}

const designRaw = readFileSync(designFile, 'utf8')
const design = JSON.parse(designRaw)
const previousManifest = existsSync(manifestFile) ? readJson(manifestFile) : { pages: [] }
const previousByRoute = new Map((previousManifest.pages || []).map(item => [item.route, item]))
const nodes = Array.isArray(design.data) ? design.data : []
const idToRoute = new Map(nodes.map(node => [node.id, routeForSource(node.devMetadata.htmlSrc)]))
const unique = new Map()
for (const node of nodes) {
  const source = node.devMetadata && node.devMetadata.htmlSrc
  if (!source || !source.endsWith('.html')) continue
  const route = routeForSource(source)
  if (!unique.has(route)) unique.set(route, node)
}

const app = readJson(appFile)
const existingRoutes = new Set(app.pages || [])
const changed = []
const skipped = []
const manifestPages = []

if (write) {
  mkdirSync(dirname(sharedStyleFile), { recursive: true })
  const sharedCss = readFileSync(join(designRoot, 'assets', 'detail-page.css'), 'utf8')
  writeFileSync(sharedStyleFile, convertSharedCss(sharedCss), 'utf8')
  mkdirSync(pageStyleDir, { recursive: true })
}

for (const [route, node] of unique) {
  const sourceFile = join(designRoot, node.devMetadata.htmlSrc)
  const html = readFileSync(sourceFile, 'utf8')
  const isDetail = /(?:^|\/)detail-page\.css(?:['"]|\?)/.test(html)
  const pageName = route.split('/')[1]
  const selected = !only || only.has(pageName) || only.has(route) || only.has(node.id)
  const dir = join(root, 'pages', pageName)
  const jsFile = join(dir, 'index.js')
  const jsonFile = join(dir, 'index.json')
  const wxmlFile = join(dir, 'index.wxml')
  const wxssFile = join(dir, 'index.wxss')
  const wasExisting = existingRoutes.has(route)
  const previous = previousByRoute.get(route)
  const generatedView = existsSync(wxmlFile) && readFileSync(wxmlFile, 'utf8').startsWith('<!-- AUTO-GENERATED DESIGN VIEW')
  let renderedSourceHash = previous && (previous.renderedSourceHash || previous.sourceHash)
  if (!renderedSourceHash && generatedView) renderedSourceHash = node.canvasData.layoutSnapshot.sourceHash
  const sourceChanged = generatedView && renderedSourceHash !== node.canvasData.layoutSnapshot.sourceHash
  let status = wasExisting ? 'manual-existing' : 'planned'

  if (selected && !isDetail && forceView && write) {
    const pageCss = extractPageCss(html)
    if (pageCss) writeFileSync(join(pageStyleDir, `${pageName}.wxss`), convertPageCss(pageCss), 'utf8')
  }

  if (selected && (isDetail || forceView) && (!wasExisting || forceView || (refreshGenerated && sourceChanged))) {
    if (write) {
      mkdirSync(dir, { recursive: true })
      if (!existsSync(jsFile)) writeFileSync(jsFile, generatedJs(node, route), 'utf8')
      if (!existsSync(jsonFile)) writeFileSync(jsonFile, generatedJson(node), 'utf8')
      if (mayOverwrite(wxmlFile, '<!-- AUTO-GENERATED DESIGN VIEW')) {
        writeFileSync(wxmlFile, convertHtml(html, node, idToRoute), 'utf8')
      }
      if (mayOverwrite(wxssFile, '/* AUTO-GENERATED DESIGN STYLE ENTRY;')) {
        writeFileSync(wxssFile, generatedWxss(node, isDetail, pageName), 'utf8')
      }
      changed.push(route)
      status = 'generated-restricted'
      renderedSourceHash = node.canvasData.layoutSnapshot.sourceHash
    } else {
      status = 'would-generate'
    }
  } else if (!isDetail && !wasExisting) {
    skipped.push(`${route}: source does not use detail-page.css`)
    status = 'skipped-non-detail'
  } else if (existsSync(jsFile) && readFileSync(jsFile, 'utf8').startsWith('// AUTO-GENERATED PAGE CONTROLLER;')) {
    status = sourceChanged ? 'generated-source-changed' : 'generated-restricted'
  }

  manifestPages.push({
    id: node.id,
    title: node.title,
    route,
    source: node.devMetadata.htmlSrc,
    sourceHash: node.canvasData.layoutSnapshot.sourceHash,
    renderedSourceHash: renderedSourceHash || null,
    sourceSha256: sha256(html),
    detailPage: isDetail,
    status
  })
}

if (write && register) {
  for (const route of unique.keys()) existingRoutes.add(route)
  app.pages = [...existingRoutes]
  writeFileSync(appFile, `${JSON.stringify(app, null, 2)}\n`, 'utf8')
}

const manifest = {
  generatedAt: new Date().toISOString(),
  designFile: '../zjrnew/zjrnew.design',
  designSha256: sha256(designRaw),
  nodeCount: nodes.length,
  uniqueTargetCount: unique.size,
  mode: write ? 'write' : 'check',
  pages: manifestPages
}
if (write) writeFileSync(manifestFile, `${JSON.stringify(manifest, null, 2)}\n`, 'utf8')

console.log(`设计节点 ${nodes.length}，唯一目标 ${unique.size}，detail-page 目标 ${manifestPages.filter(item => item.detailPage).length}`)
console.log(`${write ? '已生成/刷新' : '待生成'} ${changed.length || manifestPages.filter(item => item.status === 'would-generate').length} 页；${register && write ? `app.json=${app.pages.length}` : '未改 app.json'}`)
const staleGenerated = manifestPages.filter(item => item.status === 'generated-source-changed')
if (staleGenerated.length) console.log(`生成视图待刷新 ${staleGenerated.length} 页（使用 --write --refresh-generated）`)
if (skipped.length) {
  console.error(skipped.join('\n'))
  process.exitCode = 1
}
