Page({
  data: {
    profile: {
      initial: '张',
      name: '张师傅',
      bio: '从事水电维修行业 8 年，擅长水管漏水检测与维修。',
      area: '市区及周边',
      workingHours: '8:00 - 20:00'
    },
    serviceOptions: [
      { key: 'electric', name: '水电维修', active: true },
      { key: 'plumbing', name: '管道疏通', active: true },
      { key: 'waterproof', name: '防水补漏', active: false },
      { key: 'appliance', name: '家电维修', active: false },
      { key: 'bathroom', name: '卫浴安装', active: true }
    ]
  },

  onBack() {
    wx.navigateBack();
  },

  onChangeAvatar() {
    wx.chooseImage({
      count: 1,
      success: () => {
        wx.showToast({ title: '头像已更新', icon: 'success' });
      }
    });
  },

  onInput(e) {
    const field = e.currentTarget.dataset.field;
    this.setData({ [`profile.${field}`]: e.detail.value });
  },

  onToggleService(e) {
    const key = e.currentTarget.dataset.key;
    const options = this.data.serviceOptions.map(s =>
      s.key === key ? { ...s, active: !s.active } : s
    );
    this.setData({ serviceOptions: options });
  },

  onSave() {
    wx.showToast({ title: '保存成功', icon: 'success' });
    setTimeout(() => {
      wx.navigateBack();
    }, 800);
  }
});
