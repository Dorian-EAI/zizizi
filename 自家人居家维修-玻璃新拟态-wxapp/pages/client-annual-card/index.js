// pages/client-annual-card/index.js — 家庭年卡页
const app = getApp()
const { buildIcon, COLORS } = require('../../utils/icons')

Page({
  data: {
    statusBarHeight: 20,
    templates: [],
    myCard: null,
    myCardTotal: 0,
    myCardProgress: 0,
    selectedPlanId: '',
    serviceTypes: [
      '水电维修', '家电维修', '管道疏通', '灯具安装',
      '五金更换', '门锁维修', '家具维修', '墙面修补'
    ],
    usageRecords: [],
    compareCols: [],
    compareRows: [],
    icons: {}
  },

  onLoad() {
    this.setData({
      statusBarHeight: app.globalData.statusBarHeight || 20,
      icons: {
        back: buildIcon('chevronLeft', COLORS.text1),
        check: buildIcon('check', COLORS.brand),
        star: buildIcon('star', COLORS.accent),
        shield: buildIcon('shield', COLORS.brand)
      }
    })
    this.loadData()
  },

  async loadData() {
    const api = app.getApi()
    try {
      const [templates, my] = await Promise.all([
        api.annualCard.templates(),
        api.annualCard.mine().catch(() => null)
      ])
      const list = templates || []
      const tplList = list.map(t => Object.assign({}, t, {
        displayPrice: (Number(t.price || 0) / 100).toFixed(2),
        benefitList: this._parseBenefits(t),
        recommended: !!t.recommended
      }))
      const patch = { templates: tplList }
      const rec = tplList.find(t => t.recommended)
      if (rec) patch.selectedPlanId = rec.id

      // 后端 /my 返回列表（UserAnnualCardResponse[]），取首个；字段为 total_count/used_count/valid_end/template.name
      const myCard = Array.isArray(my) ? (my[0] || null) : my
      if (myCard) {
        const total = myCard.total_count != null ? myCard.total_count : (myCard.totalTimes || myCard.quota || 0)
        const used = myCard.used_count != null ? myCard.used_count : (myCard.usedTimes || 0)
        const remain = Math.max(0, total - used)
        const progress = total > 0 ? Math.round((used / total) * 100) : 0
        const tplName = (myCard.template && myCard.template.name) || myCard.templateName || myCard.name || '家庭年卡'
        patch.myCard = Object.assign({}, myCard, {
          templateName: tplName,
          expireAt: myCard.valid_end || myCard.expireAt || myCard.expireDate || '',
          usedTimes: remain
        })
        patch.myCardTotal = total
        patch.myCardProgress = Math.min(100, progress)
      }

      if (tplList.length >= 2) {
        patch.compareCols = tplList.map(t => ({
          id: t.id,
          name: t.name,
          recommended: t.recommended
        }))
        patch.compareRows = this._buildCompareRows(tplList)
      }

      this.setData(patch)
    } catch (e) {
      console.error('加载年卡数据失败', e)
      wx.showToast({ title: '加载失败', icon: 'none' })
    }
  },

  _parseBenefits(t) {
    if (Array.isArray(t.benefits)) return t.benefits
    if (Array.isArray(t.benefitList)) return t.benefitList
    if (typeof t.benefits === 'string') {
      return t.benefits.split(/[,，;；\n]/).map(s => s.trim()).filter(Boolean)
    }
    return []
  },

  _buildCompareRows(tplList) {
    const keys = ['上门服务次数', '免上门费', '加急折扣', '有效期', '专属客服']
    return keys.map((label, idx) => {
      const values = tplList.map(t => {
        const b = t.benefitList || []
        const hit = b.find(s => s.indexOf(label.slice(0, 2)) >= 0)
        return hit || '—'
      })
      return { key: 'row' + idx, label: label, values: values }
    })
  },

  onSelectPlan(e) {
    const id = e.currentTarget.dataset.id
    if (!id || id === this.data.selectedPlanId) return
    this.setData({ selectedPlanId: id })
  },

  onPurchase(e) {
    const id = e.currentTarget.dataset.id
    if (!id) return
    this.setData({ selectedPlanId: id })
    this._doPurchase(id)
  },

  onBuy() {
    const id = this.data.selectedPlanId
    if (!id) {
      wx.showToast({ title: '请先选择套餐', icon: 'none' })
      return
    }
    this._doPurchase(id)
  },

  _doPurchase(id) {
    const tpl = this.data.templates.find(t => t.id === id)
    if (!tpl) return
    wx.showModal({
      title: '确认购买',
      content: '即将购买「' + tpl.name + '」，支付 ¥' + tpl.displayPrice,
      confirmText: '去支付',
      success: (res) => {
        if (!res.confirm) return
        const api = app.getApi()
        wx.showLoading({ title: '处理中', mask: true })
        api.annualCard.purchase({ template_id: id }).then(() => {
          wx.hideLoading()
          wx.showToast({ title: '购买成功', icon: 'success' })
          this.loadData()
        }).catch(err => {
          wx.hideLoading()
          console.error('购买年卡失败', err)
          wx.showToast({ title: (err && err.message) || '购买失败', icon: 'none' })
        })
      }
    })
  },

  onUse() {
    wx.navigateTo({ url: '/pages/client-publish/index', fail: () => {
      wx.redirectTo({ url: '/pages/client-publish/index' })
    }})
  },

  onRefund() {
    const cardId = this.data.myCard && this.data.myCard.id
    if (!cardId) {
      wx.showToast({ title: '暂无可退年卡', icon: 'none' })
      return
    }
    wx.showModal({
      title: '退卡确认',
      content: '退卡后将扣除已使用次数费用，剩余金额原路退回。确定要退卡吗？',
      confirmText: '确定退卡',
      confirmColor: '#C4533A',
      success: async (res) => {
        if (!res.confirm) return
        const api = app.getApi()
        wx.showLoading({ title: '处理中', mask: true })
        try {
          await api.annualCard.refund(cardId)
          wx.hideLoading()
          wx.showToast({ title: '退卡成功', icon: 'success' })
          this.setData({ myCard: null, myCardTotal: 0, myCardProgress: 0 })
        } catch (e) {
          wx.hideLoading()
          console.error('退卡失败', e)
          wx.showToast({ title: (e && e.message) || '退卡失败', icon: 'none' })
        }
      }
    })
  },

  onBack() {
    wx.navigateBack({ delta: 1, fail: () => wx.redirectTo({ url: '/pages/client-mine/index' }) })
  }
})
