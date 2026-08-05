// 已审计：独立契约未就绪时仅展示受限态，并引导到已接入的真实功能中心。
const { createDesignPage } = require('../../utils/design-page-runtime')

Page(createDesignPage({
  pageId: "page-worker-lesson",
  route: "pages/worker-lesson/index",
  source: "pages/worker-lesson.html",
  sourceHash: "fnv1a-50c83feb",
  title: "课时学习"
}))
