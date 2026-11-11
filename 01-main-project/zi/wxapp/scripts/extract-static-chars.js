#!/usr/bin/env node
/**
 * 扫描所有 WXML 文件，提取静态 UI 文本字符（非数据绑定）
 * 生成去重字符列表，用于字体子集化
 */
const fs = require('fs')
const path = require('path')

const WXAPP_ROOT = path.resolve(__dirname, '..')
const CHARSET_FILE = path.join(__dirname, 'static-chars.txt')

// 递归查找所有 .wxml 文件
function findWxmlFiles(dir, results = []) {
  const items = fs.readdirSync(dir, { withFileTypes: true })
  for (const item of items) {
    const fullPath = path.join(dir, item.name)
    // 跳过 node_modules, .trae, miniprogram_npm
    if (item.name === 'node_modules' || item.name === '.trae' || item.name === 'miniprogram_npm') continue
    if (item.isDirectory()) {
      findWxmlFiles(fullPath, results)
    } else if (item.name.endsWith('.wxml')) {
      results.push(fullPath)
    }
  }
  return results
}

// 从 WXML 内容中提取静态文本（排除 {{}} 数据绑定、标签名、属性）
function extractStaticText(content) {
  let staticText = ''

  // 移除所有 {{...}} 数据绑定
  let cleaned = content.replace(/\{\{[^}]*\}\}/g, '')

  // 提取标签之间的文本内容
  // 匹配 >文本< 模式（标签之间的纯文本）
  const textMatches = cleaned.match(/>([^<]+)</g)
  if (textMatches) {
    for (const match of textMatches) {
      const text = match.slice(1, -1).trim()
      if (text) staticText += text
    }
  }

  // 提取 placeholder="静态文本" 属性中的文本
  const placeholderMatches = cleaned.match(/placeholder="([^"]+)"/g)
  if (placeholderMatches) {
    for (const match of placeholderMatches) {
      const text = match.match(/"([^"]+)"/)[1]
      staticText += text
    }
  }

  return staticText
}

// 主流程
const wxmlFiles = findWxmlFiles(WXAPP_ROOT)
console.log(`找到 ${wxmlFiles.length} 个 WXML 文件`)

let allText = ''
for (const file of wxmlFiles) {
  const content = fs.readFileSync(file, 'utf-8')
  allText += extractStaticText(content)
}

// 去重并排序
const charSet = new Set()
for (const ch of allText) {
  // 只保留 CJK 统一汉字和基本拉丁字符/数字/标点
  const code = ch.charCodeAt(0)
  if (
    (code >= 0x4E00 && code <= 0x9FFF) ||  // CJK 统一汉字
    (code >= 0x3000 && code <= 0x303F) ||  // CJK 标点符号
    (code >= 0xFF00 && code <= 0xFFEF) ||  // 全角字符
    (code >= 0x0020 && code <= 0x007E) ||  // 基本拉丁字符
    (code >= 0x2010 && code <= 0x2027) ||  // 通用标点（连字符、破折号、引号）
    (code >= 0x00A0 && code <= 0x00FF)     // 拉丁补充
  ) {
    charSet.add(ch)
  }
}

const sortedChars = Array.from(charSet).sort().join('')
console.log(`静态 UI 文本共 ${allText.length} 字符`)
console.log(`去重后 ${sortedChars.length} 个独立字符`)

// 写入文件
fs.writeFileSync(CHARSET_FILE, sortedChars, 'utf-8')
console.log(`字符列表已写入: ${CHARSET_FILE}`)

// 打印中文字符统计
const cjkChars = sortedChars.match(/[\u4E00-\u9FFF]/g)
console.log(`其中中文字符 ${cjkChars ? cjkChars.length : 0} 个`)
