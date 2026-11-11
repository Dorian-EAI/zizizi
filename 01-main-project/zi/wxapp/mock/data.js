// mock/data.js — 模拟数据
// 自家人居家维修 玻璃新拟态版

// 八大核心服务
const services = [
  { key: 'plumbing',   name: '防水维修', icon: 'plumbing',   desc: '厨卫/屋顶/阳台防水', price_min: 200, priceFrom: 200, priceTo: 1500, warranty: '12个月' },
  { key: 'detection',  name: '检测漏水', icon: 'search',     desc: '漏水点精准定位',     price_min: 100, priceFrom: 100, priceTo: 500,  warranty: '6个月' },
  { key: 'electric',   name: '水电维修', icon: 'electric',   desc: '水龙头/管道/电路',   price_min: 80,  priceFrom: 80,  priceTo: 300,  warranty: '3个月' },
  { key: 'paint',      name: '美容修复', icon: 'paint',      desc: '家具/家电/墙面修复', price_min: 150, priceFrom: 150, priceTo: 600,  warranty: '1个月' },
  { key: 'appliance',  name: '家电维修', icon: 'appliance',  desc: '厨电/家电安装维修', price_min: 100, priceFrom: 100, priceTo: 800,  warranty: '6个月' },
  { key: 'lock',       name: '开锁换锁', icon: 'lock',       desc: '门锁/窗户/窗帘',     price_min: 80,  priceFrom: 80,  priceTo: 300,  warranty: '3个月' },
  { key: 'carpentry',  name: '墙地翻新', icon: 'carpentry',  desc: '地砖/墙面/地板',     price_min: 200, priceFrom: 200, priceTo: 1500, warranty: '6个月' },
  { key: 'pipeline',   name: '管道疏通', icon: 'pipeline',   desc: '下水道/马桶/地漏',   price_min: 80,  priceFrom: 80,  priceTo: 300,  warranty: '1个月' }
]

// 推荐师傅
const workers = [
  { id: 'w1', name: '张师傅', avatar: 'user', skill: '防水维修', experience: '12年经验', rating: 4.9, serviceTimes: 1280, priceFrom: 80, distance: 1.2, certified: true, level: 4, tags: ['响应快', '技术好', '收费透明'] },
  { id: 'w2', name: '李师傅', avatar: 'user', skill: '管道疏通', experience: '8年经验',  rating: 4.8, serviceTimes: 960,  priceFrom: 60, distance: 2.5, certified: true, level: 3, tags: ['态度好', '准时到达'] },
  { id: 'w3', name: '王师傅', avatar: 'user', skill: '水电维修', experience: '10年经验', rating: 4.9, serviceTimes: 1520, priceFrom: 80, distance: 0.8, certified: true, level: 4, tags: ['技术好', '保护到位'] },
  { id: 'w4', name: '赵师傅', avatar: 'user', skill: '家电维修', experience: '6年经验',  rating: 4.7, serviceTimes: 680,  priceFrom: 100, distance: 3.1, certified: true, level: 3, tags: ['响应快', '收费透明'] },
  { id: 'w5', name: '陈师傅', avatar: 'user', skill: '墙地翻新', experience: '15年经验', rating: 5.0, serviceTimes: 2100, priceFrom: 200, distance: 4.5, certified: true, level: 4, tags: ['技术好', '服务规范'] }
]

// 客户端订单
const clientOrders = [
  {
    id: 'o20260728001', serviceKey: 'electric', serviceName: '水电维修', icon: 'electric',
    description: '厨房水龙头漏水，需更换阀芯', status: 'bidding', statusText: '竞价中',
    address: '朝阳区建国路88号', time: '今天 15:00-18:00', quotes: 3, priceRange: '¥80-150',
    createdAt: '2026-07-28 14:30', mode: 'bidding'
  },
  {
    id: 'o20260727002', serviceKey: 'plumbing', serviceName: '防水维修', icon: 'plumbing',
    description: '卫生间地面渗水', status: 'departing', statusText: '师傅已出发',
    address: '朝阳区建国路88号', time: '今天 10:00', workerName: '张师傅', workerId: 'w1',
    workerPhone: '139****6666', price: 480, createdAt: '2026-07-27 09:15', mode: 'bidding',
    lat: 39.9050, lng: 116.4080
  },
  {
    id: 'o20260727005', serviceKey: 'appliance', serviceName: '家电维修', icon: 'appliance',
    description: '空调外机异响，需要上门检查', status: 'accepted', statusText: '师傅已接单',
    address: '朝阳区建国路88号', time: '今天 13:00-15:00', workerName: '王师傅', workerId: 'w3',
    workerPhone: '138****8899', priceRange: '¥120-260', createdAt: '2026-07-27 12:20', mode: 'bidding',
    lat: 39.9050, lng: 116.4080
  },
  {
    id: 'o20260725003', serviceKey: 'pipeline', serviceName: '管道疏通', icon: 'pipeline',
    description: '厨房下水道堵塞', status: 'completed', statusText: '已完成',
    address: '朝阳区建国路88号', time: '07-25 14:00', workerName: '李师傅', workerId: 'w2',
    price: 120, createdAt: '2026-07-25 13:00', mode: 'fixed', hasReview: true
  },
  {
    id: 'o20260720004', serviceKey: 'appliance', serviceName: '家电维修', icon: 'appliance',
    description: '空调不制冷', status: 'pending_review', statusText: '待评价',
    address: '朝阳区建国路88号', time: '07-20 16:00', workerName: '赵师傅', workerId: 'w4',
    price: 260, createdAt: '2026-07-20 15:00', mode: 'bidding', hasReview: false
  }
]

// 师傅端订单（可抢/进行中）
const workerOrders = [
  {
    id: 'n20260728001', serviceKey: 'electric', serviceName: '水电维修', icon: 'electric',
    description: '厨房水龙头漏水，需更换阀芯', status: 'available', statusText: '可抢单',
    address: '朝阳区建国路88号', distance: 1.2, time: '今天 15:00-18:00',
    priceRange: '¥80-150', mode: 'bidding', urgent: false, createdAt: '2分钟前'
  },
  {
    id: 'n20260728002', serviceKey: 'lock', serviceName: '开锁换锁', icon: 'lock',
    description: '门锁损坏无法打开', status: 'available', statusText: '可抢单',
    address: '海淀区中关村大街1号', distance: 2.8, time: '立即上门',
    priceRange: '¥150', mode: 'fixed', urgent: true, createdAt: '5分钟前'
  },
  {
    id: 's20260728001', serviceKey: 'plumbing', serviceName: '防水维修', icon: 'plumbing',
    description: '卫生间地面渗水', status: 'departing', statusText: '位置上报中',
    address: '朝阳区建国路88号', time: '今天 10:00', price: 480,
    userName: '刘先生', userPhone: '138****8888', step: 'departing', createdAt: '今天 09:15',
    lat: 39.9050, lng: 116.4080
  },
  {
    id: 's20260728003', serviceKey: 'electric', serviceName: '水电维修', icon: 'electric',
    description: '厨房水龙头漏水，需更换阀芯', status: 'accepted', statusText: '已接单',
    address: '朝阳区建国路88号', time: '今天 15:00-18:00', price: 150,
    userName: '刘先生', userPhone: '138****8888', step: 'accepted', createdAt: '今天 14:35',
    lat: 39.9050, lng: 116.4080
  },
  {
    id: 's20260728004', serviceKey: 'lock', serviceName: '开锁换锁', icon: 'lock',
    description: '门锁损坏无法打开', status: 'arrived', statusText: '已到达',
    address: '朝阳区建国路88号', time: '立即上门', price: 180,
    userName: '刘先生', userPhone: '138****8888', step: 'arrived', createdAt: '今天 14:50',
    lat: 39.9050, lng: 116.4080
  },
  {
    id: 's20260727002', serviceKey: 'pipeline', serviceName: '管道疏通', icon: 'pipeline',
    description: '厨房下水道堵塞', status: 'completed', statusText: '已完成',
    address: '朝阳区建国路88号', time: '07-25 14:00', price: 120,
    userName: '刘先生', userPhone: '138****8888', createdAt: '07-25 13:00', hasReview: true, rating: 5
  }
]

// 地址列表
const addresses = [
  { id: 'a1', name: '刘先生', phone: '13888888888', tag: '家', detail: '北京市朝阳区建国路88号现代城A座1801室', isDefault: true, lat: 39.908, lng: 116.457 },
  { id: 'a2', name: '刘先生', phone: '13888888888', tag: '公司', detail: '北京市海淀区中关村大街1号理想国际大厦12层', isDefault: false, lat: 39.983, lng: 116.312 }
]

// 优惠券
const coupons = [
  { id: 'c1', name: '新用户立减', amount: 20, threshold: 0, expire: '2026-12-31', desc: '无门槛', status: 'unused' },
  { id: 'c2', name: '满100减15', amount: 15, threshold: 100, expire: '2026-08-31', desc: '满100元可用', status: 'unused' },
  { id: 'c3', name: '防水维修专享', amount: 50, threshold: 500, expire: '2026-09-30', desc: '防水维修满500可用', status: 'unused' },
  { id: 'c4', name: '管道疏通券', amount: 10, threshold: 0, expire: '2026-07-15', desc: '无门槛', status: 'expired' }
]

// 师傅钱包数据
const workerWallet = {
  balance: 5280.50,
  todayIncome: 480,
  monthIncome: 1280,
  totalIncome: 45600.80,
  monthStats: { orders: 28, rating: 4.9, avgPrice: 320 },
  transactions: [
    { id: 't1', type: 'income', title: '防水维修订单', amount: 480, time: '今天 10:30', status: '已到账' },
    { id: 't2', type: 'income', title: '管道疏通订单', amount: 120, time: '昨天 15:20', status: '已到账' },
    { id: 't3', type: 'withdraw', title: '提现到银行卡', amount: -2000, time: '07-25 09:00', status: '已到账' },
    { id: 't4', type: 'income', title: '家电维修订单', amount: 260, time: '07-24 17:00', status: '已到账' },
    { id: 't5', type: 'income', title: '水电维修订单', amount: 150, time: '07-23 11:30', status: '已到账' }
  ]
}

// 用户信息
const userInfo = {
  id: 'u100824',
  name: '刘先生',
  avatar: 'user',
  phone: '138****8888',
  level: '普通会员',
  verified: true,
  stats: { orders: 12, rating: 4.9, spent: 2458.00 },
  wallet: 528.00,
  couponCount: 3
}

// 师傅信息
const workerInfo = {
  id: 'w1',
  name: '张师傅',
  avatar: 'user',
  phone: '139****6666',
  level: 4,
  levelText: '金牌师傅',
  verified: true,
  skills: ['防水维修', '水电维修', '管道疏通'],
  rating: 4.9,
  serviceTimes: 1280,
  responseSpeed: 0.95,
  acceptStatus: 'accepting',
  todayIncome: 480,
  monthIncome: 1280,
  totalIncome: 45600.80
}

// 报价列表（某订单）
const quotes = [
  { id: 'q1', workerId: 'w3', workerName: '王师傅', avatar: 'user', rating: 4.9, serviceTimes: 1520, distance: 0.8, price: 120, eta: '30分钟', matchLevel: '最佳匹配', matchScore: 0.92, tags: ['技术好', '保护到位'] },
  { id: 'q2', workerId: 'w1', workerName: '张师傅', avatar: 'user', rating: 4.9, serviceTimes: 1280, distance: 1.2, price: 100, eta: '45分钟', matchLevel: '优秀匹配', matchScore: 0.85, tags: ['响应快', '收费透明'] },
  { id: 'q3', workerId: 'w4', workerName: '赵师傅', avatar: 'user', rating: 4.7, serviceTimes: 680, distance: 3.1, price: 90, eta: '1小时', matchLevel: '良好匹配', matchScore: 0.68, tags: ['响应快'] }
]

// 热门搜索标签
const hotTags = ['水管漏水', '电路维修', '空调清洗', '门锁更换', '墙面翻新', '马桶疏通', '灯具安装', '防水施工']

// 服务分类
const categories = ['全部', '防水维修', '水电维修', '家电维修', '管道疏通', '墙面翻新', '开锁换锁']

// 平台统计数据
const platformStats = {
  certified_worker_count: 8247,
  satisfaction_rate: 98.6,
  average_response_seconds: 180,
  average_rating: 4.9
}

module.exports = {
  services,
  workers,
  clientOrders,
  workerOrders,
  addresses,
  coupons,
  workerWallet,
  userInfo,
  workerInfo,
  quotes,
  hotTags,
  categories,
  platformStats
}
