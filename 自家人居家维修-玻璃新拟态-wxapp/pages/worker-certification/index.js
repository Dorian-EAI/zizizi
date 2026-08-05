// pages/worker-certification/index.js — 师傅认证页
const app = getApp()
const { buildIcon, COLORS } = require('../../utils/icons')

const STATUS_META = {
  pending: { text: '待审核', chip: 'chip-warning' },
  approved: { text: '已认证', chip: 'chip-success' },
  rejected: { text: '未通过', chip: 'chip-danger' },
  unsubmitted: { text: '未提交', chip: 'chip-info' }
}

const SERVICE_OPTIONS = [
  '水管维修', '电路维修', '油漆粉刷', '家电安装',
  '门窗维修', '木工家具', '管道疏通', '清洁保洁'
]

const CERTIFIED_STATUS = {
  0: 'unsubmitted',
  1: 'pending',
  2: 'approved',
  3: 'rejected'
}

function uploadURL(result) {
  if (typeof result === 'string') return result
  return result && typeof result.url === 'string' ? result.url : ''
}

Page({
  data: {
    statusBarHeight: 20,
    profile: null,
    statusBadge: { text: '未提交', chip: 'chip-info' },
    form: {
      name: '',
      idCard: '',
      phone: '',
      idFront: '',
      idBack: '',
      certImages: [],
      healthCert: '',
      city: '',
      districts: [],
      services: [],
      priceMin: '',
      priceMax: ''
    },
    serviceOptions: SERVICE_OPTIONS,
    benefits: [
      { text: '不限抢单', tag: '无上限' },
      { text: '平台抽成10%', tag: '低于标准' },
      { text: '首页推荐位', tag: '优先曝光' },
      { text: '专属客服', tag: '7×12h' }
    ],
    submitting: false,
    icons: {}
  },

  onLoad() {
    this.setData({
      statusBarHeight: app.globalData.statusBarHeight || 20,
      icons: {
        back: buildIcon('arrowLeft', COLORS.brandWorker),
        shield: buildIcon('shield', COLORS.white),
        idcard: buildIcon('user', COLORS.brandWorker),
        award: buildIcon('award', COLORS.accentDark),
        wallet: buildIcon('wallet', COLORS.blue),
        heart: buildIcon('heart', COLORS.success),
        hall: buildIcon('hall', COLORS.text3),
        checkGreen: buildIcon('check', COLORS.success),
        plus: buildIcon('plus', COLORS.white),
        camera: buildIcon('camera', COLORS.text3),
        check: buildIcon('check', COLORS.brandWorker)
      }
    })
    this.loadProfile()
  },

  async loadProfile() {
    const api = app.getApi()
    try {
      const profile = await api.auth.workerMe()
      if (!profile) return
      const status = profile.certification_status ||
        profile.certificationStatus ||
        CERTIFIED_STATUS[profile.certified] ||
        'unsubmitted'
      const meta = STATUS_META[status] || STATUS_META.unsubmitted
      const cert = profile.certification_data || profile.certificationData || {}
      this.setData({
        profile,
        statusBadge: { text: meta.text, chip: meta.chip },
        form: {
          name: cert.real_name || cert.name || profile.real_name || profile.name || '',
          // 后端永不返回身份证明文；补充/重提时必须重新输入。
          idCard: '',
          phone: cert.phone || profile.phone || '',
          idFront: cert.id_front || cert.idFront || '',
          idBack: cert.id_back || cert.idBack || '',
          certImages: cert.certificate_images || cert.certImages || [],
          healthCert: cert.health_certificate || cert.healthCert || '',
          city: cert.service_city || cert.city || '',
          districts: cert.service_districts || cert.districts || [],
          services: cert.service_types || cert.services || [],
          priceMin: cert.price_min || cert.priceMin || '',
          priceMax: cert.price_max || cert.priceMax || ''
        }
      })
    } catch (e) {
      console.error('加载认证信息失败', e)
    }
  },

  onBack() {
    wx.navigateBack({ delta: 1 })
  },

  onCertTap(e) {
    const key = e.currentTarget.dataset.key
    if (key === 'license') {
      this.chooseImage({ currentTarget: { dataset: { field: 'idFront' } } })
    }
  },

  onViewTap(e) {
    const key = e.currentTarget.dataset.key
    wx.showToast({ title: '查看 ' + key, icon: 'none' })
  },

  onUploadTap(e) {
    const key = e.currentTarget.dataset.key
    if (key === 'license') {
      this.chooseImage({ currentTarget: { dataset: { field: 'idFront' } } })
    }
  },

  onInput(e) {
    const field = e.currentTarget.dataset.field
    this.setData({ ['form.' + field]: e.detail.value })
  },

  toggleArrayItem(e) {
    const { field, value } = e.currentTarget.dataset
    const arr = (this.data.form[field] || []).slice()
    const idx = arr.indexOf(value)
    if (idx >= 0) {
      arr.splice(idx, 1)
    } else {
      arr.push(value)
    }
    this.setData({ ['form.' + field]: arr })
  },

  async chooseImage(e) {
    const field = e.currentTarget.dataset.field
    const api = app.getApi()
    try {
      const res = await new Promise((resolve, reject) => {
        wx.chooseMedia({
          count: 1,
          mediaType: ['image'],
          sizeType: ['compressed'],
          success: resolve,
          fail: reject
        })
      })
      const tempPath = res.tempFiles[0].tempFilePath
      wx.showLoading({ title: '上传中' })
      const result = api.upload.certificateImage
        ? await api.upload.certificateImage(tempPath)
        : await api.upload.image(tempPath)
      const url = uploadURL(result)
      if (!url) throw new Error('上传响应缺少图片地址')
      wx.hideLoading()
      this.setData({ ['form.' + field]: url })
    } catch (e) {
      wx.hideLoading()
      if (e && e.errMsg && e.errMsg.indexOf('cancel') >= 0) return
      console.error('上传失败', e)
      wx.showToast({ title: '上传失败', icon: 'none' })
    }
  },

  async chooseCertImages() {
    const api = app.getApi()
    const cur = this.data.form.certImages || []
    try {
      const res = await new Promise((resolve, reject) => {
        wx.chooseMedia({
          count: 4 - cur.length,
          mediaType: ['image'],
          sizeType: ['compressed'],
          success: resolve,
          fail: reject
        })
      })
      wx.showLoading({ title: '上传中' })
      const urls = []
      for (const f of res.tempFiles) {
        const result = api.upload.certificateImage
          ? await api.upload.certificateImage(f.tempFilePath)
          : await api.upload.image(f.tempFilePath)
        const url = uploadURL(result)
        if (!url) throw new Error('上传响应缺少图片地址')
        urls.push(url)
      }
      wx.hideLoading()
      this.setData({ 'form.certImages': cur.concat(urls) })
    } catch (e) {
      wx.hideLoading()
      if (e && e.errMsg && e.errMsg.indexOf('cancel') >= 0) return
      console.error('批量上传失败', e)
      wx.showToast({ title: '上传失败', icon: 'none' })
    }
  },

  removeCertImage(e) {
    const idx = e.currentTarget.dataset.idx
    const arr = this.data.form.certImages.slice()
    arr.splice(idx, 1)
    this.setData({ 'form.certImages': arr })
  },

  promptVerificationCode(phone, sendResult) {
    const maskedPhone = phone.slice(0, 3) + '****' + phone.slice(-4)
    const developmentHint = sendResult && sendResult.code
      ? '开发联调验证码：' + sendResult.code
      : '验证码已发送至 ' + maskedPhone
    return new Promise(resolve => {
      wx.showModal({
        title: '短信验证',
        content: developmentHint,
        editable: true,
        placeholderText: '请输入短信验证码',
        confirmColor: '#2D6CDF',
        success: result => resolve(result.confirm ? String(result.content || '').trim() : ''),
        fail: () => resolve('')
      })
    })
  },

  async onSubmit() {
    const f = this.data.form
    if (!f.name || !f.idCard || !f.phone) {
      wx.showToast({ title: '请填写实名信息', icon: 'none' })
      return
    }
    if (!f.idFront || !f.idBack) {
      wx.showToast({ title: '请上传身份证', icon: 'none' })
      return
    }
    if (f.services.length === 0) {
      wx.showToast({ title: '请选择服务技能', icon: 'none' })
      return
    }
    if (!/^1[3-9]\d{9}$/.test(f.phone)) {
      wx.showToast({ title: '手机号格式不正确', icon: 'none' })
      return
    }
    if (!/^\d{17}[\dXx]$/.test(f.idCard)) {
      wx.showToast({ title: '身份证号格式不正确', icon: 'none' })
      return
    }
    if (!f.city || !f.districts.length) {
      wx.showToast({ title: '请选择服务区域', icon: 'none' })
      return
    }
    const priceMin = Number(f.priceMin)
    const priceMax = Number(f.priceMax)
    if (!(priceMin > 0) || !(priceMax >= priceMin)) {
      wx.showToast({ title: '请填写正确报价范围', icon: 'none' })
      return
    }
    const api = app.getApi()
    try {
      wx.showLoading({ title: '发送验证码', mask: true })
      const sendResult = await api.sms.sendCode(f.phone, 'worker_certification')
      wx.hideLoading()
      const verificationCode = await this.promptVerificationCode(f.phone, sendResult)
      if (!verificationCode) return
      if (!/^\d{4,8}$/.test(verificationCode)) {
        wx.showToast({ title: '验证码格式不正确', icon: 'none' })
        return
      }

      this.setData({ submitting: true })
      await api.auth.submitCertification({
        real_name: f.name,
        id_card: f.idCard,
        phone: f.phone,
        phone_verification_code: verificationCode,
        id_front: f.idFront,
        id_back: f.idBack,
        certificate_images: f.certImages,
        health_certificate: f.healthCert || null,
        service_city: f.city,
        service_districts: f.districts,
        service_types: f.services,
        price_min: String(priceMin),
        price_max: String(priceMax)
      })
      wx.showToast({ title: '提交成功', icon: 'success' })
      setTimeout(() => wx.navigateBack({ delta: 1 }), 800)
    } catch (e) {
      wx.hideLoading()
      console.error('提交认证失败', e)
      wx.showToast({ title: (e && e.message) || '提交失败', icon: 'none' })
    } finally {
      this.setData({ submitting: false })
    }
  }
})
