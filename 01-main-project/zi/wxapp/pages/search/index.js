// pages/search/index.js — 客服中心
// 像素级复刻 zjrnew/pages/client-service.html

const app = getApp();
const { buildIcon, COLORS } = require('../../utils/icons');

function formatTime(value) {
  if (!value) return '';
  return String(value).replace('T', ' ').slice(0, 16);
}

Page({
  data: {
    statusBarHeight: 44,
    servicePhoneDisplay: '暂未配置',
    servicePhoneConfigured: false,
    icons: {},
    activeFilter: 'all',
    tickets: [],
    filteredTickets: [],
    faqList: []
  },

  onLoad() {
    const sysInfo = wx.getSystemInfoSync();
    this.setData({
      statusBarHeight: sysInfo.statusBarHeight || 44,
      servicePhoneDisplay: app.globalData.servicePhone || '暂未配置',
      servicePhoneConfigured: !!String(app.globalData.servicePhone || '').trim(),
      icons: {
        back: buildIcon('arrowLeft', COLORS.text1),
        chat: buildIcon('message', COLORS.brand),
        phone: buildIcon('phone', COLORS.accent),
        plus: buildIcon('plus', COLORS.brand),
        chevronRight: buildIcon('chevronRight', COLORS.brand),
        chevronDown: buildIcon('chevronRight', COLORS.text3)
      }
    });
    this.loadFaqs();
  },

  onShow() {
    this.loadTickets();
  },

  normalizeTicket(ticket) {
    const type = ticket.ticket_type || ticket.type || 'consult';
    const typeLabels = { complaint: '投诉', refund: '退款', claim: '理赔', consult: '咨询', other: '其他' };
    const rawStatus = ticket.status || 'open';
    const resolved = rawStatus === 'resolved' || rawStatus === 'closed';
    const waiting = rawStatus === 'waiting_user' || rawStatus === 'reply';
    return {
      ...ticket,
      id: ticket.id,
      typeLabel: typeLabels[type] || type,
      typeClass: typeLabels[type] ? type : 'consult',
      statusLabel: resolved ? '已解决' : (waiting ? '待回复' : '处理中'),
      statusClass: resolved ? 'resolved' : (waiting ? 'reply' : 'processing'),
      no: ticket.ticket_no || ticket.ticketNo || ticket.id,
      time: formatTime(ticket.updated_at || ticket.created_at || ticket.time),
      filter: resolved ? 'resolved' : 'processing'
    };
  },

  async loadTickets() {
    const api = app.getApi();
    try {
      const result = await api.ticket.mine();
      const source = Array.isArray(result) ? result : ((result && result.items) || []);
      this.setData({ tickets: source.map(item => this.normalizeTicket(item)) }, () => this.applyFilter());
    } catch (error) {
      console.error('加载客服工单失败', error);
      this.setData({ tickets: [], filteredTickets: [] });
    }
  },

  async loadFaqs() {
    const api = app.getApi();
    try {
      const categories = await api.pages.faqs();
      const items = [];
      (Array.isArray(categories) ? categories : []).forEach(category => {
        (Array.isArray(category.faqs) ? category.faqs : []).forEach(faq => {
          if (faq && faq.question && faq.answer) items.push(faq);
        });
      });
      this.setData({ faqList: items.slice(0, 5) });
    } catch (error) {
      console.error('加载常见问题失败', error);
      this.setData({ faqList: [] });
    }
  },

  onFilter(e) {
    const filter = e.currentTarget.dataset.filter;
    if (filter === this.data.activeFilter) return;
    this.setData({ activeFilter: filter }, () => this.applyFilter());
  },

  applyFilter() {
    const { activeFilter, tickets } = this.data;
    const filtered = activeFilter === 'all'
      ? tickets
      : tickets.filter(t => t.filter === activeFilter);
    this.setData({ filteredTickets: filtered });
  },

  onBack() {
    wx.navigateBack({
      fail: () => wx.redirectTo({ url: '/pages/client-home/index' })
    });
  },

  onConsult() {
    wx.navigateTo({ url: '/package-client/pages/client-service/index?create=1' });
  },

  onCall() {
    const phone = String(app.globalData.servicePhone || '').replace(/[^\d]/g, '');
    if (!phone) {
      wx.showToast({ title: '客服电话暂未配置', icon: 'none' });
      return;
    }
    wx.makePhoneCall({
      phoneNumber: phone,
      fail: () => {
        wx.showToast({ title: '呼叫失败，请稍后重试', icon: 'none' });
      }
    });
  },

  onNewTicket() {
    wx.navigateTo({ url: '/package-client/pages/client-service/index?create=1' });
  },

  async onTicketTap(e) {
    const id = e.currentTarget.dataset.id;
    if (!id) return;
    const api = app.getApi();
    wx.showLoading({ title: '加载中', mask: true });
    try {
      const detail = await api.ticket.detail(id);
      wx.hideLoading();
      const ticket = this.normalizeTicket(detail || {});
      const content = [
        '状态：' + ticket.statusLabel,
        ticket.description || '',
        ticket.resolution ? ('处理结果：' + ticket.resolution) : ''
      ].filter(Boolean).join('\n\n');
      wx.showModal({
        title: ticket.title || ('工单 #' + (ticket.no || id)),
        content: content || '暂无更多详情',
        showCancel: false,
        confirmColor: '#0D9488'
      });
    } catch (error) {
      wx.hideLoading();
      console.error('加载工单详情失败', error);
    }
  },

  onFaqTap(e) {
    const id = e.currentTarget.dataset.id;
    const faq = this.data.faqList.find(f => String(f.id) === String(id));
    if (faq) {
      wx.showModal({
        title: faq.question,
        content: faq.answer,
        showCancel: false,
        confirmText: '知道了',
        confirmColor: '#0D9488'
      });
    }
  }
});
