const { createBusinessPage } = require('../../utils/design-business-page')
const { money, dateTime, safePositiveId } = require('../../utils/client-finance')

const STATUS_VIEW = {
  pending: { title: '理赔申请审核中', description: '服务端已记录申请，等待平台审核。', tone: 'warning', label: '审核中' },
  approved: { title: '理赔申请已通过', description: '平台已审核通过，赔付进度以服务端记录为准。', tone: 'success', label: '已通过' },
  rejected: { title: '理赔申请未通过', description: '平台已完成审核，请查看审核说明或联系客服。', tone: 'danger', label: '未通过' },
  settled: { title: '理赔已完成', description: '服务端已记录理赔结算完成。', tone: 'success', label: '已结算' }
}

Page(createBusinessPage(Object.freeze({
  pageId: 'page-client-claim-result',
  route: 'pages/client-claim-result/index',
  source: 'pages/client-claim-result.html',
  sourceHash: 'fnv1a-de3cb9cd',
  title: '理赔结果'
}), {
  data: {
    claimId: 0, orderId: 0, loading: true, found: false, tone: 'warning',
    titleText: '理赔结果待确认', description: '正在查询服务端理赔记录。', statusText: '查询中',
    amountText: '—', settledAmountText: '—', createdAtText: '待确认', auditRemark: ''
  },

  onLoad(options) {
    this.setData({
      claimId: safePositiveId(options && options.claimId),
      orderId: safePositiveId(options && options.orderId)
    })
    this.loadClaim()
  },

  async loadClaim() {
    try {
      const payload = await getApp().getApi().insurance.claims()
      const list = Array.isArray(payload) ? payload : (payload && Array.isArray(payload.items) ? payload.items : [])
      const claim = this.data.claimId
        ? list.find(item => Number(item.id) === this.data.claimId)
        : (this.data.orderId ? list.find(item => Number(item.order_id) === this.data.orderId) : null)
      if (!claim) {
        this.setData({ loading: false, found: false, titleText: '未找到理赔记录', description: '未提供有效理赔编号，或当前账户没有对应记录。', statusText: '状态未知' })
        return
      }
      const status = String(claim.status || '').toLowerCase()
      const view = STATUS_VIEW[status] || { title: '理赔状态待确认', description: '服务端返回了尚未识别的理赔状态。', tone: 'warning', label: status || '未知' }
      this.setData({
        loading: false, found: true, claimId: Number(claim.id), orderId: Number(claim.order_id) || 0,
        tone: view.tone, titleText: view.title, description: view.description, statusText: view.label,
        amountText: money((Number(claim.claim_amount) || 0) / 100),
        settledAmountText: money((Number(claim.settled_amount) || 0) / 100),
        createdAtText: dateTime(claim.created_at), auditRemark: claim.audit_remark || ''
      })
    } catch (error) {
      this.setData({ loading: false, found: false, titleText: '理赔结果查询失败', description: error.message || '暂时无法读取理赔记录', statusText: '状态未知' })
    }
  },

  onViewOrder() {
    if (!this.data.orderId) return
    wx.navigateTo({ url: '/pages/order-detail-client/index?id=' + this.data.orderId })
  }
}))
