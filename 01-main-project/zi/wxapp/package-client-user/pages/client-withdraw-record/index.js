const { createTransactionListPage } = require('../../utils/transaction-list-page')

Page(createTransactionListPage(Object.freeze({
  pageId: 'page-client-withdraw-record',
  route: 'pages/client-withdraw-record/index',
  source: 'pages/client-withdraw-record.html',
  sourceHash: 'fnv1a-23e3f554',
  title: '提现记录'
}), { filterMode: 'status', queryType: 'withdraw', summaryLabel: '本月提现' }))
