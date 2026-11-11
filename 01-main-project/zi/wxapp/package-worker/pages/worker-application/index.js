Page({
  data: {
    form: {
      name: '',
      phone: '',
      idCard: '',
      experience: '',
      bio: ''
    },
    skillOptions: [
      { key: 'electric', name: '水电维修', active: false },
      { key: 'plumbing', name: '管道疏通', active: false },
      { key: 'waterproof', name: '防水补漏', active: false },
      { key: 'appliance', name: '家电维修', active: false },
      { key: 'bathroom', name: '卫浴安装', active: false },
      { key: 'paint', name: '油漆涂料', active: false }
    ]
  },

  onBack() {
    wx.navigateBack();
  },

  onInput(e) {
    const field = e.currentTarget.dataset.field;
    this.setData({ [`form.${field}`]: e.detail.value });
  },

  onSkillToggle(e) {
    const key = e.currentTarget.dataset.key;
    const skills = this.data.skillOptions.map(s =>
      s.key === key ? { ...s, active: !s.active } : s
    );
    this.setData({ skillOptions: skills });
  },

  onUploadCert() {
    wx.chooseImage({
      count: 1,
      success: (res) => {
        wx.showToast({ title: '上传成功', icon: 'success' });
      }
    });
  },

  onSubmit() {
    wx.showToast({ title: '申请已提交', icon: 'success' });
    setTimeout(() => {
      wx.navigateBack();
    }, 1000);
  }
});
