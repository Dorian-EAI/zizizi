// pages/worker-deposit/index.js — 师傅保证金页（像素级复刻 worker-deposit.html）
const app = getApp()
const { buildIcon, COLORS } = require('../../utils/icons')
const { requestPayment, isPaymentCancelled } = require('../../utils/wx-payment')

const ACCOUNT_NOTES = [
  '保证金等级、接单限制与平台费率均以服务端当前返回为准。',
  '退还申请会实时校验冻结金额、进行中订单和未处理工单。'
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
    statusText: '—',
    levelName: '—',
    accountFacts: [],
    accountNotes: ACCOUNT_NOTES,
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

      const levelMap = { trainee: '见习账户', formal: '正式账户', gold: '金牌账户' }
      const statusMap = { normal: '正常', refunding: '退还审核中', frozen: '已冻结' }
      const levelName = levelMap[detail && detail.deposit_level] || (detail && detail.deposit_level) || '—'
      const statusText = statusMap[detail && detail.status] || (detail && detail.status) || '—'
      const frozen = Number((detail && detail.frozen_amount) || 0) / 100
      const totalDeposited = Number((detail && detail.total_deposited) || 0) / 100
      const cutRate = detail && detail.platform_cut_rate != null
        ? (Number(detail.platform_cut_rate) * 100).toFixed(1).replace(/\.0$/, '') + '%'
        : '—'
      const dailyLimit = detail && detail.daily_order_limit != null
        ? String(detail.daily_order_limit)
        : '—'
      const accountFacts = [
        '账户等级：' + levelName,
        '账户状态：' + statusText,
        '冻结金额：¥' + formatMoney(frozen),
        '累计缴纳：¥' + formatMoney(totalDeposited),
        '每日接单上限（服务端）：' + dailyLimit,
        '平台费率（服务端）：' + cutRate
      ]

      // 格式化记录
      const records = rawRecords.map(r => {
        // 后端 type: deposit/unfreeze=入账，deduct/freeze/refund=出账；amount 恒正
        const incomeTypes = { deposit: true, unfreeze: true }
        const titleMap = {
          deposit: '保证金缴纳',
          unfreeze: '保证金解冻',
          deduct: '保证金扣除',
          freeze: '保证金冻结',
          refund: '保证金退还'
        }
        const isIncome = r.type ? !!incomeTypes[r.type] : r.amount > 0
        return {
          id: r.id || r.created_at || r.time,
          title: r.reason || r.title || titleMap[r.type] || '保证金变动',
          time: r.created_at || r.time || '',
          iconTone: isIncome ? 'income' : 'outcome',
          iconUrl: buildIcon(isIncome ? 'arrow-up' : 'arrow-down',
            isIncome ? COLORS.green : COLORS.red),
          amountText: (isIncome ? '+' : '-') + '¥' + formatMoney(Math.abs(Number(r.amount) || 0) / 100),
          amountTone: isIncome ? 'plus' : 'minus',
          statusText: r.status || '已记录',
          statusTone: isIncome ? 'green' : 'orange'
        }
      })

      this.setData({
        detail,
        balance,
        balanceText: formatMoney(balance),
        statusText,
        levelName,
        accountFacts,
        records
      })
    } catch (e) {
      console.error('加载保证金失败', e)
      this.setData({
        detail: null,
        balance: 0,
        balanceText: formatMoney(0),
        statusText: '—',
        levelName: '—',
        accountFacts: [],
        records: []
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
    if (this.data.paying) return
    const input = await new Promise(resolve => {
      wx.showModal({
        title: '缴纳保证金',
        editable: true,
        placeholderText: '请输入缴纳金额（元）',
        confirmText: '继续',
        confirmColor: '#2D6CDF',
        success: result => resolve(result.confirm ? String(result.content || '').trim() : '')
      })
    })
    if (!input) return
    const payAmount = Number(input)
    if (!/^\d+(?:\.\d{1,2})?$/.test(input) || payAmount <= 0 || payAmount > 1000000) {
      wx.showToast({ title: '请输入有效金额', icon: 'none' })
      return
    }
    const api = app.getApi()
    this.setData({ paying: true })
    try {
      const payParams = await api.deposit.pay(Math.round(payAmount * 100))
      if (payParams && payParams.timeStamp) {
        await requestPayment(payParams)
        wx.showToast({ title: '支付已提交，请稍后确认', icon: 'none', duration: 2500 })
      } else if (!payParams || payParams.balance === undefined) {
        throw new Error('保证金缴纳响应无效')
      } else {
        wx.showToast({ title: '服务端已记录', icon: 'success' })
      }
      await this.loadData()
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
      content: '确定提交保证金退还申请吗？是否可退及后续处理以服务端审核结果为准。',
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
