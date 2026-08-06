import { existsSync, readFileSync, readdirSync } from 'node:fs'
import { dirname, extname, isAbsolute, join, relative, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { Script } from 'node:vm'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const errors = []
const warnings = []
const activeFiles = new Set()
const parsedJson = new Map()
const AUXILIARY_ROUTES = new Set(['pages/entry/index', 'pages/search/index'])

function targetForDesignSource(source) {
  const name = String(source || '').split('/').pop().replace(/\.html$/, '')
  if (name.startsWith('client-home-glass-neu')) return 'client-home'
  if (name === 'client-address') return 'address'
  if (name === 'client-order-detail') return 'order-detail-client'
  if (name === 'worker-order-detail') return 'order-detail-worker'
  if (name === 'client-order-tracking-2') return 'client-order-tracking'
  return name
}

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
  wxmlSyntax: 0,
  runtimeConfigCases: 0,
  truthfulnessRules: 0
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

function checkWxmlStructure(file, source) {
  const stack = []
  const voidTags = new Set(['image', 'input', 'import', 'include', 'wxs', 'icon', 'progress', 'slider', 'switch'])
  let cursor = 0
  while (cursor < source.length) {
    const start = source.indexOf('<', cursor)
    if (start < 0) break
    if (source.startsWith('<!--', start)) {
      const end = source.indexOf('-->', start + 4)
      if (end < 0) {
        issue(file, 'WXML 注释未闭合', source, start)
        return
      }
      cursor = end + 3
      continue
    }
    let quote = ''
    let end = start + 1
    for (; end < source.length; end += 1) {
      const char = source[end]
      if (quote) {
        if (char === quote) quote = ''
      } else if (char === '"' || char === "'") {
        quote = char
      } else if (char === '>') {
        break
      }
    }
    if (end >= source.length) {
      issue(file, 'WXML 标签未闭合', source, start)
      return
    }
    const body = source.slice(start + 1, end).trim()
    cursor = end + 1
    if (!body || body[0] === '!' || body[0] === '?') continue
    const closing = body[0] === '/'
    const nameMatch = body.match(/^\/?([A-Za-z][\w-]*)/)
    if (!nameMatch) continue
    const name = nameMatch[1]
    if (closing) {
      const opened = stack.pop()
      if (!opened || opened.name !== name) {
        issue(file, `WXML 标签错配：期望 </${opened ? opened.name : '无'}>，实际 </${name}>`, source, start)
        return
      }
    } else if (!body.endsWith('/') && !voidTags.has(name)) {
      stack.push({ name, index: start })
    }
  }
  if (stack.length) {
    const opened = stack[stack.length - 1]
    issue(file, `WXML 标签未闭合：<${opened.name}>`, source, opened.index)
    return
  }
  stats.wxmlSyntax += 1
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

function checkTruthfulRuntimeSemantics() {
  const rules = [
    {
      file: 'pages/client-service/index.wxml',
      forbidden: [/400[-\d ]{6,}/, /7x24小时在线/, /平均响应\s*30秒/, /8:00-22:00/],
      required: [/servicePhoneDisplay/, /servicePhoneConfigured/]
    },
    {
      file: 'pages/search/index.wxml',
      forbidden: [/400[-\d ]{6,}/, /7x24小时在线/, /平均响应\s*30秒/, /8:00-22:00/],
      required: [/servicePhoneDisplay/, /servicePhoneConfigured/]
    },
    {
      file: 'pages/worker-appeal/index.wxml',
      forbidden: [/工单WO20260720/, /限制抢单3天/, /扣除保证金 ¥200/, /3个工作日内复核/],
      required: [/wx:for="{{appeals}}"/, /暂无申诉记录/]
    },
    {
      file: 'pages/worker-appeal/index.js',
      required: [/api\.ticket\.mine\(/, /ticket_type:\s*'appeal'/]
    },
    {
      file: 'pages/worker-training/index.js',
      forbidden: [/高客单价订单/, /优先派单权益/, /平台抽成降低/],
      required: [/LEARNING_NOTES/, /duration_minutes/, /total_credits/]
    },
    {
      file: 'pages/worker-quote-submit/index.wxml',
      forbidden: [/平台抽成\s*<text/, /预计到手/, /\b5%/],
      required: [/服务端结算规则/]
    },
    {
      file: 'pages/worker-quote-submit/index.js',
      forbidden: [/PLATFORM_FEE_RATE/, /computePayout/, /materialFee/]
    },
    {
      file: 'pages/worker-deposit/index.js',
      forbidden: [/DEPOSIT_LEVELS/, /优先派单/, /平台补贴/, /T\+\d/],
      required: [/accountFacts/, /platform_cut_rate/, /daily_order_limit/]
    },
    {
      file: 'pages/worker-settings/index.wxml',
      forbidden: [/张师傅/, /已完成\s*328/, /好评率\s*98%/, /5 公里/, /防水\/家电\/管道/],
      required: [/workerProfile\.phoneStatusText/, /workerProfile\.certificationText/, /workerProfile\.praiseRateText/]
    },
    {
      file: 'pages/client-service-detail/index.wxml',
      forbidden: [/王师傅/, /陈师傅/, /李女士/, /张先生/, /326次服务/, /215次服务/],
      required: [/wx:for="{{workers}}"/, /wx:for="{{reviews}}"/]
    },
    {
      file: 'pages/client-service-detail/index.js',
      required: [/api\.services\.workers\(/, /api\.reviews\.list\(/, /api\.reviews\.stats\(/]
    },
    {
      file: 'pages/client-order-tracking/index.wxml',
      forbidden: [/rating\s*\|\|\s*'4\.8'/, /services\s*\|\|\s*158/],
      required: [/tracking\.worker\.certified === true/]
    },
    {
      file: 'pages/worker-profile/index.wxml',
      required: [/workerInfo\.verifyStatus/]
    },
    {
      file: 'pages/worker-recharge/index.js',
      forbidden: [
        /title:\s*'充值成功'/,
        /充值金额即时到账/,
        /wallet\.recharge\s*\(/,
        /wxpay\.rechargeJsapi\s*\(/,
        /requestPayment\s*\(/
      ],
      required: [/不开放师傅充值/, /不发起任何资金请求/]
    },
    {
      file: 'pages/client-login/index.js',
      required: [/api\.auth\.wxLogin\(/, /client-agreement\/index\?document=/, /AUTH_REQUIRED/, /请先阅读并同意协议/]
    },
    {
      file: 'pages/client-agreement/index.js',
      forbidden: [/slice\(0,\s*1800\)/],
      required: [/pages\.agreement\(/, /pages\.privacy\(/, /pages\.byKey\(/]
    },
    {
      file: 'pages/client-customer-service/index.js',
      forbidden: [/小佳/, /人工客服.*在线/],
      required: [/\.ticket\.create\(/, /\.ticket\.detail\(/, /\.ticket\.reply\(/]
    },
    {
      file: 'pages/client-points/index.js',
      forbidden: [/2680/, /got_points\s*\|\|\s*10/],
      required: [/\.points\.detail\(/, /\.points\.logs\(/, /\.points\.signin\(/]
    },
    {
      file: 'pages/client-invite/index.wxml',
      forbidden: [/ZJR8866/, /累计奖励.*240/, /已邀请人数.*12/],
      required: [/邀请关系与奖励结算/, /不会生成邀请码/]
    },
    {
      file: 'pages/client-payment/index.js',
      forbidden: [/168\.00/, /支付宝/, /银行卡/, /status === 'success'/, /status === 'paid'\s*\|\|/],
      required: [
        /allowed_actions/,
        /payment_methods/,
        /getPaymentAttemptKey\(/,
        /\.wxpay\.orderJsapi\([^)]*idempotencyKey[^)]*\)/s,
        /\.wallet\.pay\([^)]*idempotencyKey\)/s,
        /\.wxpay\.paymentStatus\(/,
        /status === 'paid'/
      ]
    },
    {
      file: 'pages/client-review/index.js',
      forbidden: [/张师傅/, /rating:\s*5/],
      required: [/allowed_actions/, /\.orders\.review\(/, /\.upload\.image\(/]
    },
    {
      file: 'pages/client-price-adjust/index.js',
      forbidden: [/50\.00/, /158\.00/, /208\.00/],
      required: [/allowed_actions/, /\.extraFee\.list\(/, /\.extraFee\.approve\(/, /\.extraFee\.reject\(/]
    },
    {
      file: 'pages/client-wallet/index.wxml',
      forbidden: [/1,280\.50/, /2,580/, /1,300/, /202608030001/, /张师傅/],
      required: [/balanceText/, /monthIncomeText/, /wx:for="{{transactions}}"/, /暂无交易/]
    },
    {
      file: 'pages/client-wallet/index.js',
      required: [/api\.wallet\.detail\(/, /api\.wallet\.transactions\(/]
    },
    {
      file: 'pages/client-wallet-recharge/index.js',
      forbidden: [/title:\s*'充值成功'/, /status === 'success'/],
      required: [
        /idempotency\.getOrCreate\(/,
        /\.wxpay\.rechargeJsapi\([^)]*key\)/s,
        /\.wxpay\.paymentStatus\(/,
        /status === 'paid'/,
        /PENDING_STORAGE_KEY/
      ]
    },
    {
      file: 'pages/client-wallet-recharge/index.wxml',
      forbidden: [/1,280\.50/, /确认充值 ¥500<\/view>/],
      required: [/balanceText/, /statusText/, /刷新上笔充值结果/, /支付结果以服务端验签回调为准/]
    },
    {
      file: 'pages/client-payment-result/index.js',
      forbidden: [/status === 'success'/, /title:\s*'支付成功'/],
      required: [/\.wxpay\.paymentStatus\(/, /status === 'paid'/, /applyPaid\(/]
    },
    {
      file: 'pages/client-payment-result/index.wxml',
      forbidden: [/268\.00/, /202608030001/, /恭喜获得 26 积分/],
      required: [/paymentNo/, /只有服务端支付单状态为 paid/, /刷新服务端结果/]
    },
    {
      file: 'pages/client-wallet-withdraw/index.js',
      forbidden: [/\.wallet\.withdraw\(/, /title:\s*'提现成功'/],
      required: [/仅允许师傅收入账户/, /未提交、未冻结、未扣减任何资金/]
    },
    {
      file: 'pages/client-wallet-withdraw/index.wxml',
      forbidden: [/1,280\.50/, /招商银行/, /尾号 6688/, /确认提现 ¥500/],
      required: [/客户端提现尚未开放/, /不会调用师傅提现接口/, /提现暂未开放/]
    },
    {
      file: 'utils/transaction-list-page.js',
      required: [/\.wallet\.transactions\(/, /size:\s*100/, /transactionView/]
    },
    {
      file: 'pages/client-transaction-detail/index.wxml',
      forbidden: [/TX20260803001/, /水管维修/, /张师傅/, /268\.00/],
      required: [/transaction\.id/, /transaction\.statusText/, /服务端流水/]
    },
    {
      file: 'pages/client-bank-cards/index.wxml',
      forbidden: [/8888/, /6666/, /张先生/, /招商银行/, /工商银行/],
      required: [/银行卡服务暂未开放/, /不展示画布示例卡号/]
    },
    {
      file: 'pages/client-bank-card-add/index.wxml',
      forbidden: [/110\*+5219/, /张先生/, /138\*+8888/],
      required: [/当前不收集/, /实名校验与令牌化存储尚未接入/]
    },
    {
      file: 'pages/client-refund/index.js',
      forbidden: [/\.wallet\.refund\(/],
      required: [/\.ticket\.create\(/, /ticket_type:\s*'refund_review'/, /不会立即退款或变更资金/]
    },
    {
      file: 'pages/client-refund/index.wxml',
      forbidden: [/张师傅/, /水管维修服务/, /268\.00/],
      required: [/退款审核工单/, /不直接执行退款/]
    },
    {
      file: 'pages/client-refund-card/index.js',
      forbidden: [/\.annualCard\.refund\(/, /title:\s*'退卡成功'/],
      required: [/年卡退款服务当前明确返回未实现/, /不会冻结年卡/]
    },
    {
      file: 'pages/client-annual-card/index.js',
      forbidden: [/\.annualCard\.refund\(/, /title:\s*'退卡成功'/],
      required: [/client-refund-card\/index\?cardId=/]
    },
    {
      file: 'pages/client-refund-card-result/index.js',
      forbidden: [/titleText:\s*'退卡申请已提交'/],
      required: [/status === 'refunded'/, /status === 'refunding'/, /未提交退卡申请/]
    },
    {
      file: 'pages/client-claim-result/index.js',
      required: [/\.insurance\.claims\(/, /STATUS_VIEW/, /未找到理赔记录/]
    },
    {
      file: 'pages/client-insurance-claim/index.js',
      forbidden: [/24小时内联系/, /title:\s*'提交成功'/],
      required: [/const claim = await api\.insurance\.claim\(/, /client-claim-result\/index\?claimId=/]
    },
    {
      file: 'pages/client-claim-result/index.wxml',
      forbidden: [/2,580/, /202608030001/, /理赔申请已提交/],
      required: [/amountText/, /statusText/, /只按服务端真实理赔状态/]
    },
    {
      file: 'pages/client-invoice/index.wxml',
      forbidden: [/1,247\.00/, /299\.00/, /948\.00/, /张先生/, /北京自家人科技有限公司/],
      required: [/暂未接入/, /暂无可验证的发票记录/, /不会在当前版本收集或伪造/]
    },
    {
      file: 'pages/client-invoice-orders/index.wxml',
      forbidden: [/202608030001/, /202608010016/, /202607300088/, /1,247\.00/, /¥559/],
      required: [/开票资格待接入/, /不能把普通已完成订单推断成可开票订单/]
    },
    {
      file: 'pages/client-invoice-detail/index.wxml',
      forbidden: [/00123456/, /299\.00/, /8\.71/, /91110/, /张先生/],
      required: [/未提供可验证的发票记录/, /不会生成占位 PDF/]
    },
    {
      file: 'pages/client-invoice-title-edit/index.wxml',
      forbidden: [/91110/, /zhang@example\.com/, /138\*+8888/, /自家人科技有限公司/],
      required: [/当前不收集/, /保存契约尚未接入/]
    },
    {
      file: 'pages/client-coupon-select/index.js',
      required: [/\.orders\.paymentQuote\(/, /\.coupon\.available\(/, /couponSelected/]
    },
    {
      file: 'pages/client-payment/index.js',
      required: [/client-coupon-select\/index/, /couponSelected/, /refreshQuoteForCoupon\(selected\)/]
    },
    {
      file: 'pages/client-coupon-detail/index.wxml',
      forbidden: [/¥20/, /满 ¥100/, /预计省 ¥20/],
      required: [/coupon\.minSpendText/, /支付创建时服务端会再次锁定并校验/]
    }
  ]

  for (const rule of rules) {
    const file = join(root, rule.file)
    const source = read(file)
    for (const pattern of rule.forbidden || []) {
      stats.truthfulnessRules += 1
      const match = source.match(pattern)
      if (match) issue(file, '检测到禁止的演示/固定业务文案：' + pattern, source, match.index)
    }
    for (const pattern of rule.required || []) {
      stats.truthfulnessRules += 1
      if (!pattern.test(source)) issue(file, '缺少真实数据绑定或确认流程：' + pattern)
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
const designFile = resolve(root, '..', 'zjrnew', 'zjrnew.design')
const design = readJson(designFile)
const expectedRoutes = new Set(AUXILIARY_ROUTES)
for (const node of Array.isArray(design.data) ? design.data : []) {
  const source = node && node.devMetadata && node.devMetadata.htmlSrc
  const target = targetForDesignSource(source)
  if (target) expectedRoutes.add(`pages/${target}/index`)
}
const expectedRouteCount = expectedRoutes.size
addRequiredFile(join(root, 'app.js'), '应用入口脚本')
addRequiredFile(appJsonFile, '应用配置')
addRequiredFile(join(root, 'app.wxss'), '应用全局样式')
checkRuntimeEnvironmentGate()
checkTruthfulRuntimeSemantics()

const routes = Array.isArray(appJson.pages) ? appJson.pages.map(route => String(route).replace(/^\//, '')) : []
const routeSet = new Set(routes)
stats.routes = routes.length

if (routes.length !== expectedRouteCount) {
  issue(appJsonFile, `当前画布与辅助页应为 ${expectedRouteCount} 条正式路由，当前为 ${routes.length} 条`)
}
if (routeSet.size !== routes.length) issue(appJsonFile, 'pages 中存在重复路由')
for (const route of expectedRoutes) {
  if (!routeSet.has(route)) issue(appJsonFile, '缺少画布或辅助页路由：' + route)
}
for (const route of routeSet) {
  if (!expectedRoutes.has(route)) issue(appJsonFile, '存在未登记正式路由：' + route)
}
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
    checkWxmlStructure(file, text)
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
    if (file === join(root, 'styles', 'generated-detail-page.wxss')) {
      const brokenGeneratedSelectors = [/\.\./, /-\.design-/, /page-page/, /icon-\.design/, /\btranslate\s*:/]
      for (const pattern of brokenGeneratedSelectors) {
        const match = text.match(pattern)
        if (match) issue(file, '生成共享样式包含损坏选择器：' + pattern, text, match.index)
      }
    }
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
  console.log(`- app.json 正式路由：${stats.routes}/${expectedRouteCount}`)
  console.log(`- 页面四件套：${stats.pageFiles}/${expectedRouteCount * 4}`)
  console.log(`- 本地组件引用：${stats.components}`)
  console.log(`- 静态导航引用：${stats.navigationRefs}`)
  console.log(`- 动态导航调用（已校验同文件静态候选）：${stats.dynamicNavigationCalls}`)
  console.log(`- 本地模块引用：${stats.moduleRefs}`)
  console.log(`- 模板/WXS import：${stats.templateImports}`)
  console.log(`- WXSS import：${stats.styleImports}`)
  console.log(`- 本地资源引用：${stats.localResources}`)
  console.log(`- 运行 JS 语法：${stats.jsSyntax}`)
  console.log(`- WXML 结构：${stats.wxmlSyntax}`)
  console.log(`- 运行环境 fail-closed 用例：${stats.runtimeConfigCases}`)
  console.log(`- 真实运行语义规则：${stats.truthfulnessRules}`)
  console.log(`- .backups：已排除上传包，未纳入运行扫描`)
  if (warnings.length) {
    console.warn(`无法静态确认：${warnings.length} 项`)
    for (const warning of warnings) console.warn('- ' + warning)
  }
}
