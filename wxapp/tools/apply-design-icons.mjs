import { existsSync, readFileSync, writeFileSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const designRoot = resolve(root, '..', 'zjrnew')
const designFile = join(designRoot, 'zjrnew.design')
const write = process.argv.includes('--write')

function readText(file) {
  return existsSync(file) ? readFileSync(file, 'utf8') : ''
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

function extractDesignMarkup(html) {
  const main = html.match(/<main\b[^>]*>[\s\S]*?<\/main>/i)
  if (main) return main[0]
  const body = html.match(/<body\b[^>]*>([\s\S]*?)<\/body>/i)?.[1] || html
  const beforeBodyStyle = body.split(/<style\b/i)[0]
  const phone = beforeBodyStyle.match(/<div\b[^>]*\bclass=(['"])[^'"]*\bphone\b[^'"]*\1[^>]*>[\s\S]*<\/div>\s*$/i)
  return phone ? phone[0] : beforeBodyStyle
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

function iconColorForContext(context, worker) {
  const brand = worker ? '#2D6CDF' : '#0D9488'
  if (/\b(success|text-success)\b/i.test(context)) return '#5B8C5A'
  if (/\b(warning|pending)\b/i.test(context)) return '#D4944C'
  if (/\b(danger|text-danger|error|failed)\b/i.test(context)) return '#C4533A'
  if (/\b(info)\b/i.test(context)) return '#5A8FAD'
  if (/\b(row-icon|empty-icon|upload-icon|inline-icon|media-placeholder|media-visual|service-glyph|play-icon|icon-action|top-action|result-icon)\b/i.test(context)) return brand
  return '#2C2824'
}

function categoryForContext(context) {
  if (/\bicon-button\b/i.test(context)) return 'icon-button'
  if (/\b(row-icon|inline-icon)\b/i.test(context)) return 'row-icon'
  if (/\bempty-icon\b/i.test(context)) return 'empty-icon'
  if (/\bresult-icon\b/i.test(context)) return 'result-icon'
  if (/\b(media-placeholder|media-visual|play-icon|map-pin)\b/i.test(context)) return 'media'
  if (/\b(upload-icon|upload-tile)\b/i.test(context)) return 'upload'
  return 'other'
}

function extractSvgEntries(markup, worker) {
  const entries = []
  const pattern = /<svg\b[\s\S]*?<\/svg>/gi
  let match
  while ((match = pattern.exec(markup))) {
    const context = markup.slice(Math.max(0, match.index - 320), match.index)
    entries.push({
      category: categoryForContext(context),
      image: `<image class="design-svg-icon" src="${dataUriForSvg(match[0], iconColorForContext(context, worker))}" mode="aspectFill" />`
    })
  }
  return entries
}

function createPicker(entries) {
  const indexes = new Map()
  return category => {
    const pool = entries.filter(entry => entry.category === category)
    const key = category
    const index = indexes.get(key) || 0
    if (index >= pool.length) return ''
    indexes.set(key, index + 1)
    return pool[index].image
  }
}

function replaceSimpleIconButton(wxml, pick) {
  return wxml.replace(
    /<view([^>]*\bclass=(['"])[^'"]*\bicon-button\b[^'"]*\2[^>]*)>([\s\S]*?)<\/view>/gi,
    (whole, attributes, quote, inner) => {
      if (/<image\b/i.test(inner) || /{{/.test(inner)) return whole
      if (inner.replace(/\s+/g, '').length > 4) return whole
      const image = pick('icon-button')
      return image ? `<view${attributes}>${image}</view>` : whole
    }
  )
}

function replaceSimpleWrapper(wxml, className, category, pick) {
  const pattern = new RegExp(`<([a-z]+)([^>]*\\bclass=(['"])[^'"]*\\b${className}\\b[^'"]*\\3[^>]*)>([\\s\\S]*?)<\\/\\1>`, 'gi')
  return wxml.replace(pattern, (whole, tag, attributes, quote, inner) => {
    if (/<image\b/i.test(inner) || /{{/.test(inner)) return whole
    if (inner.replace(/\s+/g, '').length > 6) return whole
    const image = pick(category)
    return image ? `<view${attributes}>${image}</view>` : whole
  })
}

function patchWxml(wxml, entries) {
  const pick = createPicker(entries)
  let next = replaceSimpleIconButton(wxml, pick)
  next = replaceSimpleWrapper(next, 'empty-icon', 'empty-icon', pick)
  next = replaceSimpleWrapper(next, 'result-icon', 'result-icon', pick)
  next = replaceSimpleWrapper(next, 'media-placeholder', 'media', pick)
  next = replaceSimpleWrapper(next, 'row-icon', 'row-icon', pick)
  return next
}

const design = JSON.parse(readText(designFile))
const seen = new Set()
const changed = []

for (const node of design.data || []) {
  const source = node.devMetadata?.htmlSrc
  if (!source || !source.endsWith('.html')) continue
  const pageName = targetName(source)
  if (seen.has(pageName)) continue
  seen.add(pageName)

  const sourceHtml = readText(join(designRoot, source))
  const sourceMarkup = extractDesignMarkup(sourceHtml)
  const worker = /<html\b[^>]*data-role=['"]worker['"]/i.test(sourceHtml) || /\bworker-theme\b/.test(sourceMarkup)
  const entries = extractSvgEntries(sourceMarkup, worker).filter(entry => entry.category !== 'other')
  if (!entries.length) continue

  const wxmlFile = join(root, 'pages', pageName, 'index.wxml')
  const wxml = readText(wxmlFile)
  if (!wxml || /<image\b/i.test(wxml)) continue

  const next = patchWxml(wxml, entries)
  if (next !== wxml) {
    changed.push(`pages/${pageName}/index.wxml`)
    if (write) writeFileSync(wxmlFile, next, 'utf8')
  }
}

console.log(`${write ? '已修复' : '待修复'} ${changed.length} 个旧图标页面`)
for (const file of changed) console.log(`- ${file}`)
