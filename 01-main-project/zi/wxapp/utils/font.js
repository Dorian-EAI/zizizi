// utils/font.js — 字体加载（集中管理，懒加载）
//
// 设计使用衬线字体（Noto Serif SC / Cormorant Garamond）作为玻璃新拟态的标题与数字字体，
// 与 zjrnew.design 画布严格一致；UGC 内容使用无衬线网络字体（支持 emoji 与生僻字）。
//
// 加载策略（由 globalData.fontCDN 控制，零默认行为变化）：
//   1) 若配置了 fontCDN（自有对象存储，如 https://cdn.example.com/fonts）
//      → 走网络加载，主包可删除 assets/fonts/fonts.js 把体积降到约 1.1MB。
//        CDN 失败时回退 gstatic 网络字体（境外，国内可能偏慢）。
//   2) 若未配置 fontCDN（默认）
//      → 使用主包内嵌 base64 衬线字体（约 600KB，最稳，零外网依赖）。
//        base64 失败时才回退 gstatic。
//
// 无论哪种模式，画布视觉令牌（衬线标题 / 青色玻璃质感）完全一致，页面无需任何改动。
const SERIF_FILES = {
  'Noto Serif SC': {
    400: 'noto-serif-sc-400.woff2',
    700: 'noto-serif-sc-700.woff2'
  },
  'Cormorant Garamond': {
    700: 'cormorant-garamond-700.woff2'
  }
}
const UGC_FILE = 'noto-sans-cjk-sc.woff2'

// gstatic 境外回退源（与画布同源，仅作兜底）
const NETWORK_SOURCES = {
  'Noto Serif SC': {
    400: 'https://fonts.gstatic.com/s/notoserif/v23/ga6Ia6J1jKT9OCKjvG3tQv5DcW5Pb0YF.woff2',
    700: 'https://fonts.gstatic.com/s/notoserif/v23/ga6fa6J1jKT9OCKjvG3tQv5DcW5Pb0YF.woff2'
  },
  'Cormorant Garamond': {
    700: 'https://fonts.gstatic.com/s/cormorantgaramond/v16/co3YmX5slCNuHLi8bLeY9MK7whWMhyjYrEpvw.woff2'
  },
  'Noto Sans CJK SC': 'https://fonts.gstatic.com/s/notosanssc/v37/k3kCo4MPqYKzDn85DY_rLjHvu0-Tg.woff2'
}

function getCDN() {
  try {
    const app = typeof getApp === 'function' ? getApp() : null
    const cdn = app && app.globalData && app.globalData.fontCDN
    return (typeof cdn === 'string' && cdn.trim()) ? cdn.trim().replace(/\/+$/, '') : ''
  } catch (e) {
    return ''
  }
}

function loadFace(family, source, weight, label) {
  if (!wx.loadFontFace) return
  wx.loadFontFace({
    family,
    source,
    global: true,
    scopes: ['webview', 'native'],
    success: () => console.log(`[字体] ${family} (${weight || '—'}) ${label} 加载成功`),
    fail: (err) => console.warn(`[字体] ${family} ${label} 加载失败`, err)
  })
}

// 模式一：CDN 优先（瘦身路径，主包不含 base64）
function loadFromCDN(cdn) {
  Object.keys(SERIF_FILES).forEach((family) => {
    Object.keys(SERIF_FILES[family]).forEach((weight) => {
      const file = SERIF_FILES[family][weight]
      const cdnUrl = `url("${cdn}/${file}")`
      const fallback = NETWORK_SOURCES[family] && NETWORK_SOURCES[family][weight]
      wx.loadFontFace({
        family,
        source: cdnUrl,
        global: true,
        scopes: ['webview', 'native'],
        success: () => console.log(`[衬线字体] ${family} (${weight}) CDN 加载成功`),
        fail: (err) => {
          console.warn(`[衬线字体] ${family} CDN 加载失败，尝试 gstatic`, err)
          if (fallback) loadFace(family, `url("${fallback}")`, weight, 'gstatic')
        }
      })
    })
  })

  // UGC 无衬线字体：优先 CDN，失败回退 gstatic
  const ugcCDN = `${cdn}/${UGC_FILE}`
  wx.loadFontFace({
    family: 'Noto Sans CJK SC',
    source: `url("${ugcCDN}")`,
    global: true,
    scopes: ['webview', 'native'],
    success: () => console.log('[UGC字体] Noto Sans CJK SC CDN 加载成功'),
    fail: (err) => {
      console.warn('[UGC字体] CDN 加载失败，尝试 gstatic', err)
      loadFace('Noto Sans CJK SC', `url("${NETWORK_SOURCES['Noto Sans CJK SC']}")`, null, 'gstatic')
    }
  })
}

// 模式二：主包 base64（默认，最稳，零外网依赖）
function loadFromBase64() {
  const fonts = require('../assets/fonts/fonts.js')
  const serifFonts = [
    { family: 'Noto Serif SC', source: `url("data:font/woff2;base64,${fonts.noto400}")`, weight: 400 },
    { family: 'Noto Serif SC', source: `url("data:font/woff2;base64,${fonts.noto700}")`, weight: 700 },
    { family: 'Cormorant Garamond', source: `url("data:font/woff2;base64,${fonts.cormorant}")`, weight: 700 }
  ]
  serifFonts.forEach(({ family, source, weight }) => {
    wx.loadFontFace({
      family,
      source,
      global: true,
      scopes: ['webview', 'native'],
      success: () => console.log(`[衬线字体] ${family} (${weight}) base64 加载成功`),
      fail: (err) => {
        console.warn(`[衬线字体] ${family} base64 加载失败，尝试网络加载`, err)
        const url = NETWORK_SOURCES[family] && NETWORK_SOURCES[family][weight]
        if (!url) return
        loadFace(family, `url("${url}")`, weight, 'gstatic')
      }
    })
  })

  // UGC 用的无衬线网络字体（支持全量字符）
  loadFace(
    'Noto Sans CJK SC',
    `url("${NETWORK_SOURCES['Noto Sans CJK SC']}")`,
    null,
    'gstatic'
  )
}

let loaded = false

function loadFontsOnce() {
  if (loaded) return
  loaded = true
  if (!wx.loadFontFace) return

  const cdn = getCDN()
  if (cdn) {
    console.log('[字体] 检测到 fontCDN，走网络加载路径')
    loadFromCDN(cdn)
  } else {
    console.log('[字体] 未配置 fontCDN，使用主包内嵌 base64')
    loadFromBase64()
  }
}

module.exports = { loadFontsOnce }
