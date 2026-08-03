// pages/worker-deposit/index.js — 师傅保证金页（像素级复刻 worker-deposit.html）
const app = getApp()
const { buildIcon, COLORS } = require('../../utils/icons')
const { requestPayment, isPaymentCancelled } = require('../../utils/wx-payment')

const REQUIRED_AMOUNT = 500

// 保证金等级定义（对应 HTML 参考的 level-list）
const DEPOSIT_LEVELS = [
  {
    key: 'standard',
    name: '标准保证金',
    amount: 500,
    state: 'current',
    tagText: '当前',
    tagTone: 'brand',
    benefits: [
      '接单权限：可接普通维修订单',
      '结算周期：T+3 工作日',
      '保证金可申请退还'
    ]
  },
  {
    key: 'silver',
    name: '银牌师傅',
    amount: 2000,
    state: 'locked',
    tagText: '需补缴 ¥1,500',
    tagTone: 'gray',
    benefits: [
      '接单权限：可接高价值订单',
      '结算周期：T+1 工作日',
      '优先派单权益',
      '平台补贴 +5%'
    ]
  },
  {
    key: 'gold',
    name: '金牌师傅',
    amount: 5000,
    state: 'locked',
    tagText: '需补缴 ¥4,500',
    tagTone: 'gray',
    benefits: [
      '接单权限：全部类型订单',
      '结算周期：当日结算',
      '最高优先派单',
      '平台补贴 +10%',
      '专属客服通道'
    ]
  }
]

// 千分位金额格式化
function formatMoney(num) {
  const n = Number(num) || 0
  return n.toFixed(2).replace(/\B(?=(\d{3})+(?!\d))/g, ',')
}

Page({
  data: {
    statusBarHeight: 20,
    detail: null,
    balance: 0,
    balanceText: '0.00',
    statusText: '未缴纳',
    levelName: '标准保证金',
    levels: DEPOSIT_LEVELS,
    benefits: DEPOSIT_LEVELS[0].benefits,
    records: [],
    payAmount: '',
    paying: false,
    navScrolled: false,
    icons: {}
  },

  onLoad() {
    this.setData({
      statusBarHeight: app.globalData.statusBarHeight || 20,
      icons: {
        back: buildIcon('arrowLeft', COLORS.text1),
        shield: buildIcon('shield', COLORS.white),
        check: buildIcon('check', COLORS.green),
        award: buildIcon('award', COLORS.brandWorker),
        checkGreen: buildIcon('check', COLORS.green),
        refresh: buildIcon('refresh', COLORS.white)
      }
    })
  },

  onShow() {
    this.loadData()
  },

  async loadData() {
    const api = app.getApi()
    try {
      const detail = await api.deposit.detail()
      // 保证金接口金额统一为“分”，画布展示统一为“元”。
      const balance = Number((detail && detail.balance) || 0) / 100
      // 后端返回 transactions（非 records）；每条流水字段：id/type/amount/balance_after/reason/created_at
      const rawRecords = (detail && (detail.transactions || detail.records)) || []

      // 状态判定
      let statusText = '未缴纳'
      let levelName = '标准保证金'
      let currentLevelIdx = 0
      if (balance >= 5000) {
        statusText = '已缴足'
        levelName = '金牌师傅'
        currentLevelIdx = 2
      } else if (balance >= 2000) {
        statusText = '已缴足'
        levelName = '银牌师傅'
        currentLevelIdx = 1
      } else if (balance >= REQUIRED_AMOUNT) {
        statusText = '已缴足'
        levelName = '标准保证金'
        currentLevelIdx = 0
      } else if (balance > 0) {
        statusText = '部分缴纳'
      }

      // 构建等级列表（根据余额动态标记 current/locked 及补缴金额）
      const levels = DEPOSIT_LEVELS.map((lv, i) => {
        const state = i === currentLevelIdx ? 'current' : 'locked'
        let tagText = ''
        let tagTone = 'gray'
        if (i === currentLevelIdx) {
          tagText = '当前'
          tagTone = 'brand'
        } else {
          const diff = lv.amount - balance
          tagText = diff > 0 ? '需补缴 ¥' + formatMoney(diff) : '已满足'
          tagTone = 'gray'
        }
        return Object.assign({}, lv, { state, tagText, tagTone })
      })

      // 格式化记录
      const records = rawRecords.map(r => {
        // 后端 type: deposit/unfreeze=入账，deduct/freeze/refund=出账；amount 恒正
        const incomeTypes = { deposit: true, unfreeze: true }
        const isIncome = r.type ? !!incomeTypes[r.type] : r.amount > 0
        return {
          id: r.id || r.created_at || r.time,
          title: r.reason || r.title || (isIncome ? '保证金缴纳' : '保证金退还'),
          time: r.created_at || r.time || '',
          iconTone: isIncome ? 'income' : 'outcome',
          iconUrl: buildIcon(isIncome ? 'arrow-up' : 'arrow-down',
            isIncome ? COLORS.green : COLORS.red),
          amountText: (isIncome ? '+' : '-') + '¥' + formatMoney(Math.abs(Number(r.amount) || 0) / 100),
          amountTone: isIncome ? 'plus' : 'minus',
          statusText: r.status || (isIncome ? '已到账' : '已退款'),
          statusTone: isIncome ? 'green' : 'orange'
        }
      })

      this.setData({
        detail,
        balance,
        balanceText: formatMoney(balance),
        statusText,
        levelName,
        levels,
        benefits: levels[currentLevelIdx].benefits,
        records
      })
    } catch (e) {
      console.error('加载保证金失败', e)
      // 失败时保留默认等级数据
      this.setData({
        balanceText: formatMoney(0),
        levels: DEPOSIT_LEVELS.map((lv, i) => Object.assign({}, lv, {
          state: i === 0 ? 'current' : 'locked',
          tagText: i === 0 ? '当前' : '需补缴 ¥' + formatMoney(lv.amount),
          tagTone: i === 0 ? 'brand' : 'gray'
        })),
        benefits: DEPOSIT_LEVELS[0].benefits
      })
    }
  },

  // 滚动驱动标题栏变形动画
  onScroll(e) {
    const scrollTop = e.detail.scrollTop
    const shouldScroll = scrollTop > 40
    if (shouldScroll !== this.data.navScrolled) {
      this.setData({ navScrolled: shouldScroll })
    }
  },

  onBack() {
    wx.navigateBack({ delta: 1 })
  },

  async onPay() {
    // 补缴保证金：跳转到缴纳流程（使用默认补缴金额或让用户输入）
    const api = app.getApi()
    const diff = REQUIRED_AMOUNT - this.data.balance
    const payAmount = diff > 0 ? diff : REQUIRED_AMOUNT
    this.setData({ paying: true })
    try {
      const payParams = await api.deposit.pay(Math.round(payAmount * 100))
      // 兼容当前后端“直接入账”响应；后端返回 JSAPI 参数后自动走真实微信支付。
      if (payParams && payParams.timeStamp) {
        await requestPayment(payParams)
      } else if (!payParams || payParams.balance === undefined) {
        throw new Error('保证金缴纳响应无效')
      }
      wx.showToast({ title: '缴纳成功', icon: 'success' })
      this.loadData()
    } catch (e) {
      console.error('缴纳失败', e)
      if (isPaymentCancelled(e)) {
        wx.showToast({ title: '已取消支付', icon: 'none' })
      } else {
        wx.showToast({ title: '缴纳失败', icon: 'none' })
      }
    } finally {
      this.setData({ paying: false })
    }
  },

  async onRefund() {
    const api = app.getApi()
    wx.showModal({
      title: '申请退还',
      content: '确定要申请保证金退款吗？审核通过后将原路退回。',
      success: async (res) => {
        if (!res.confirm) return
        try {
          await api.deposit.refund()
          wx.showToast({ title: '已提交申请', icon: 'success' })
          this.loadData()
        } catch (e) {
          console.error('退款失败', e)
          wx.showToast({ title: '申请失败', icon: 'none' })
        }
      }
    })
  }
})
