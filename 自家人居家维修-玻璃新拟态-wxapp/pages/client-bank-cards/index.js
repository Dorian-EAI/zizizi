const { createBusinessPage } = require('../../utils/design-business-page')
const { unavailable } = require('../../utils/client-finance')

Page(createBusinessPage(Object.freeze({
  pageId: 'page-client-bank-cards',
  route: 'pages/client-bank-cards/index',
  source: 'pages/client-bank-cards.html',
  sourceHash: 'fnv1a-3d170518',
  title: '我的银行卡'
}), {
  onUnavailable() {
    unavailable('银行卡查询、绑定与解绑接口尚未接入。本页不会展示画布中的示例卡号，也不会把银行卡信息保存在本地。')
  }
}))
