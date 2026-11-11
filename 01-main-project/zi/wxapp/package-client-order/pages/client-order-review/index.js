Page({
  data: {
    filter: 'all',
    summary: {
      avgRating: '4.8',
      totalCount: 126,
      goodRate: '96.8',
      hasImageCount: 42
    },
    reviews: [
      {
        id: 1,
        workerName: '张师傅',
        workerAvatar: '',
        rating: 5,
        stars: '★★★★★',
        content: '师傅非常专业，准时到达，服务态度很好，维修效果非常满意！强烈推荐！',
        createdAt: '2026-08-03 15:00',
        serviceType: '水电维修',
        tags: ['专业', '准时', '态度好'],
        images: [],
        liked: false,
        likeCount: 12
      },
      {
        id: 2,
        workerName: '李师傅',
        workerAvatar: '',
        rating: 5,
        stars: '★★★★★',
        content: '上门速度快，技术过硬，价格透明，以后有需要还会找这位师傅。',
        createdAt: '2026-07-28 10:30',
        serviceType: '家电维修',
        tags: ['专业', '价格透明'],
        images: [],
        liked: false,
        likeCount: 8
      },
      {
        id: 3,
        workerName: '王师傅',
        workerAvatar: '',
        rating: 4,
        stars: '★★★★',
        content: '整体服务不错，就是等待时间稍长了点，其他都很好。',
        createdAt: '2026-07-20 16:45',
        serviceType: '空调维修',
        tags: ['服务好'],
        images: [],
        liked: false,
        likeCount: 3
      }
    ],
    icons: {
      back: '/assets/icons/back.svg'
    }
  },

  onBack() { wx.navigateBack(); },

  onFilter(e) {
    this.setData({ filter: e.currentTarget.dataset.filter });
  },

  onLike(e) {
    const index = e.currentTarget.dataset.index;
    const reviews = this.data.reviews;
    reviews[index].liked = !reviews[index].liked;
    reviews[index].likeCount += reviews[index].liked ? 1 : -1;
    this.setData({ reviews });
  }
})
