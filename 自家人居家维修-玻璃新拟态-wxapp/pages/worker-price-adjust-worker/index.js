// 已审计：独立契约未就绪时仅展示受限态，并引导到已接入的真实功能中心。
const { createDesignPage } = require('../../utils/design-page-runtime')

Page(createDesignPage({
  pageId: "page-worker-price-adjust-worker",
  route: "pages/worker-price-adjust-worker/index",
  source: "pages/worker-price-adjust-worker.html",
  sourceHash: "fnv1a-7d3a59c6",
  title: "申请补差价"
}))
