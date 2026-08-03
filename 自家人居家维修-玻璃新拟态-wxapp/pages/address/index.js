// pages/address/index.js — 地址管理
// 像素级复刻 zjrnew/pages/client-address.html

const app = getApp();
const { buildIcon, COLORS } = require('../../utils/icons');

Page({
  data: {
    statusBarHeight: 44,
    addresses: [],
    selectMode: false,
    currentLocation: '点击获取当前位置',
    operating: false,
    icons: {}
  },

  onLoad(query) {
    const sysInfo = wx.getSystemInfoSync();
    this.setData({
      statusBarHeight: sysInfo.statusBarHeight || 44,
      selectMode: !!(query && query.select),
      icons: {
        back: buildIcon('arrowLeft', COLORS.text1),
        menu: buildIcon('menu', COLORS.text1),
        location: buildIcon('location', COLORS.brand),
        locationWhite: buildIcon('location', COLORS.white),
        refresh: buildIcon('refresh', COLORS.brand),
        edit: buildIcon('edit', COLORS.brand),
        trash: buildIcon('trash', COLORS.red),
        plus: buildIcon('plus', COLORS.white),
        check: buildIcon('check', COLORS.white)
      }
    });
    this.loadAddresses();
  },

  async loadAddresses() {
    const api = app.getApi && app.getApi();
    if (!api || !api.auth || !api.auth.getAddresses) {
      this.setData({ addresses: [] });
      return;
    }
    try {
      const list = await api.auth.getAddresses();
      const addresses = (list || []).map(a => Object.assign({}, a, {
        isDefault: a.is_default != null ? a.is_default : a.isDefault,
        tag: a.label != null ? a.label : a.tag,
        lat: a.location_lat != null ? a.location_lat : a.lat,
        lng: a.location_lng != null ? a.location_lng : a.lng
      }));
      const defaultAddress = addresses.find(item => item.isDefault) || addresses[0];
      this.setData({
        addresses,
        currentLocation: defaultAddress ? defaultAddress.detail : this.data.currentLocation
      });
    } catch (e) {
      console.error('加载地址列表失败', e);
      this.setData({ addresses: [] });
    }
  },

  _chooseLocation() {
    return new Promise((resolve, reject) => {
      wx.chooseLocation({ success: resolve, fail: reject });
    });
  },

  async _getUserInfo() {
    const cached = app.globalData.userInfo || {};
    if (cached.phone) return cached;
    const api = app.getApi();
    const userInfo = await api.auth.me();
    app.globalData.userInfo = userInfo;
    try { wx.setStorageSync('userInfo', userInfo); } catch (e) {}
    return userInfo || {};
  },

  _fallbackRegion(detail) {
    const text = String(detail || '');
    const provinceMatch = text.match(/^(.+?(?:省|自治区|特别行政区|市))/);
    const cityMatch = text.match(/(?:省|自治区)(.+?市)/);
    const districtMatches = text.match(/[^省市]+?(?:区|县|旗)/g) || [];
    const province = provinceMatch ? provinceMatch[1] : '';
    return {
      province,
      city: cityMatch ? cityMatch[1] : (/市$/.test(province) ? province : ''),
      district: districtMatches.length ? districtMatches[districtMatches.length - 1] : ''
    };
  },

  async _buildAddressPayload(location, existing) {
    const api = app.getApi();
    const userInfo = await this._getUserInfo();
    const phone = (existing && existing.phone) || userInfo.phone || '';
    if (!/^1[3-9]\d{9}$/.test(phone)) {
      wx.showModal({
        title: '请先绑定手机号',
        content: '新增服务地址前，需要在设置页完成短信验证绑定。',
        confirmText: '去设置',
        success: res => {
          if (res.confirm) wx.navigateTo({ url: '/pages/client-settings/index' });
        }
      });
      return null;
    }
    const detail = [location.address, location.name]
      .filter(Boolean)
      .filter((value, index, values) => index === 0 || value !== values[0])
      .join(' ')
      .trim();
    let geocode = {};
    try {
      geocode = await api.map.reverseGeocode(location.latitude, location.longitude) || {};
    } catch (e) {
      console.warn('逆地址解析不可用，保留微信选点地址', e);
    }
    const region = this._fallbackRegion(detail);
    return {
      name: (existing && existing.name) || userInfo.nickname || '微信用户',
      phone,
      province: geocode.province || region.province,
      city: geocode.city || region.city,
      district: geocode.district || region.district,
      detail: geocode.address || detail || location.name,
      label: (existing && (existing.label || existing.tag)) || '家',
      is_default: existing ? !!existing.isDefault : this.data.addresses.length === 0,
      location_lat: location.latitude,
      location_lng: location.longitude
    };
  },

  onBack() {
    wx.navigateBack({
      fail: () => wx.redirectTo({ url: '/pages/client-mine/index' })
    });
  },

  onNavEdit() {
    wx.showToast({ title: '管理功能开发中', icon: 'none' });
  },

  async onRelocate() {
    try {
      const location = await this._chooseLocation();
      this.setData({ currentLocation: location.address || location.name || '已获取当前位置' });
    } catch (e) {
      if (!e || !String(e.errMsg || '').includes('cancel')) {
        wx.showToast({ title: '暂时无法获取位置', icon: 'none' });
      }
    }
  },

  onAddrTap(e) {
    const id = e.currentTarget.dataset.id;
    const addr = this.data.addresses.find(a => String(a.id) === String(id));
    if (!addr) return;
    if (this.data.selectMode) {
      const pages = getCurrentPages();
      const prev = pages[pages.length - 2];
      if (prev && prev.setData) {
        prev.setData({ address: addr });
      }
      wx.navigateBack({ delta: 1 });
    }
  },

  async onAdd() {
    if (this.data.operating) return;
    this.setData({ operating: true });
    try {
      const location = await this._chooseLocation();
      const payload = await this._buildAddressPayload(location, null);
      if (!payload) return;
      await app.getApi().auth.addAddress(payload);
      await this.loadAddresses();
      wx.showToast({ title: '地址已添加', icon: 'success' });
    } catch (e) {
      if (!e || !String(e.errMsg || '').includes('cancel')) {
        console.error('新增地址失败', e);
      }
    } finally {
      this.setData({ operating: false });
    }
  },

  async onEdit(e) {
    const id = e.currentTarget.dataset.id;
    const existing = this.data.addresses.find(a => String(a.id) === String(id));
    if (!existing || this.data.operating) return;
    this.setData({ operating: true });
    try {
      const location = await this._chooseLocation();
      const payload = await this._buildAddressPayload(location, existing);
      if (!payload) return;
      await app.getApi().auth.updateAddress(id, payload);
      await this.loadAddresses();
      wx.showToast({ title: '地址已更新', icon: 'success' });
    } catch (error) {
      if (!error || !String(error.errMsg || '').includes('cancel')) {
        console.error('更新地址失败', error);
      }
    } finally {
      this.setData({ operating: false });
    }
  },

  onDel(e) {
    const id = e.currentTarget.dataset.id;
    const addr = this.data.addresses.find(a => String(a.id) === String(id));
    if (!addr) return;
    wx.showModal({
      title: '删除地址',
      content: '确认删除该地址？删除后无法恢复',
      confirmColor: '#C4533A',
      success: async (res) => {
        if (!res.confirm) return;
        try {
          await app.getApi().auth.deleteAddress(id);
          await this.loadAddresses();
          wx.showToast({ title: '已删除', icon: 'success' });
        } catch (error) {
          console.error('删除地址失败', error);
        }
      }
    });
  },

  onAddrLongPress(e) {
    this.onDel(e);
  },

  async onSetDefault(e) {
    const id = e.currentTarget.dataset.id;
    const target = this.data.addresses.find(a => String(a.id) === String(id));
    if (!target || target.isDefault) return;
    try {
      await app.getApi().auth.setDefaultAddress(id);
      await this.loadAddresses();
      wx.showToast({ title: '已设为默认', icon: 'success' });
    } catch (error) {
      console.error('设置默认地址失败', error);
    }
  },

  onChooseLocation(e) {
    const id = e.currentTarget.dataset.id;
    const addr = this.data.addresses.find(a => String(a.id) === String(id));
    if (!addr) return;
    if (!Number.isFinite(Number(addr.lat)) || !Number.isFinite(Number(addr.lng))) {
      wx.showToast({ title: '该地址暂无可用坐标', icon: 'none' });
      return;
    }
    wx.openLocation({
      latitude: Number(addr.lat),
      longitude: Number(addr.lng),
      name: addr.tag + '地址',
      address: addr.detail,
      scale: 18
    });
  }
});
