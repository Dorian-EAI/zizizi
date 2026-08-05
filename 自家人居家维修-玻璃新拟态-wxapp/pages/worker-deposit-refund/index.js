// 已审计：独立契约未就绪时仅展示受限态，并引导到已接入的真实功能中心。
const { createDesignPage } = require('../../utils/design-page-runtime')

Page(createDesignPage({
  pageId: "page-worker-deposit-refund",
  route: "pages/worker-deposit-refund/index",
  source: "pages/worker-deposit-refund.html",
  sourceHash: "fnv1a-0a7dbd5c",
  title: "申请退保"
}))
