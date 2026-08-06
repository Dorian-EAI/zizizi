const { createBusinessPage } = require('../../utils/design-business-page')
const { unavailable } = require('../../utils/client-finance')

Page(createBusinessPage(Object.freeze({
  pageId: 'page-client-invoice-orders', route: 'pages/client-invoice-orders/index',
  source: 'pages/client-invoice-orders.html', sourceHash: 'fnv1a-a62d23f1', title: '可开票订单'
}), {
  onUnavailable() {
    unavailable('后端尚未定义订单开票资格与重复开票校验契约，不能把普通已完成订单推断为“可开票”。本次未选择或提交任何订单。')
  }
}))
