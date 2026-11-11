const { createBusinessPage } = require('../../utils/design-business-page')
const { money, unavailable } = require('../../utils/client-finance')

const DESIGN_META = Object.freeze({
  pageId: 'page-client-wallet-withdraw',
  route: 'pages/client-wallet-withdraw/index',
  source: 'pages/client-wallet-withdraw.html',
  sourceHash: 'fnv1a-a7fc041d',
  title: '钱包提现'
})

Page(createBusinessPage(DESIGN_META, {
  data: { balanceText: '—', loadError: '' },

  onShow() {
    this.loadBalance()
  },

  async loadBalance() {
    try {
      const wallet = await getApp().getApi().wallet.detail()
      this.setData({ balanceText: money(wallet && wallet.balance), loadError: '' })
    } catch (error) {
      this.setData({ balanceText: '—', loadError: error.message || '账户余额加载失败' })
    }
  },

  onUnavailable() {
    unavailable('当前后端仅允许师傅收入账户在受控环境申请提现，客户端账户没有提现契约；本次未提交、未冻结、未扣减任何资金。')
  }
}))
