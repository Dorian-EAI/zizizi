const { createBusinessPage } = require('../../utils/design-business-page')
const { safePositiveId } = require('../../utils/client-finance')

Page(createBusinessPage(Object.freeze({
  pageId: 'page-client-refund-card-result',
  route: 'pages/client-refund-card-result/index',
  source: 'pages/client-refund-card-result.html',
  sourceHash: 'fnv1a-c3226952',
  title: '退卡结果'
}), {
  data: {
    cardId: 0, loading: true, found: false, state: 'unknown', stateTone: 'warning',
    titleText: '退卡结果待确认', description: '正在查询服务端年卡状态。', cardName: '家庭年卡', statusText: '待确认'
  },

  onLoad(options) {
    this.setData({ cardId: safePositiveId(options && options.cardId) })
    this.loadResult()
  },

  async loadResult() {
    if (!this.data.cardId) {
      this.setData({ loading: false, description: '未提供年卡编号，不能确认任何退卡结果。' })
      return
    }
    try {
      const cards = await getApp().getApi().annualCard.mine()
      const card = (Array.isArray(cards) ? cards : []).find(item => Number(item.id) === this.data.cardId)
      if (!card) throw new Error('未找到该年卡')
      const status = String(card.status || '').toLowerCase()
      const view = status === 'refunded'
        ? { stateTone: 'success', titleText: '退卡已完成', description: '服务端年卡状态已确认为已退款。', statusText: '已退款' }
        : status === 'refunding'
          ? { stateTone: 'warning', titleText: '退卡审核中', description: '服务端年卡状态为退款处理中。', statusText: '处理中' }
          : { stateTone: 'warning', titleText: '未提交退卡申请', description: '服务端年卡状态未进入退款流程，不会展示申请成功。', statusText: status || '状态未知' }
      this.setData(Object.assign({
        loading: false, found: true, state: status,
        cardName: card.template && card.template.name || '家庭年卡'
      }, view))
    } catch (error) {
      this.setData({ loading: false, found: false, titleText: '无法确认退卡结果', description: error.message || '年卡状态查询失败', statusText: '状态未知' })
    }
  }
}))
