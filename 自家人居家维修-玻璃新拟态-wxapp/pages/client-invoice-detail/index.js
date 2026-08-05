const { createBusinessPage } = require('../../utils/design-business-page')
const { unavailable } = require('../../utils/client-finance')

Page(createBusinessPage(Object.freeze({
  pageId: 'page-client-invoice-detail', route: 'pages/client-invoice-detail/index',
  source: 'pages/client-invoice-detail.html', sourceHash: 'fnv1a-8bb0875c', title: '发票详情'
}), {
  onUnavailable() {
    unavailable('没有可验证的发票详情、PDF 下载地址或邮件发送接口。本次不会复制示例号码、下载占位文件或提示发送成功。')
  }
}))
