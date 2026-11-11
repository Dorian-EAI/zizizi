const api = require('../../utils/request')

const USER = {
  nickname: '李先生'
}

const HOT_TAGS = [
  { key: 'waterproof', name: '防水维修' },
  { key: 'leak', name: '漏水检测' },
  { key: 'electrical', name: '水电改造' },
  { key: 'cleaning', name: '清洁服务' },
  { key: 'kitchen', name: '厨房改造' },
  { key: 'appliance', name: '家电维修' }
]

const CATEGORIES = [
  { key: 'all', name: '全部' },
  { key: 'waterproof', name: '防水维修' },
  { key: 'leak', name: '漏水检测' },
  { key: 'electrical', name: '水电改造' },
  { key: 'cleaning', name: '清洁服务' },
  { key: 'kitchen', name: '厨房改造' }
]

const SERVICES = [
  { key: 'waterproof', name: '防水维修', icon_svg: '/assets/svg/droplet.svg' },
  { key: 'appliance', name: '家电维修', icon_svg: '/assets/svg/appliance.svg' },
  { key: 'plumbing', name: '管道疏通', icon_svg: '/assets/svg/plumbing.svg' },
  { key: 'lock', name: '开锁换锁', icon_svg: '/assets/svg/lock.svg' },
  { key: 'cleaning', name: '家政清洁', icon_svg: '/assets/svg/clean.svg' },
  { key: 'wall', name: '墙面翻新', icon_svg: '/assets/svg/wall.svg' },
  { key: 'furniture', name: '家具维修', icon_svg: '/assets/svg/sofa.svg' },
  { key: 'install', name: '电器安装', icon_svg: '/assets/svg/lightbulb.svg' }
]

const MASTERS = [
  { id: 1, name: '张师傅', subtitle: '防水维修 · 12年经验 · 好评99%', price: '80', rating: '4.9' },
  { id: 2, name: '李师傅', subtitle: '管道疏通 · 8年经验 · 好评98%', price: '60', rating: '4.8' }
]

const REC_SERVICES = [
  { id: 1, key: 'waterproof', title: '防水维修', label: '防水维修', color: '#0D9488', rating: '4.9', count: '128', price: '128' },
  { id: 2, key: 'appliance', title: '水电维修', label: '水电维修', color: '#D4944C', rating: '4.8', count: '256', price: '88' },
  { id: 3, key: 'plumbing', title: '管道疏通', label: '管道疏通', color: '#5B8C5A', rating: '4.9', count: '192', price: '68' }
]

Page({
  data: {
    user: USER,
    hotTags: HOT_TAGS,
    services: SERVICES,
    categories: CATEGORIES,
    masters: MASTERS,
    recServices: REC_SERVICES,
    activeCategory: 'all',
    loading: false,
    navScrolled: false
  },

  onLoad() {
    this.loadServices()
  },

  onPageScroll(e) {
    const scrolled = e.scrollTop > 80
    if (scrolled !== this.data.navScrolled) {
      this.setData({ navScrolled: scrolled })
    }
  },

  loadServices() {
    this.setData({ loading: true })
    api.get('/api/services').then(data => {
      const list = Array.isArray(data) ? data : (data.list || [])
      if (list.length > 0) {
        const services = list.map((s, i) => ({
          key: s.key || s.id || String(i),
          name: s.name,
          icon_svg: s.icon_svg || (SERVICES[i] && SERVICES[i].icon_svg) || '/assets/svg/plus-circle.svg'
        }))
        this.setData({ services, loading: false })
      } else {
        this.setData({ loading: false })
      }
    }).catch(() => {
      this.setData({ loading: false })
    })
  },

  onSearch() {
    wx.navigateTo({ url: '/pages/search/search' })
  },

  onAI() {
    wx.navigateTo({ url: '/pages/ai-chat/ai-chat' })
  },

  onHotTag(e) {
    const key = e.currentTarget.dataset.key
    wx.navigateTo({ url: `/pages/service/detail/detail?key=${key}` })
  },

  onCategoryTap(e) {
    const key = e.currentTarget.dataset.key
    this.setData({ activeCategory: key })
  },

  goService(e) {
    const key = e.currentTarget.dataset.key
    wx.navigateTo({ url: `/pages/service/detail/detail?key=${key}` })
  },

  goMaster(e) {
    const id = e.currentTarget.dataset.id
    wx.navigateTo({ url: `/pages/worker/detail/detail?id=${id}` })
  },

  goOrders() {
    wx.switchTab({ url: '/pages/orders/orders' })
  },

  goFavorites() {
    wx.navigateTo({ url: '/pages/favorites/favorites' })
  },

  goCoupons() {
    wx.navigateTo({ url: '/pages/coupon/coupon' })
  },

  goMasterList() {
    wx.navigateTo({ url: '/pages/worker/list/list' })
  },

  goPublish() {
    wx.switchTab({ url: '/pages/publish/publish' })
  },

  goMine() {
    wx.switchTab({ url: '/pages/mine/mine' })
  },

  onShareAppMessage() {
    return { title: '自家人维修 - 专业上门服务', path: '/pages/index/index' }
  }
})
