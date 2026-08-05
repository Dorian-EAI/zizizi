// 已审计：独立契约未就绪时仅展示受限态，并引导到已接入的真实功能中心。
const { createDesignPage } = require('../../utils/design-page-runtime')

Page(createDesignPage({
  pageId: "page-worker-exam-result",
  route: "pages/worker-exam-result/index",
  source: "pages/worker-exam-result.html",
  sourceHash: "fnv1a-5f567f76",
  title: "考试结果"
}))
