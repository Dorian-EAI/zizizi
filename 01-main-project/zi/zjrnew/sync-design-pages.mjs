import { readFileSync, readdirSync, writeFileSync } from 'node:fs'
import { basename, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = resolve(fileURLToPath(new URL('.', import.meta.url)))
const pagesDir = join(root, 'pages')
const designFile = join(root, 'zjrnew.design')

function fnv1a(text) {
  let value = 0x811c9dc5
  for (let index = 0; index < text.length; index += 1) {
    value ^= text.charCodeAt(index)
    value = Math.imul(value, 0x01000193) >>> 0
  }
  return `fnv1a-${value.toString(16).padStart(8, '0')}`
}

function decodeHtml(text) {
  return text
    .replaceAll('&amp;', '&')
    .replaceAll('&middot;', '·')
    .replaceAll('&mdash;', '—')
    .replaceAll('&nbsp;', ' ')
}

function pageTitle(html, filename) {
  const explicit = html.match(/<meta\s+name=["']design-title["']\s+content=["']([^"']+)["']/i)?.[1]
  const documentTitle = html.match(/<title>([^<]+)<\/title>/i)?.[1]
  const heading = html.match(/<h1[^>]*>(.*?)<\/h1>/is)?.[1]?.replace(/<[^>]+>/g, '')
  const raw = explicit || heading || documentTitle || basename(filename, '.html')
  return decodeHtml(raw).replace(/\s*[·|｜]\s*自家人.*$/u, '').trim()
}

function interactions(html) {
  const found = []
  const seen = new Set()
  for (const match of html.matchAll(/<[^>]+data-dom-id=["']([^"']+)["'][^>]*>/gi)) {
    const tag = match[0]
    const domId = match[1]
    const targetPageId = tag.match(/data-target-page=["']([^"']+)["']/i)?.[1]
    if (!targetPageId || seen.has(domId)) continue
    found.push({ domId, targetPageId })
    seen.add(domId)
  }
  for (const match of html.matchAll(/<[^>]+data-target-page=["']([^"']+)["'][^>]*>/gi)) {
    const tag = match[0]
    const targetPageId = match[1]
    const domId = tag.match(/data-dom-id=["']([^"']+)["']/i)?.[1]
    if (!domId || seen.has(domId)) continue
    found.push({ domId, targetPageId })
    seen.add(domId)
  }
  return found
}

const design = JSON.parse(readFileSync(designFile, 'utf8'))
const existing = new Map(design.data.map(node => [node.id, node]))
const files = readdirSync(pagesDir)
  .filter(name => /^(client|worker)-.+\.html$/i.test(name))
  .sort((a, b) => a.localeCompare(b, 'zh-CN'))

const allIds = new Set(files.map(name => `page-${basename(name, '.html')}`))
for (const id of existing.keys()) allIds.add(id)

const aliases = new Map([
  ['page-client-home', 'page-client-home-glass-neu-contrast-1'],
  ['page-client-tracking', 'page-client-order-tracking'],
  ['page-client-notifications', 'page-client-notification'],
  ['page-client-auth-management', 'page-client-auth'],
  ['page-client-privacy-policy', 'page-client-agreement'],
  ['page-client-user-agreement', 'page-client-agreement'],
  ['page-worker-cert', 'page-worker-certification'],
])

function normalizeTarget(raw) {
  const withoutState = raw.split(/[?#]/, 1)[0]
  const withPrefix = withoutState.startsWith('page-') ? withoutState : `page-${withoutState}`
  return aliases.get(withPrefix) || withPrefix
}

let added = 0
let updated = 0
const unresolved = []
const interactionGaps = []
const startY = 14000
const columns = 5
const xGap = 430
const yGap = 980
const measuredAt = Date.now()

for (const name of files) {
  const id = `page-${basename(name, '.html')}`
  const source = `pages/${name}`
  const html = readFileSync(join(pagesDir, name), 'utf8')
  const domIds = new Set()
  for (const match of html.matchAll(/<[^>]+data-dom-id=["']([^"']+)["'][^>]*>/gi)) {
    if (domIds.has(match[1])) interactionGaps.push(`${name}: 重复 data-dom-id ${match[1]}`)
    domIds.add(match[1])
  }
  for (const match of name === 'worker-recharge.html' ? [] : html.matchAll(/<(button|a)\b[^>]*>|<[^>]+role=["']button["'][^>]*>/gi)) {
    const tag = match[0]
    if (/\bdisabled\b/i.test(tag)) continue
    if (!/data-dom-id=["'][^"']+["']/i.test(tag)) interactionGaps.push(`${name}: 缺少 data-dom-id ${tag.slice(0, 110)}`)
    if (!/(data-target-page|data-action|href)=["'][^"']+["']/i.test(tag)) interactionGaps.push(`${name}: 缺少目标或动作 ${tag.slice(0, 110)}`)
  }
  const links = interactions(html).map(link => ({ ...link, targetPageId: normalizeTarget(link.targetPageId) }))
  for (const link of links) {
    if (!allIds.has(link.targetPageId)) unresolved.push(`${id}:${link.domId} -> ${link.targetPageId}`)
  }

  const snapshot = {
    version: 1,
    contentHeight: 900,
    viewportWidth: 375,
    sourceHash: fnv1a(html),
    measuredAt,
  }

  if (existing.has(id)) {
    const node = existing.get(id)
    node.canvasData ||= {}
    node.canvasData.layoutSnapshot = { ...(node.canvasData.layoutSnapshot || {}), ...snapshot }
    node.devMetadata ||= {}
    node.devMetadata.htmlSrc = source
    // HTML 是当前交互真源；直接替换，避免保留已经从页面移除的旧按钮映射。
    node.devMetadata.interactions = links
    updated += 1
    continue
  }

  const position = added
  const node = {
    id,
    title: pageTitle(html, name),
    type: 'page',
    version: 1,
    createdAt: measuredAt + added,
    canvasData: {
      x: (position % columns) * xGap,
      y: startY + Math.floor(position / columns) * yGap,
      group: id.startsWith('page-worker-') ? 2 : 1,
      layoutSnapshot: snapshot,
    },
    devMetadata: {
      htmlSrc: source,
      interactions: links,
    },
  }
  design.data.push(node)
  existing.set(id, node)
  added += 1
}

if (unresolved.length) {
  console.error('存在未创建的页面目标：')
  for (const item of unresolved) console.error(`- ${item}`)
  process.exit(1)
}

if (interactionGaps.length) {
  console.error('存在未闭合的可点击元素：')
  for (const item of interactionGaps) console.error(`- ${item}`)
  process.exit(1)
}

writeFileSync(designFile, `${JSON.stringify(design, null, 2)}\n`, 'utf8')
console.log(`DESIGN 同步完成：新增 ${added} 页，更新 ${updated} 页，总计 ${design.data.length} 页。`)
