// pages/client-insurance-claim/index.js — 理赔申请 玻璃新拟态
const app = getApp()
const { buildIcon, COLORS } = require('../../utils/icons')

function formatCents(cents) {
  const yuan = Number(cents || 0) / 100
  return yuan.toFixed(2).replace(/\.00$/, '')
}

function getUploadedImageUrl(uploaded) {
  const raw = typeof uploaded === 'string'
    ? uploaded
    : uploaded && (uploaded.url || (uploaded.data && uploaded.data.url))
  if (typeof raw !== 'string') return ''
  const url = raw.trim()
  if (/^\/uploads\//.test(url)) return url
  if (/^https?:\/\//i.test(url) && !/^https?:\/\/tmp\//i.test(url)) return url
  return ''
}

Page({
  data: {
    statusBarHeight: 20,
    policy: {
      name: '安心保',
      tier: '保单信息待加载',
      status: '',
      policyNo: '—',
      orderNo: '—'
    },
    orderId: '',
    form: {
      lossDesc: '',
      lossAmount: '',
      liability: ''
    },
    photos: [],          // 已选照片本地路径
    maxPhotos: 5,
    submitting: false,
    icons: {}
  },

  onLoad(query) {
    const orderId = query && query.orderId ? String(query.orderId) : ''
    let orderNo = query && query.orderNo ? query.orderNo : ''
    try { orderNo = decodeURIComponent(orderNo) } catch (e) {}
    this.setData({
      orderId,
      statusBarHeight: app.globalData.statusBarHeight || 20,
      icons: {
        back: buildIcon('chevronLeft', COLORS.text1),
        shield: buildIcon('shield', COLORS.brand),
        shieldAccent: buildIcon('shield', COLORS.accent),
        plus: buildIcon('plus', COLORS.text3),
        close: buildIcon('x', COLORS.white),
        send: buildIcon('send', COLORS.white),
        document: buildIcon('orders', COLORS.white),
        headset: buildIcon('message', COLORS.white),
        wallet: buildIcon('wallet', COLORS.white)
      }
    })
    if (orderNo) {
      this.setData({
        'policy.orderNo': '#' + orderNo.replace(/^#/, '')
      })
    }
    if (orderId) this.loadPolicy(orderId, orderNo)
  },

  async loadPolicy(orderId, orderNo) {
    const api = app.getApi()
    try {
      const policy = await api.insurance.policy(orderId)
      if (!policy) {
        this.setData({
          policy: { name: '安心保', tier: '未查询到有效保单', status: '', policyNo: '—', orderNo: orderNo || '—' }
        })
        wx.showToast({ title: '未查询到有效保单', icon: 'none' })
        return
      }
      const levelName = { basic: '基础版', standard: '标准版', premium: '尊享版' }
      const statusName = { active: '生效中', claimed: '理赔中', expired: '已过期', cancelled: '已失效' }
      const coverage = Number(formatCents(policy.coverage || 0)).toLocaleString()
      this.setData({
        policy: Object.assign({}, this.data.policy, policy, {
          name: '安心保 · ' + (levelName[policy.level] || policy.level || '未知方案'),
          tier: '保费 ¥' + formatCents(policy.premium) + ' · 最高赔付 ¥' + coverage,
          status: statusName[policy.status] || policy.status || '状态未知',
          policyNo: policy.policy_no
            ? ('#' + String(policy.policy_no).replace(/^#/, ''))
            : ('#' + String(policy.id)),
          orderNo: orderNo
            ? ('#' + orderNo.replace(/^#/, ''))
            : ('#' + String(policy.order_id || orderId))
        })
      })
    } catch (error) {
      console.error('加载保单失败', error)
      this.setData({
        policy: { name: '安心保', tier: '保单加载失败', status: '', policyNo: '—', orderNo: orderNo || '—' }
      })
    }
  },

  // 返回
  onBack() {
    wx.navigateBack({ delta: 1, fail: () => wx.redirectTo({ url: '/pages/client-orders/index' }) })
  },

  // 输入损失描述
  onLossDescInput(e) {
    this.setData({ 'form.lossDesc': e.detail.value })
  },

  // 输入损失金额
  onLossAmountInput(e) {
    this.setData({ 'form.lossAmount': e.detail.value })
  },

  // 输入责任说明
  onLiabilityInput(e) {
    this.setData({ 'form.liability': e.detail.value })
  },

  // 选择照片
  onChoosePhoto() {
    const remaining = this.data.maxPhotos - this.data.photos.length
    if (remaining <= 0) {
      wx.showToast({ title: '最多上传5张照片', icon: 'none' })
      return
    }
    wx.chooseImage({
      count: remaining,
      sizeType: ['compressed'],
      sourceType: ['album', 'camera'],
      success: (res) => {
        const newPhotos = this.data.photos.concat(res.tempFilePaths)
        this.setData({ photos: newPhotos })
      }
    })
  },

  // 预览照片
  onPreviewPhoto(e) {
    const idx = e.currentTarget.dataset.idx
    const urls = this.data.photos
    wx.previewImage({ current: urls[idx], urls })
  },

  // 删除照片
  onRemovePhoto(e) {
    const idx = e.currentTarget.dataset.idx
    const photos = this.data.photos.filter((_, i) => i !== idx)
    this.setData({ photos })
  },

  // 提交理赔申请
  async uploadEvidence() {
    const api = app.getApi()
    const urls = []
    for (let index = 0; index < this.data.photos.length; index += 1) {
      const photo = this.data.photos[index]
      const existingUrl = getUploadedImageUrl(photo)
      if (existingUrl) {
        urls.push(existingUrl)
      } else {
        const uploaded = await api.upload.image(photo)
        const url = getUploadedImageUrl(uploaded)
        if (!url) throw new Error('第' + (index + 1) + '张照片上传失败')
        urls.push(url)
      }
    }
    return urls
  },

  async onSubmitClaim() {
    if (this.data.submitting) return
    const { lossDesc, lossAmount, liability } = this.data.form
    if (!lossDesc.trim()) {
      wx.showToast({ title: '请填写损失描述', icon: 'none' })
      return
    }
    if (!lossAmount || parseFloat(lossAmount) <= 0) {
      wx.showToast({ title: '请填写损失金额预估', icon: 'none' })
      return
    }
    if (!liability.trim()) {
      wx.showToast({ title: '请填写师傅责任说明', icon: 'none' })
      return
    }
    if (!this.data.photos.length) {
      wx.showToast({ title: '请至少上传1张损失照片', icon: 'none' })
      return
    }
    const policyId = this.data.policy.id || this.data.policy.policyId
    if (!policyId) {
      wx.showToast({ title: '缺少有效保单，无法提交', icon: 'none' })
      return
    }

    this.setData({ submitting: true })
    wx.showLoading({ title: '提交中', mask: true })
    const api = app.getApi()
    try {
      const evidenceImages = await this.uploadEvidence()
      // 后端 SubmitClaimRequest 字段：policy_id / reason / claim_amount / evidence_images
      await api.insurance.claim({
        policy_id: Number(policyId),
        reason: lossDesc.trim() + '\n责任说明：' + liability.trim(),
        // 后端保险金额统一使用“分”。
        claim_amount: Math.round(Number(lossAmount) * 100),
        evidence_images: evidenceImages
      })
      wx.hideLoading()
      wx.showModal({
        title: '提交成功',
        content: '理赔申请已提交，专属客服将在24小时内联系您',
        confirmText: '知道了',
        success: () => wx.navigateBack({ delta: 1 })
      })
    } catch (error) {
      wx.hideLoading()
      console.error('提交理赔失败', error)
      if (!error || error.code !== 'AUTH_REQUIRED') {
        wx.showToast({ title: (error && error.message) || '提交失败，请重试', icon: 'none' })
      }
    } finally {
      this.setData({ submitting: false })
    }
  }
})
