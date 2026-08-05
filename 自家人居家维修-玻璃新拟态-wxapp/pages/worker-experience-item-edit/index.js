// 已审计：独立契约未就绪时仅展示受限态，并引导到已接入的真实功能中心。
const { createDesignPage } = require('../../utils/design-page-runtime')

Page(createDesignPage({
  pageId: "page-worker-experience-item-edit",
  route: "pages/worker-experience-item-edit/index",
  source: "pages/worker-experience-item-edit.html",
  sourceHash: "fnv1a-91de31b4",
  title: "工作经历"
}))
