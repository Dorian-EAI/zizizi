const { createTransactionListPage } = require('../../utils/transaction-list-page')

Page(createTransactionListPage(Object.freeze({
  pageId: 'page-client-recharge-record',
  route: 'pages/client-recharge-record/index',
  source: 'pages/client-recharge-record.html',
  sourceHash: 'fnv1a-85fcdbaa',
  title: '充值记录'
}), { filterMode: 'status', queryType: 'recharge', summaryLabel: '本月充值' }))
