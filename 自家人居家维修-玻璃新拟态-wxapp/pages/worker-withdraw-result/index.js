// 已审计：独立契约未就绪时仅展示受限态，并引导到已接入的真实功能中心。
const { createDesignPage } = require('../../utils/design-page-runtime')

Page(createDesignPage({
  pageId: "page-worker-withdraw-result",
  route: "pages/worker-withdraw-result/index",
  source: "pages/worker-withdraw-result.html",
  sourceHash: "fnv1a-6c78d8b4",
  title: "提现结果"
}))
