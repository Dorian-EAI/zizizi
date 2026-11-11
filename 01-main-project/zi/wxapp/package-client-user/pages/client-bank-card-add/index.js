const { createBusinessPage } = require('../../utils/design-business-page')
const { unavailable } = require('../../utils/client-finance')

Page(createBusinessPage(Object.freeze({
  pageId: 'page-client-bank-card-add',
  route: 'pages/client-bank-card-add/index',
  source: 'pages/client-bank-card-add.html',
  sourceHash: 'fnv1a-bfe99caa',
  title: '添加银行卡'
}), {
  onUnavailable() {
    unavailable('银行卡实名校验、短信验证和令牌化存储尚未接入，当前不会收集或保存姓名、身份证号、卡号与预留手机号。')
  }
}))
