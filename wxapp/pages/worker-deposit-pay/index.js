// 已审计：独立契约未就绪时仅展示受限态，并引导到已接入的真实功能中心。
const { createDesignPage } = require('../../utils/design-page-runtime')

Page(createDesignPage({
  pageId: "page-worker-deposit-pay",
  route: "pages/worker-deposit-pay/index",
  source: "pages/worker-deposit-pay.html",
  sourceHash: "fnv1a-680e2216",
  title: "缴纳保证金"
}))
