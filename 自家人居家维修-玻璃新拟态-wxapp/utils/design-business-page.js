const { createDesignPage } = require('./design-page-runtime')

function createBusinessPage(meta, specification) {
  const base = createDesignPage(meta)
  const spec = specification || {}
  const page = Object.assign({}, base, spec)
  page.data = Object.assign({}, base.data, {
    designPageId: meta.pageId,
    designSource: meta.source,
    designSourceHash: meta.sourceHash
  }, spec.data || {})
  return page
}

module.exports = { createBusinessPage }
