const { createBusinessPage } = require('../../utils/design-business-page')
const { unavailable } = require('../../utils/client-finance')

Page(createBusinessPage(Object.freeze({
  pageId: 'page-client-invoice', route: 'pages/client-invoice/index',
  source: 'pages/client-invoice.html', sourceHash: 'fnv1a-6d3a4e44', title: '发票与报销'
}), {
  onUnavailable() {
    unavailable('发票抬头、可开票订单、申请、开具状态和电子文件接口均未接入。本次不会创建发票或展示画布示例记录。')
  }
}))
