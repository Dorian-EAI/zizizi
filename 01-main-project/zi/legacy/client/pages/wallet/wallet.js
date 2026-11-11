const api = require('../../../utils/request')

const TYPE_MAP = {
  order_pay: '订单支付',
  refund: '退款',
  withdraw: '提现',
  recharge: '充值',
  worker_income: '师傅收入',
  commission: '抽成'
}

Page({
  data: {
    wallet: { balance: 0 },
    totalEarnings: '3,826.50',
    monthEarnings: '1,280',
    withdrawable: '2,546.50',
    weekIncome: '1,280',
    weekDays: [
      { day: '周一', height: 40, isToday: false },
      { day: '周二', height: 65, isToday: false },
      { day: '周三', height: 85, isToday: true },
      { day: '周四', height: 50, isToday: false },
      { day: '周五', height: 90, isToday: false },
      { day: '周六', height: 70, isToday: false },
      { day: '周日', height: 30, isToday: false }
    ],
    transactions: [],
    currentTab: 'wallet',
    page: 1,
    size: 20,
    hasMore: true,
    loading: false
  },

  onLoad() {
    this.loadWallet()
    this.loadTransactions(true)
    this.loadWeekData()
  },

  loadWallet() {
    api.get('/api/wallet').then(data => {
      if (data) {
        this.setData({
          wallet: data,
          totalEarnings: data.total_earnings || '3,826.50',
          monthEarnings: data.month_earnings || '1,280',
          withdrawable: data.withdrawable || data.balance || '2,546.50'
        })
      }
    }).catch(() => {})
  },

  loadWeekData() {
    api.get('/api/wallet/week-stats').then(data => {
      if (data && data.days) {
        const today = new Date().getDay()
        const dayNames = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']
        const weekDays = data.days.map((item, index) => ({
          day: dayNames[index],
          height: item.percent || 30,
          isToday: (index === today - 1) || (today === 0 && index === 6)
        }))
        this.setData({
          weekDays,
          weekIncome: data.week_income || '1,280'
        })
      }
    }).catch(() => {})
  },

  loadTransactions(reset = false) {
    if (this.data.loading) return
    if (!reset && !this.data.hasMore) return
    this.setData({ loading: true })
    const page = reset ? 1 : this.data.page
    api.get('/api/wallet/transactions', { page, size: this.data.size }).then(data => {
      const list = Array.isArray(data) ? data : (data.list || [])
      const formatted = list.map(t => ({
        ...t,
        type_text: TYPE_MAP[t.type] || t.type,
        amount_text: (t.direction === 'in' ? '+' : '-') + (t.amount || 0),
        amount_class: t.direction === 'in' ? 'income' : 'outcome'
      }))
      this.setData({
        transactions: reset ? formatted : this.data.transactions.concat(formatted),
        page: page + 1,
        hasMore: list.length === this.data.size,
        loading: false
      })
    }).catch(() => {
      this.setData({ loading: false })
    })
  },

  onPullDownRefresh() {
    this.loadWallet()
    this.loadTransactions(true)
    this.loadWeekData()
    wx.stopPullDownRefresh()
  },

  onReachBottom() {
    this.loadTransactions()
  },

  withdraw() {
    const balance = parseFloat(this.data.withdrawable) || 0
    if (balance <= 0) {
      wx.showToast({ title: '余额不足', icon: 'none' })
      return
    }
    wx.showModal({
      title: '提现金额',
      content: `可提现余额 ¥${balance.toFixed(2)}，请输入提现金额`,
      editable: true,
      placeholderText: '请输入金额',
      success: (res) => {
        if (res.confirm) {
          const amount = parseFloat(res.content)
          if (!amount || amount <= 0) {
            wx.showToast({ title: '请输入有效金额', icon: 'none' })
            return
          }
          if (amount > balance) {
            wx.showToast({ title: '超出可提现余额', icon: 'none' })
            return
          }
          this.collectBankInfo(amount)
        }
      }
    })
  },

  transfer() {
    wx.showModal({
      title: '转账',
      content: '请输入转账金额',
      editable: true,
      placeholderText: '请输入金额',
      success: (res) => {
        if (res.confirm && res.content) {
          wx.showToast({ title: '转账功能开发中', icon: 'none' })
        }
      }
    })
  },

  viewDetail() {
    wx.pageScrollTo({ scrollTop: 500, duration: 300 })
  },

  goDetail(e) {
    const id = e.currentTarget.dataset.id
    if (id) {
      wx.navigateTo({ url: `/pages/wallet/detail/detail?id=${id}` }).catch(() => {})
    }
  },

  collectBankInfo(amount) {
    wx.showModal({
      title: '持卡人姓名',
      editable: true,
      placeholderText: '请输入银行卡开户姓名',
      success: (r1) => {
        if (!r1.confirm || !r1.content) return
        const bank_card_name = r1.content
        wx.showModal({
          title: '银行卡号',
          editable: true,
          placeholderText: '请输入银行卡号',
          success: (r2) => {
            if (!r2.confirm || !r2.content) return
            const bank_card_no = r2.content
            wx.showModal({
              title: '开户银行',
              editable: true,
              placeholderText: '如：中国工商银行',
              success: (r3) => {
                if (!r3.confirm || !r3.content) return
                const bank_name = r3.content
                this.submitWithdraw({ amount, bank_card_name, bank_card_no, bank_name })
              }
            })
          }
        })
      }
    })
  },

  submitWithdraw(body) {
    wx.showLoading({ title: '提交中...' })
    api.post('/api/wallet/withdraw', body).then(() => {
      wx.hideLoading()
      wx.showToast({ title: '提现申请已提交', icon: 'success' })
      this.loadWallet()
      this.loadTransactions(true)
    }).catch(() => {
      wx.hideLoading()
    })
  },

  onTabTap(e) {
    const key = e.currentTarget.dataset.key
    const routes = {
      home: '/pages/worker/index/index',
      orders: '/pages/worker/orders/orders',
      wallet: '/pages/wallet/wallet',
      profile: '/pages/worker/profile/profile'
    }
    const path = routes[key]
    if (path) {
      wx.redirectTo({ url: path })
    }
  }
})
