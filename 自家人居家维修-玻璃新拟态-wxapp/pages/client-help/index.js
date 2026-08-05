const app = getApp()
const { createRuntimePage, messageOf } = require('../../utils/detail-page')

Page(createRuntimePage({
  pageId: 'page-client-help', route: 'pages/client-help/index',
  source: 'pages/client-help.html', sourceHash: 'fnv1a-c7aaa72c', title: '帮助中心'
}, {
  data: {
    loading: true, loadError: '', categories: [], faqs: [], visibleFaqs: [],
    selectedCategory: '', keyword: '', expandedId: ''
  },

  onLoad() { this.loadFaqs() },

  async loadFaqs() {
    this.setData({ loading: true, loadError: '' })
    try {
      const categories = await app.getApi().pages.faqs()
      const safeCategories = Array.isArray(categories) ? categories : []
      const faqs = []
      safeCategories.forEach(category => {
        ;(Array.isArray(category.faqs) ? category.faqs : []).forEach(item => {
          faqs.push(Object.assign({}, item, {
            categoryName: category.name || '其他',
            viewId: String(item.id)
          }))
        })
      })
      this.setData({ loading: false, categories: safeCategories, faqs }, () => this.applyFilter())
    } catch (error) {
      this.setData({ loading: false, loadError: messageOf(error), categories: [], faqs: [], visibleFaqs: [] })
    }
  },

  onSearch(event) { this.setData({ keyword: String(event.detail.value || '').trim() }, () => this.applyFilter()) },
  onCategory(event) {
    const name = String(event.currentTarget.dataset.name || '')
    this.setData({ selectedCategory: this.data.selectedCategory === name ? '' : name }, () => this.applyFilter())
  },
  applyFilter() {
    const keyword = this.data.keyword.toLowerCase()
    const category = this.data.selectedCategory
    const visibleFaqs = this.data.faqs.filter(item => {
      if (category && item.categoryName !== category) return false
      if (!keyword) return true
      return (String(item.question || '') + ' ' + String(item.answer || '')).toLowerCase().indexOf(keyword) >= 0
    })
    this.setData({ visibleFaqs })
  },
  onToggle(event) {
    const id = String(event.currentTarget.dataset.id || '')
    this.setData({ expandedId: this.data.expandedId === id ? '' : id })
  }
}))
