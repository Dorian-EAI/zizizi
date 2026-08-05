const app = getApp()

Page({
  data: {
    loading: true,
    hasCard: false,
    cardName: '',
    cardStatus: '',
    usedCount: 0,
    totalCount: 0,
    remainingCount: 0,
    progress: 0,
    expireDate: '',
    usageGroups: [],
    hasRecords: false,
    totalDeduction: '0'
  },

  onLoad() {
    this.loadData()
  },

  async loadData() {
    this.setData({ loading: true })
    const api = app.getApi()
    try {
      const my = await api.annualCard.mine()
      const card = Array.isArray(my) ? (my[0] || null) : my

      if (!card) {
        this.setData({
          loading: false,
          hasCard: false,
          hasRecords: false
        })
        return
      }

      const total = card.total_count != null ? card.total_count : (card.totalTimes || card.quota || 0)
      const used = card.used_count != null ? card.used_count : (card.usedTimes || 0)
      const remain = Math.max(0, total - used)
      const progress = total > 0 ? Math.round((used / total) * 100) : 0
      const tplName = (card.template && card.template.name) || card.templateName || card.name || '家庭年卡'
      const expireRaw = card.valid_end || card.expireAt || card.expireDate || ''
      const expireStr = this._formatDate(expireRaw)
      const status = card.status === 'active' || card.status === 1 ? '生效中' : (card.statusText || '生效中')

      const records = Array.isArray(card.usage_records) ? card.usage_records :
        (Array.isArray(card.usageRecords) ? card.usageRecords : [])

      const usageGroups = this._groupByMonth(records)
      const totalDeduction = this._sumDeduction(records)

      this.setData({
        loading: false,
        hasCard: true,
        cardName: tplName,
        cardStatus: status,
        usedCount: used,
        totalCount: total,
        remainingCount: remain,
        progress: Math.min(100, progress),
        expireDate: expireStr,
        usageGroups: usageGroups,
        hasRecords: records.length > 0,
        totalDeduction: totalDeduction
      })
    } catch (e) {
      console.error('加载年卡使用记录失败', e)
      this.setData({ loading: false, hasCard: false, hasRecords: false })
      wx.showToast({ title: '加载失败', icon: 'none' })
    }
  },

  _formatDate(raw) {
    if (!raw) return ''
    const d = new Date(raw)
    if (isNaN(d.getTime())) return String(raw)
    const y = d.getFullYear()
    const m = String(d.getMonth() + 1).padStart(2, '0')
    const day = String(d.getDate()).padStart(2, '0')
    return `${y}-${m}-${day}`
  },

  _formatDateTime(raw) {
    if (!raw) return ''
    const d = new Date(raw)
    if (isNaN(d.getTime())) return String(raw)
    const y = d.getFullYear()
    const m = String(d.getMonth() + 1).padStart(2, '0')
    const day = String(d.getDate()).padStart(2, '0')
    const h = String(d.getHours()).padStart(2, '0')
    const min = String(d.getMinutes()).padStart(2, '0')
    const now = new Date()
    const isToday = y === now.getFullYear() && d.getMonth() === now.getMonth() && d.getDate() === now.getDate()
    const dateStr = isToday ? '今日' : `${m}-${day}`
    return `${dateStr} ${h}:${min}`
  },

  _groupByMonth(records) {
    if (!records.length) return []
    const groups = {}
    records.forEach((r, idx) => {
      const ts = r.used_at || r.usedAt || r.created_at || r.createdAt || r.useTime || 0
      const d = ts ? new Date(ts) : null
      let year, month
      if (d && !isNaN(d.getTime())) {
        year = d.getFullYear()
        month = d.getMonth() + 1
      } else {
        year = new Date().getFullYear()
        month = new Date().getMonth() + 1
      }
      const key = `${year}-${month}`
      if (!groups[key]) {
        groups[key] = {
          key: key,
          label: `${year} 年 ${month} 月`,
          totalDeduction: 0,
          records: []
        }
      }
      const amount = r.deduct_amount != null ? r.deduct_amount : (r.deductAmount != null ? r.deductAmount : (r.amount || 0))
      groups[key].records.push({
        id: r.id || r.record_id || ('rec_' + idx),
        orderId: r.order_id || r.orderId || r.id || '',
        icon: r.icon || this._pickIcon(r.service_name || r.serviceName || r.title || ''),
        title: r.service_name || r.serviceName || r.title || r.itemName || '服务使用',
        orderNo: r.order_no || r.orderNo || r.order_sn || r.orderSn || '',
        timeText: this._formatDateTime(ts),
        amountText: '抵扣 ¥' + (amount || 0),
        statusText: r.statusText || r.status_text || '已使用',
        statusTone: 'success'
      })
      groups[key].totalDeduction += Number(amount) || 0
    })
    return Object.values(groups).sort((a, b) => b.key.localeCompare(a.key))
  },

  _sumDeduction(records) {
    let sum = 0
    records.forEach(r => {
      const amt = r.deduct_amount != null ? r.deduct_amount : (r.deductAmount != null ? r.deductAmount : (r.amount || 0))
      sum += Number(amt) || 0
    })
    return String(sum)
  },

  _pickIcon(title) {
    const t = String(title || '')
    if (/水|管|漏|堵/.test(t)) return '🔧'
    if (/电|线路|灯|开关/.test(t)) return '⚡'
    if (/空调|清洗|家电/.test(t)) return '✦'
    if (/锁|门/.test(t)) return '🔑'
    if (/家具|木/.test(t)) return '🪑'
    if (/墙|漆|涂/.test(t)) return '🎨'
    return '🔧'
  },

  onRecordTap(e) {
    const orderId = e.currentTarget.dataset.orderid
    if (!orderId) {
      wx.showToast({ title: '订单信息缺失', icon: 'none' })
      return
    }
    wx.navigateTo({
      url: '/pages/order-detail-client/index?id=' + encodeURIComponent(orderId),
      fail: () => {
        wx.showToast({ title: '订单详情暂不可用', icon: 'none' })
      }
    })
  },

  onBack() {
    wx.navigateBack({
      delta: 1,
      fail: () => wx.redirectTo({ url: '/pages/client-annual-card/index' })
    })
  },

  onPullDownRefresh() {
    this.loadData()
    wx.stopPullDownRefresh()
  }
})