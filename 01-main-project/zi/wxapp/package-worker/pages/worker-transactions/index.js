// pages/worker-transactions/index.js — 师傅交易明细页（像素级复刻 worker-transactions.html）
const app = getApp()
const api = app.getApi()
const { buildIcon, COLORS } = require('../../utils/icons')

// 千分位金额格式化：1286.5 → "1,286.50"
function formatMoney(num) {
  const n = Number(num) || 0
  return n.toFixed(2).replace(/\B(?=(\d{3})+(?!\d))/g, ',')
}

// 按日期分组：将扁平 list 转换为 [{date, subtotalText, items}] 结构（对应 HTML tx-group）
function buildGroups(list) {
  const map = {}
  const order = []
  list.forEach(item => {
    const fullTime = item.time || ''
    // 拆分日期与时间：'今天 14:30' → date='今天', time='14:30'
    const parts = fullTime.split(' ')
    const date = parts[0] || '其他'
    const timeText = parts.length > 1 ? parts.slice(1).join(' ') : fullTime
    if (!map[date]) {
      map[date] = { date, subtotal: 0, items: [] }
      order.push(date)
    }
    const amt = Number(item.amount) || 0
    const signed = item.type === 'income' ? amt : -amt
    map[date].subtotal += signed
    map[date].items.push(Object.assign({}, item, { timeText }))
  })
  return order.map(k => {
    const g = map[k]
    const sign = g.subtotal >= 0 ? '+' : '-'
    return {
      date: g.date,
      subtotalText: sign + '¥' + formatMoney(Math.abs(g.subtotal)),
      items: g.items
    }
  })
}

// 根据交易类型构建图标 data URI
function buildTxIcon(type) {
  if (type === 'income') return buildIcon('arrow-up', COLORS.green)
  if (type === 'withdraw') return buildIcon('creditCard', '#5A8FAD')
  if (type === 'deduct' || type === 'expense') return buildIcon('scissors', COLORS.accent)
  if (type === 'recharge') return buildIcon('arrow-down', COLORS.green)
  // 兼容原 expense 类型
  return buildIcon('download', COLORS.danger)
}

// 构建金额展示文本：income → '+¥128.00'，其余 → '-¥500.00'
function buildAmountText(item) {
  const amt = formatMoney(item.amount)
  if (item.type === 'income') return '+¥' + amt
  return '-¥' + amt
}

Page({
  data: {
    statusBarHeight: 20,
    navScrolled: false,
    // 筛选标签（对应 HTML filter-segment：全部/收入/提现/扣款）
    tabs: [
      { key: '', label: '全部', selected: true },
      { key: 'income', label: '收入', selected: false },
      { key: 'withdraw', label: '提现', selected: false },
      { key: 'deduct', label: '扣款', selected: false }
    ],
    // 收支汇总（对应 HTML summary-card）
    monthIncome: 0,
    monthIncomeText: '0.00',
    totalWithdrawn: 0,
    totalWithdrawnText: app.globalData.useMock ? '0.00' : '—',
    monthOrders: app.globalData.useMock ? 0 : '—',
    goodRate: app.globalData.useMock ? 98 : '—',
    // 交易分组（由 flat list 转换而来）
    groups: [],
    list: [],
    page: 1,
    pageSize: 20,
    hasMore: true,
    loading: false,
    icons: {}
  },

  onLoad() {
    this.setData({
      statusBarHeight: app.globalData.statusBarHeight || 20,
      icons: {
        back: buildIcon('arrowLeft', COLORS.text1)
      }
    })
    this.loadList(true)
  },

  async loadList(reset) {
    if (this.data.loading) return
    const page = reset ? 1 : this.data.page
    this.setData({ loading: true })
    try {
      const tab = this.data.tabs.find(t => t.selected)
      // 后端 /api/wallet/transactions 参数为 size（非 page_size），type 枚举 income/expense/recharge/withdraw/all
      const typeMap = { '': 'all', income: 'income', withdraw: 'withdraw', deduct: 'expense' }
      const txType = typeMap[tab.key] || 'all'
      const res = await api.wallet.transactions({ type: txType, page: page, size: this.data.pageSize })
      const items = Array.isArray(res) ? res : ((res && (res.list || res.items || res.data)) || [])

      // 汇总数据：/api/wallet/transactions 仅返回 {list,total,page,has_more}，
      // 月收入需并行取 /api/wallet（get_wallet_info 返回 month_income）；其余字段后端未提供，兜底当前值
      let monthIncome = this.data.monthIncome
      let totalWithdrawn = this.data.totalWithdrawn
      if (reset) {
        try {
          const wallet = await api.wallet.detail()
          if (wallet && wallet.month_income != null) monthIncome = wallet.month_income
          if (wallet && wallet.total_withdrawn != null) totalWithdrawn = wallet.total_withdrawn
        } catch (e2) {}
      }
      const monthOrders = this.data.monthOrders
      const goodRate = this.data.goodRate

      const newList = reset ? items : this.data.list.concat(items)
      // 为每条记录补充图标 URL、金额文本、子标题、时间
      const enriched = newList.map(it => Object.assign({}, it, {
        iconUrl: buildTxIcon(it.type),
        amountText: buildAmountText(it),
        // 后端 created_at → 前端 time（buildGroups 按 item.time 分组）
        time: it.time || it.created_at || '',
        // 后端 description / order_id → 前端 sub
        sub: it.sub || it.description || (it.order_id ? ('订单 ' + it.order_id) : (it.order_no ? ('订单 ' + it.order_no) : ''))
      }))
      const groups = buildGroups(enriched)
      this.setData({
        list: newList,
        groups,
        page: page + 1,
        hasMore: res && res.has_more != null ? res.has_more : items.length >= this.data.pageSize,
        monthIncome,
        monthIncomeText: formatMoney(monthIncome),
        totalWithdrawn,
        totalWithdrawnText: formatMoney(totalWithdrawn),
        monthOrders,
        goodRate,
        loading: false
      })
    } catch (e) {
      console.error('加载交易明细失败', e)
      this.setData({ loading: false })
    }
  },

  onTab(e) {
    const idx = e.currentTarget.dataset.idx
    const tabs = this.data.tabs.map((t, i) => ({ ...t, selected: i === idx }))
    this.setData({ tabs, list: [], groups: [], page: 1, hasMore: true })
    this.loadList(true)
  },

  // 滚动驱动标题栏变形：滚动超过 40rpx 时添加磨砂背景
  onScroll(e) {
    const scrollTop = e.detail.scrollTop
    const shouldScroll = scrollTop > 40
    if (shouldScroll !== this.data.navScrolled) {
      this.setData({ navScrolled: shouldScroll })
    }
  },

  onPullDownRefresh() {
    this.setData({ list: [], groups: [], page: 1, hasMore: true })
    this.loadList(true).then(() => wx.stopPullDownRefresh())
  },

  onReachBottom() {
    if (this.data.hasMore && !this.data.loading) this.loadList(false)
  },

  onBack() {
    wx.navigateBack()
  }
})
