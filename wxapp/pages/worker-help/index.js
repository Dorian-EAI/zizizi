// 已审计：独立契约未就绪时仅展示受限态，并引导到已接入的真实功能中心。
const { createDesignPage } = require('../../utils/design-page-runtime')

Page(createDesignPage({
  pageId: "page-worker-help",
  route: "pages/worker-help/index",
  source: "pages/worker-help.html",
  sourceHash: "fnv1a-486a1c1e",
  title: "帮助中心"
}))
