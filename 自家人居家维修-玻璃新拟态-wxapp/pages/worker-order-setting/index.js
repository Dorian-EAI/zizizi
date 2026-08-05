// 已审计：独立契约未就绪时仅展示受限态，并引导到已接入的真实功能中心。
const { createDesignPage } = require('../../utils/design-page-runtime')

Page(createDesignPage({
  pageId: "page-worker-order-setting",
  route: "pages/worker-order-setting/index",
  source: "pages/worker-order-setting.html",
  sourceHash: "fnv1a-dc769161",
  title: "接单设置"
}))
