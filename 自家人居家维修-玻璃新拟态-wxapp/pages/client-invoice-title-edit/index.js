const { createBusinessPage } = require('../../utils/design-business-page')
const { unavailable } = require('../../utils/client-finance')

Page(createBusinessPage(Object.freeze({
  pageId: 'page-client-invoice-title-edit', route: 'pages/client-invoice-title-edit/index',
  source: 'pages/client-invoice-title-edit.html', sourceHash: 'fnv1a-39d759f0', title: '编辑发票抬头'
}), {
  onUnavailable() {
    unavailable('发票抬头保存接口与敏感税务信息保护契约尚未接入，当前不会收集、缓存或保存企业名称、税号、银行账号等信息。')
  }
}))
