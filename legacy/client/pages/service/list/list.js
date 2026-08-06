Page({
  data: {
    tickets: [
      { id: 1, type: '维修咨询', typeClass: 'ticket-type-repair', status: '处理中', statusClass: 'processing', title: '关于卫生间漏水维修的咨询', time: '2小时前' },
      { id: 2, type: '服务投诉', typeClass: 'ticket-type-complaint', status: '待处理', statusClass: 'pending', title: '上次服务师傅迟到问题反馈', time: '昨天' }
    ],
    faqs: [
      { id: 1, question: '如何预约上门服务？', answer: '您可以在首页选择所需服务类型，填写问题描述和地址信息后提交需求，系统将为您匹配合适的师傅。', open: false }
    ],
    faqs2: [
      { id: 2, question: '服务价格如何计算？' }
    ],
    faqs3: [
      { id: 3, question: '师傅上门时间可以改吗？' }
    ],
    faqs4: [
      { id: 4, question: '服务不满意怎么办？' }
    ]
  },

  onBack() {
    wx.navigateBack()
  },

  onOnlineService() {
    wx.showToast({ title: '正在连接客服...', icon: 'none' })
  },

  onCallService() {
    wx.makePhoneCall({ phoneNumber: '4008888888' })
  },

  goAllTickets() {
    wx.showToast({ title: '全部工单', icon: 'none' })
  },

  replyTicket(e) {
    const id = e.currentTarget.dataset.id
    wx.showToast({ title: '回复工单 #' + id, icon: 'none' })
  },

  toggleFaq(e) {
    const id = e.currentTarget.dataset.id
    const faqs = this.data.faqs.map(f => ({
      ...f,
      open: f.id === id ? !f.open : f.open
    }))
    this.setData({ faqs })
  },

  onSubmitTicket() {
    wx.showToast({ title: '提交工单', icon: 'none' })
  }
})
