const { createBusinessPage } = require('../../utils/design-business-page')
const { money, safePositiveId, unavailable } = require('../../utils/client-finance')

const DESIGN_META = Object.freeze({
  pageId: 'page-client-refund-card',
  route: 'pages/client-refund-card/index',
  source: 'pages/client-refund-card.html',
  sourceHash: 'fnv1a-5371b28e',
  title: '退卡申请'
})

Page(createBusinessPage(DESIGN_META, {
  data: { loading: true, cardId: 0, card: null, loadError: '', reason: '使用频率低' },

  onLoad(options) {
    this.setData({ cardId: safePositiveId(options && options.cardId) })
    this.loadCard()
  },

  async loadCard() {
    try {
      const cards = await getApp().getApi().annualCard.mine()
      const list = Array.isArray(cards) ? cards : []
      const card = this.data.cardId
        ? list.find(item => Number(item.id) === this.data.cardId)
        : list.find(item => item.status === 'active')
      if (!card) {
        this.setData({ loading: false, card: null, loadError: '当前账户没有可核验的有效年卡' })
        return
      }
      const end = card.valid_end ? new Date(card.valid_end) : null
      const remainingDays = end && !Number.isNaN(end.getTime())
        ? Math.max(0, Math.ceil((end.getTime() - Date.now()) / 86400000))
        : 0
      this.setData({
        loading: false,
        cardId: Number(card.id),
        card: {
          name: card.template && card.template.name || '家庭年卡',
          status: card.status,
          remainingDays,
          usageText: (Number(card.used_count) || 0) + ' / ' + (Number(card.total_count) || 0),
          paidText: card.template ? money((Number(card.template.price) || 0) / 100) : '待确认',
          orderNo: card.order_no || ''
        },
        loadError: ''
      })
    } catch (error) {
      this.setData({ loading: false, card: null, loadError: error.message || '年卡信息加载失败' })
    }
  },

  onReason(event) {
    this.setData({ reason: String(event.currentTarget.dataset.reason || '') })
  },

  onSubmit() {
    unavailable('年卡退款服务当前明确返回未实现，且没有原支付渠道退款契约。本次不会冻结年卡、创建退款或展示“申请成功”。')
  }
}))
