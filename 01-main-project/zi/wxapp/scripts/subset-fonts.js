#!/usr/bin/env node
/**
 * 下载 Noto Serif SC 全量中文字体，根据静态 UI 文本字符生成子集
 * 输出: assets/fonts/NotoSerifSC-Subset.woff2
 */
const fs = require('fs')
const path = require('path')
const https = require('https')
const http = require('http')

const SUBSET_FONT = require('/private/tmp/font-subset-work/node_modules/subset-font')

const WXAPP_ROOT = path.resolve(__dirname, '..')
const CHARS_FILE = path.join(__dirname, 'static-chars.txt')
const OUTPUT_DIR = path.join(WXAPP_ROOT, 'assets', 'fonts')
const OUTPUT_400 = path.join(OUTPUT_DIR, 'NotoSerifSC-Subset-400.woff2')
const OUTPUT_700 = path.join(OUTPUT_DIR, 'NotoSerifSC-Subset-700.woff2')

// 下载文件
function download(url) {
  return new Promise((resolve, reject) => {
    console.log(`下载: ${url}`)
    const mod = url.startsWith('https') ? https : http
    mod.get(url, { headers: { 'User-Agent': 'Mozilla/5.0' } }, (res) => {
      if (res.statusCode >= 300 && res.statusCode < 400 && res.headers.location) {
        return resolve(download(res.headers.location))
      }
      if (res.statusCode !== 200) {
        return reject(new Error(`HTTP ${res.statusCode}`))
      }
      const chunks = []
      res.on('data', (c) => chunks.push(c))
      res.on('end', () => resolve(Buffer.concat(chunks)))
      res.on('error', reject)
    }).on('error', reject)
  })
}

async function main() {
  const chars = fs.readFileSync(CHARS_FILE, 'utf-8')
  console.log(`子集字符: ${chars.length} 个`)

  // 下载 Noto Serif SC 400 和 700
  const url400 = 'https://cdn.jsdelivr.net/npm/@fontsource/noto-serif-sc@5.0.5/files/noto-serif-sc-chinese-simplified-400-normal.woff2'
  const url700 = 'https://cdn.jsdelivr.net/npm/@fontsource/noto-serif-sc@5.0.5/files/noto-serif-sc-chinese-simplified-700-normal.woff2'

  console.log('下载 400 字重...')
  const buf400 = await download(url400)
  console.log(`400 字重原始大小: ${(buf400.length / 1024).toFixed(1)} KB`)

  console.log('下载 700 字重...')
  const buf700 = await download(url700)
  console.log(`700 字重原始大小: ${(buf700.length / 1024).toFixed(1)} KB`)

  // 子集化
  console.log('子集化 400 字重...')
  const subset400 = await SUBSET_FONT(buf400, chars, { targetFormat: 'woff2' })
  console.log(`400 字重子集大小: ${(subset400.length / 1024).toFixed(1)} KB`)

  console.log('子集化 700 字重...')
  const subset700 = await SUBSET_FONT(buf700, chars, { targetFormat: 'woff2' })
  console.log(`700 字重子集大小: ${(subset700.length / 1024).toFixed(1)} KB`)

  // 写入文件
  fs.mkdirSync(OUTPUT_DIR, { recursive: true })
  fs.writeFileSync(OUTPUT_400, subset400)
  fs.writeFileSync(OUTPUT_700, subset700)

  console.log(`\n✅ 子集字体已保存到:`)
  console.log(`   ${OUTPUT_400}`)
  console.log(`   ${OUTPUT_700}`)
  console.log(`\n压缩率: 400=${((1 - subset400.length / buf400.length) * 100).toFixed(1)}%  700=${((1 - subset700.length / buf700.length) * 100).toFixed(1)}%`)
}

main().catch(err => { console.error('❌', err); process.exit(1) })
