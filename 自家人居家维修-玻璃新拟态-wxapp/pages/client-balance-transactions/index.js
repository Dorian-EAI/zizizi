const { createTransactionListPage } = require('../../utils/transaction-list-page')

Page(createTransactionListPage(Object.freeze({
  pageId: 'page-client-balance-transactions',
  route: 'pages/client-balance-transactions/index',
  source: 'pages/client-balance-transactions.html',
  sourceHash: 'fnv1a-6915766c',
  title: '收支明细'
}), { filterMode: 'type', summaryLabel: '本月净支出' }))
