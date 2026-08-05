const { money, listFromPage } = require('../../utils/client-finance')

function formatPeriodLabel(period, date) {
  const year = date.getFullYear()
  const month = date.getMonth() + 1
  if (period === 'month') return year + ' 年 ' + month + ' 月'
  if (period === 'quarter') return year + ' 年第 ' + Math.ceil(month / 3) + ' 季度'
  if (period === 'year') return year + ' 年'
  return ''
}

function getMonthStart(date) {
  return new Date(date.getFullYear(), date.getMonth(), 1)
}

function getStartDate(period, now) {
  if (period === 'month') return getMonthStart(now)
  if (period === 'quarter') {
    const q = Math.floor(now.getMonth() / 3)
    return new Date(now.getFullYear(), q * 3, 1)
  }
  if (period === 'year') return new Date(now.getFullYear(), 0, 1)
  return getMonthStart(now)
}

function matchesPeriod(createdAt, startDate, endDate) {
  if (!createdAt) return false
  const raw = String(createdAt)
  const date = new Date(raw.indexOf('T') < 0 ? raw.replace(' ', 'T') + 'Z' : raw)
  if (Number.isNaN(date.getTime())) return false
  return date >= startDate && date < endDate
}

function categorizeTransaction(raw) {
  const desc = String(raw.description || raw.title || '').toLowerCase()
  const type = String(raw.type || '').toLowerCase()

  if (type === 'expense' || type === 'withdraw') {
    if (desc.indexOf('年卡') >= 0 || desc.indexOf('会员卡') >= 0 || desc.indexOf('会员') >= 0 || desc.indexOf('annual') >= 0) {
      return 'annual'
    }
    if (desc.indexOf('维修') >= 0 || desc.indexOf('防水') >= 0 || desc.indexOf('水电') >= 0 ||
        desc.indexOf('家电') >= 0 || desc.indexOf('管道') >= 0 || desc.indexOf('疏通') >= 0 ||
        desc.indexOf('开锁') >= 0 || desc.indexOf('墙地') >= 0 || desc.indexOf('美容') >= 0 ||
        desc.indexOf('检测') >= 0 || desc.indexOf('paint') >= 0 || desc.indexOf('appliance') >= 0 ||
        desc.indexOf('plumbing') >= 0 || desc.indexOf('electric') >= 0 || desc.indexOf('pipeline') >= 0 ||
        desc.indexOf('lock') >= 0 || desc.indexOf('carpentry') >= 0) {
      return 'service'
    }
    if (type === 'withdraw') return 'withdraw'
    return 'other'
  }
  return null
}

const CATEGORY_META = {
  service: { icon: '修', title: '维修服务',     copy: '防水、家电、电路等' },
  annual:  { icon: '卡', title: '会员与年卡',   copy: '家庭年卡续费' },
  withdraw: { icon: '提', title: '提现',        copy: '余额提现' },
  other:   { icon: '其', title: '其他',         copy: '服务费与调整' }
}

Page({
  data: {
    loading: true,
    loadError: '',
    activePeriod: 'month',
    periodLabel: '',
    incomeText: '¥0.00',
    expenseText: '¥0.00',
    netText: '¥0.00',
    netTrendText: '暂无上期对比数据',
    expenseCategories: [],
    isEmpty: false,
    emptyText: '暂无收支数据',
    updatedText: '正在加载'
  },

  onLoad() {
    const now = new Date()
    this.setData({
      periodLabel: formatPeriodLabel('month', now)
    })
  },

  onShow() {
    this.loadTransactions()
  },

  onPullDownRefresh() {
    this.loadTransactions().then(() => {
      wx.stopPullDownRefresh()
    })
  },

  onPeriodChange(e) {
    const period = String(e.currentTarget.dataset.period || 'month')
    if (period === this.data.activePeriod) return
    const now = new Date()
    this.setData({
      activePeriod: period,
      periodLabel: formatPeriodLabel(period, now)
    })
    this.computeStats(this._rawTransactions || [])
  },

  onRefresh() {
    this.loadTransactions()
  },

  async loadTransactions() {
    if (this._loading) return
    this._loading = true
    this.setData({ loading: true, loadError: '' })

    try {
      const api = getApp().getApi()
      const page = await api.wallet.transactions({ page: 1, size: 200 })
      const all = listFromPage(page)
      this._rawTransactions = all
      this.setData({ updatedText: '已更新至今天' })
      this.computeStats(all)
    } catch (error) {
      console.error('[收支统计] 加载失败', error)
      this.setData({
        loading: false,
        loadError: error.message || '加载失败，请稍后重试',
        isEmpty: true,
        emptyText: '加载失败，请点击重试'
      })
    } finally {
      this._loading = false
    }
  },

  computeStats(allTransactions) {
    const now = new Date()
    const period = this.data.activePeriod

    const currentStart = getStartDate(period, now)
    const currentEnd = new Date(now.getFullYear(), now.getMonth() + (period === 'month' ? 1 : (period === 'quarter' ? 0 : 0)), 1)
    if (period === 'month') {
      currentEnd.setMonth(currentEnd.getMonth() + 1)
    } else if (period === 'quarter') {
      currentEnd.setMonth(currentEnd.getMonth() + 3)
    } else {
      currentEnd.setFullYear(currentEnd.getFullYear() + 1)
    }

    let prevStart, prevEnd
    if (period === 'month') {
      prevStart = new Date(now.getFullYear(), now.getMonth() - 1, 1)
      prevEnd = currentStart
    } else if (period === 'quarter') {
      prevStart = new Date(now.getFullYear(), currentStart.getMonth() - 3, 1)
      prevEnd = currentStart
    } else {
      prevStart = new Date(now.getFullYear() - 1, 0, 1)
      prevEnd = currentStart
    }

    const currentList = allTransactions.filter(t => matchesPeriod(t.created_at, currentStart, currentEnd))
    const prevList = allTransactions.filter(t => matchesPeriod(t.created_at, prevStart, prevEnd))

    const isIncome = t => ['income', 'recharge', 'refund'].indexOf(String(t.type || '').toLowerCase()) >= 0
    const isExpense = t => ['expense', 'withdraw'].indexOf(String(t.type || '').toLowerCase()) >= 0

    const income = currentList.filter(isIncome).reduce((s, t) => s + Math.abs(Number(t.amount) || 0), 0)
    const expense = currentList.filter(isExpense).reduce((s, t) => s + Math.abs(Number(t.amount) || 0), 0)
    const net = income - expense

    const prevExpense = prevList.filter(isExpense).reduce((s, t) => s + Math.abs(Number(t.amount) || 0), 0)

    let trendText = '暂无上期对比数据'
    if (prevExpense > 0) {
      const diff = expense - prevExpense
      const pct = Math.round(Math.abs(diff) / prevExpense * 100)
      if (diff < 0) trendText = '较上期减少 ' + pct + '%'
      else if (diff > 0) trendText = '较上期增加 ' + pct + '%'
      else trendText = '与上期持平'
    } else if (expense > 0) {
      trendText = '本期新增支出 ¥' + money(expense)
    }

    const categoryMap = {}
    currentList.filter(isExpense).forEach(t => {
      const cat = categorizeTransaction(t)
      if (!cat) return
      categoryMap[cat] = (categoryMap[cat] || 0) + Math.abs(Number(t.amount) || 0)
    })

    const totalExpense = Object.values(categoryMap).reduce((s, v) => s + v, 0)
    const expenseCategories = Object.keys(categoryMap)
      .map(key => ({
        key,
        icon: CATEGORY_META[key].icon,
        title: CATEGORY_META[key].title,
        copy: CATEGORY_META[key].copy,
        amountText: '¥' + money(categoryMap[key]),
        percentText: totalExpense > 0 ? Math.round(categoryMap[key] / totalExpense * 100) + '%' : '0%'
      }))
      .sort((a, b) => {
        const aVal = Number(a.amountText.replace(/[^\d.]/g, '')) || 0
        const bVal = Number(b.amountText.replace(/[^\d.]/g, '')) || 0
        return bVal - aVal
      })

    const isEmpty = currentList.length === 0

    this.setData({
      loading: false,
      incomeText: '¥' + money(income),
      expenseText: '¥' + money(expense),
      netText: '¥' + money(Math.abs(net)),
      netTrendText: trendText,
      expenseCategories,
      isEmpty,
      emptyText: period === 'year' ? '本年度暂无收支记录' : (period === 'quarter' ? '本季度暂无收支记录' : '本月暂无收支记录')
    })
  },

  onNavigate(e) {
    const dataset = e && e.currentTarget && e.currentTarget.dataset || {}
    const route = String(dataset.route || '')
    if (!route) {
      wx.showToast({ title: '页面入口未配置', icon: 'none' })
      return
    }
    wx.navigateTo({
      url: route,
      fail: () => {
        wx.showToast({ title: '目标页面暂不可用', icon: 'none' })
      }
    })
  },

  onBack() {
    wx.navigateBack({
      delta: 1,
      fail: () => {
        wx.reLaunch({ url: '/pages/client-wallet/index' })
      }
    })
  },

  onAction(e) {
    const dataset = e && e.currentTarget && e.currentTarget.dataset || {}
    const action = String(dataset.action || '')
    if (action === 'open-income-calendar') {
      wx.showToast({ title: '日期选择暂未开放', icon: 'none' })
      return
    }
    wx.showToast({ title: '功能开发中', icon: 'none' })
  }
})