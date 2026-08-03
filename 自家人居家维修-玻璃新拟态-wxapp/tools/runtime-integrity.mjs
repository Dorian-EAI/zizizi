import { existsSync, readFileSync, readdirSync } from 'node:fs'
import { dirname, extname, isAbsolute, join, relative, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { Script } from 'node:vm'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const errors = []
const warnings = []
const activeFiles = new Set()
const parsedJson = new Map()
const EXPECTED_ROUTE_COUNT = 37

const stats = {
  routes: 0,
  pageFiles: 0,
  components: 0,
  navigationRefs: 0,
  dynamicNavigationCalls: 0,
  moduleRefs: 0,
  templateImports: 0,
  styleImports: 0,
  localResources: 0,
  jsSyntax: 0,
  runtimeConfigCases: 0
}

function rel(file) {
  return relative(root, file).replaceAll('\\', '/') || '.'
}

function lineOf(text, index) {
  return text.slice(0, Math.max(0, index)).split(/\r?\n/).length
}

function issue(file, message, text, index) {
  const location = file ? rel(file) + (text ? ':' + lineOf(text, index || 0) : '') : 'project'
  errors.push(location + ' — ' + message)
}

function warn(file, message, text, index) {
  const location = file ? rel(file) + (text ? ':' + lineOf(text, index || 0) : '') : 'project'
  warnings.push(location + ' — ' + message)
}

function read(file) {
  try {
    return readFileSync(file, 'utf8')
  } catch (error) {
    issue(file, '读取失败：' + error.message)
    return ''
  }
}

function readJson(file) {
  if (parsedJson.has(file)) return parsedJson.get(file)
  try {
    const value = JSON.parse(readFileSync(file, 'utf8'))
    parsedJson.set(file, value)
    return value
  } catch (error) {
    issue(file, 'JSON 解析失败：' + error.message)
    parsedJson.set(file, {})
    return {}
  }
}

function addRequiredFile(file, label) {
  if (!existsSync(file)) {
    issue(file, label + '不存在')
    return false
  }
  activeFiles.add(file)
  return true
}

function checkRuntimeEnvironmentGate() {
  const file = join(root, 'config', 'env.js')
  const source = read(file)
  const devBaseKey = '__DEV_API_BASE_URL__'
  const devMockKey = '__DEV_USE_MOCK__'
  const cases = [
    { label: '缺失 envVersion', info: undefined, expectedEnv: 'invalid', expectedMock: false, expectedBase: '' },
    { label: '未知 envVersion', info: { miniProgram: { envVersion: 'unknown' } }, expectedEnv: 'invalid', expectedMock: false, expectedBase: '' },
    { label: '体验版', info: { miniProgram: { envVersion: 'trial' } }, expectedEnv: 'trial', expectedMock: false, expectedBase: '' },
    { label: '正式版', info: { miniProgram: { envVersion: 'release' } }, expectedEnv: 'release', expectedMock: false, expectedBase: '' },
    { label: '显式开发版', info: { miniProgram: { envVersion: 'develop' } }, expectedEnv: 'develop', expectedMock: true, expectedBase: 'http://127.0.0.1:9000' },
    { label: '环境 API 异常', throws: true, expectedEnv: 'invalid', expectedMock: false, expectedBase: '' }
  ]

  for (const testCase of cases) {
    try {
      const module = { exports: {} }
      const storage = {
        [devBaseKey]: 'http://127.0.0.1:9000/',
        [devMockKey]: true
      }
      const wx = {
        getAccountInfoSync: () => {
          if (testCase.throws) throw new Error('account info unavailable')
          return testCase.info
        },
        getStorageSync: key => storage[key]
      }
      new Script(source, { filename: rel(file) }).runInNewContext({ module, exports: module.exports, wx })
      const config = module.exports.getRuntimeConfig()
      stats.runtimeConfigCases += 1
      if (config.envVersion !== testCase.expectedEnv ||
        config.useMock !== testCase.expectedMock ||
        config.baseURL !== testCase.expectedBase) {
        issue(file, `${testCase.label}未 fail closed：${JSON.stringify(config)}`)
      }
    } catch (error) {
      issue(file, `${testCase.label}环境门禁测试失败：${error.message}`)
    }
  }
}

function isInsideRoot(file) {
  const value = relative(root, file)
  return value === '' || (!value.startsWith('..') && !isAbsolute(value))
}

function cleanRef(value) {
  return String(value || '').trim().replace(/[?#].*$/, '')
}

function isExternalOrDynamic(value) {
  const ref = String(value || '').trim()
  return !ref || ref.includes('{{') || /^(?:https?:|data:|wxfile:|cloud:|plugin:|dynamicLib:|ext:|\/\/|#)/i.test(ref)
}

function maskJsComments(source) {
  const chars = source.split('')
  let state = 'code'
  let escaped = false
  for (let index = 0; index < chars.length; index += 1) {
    const char = chars[index]
    const next = chars[index + 1]
    if (state === 'line') {
      if (char === '\n' || char === '\r') state = 'code'
      else chars[index] = ' '
      continue
    }
    if (state === 'block') {
      if (char === '*' && next === '/') {
        chars[index] = ' '
        chars[index + 1] = ' '
        index += 1
        state = 'code'
      } else if (char !== '\n' && char !== '\r') {
        chars[index] = ' '
      }
      continue
    }
    if (state !== 'code') {
      if (escaped) escaped = false
      else if (char === '\\') escaped = true
      else if ((state === 'single' && char === "'") ||
        (state === 'double' && char === '"') ||
        (state === 'template' && char === '`')) state = 'code'
      continue
    }
    if (char === "'") state = 'single'
    else if (char === '"') state = 'double'
    else if (char === '`') state = 'template'
    else if (char === '/' && next === '/') {
      chars[index] = ' '
      chars[index + 1] = ' '
      index += 1
      state = 'line'
    } else if (char === '/' && next === '*') {
      chars[index] = ' '
      chars[index + 1] = ' '
      index += 1
      state = 'block'
    }
  }
  return chars.join('')
}

function resolveProjectRef(fromFile, value) {
  const ref = cleanRef(value)
  const file = ref.startsWith('/')
    ? resolve(root, '.' + ref)
    : resolve(dirname(fromFile), ref)
  if (!isInsideRoot(file)) {
    issue(fromFile, '本地引用越出小程序根目录：' + value)
    return null
  }
  return file
}

function checkExactLocalRef(fromFile, value, label, text, index) {
  if (isExternalOrDynamic(value)) return null
  const file = resolveProjectRef(fromFile, value)
  if (!file) return null
  if (!existsSync(file)) {
    issue(fromFile, label + '断链：' + value, text, index)
    return null
  }
  stats.localResources += 1
  return file
}

const appJsonFile = join(root, 'app.json')
const appJson = readJson(appJsonFile)
addRequiredFile(join(root, 'app.js'), '应用入口脚本')
addRequiredFile(appJsonFile, '应用配置')
addRequiredFile(join(root, 'app.wxss'), '应用全局样式')
checkRuntimeEnvironmentGate()

const routes = Array.isArray(appJson.pages) ? appJson.pages.map(route => String(route).replace(/^\//, '')) : []
const routeSet = new Set(routes)
stats.routes = routes.length

if (routes.length !== EXPECTED_ROUTE_COUNT) {
  issue(appJsonFile, `正式路由应为 ${EXPECTED_ROUTE_COUNT} 条，当前为 ${routes.length} 条`)
}
if (routeSet.size !== routes.length) issue(appJsonFile, 'pages 中存在重复路由')
if (appJson.entryPagePath && !routeSet.has(String(appJson.entryPagePath).replace(/^\//, ''))) {
  issue(appJsonFile, 'entryPagePath 未注册到 pages：' + appJson.entryPagePath)
}

for (const route of routes) {
  if (!/^pages\/[A-Za-z0-9_-]+\/index$/.test(route)) {
    issue(appJsonFile, '路由格式异常：' + route)
  }
  for (const suffix of ['.js', '.json', '.wxml', '.wxss']) {
    if (addRequiredFile(join(root, route + suffix), '页面文件 ' + route + suffix)) stats.pageFiles += 1
  }
}

const pageRoot = join(root, 'pages')
if (existsSync(pageRoot)) {
  for (const entry of readdirSync(pageRoot, { withFileTypes: true })) {
    if (!entry.isDirectory() || entry.name.startsWith('.') || entry.name.startsWith('._')) continue
    const candidate = `pages/${entry.name}/index`
    if (!routeSet.has(candidate)) issue(join(pageRoot, entry.name), '存在未注册页面目录：' + candidate)
  }
}

// 递归解析页面和组件 usingComponents。
const jsonQueue = routes.map(route => join(root, route + '.json'))
const processedComponentJson = new Set()
while (jsonQueue.length) {
  const jsonFile = jsonQueue.shift()
  if (!jsonFile || processedComponentJson.has(jsonFile) || !existsSync(jsonFile)) continue
  processedComponentJson.add(jsonFile)
  const config = readJson(jsonFile)
  const using = config.usingComponents && typeof config.usingComponents === 'object'
    ? config.usingComponents
    : {}
  for (const [name, componentRef] of Object.entries(using)) {
    if (/^(?:plugin:|dynamicLib:|ext:)/.test(componentRef)) continue
    if (!componentRef.startsWith('.') && !componentRef.startsWith('/')) {
      warn(jsonFile, `外部组件 ${name} 无法做本地存在性校验：${componentRef}`)
      continue
    }
    const base = resolveProjectRef(jsonFile, componentRef)
    if (!base) continue
    stats.components += 1
    for (const suffix of ['.js', '.json', '.wxml', '.wxss']) {
      addRequiredFile(base + suffix, `组件 ${name} 文件 ${componentRef + suffix}`)
    }
    jsonQueue.push(base + '.json')
  }
}

const nativeTabs = new Set(
  appJson.tabBar && Array.isArray(appJson.tabBar.list)
    ? appJson.tabBar.list.map(item => '/' + String(item.pagePath || '').replace(/^\//, ''))
    : []
)

function checkRouteRef(file, route, text, index) {
  const normalized = route.replace(/^\//, '')
  stats.navigationRefs += 1
  if (!routeSet.has(normalized)) issue(file, '导航目标未注册：/' + normalized, text, index)
}

function resolveModule(fromFile, value) {
  if (!value.startsWith('.') && !value.startsWith('/')) return null
  const base = resolveProjectRef(fromFile, value)
  if (!base) return false
  const candidates = extname(base)
    ? [base]
    : [base, base + '.js', base + '.json', join(base, 'index.js'), join(base, 'index.json')]
  return candidates.find(existsSync) || false
}

const scanQueue = [...activeFiles]
const scannedFiles = new Set()
while (scanQueue.length) {
  const file = scanQueue.shift()
  if (!file || scannedFiles.has(file)) continue
  scannedFiles.add(file)
  if (!existsSync(file)) continue
  const extension = extname(file).toLowerCase()
  if (!['.js', '.wxml', '.wxss'].includes(extension)) continue
  const text = read(file)
  const runtimeText = extension === '.js' ? maskJsComments(text) : text

  if (runtimeText.includes('.backups')) issue(file, '运行源码不得引用 .backups', text, runtimeText.indexOf('.backups'))

  // 所有静态 /pages/.../index 字符串都必须属于 app.json 的正式路由集合。
  const routeRegex = /\/pages\/[A-Za-z0-9_-]+\/index/g
  for (const match of runtimeText.matchAll(routeRegex)) checkRouteRef(file, match[0], text, match.index)

  if (extension === '.js') {
    try {
      new Script(text, { filename: rel(file) })
      stats.jsSyntax += 1
    } catch (error) {
      issue(file, 'JavaScript 语法错误：' + error.message)
    }

    const moduleRegex = /\brequire\s*\(\s*(['"])([^'"]+)\1\s*\)|\bfrom\s*(['"])([^'"]+)\3/g
    for (const match of runtimeText.matchAll(moduleRegex)) {
      const moduleRef = match[2] || match[4]
      if (!moduleRef || (!moduleRef.startsWith('.') && !moduleRef.startsWith('/'))) continue
      stats.moduleRefs += 1
      const moduleFile = resolveModule(file, moduleRef)
      if (!moduleFile) {
        issue(file, '本地模块断链：' + moduleRef, text, match.index)
      } else if (!activeFiles.has(moduleFile)) {
        activeFiles.add(moduleFile)
        if (extname(moduleFile).toLowerCase() === '.json') readJson(moduleFile)
        else scanQueue.push(moduleFile)
      }
    }

    // 没有原生 tabBar 时，wx.switchTab 必然失败；本项目使用自定义 tab-bar。
    for (const match of runtimeText.matchAll(/wx\.switchTab\s*\(/g)) {
      if (!nativeTabs.size) issue(file, '项目未配置原生 tabBar，禁止调用 wx.switchTab', text, match.index)
    }

    const navRegex = /wx\.(navigateTo|redirectTo|reLaunch|switchTab)\s*\(\s*\{/g
    for (const match of runtimeText.matchAll(navRegex)) {
      const objectBody = runtimeText.slice(match.index + match[0].length, match.index + match[0].length + 500)
      const property = objectBody.match(/^\s*url\s*(?::\s*([^,\r\n}]+))?/)
      const expression = property && property[1] ? property[1].trim() : ''
      const url = expression.match(/^(['"`])([^'"`]+)\1/)
      if (!url) {
        stats.dynamicNavigationCalls += 1
        continue
      }
      const page = url[2].match(/\/pages\/[A-Za-z0-9_-]+\/index/)
      if (match[1] === 'switchTab' && page && nativeTabs.size && !nativeTabs.has(page[0])) {
        issue(file, 'switchTab 目标不是原生 tabBar 页面：' + page[0], text, match.index)
      }
    }

    const jsAssetRegex = /(['"`])(\/?assets\/[^'"`\s)]+)\1/g
    for (const match of runtimeText.matchAll(jsAssetRegex)) {
      checkExactLocalRef(file, match[2], '脚本本地资源', text, match.index)
    }
  }

  if (extension === '.wxml') {
    const importRegex = /<(import|include|wxs)\b[^>]*\bsrc\s*=\s*(['"])([^'"]+)\2[^>]*>/g
    for (const match of text.matchAll(importRegex)) {
      stats.templateImports += 1
      const importedFile = checkExactLocalRef(file, match[3], match[1] + ' 模板/模块', text, match.index)
      if (importedFile && match[1] !== 'wxs' && !activeFiles.has(importedFile)) {
        activeFiles.add(importedFile)
        scanQueue.push(importedFile)
      }
    }
    const resourceRegex = /\b(?:src|poster)\s*=\s*(['"])([^'"]+)\1/g
    for (const match of text.matchAll(resourceRegex)) {
      checkExactLocalRef(file, match[2], 'WXML 本地资源', text, match.index)
    }
    const navigatorRegex = /<navigator\b[^>]*\burl\s*=\s*(['"])([^'"]+)\1[^>]*>/g
    for (const match of text.matchAll(navigatorRegex)) {
      if (match[2].includes('{{')) stats.dynamicNavigationCalls += 1
    }
  }

  if (extension === '.wxss') {
    const importRegex = /@import\s+(?:url\()?\s*(['"])([^'"]+)\1\s*\)?\s*;/g
    for (const match of text.matchAll(importRegex)) {
      stats.styleImports += 1
      const importedFile = checkExactLocalRef(file, match[2], 'WXSS @import', text, match.index)
      if (importedFile && !activeFiles.has(importedFile)) {
        activeFiles.add(importedFile)
        scanQueue.push(importedFile)
      }
    }
    const urlRegex = /url\(\s*(['"]?)([^)'"\s]+)\1\s*\)/g
    for (const match of text.matchAll(urlRegex)) {
      checkExactLocalRef(file, match[2], 'WXSS 本地资源', text, match.index)
    }
  }
}

// .backups 可以保留在工作区，但必须从微信上传/预览包排除。
const projectConfigFile = join(root, 'project.config.json')
const projectConfig = readJson(projectConfigFile)
const packOptions = projectConfig.packOptions || {}
const ignores = Array.isArray(packOptions.ignore) ? packOptions.ignore : []
const backupIgnored = ignores.some(item => item && item.type === 'folder' && String(item.value).replace(/[\\/]+$/, '') === '.backups')
if (existsSync(join(root, '.backups')) && !backupIgnored) {
  issue(projectConfigFile, '.backups 存在但未加入 packOptions.ignore')
}
const includes = Array.isArray(packOptions.include) ? packOptions.include : []
if (includes.some(item => String(item && item.value || '').includes('.backups'))) {
  issue(projectConfigFile, 'packOptions.include 不得包含 .backups')
}

if (errors.length) {
  console.error(`运行完整性检查失败：${errors.length} 项`)
  for (const error of errors) console.error('- ' + error)
  if (warnings.length) {
    console.warn(`无法静态确认：${warnings.length} 项`)
    for (const warning of warnings) console.warn('- ' + warning)
  }
  process.exitCode = 1
} else {
  console.log('运行完整性检查通过')
  console.log(`- app.json 正式路由：${stats.routes}/${EXPECTED_ROUTE_COUNT}`)
  console.log(`- 页面四件套：${stats.pageFiles}/${EXPECTED_ROUTE_COUNT * 4}`)
  console.log(`- 本地组件引用：${stats.components}`)
  console.log(`- 静态导航引用：${stats.navigationRefs}`)
  console.log(`- 动态导航调用（已校验同文件静态候选）：${stats.dynamicNavigationCalls}`)
  console.log(`- 本地模块引用：${stats.moduleRefs}`)
  console.log(`- 模板/WXS import：${stats.templateImports}`)
  console.log(`- WXSS import：${stats.styleImports}`)
  console.log(`- 本地资源引用：${stats.localResources}`)
  console.log(`- 运行 JS 语法：${stats.jsSyntax}`)
  console.log(`- 运行环境 fail-closed 用例：${stats.runtimeConfigCases}`)
  console.log(`- .backups：已排除上传包，未纳入运行扫描`)
  if (warnings.length) {
    console.warn(`无法静态确认：${warnings.length} 项`)
    for (const warning of warnings) console.warn('- ' + warning)
  }
}
