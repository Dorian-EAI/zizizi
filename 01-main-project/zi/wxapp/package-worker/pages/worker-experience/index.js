// 已审计：独立契约未就绪时仅展示受限态，并引导到已接入的真实功能中心。
const { createDesignPage } = require('../../utils/design-page-runtime')

Page(createDesignPage({
  pageId: "page-worker-experience",
  route: "pages/worker-experience/index",
  source: "pages/worker-experience.html",
  sourceHash: "fnv1a-39b69b17",
  title: "从业经验"
}))
