const fs = require('fs');
const path = require('path');

const designFile = 'c:\\Users\\12620\\Desktop\\zi\\zjrnew\\zjrnew.design';
const backupFile = 'c:\\Users\\12620\\Desktop\\zi\\zjrnew\\zjrnew.design.bak2';

// Backup
fs.copyFileSync(designFile, backupFile);
console.log('Backup saved:', backupFile);

const raw = fs.readFileSync(designFile, 'utf-8');
const data = JSON.parse(raw);

const pageW = 375;
const pageH = 812;
const gapX = 80;
const gapY = 120;
const startX = 100;
const startY = 100;

const layout = {};

function setRow(pages, row, startCol) {
  pages.forEach((p, i) => {
    layout[p] = { row, col: startCol + i };
  });
  return startCol + pages.length;
}

// ========== Row 0: 5 primary pages ==========
setRow([
  'page-client-home-glass-neu',
  'page-client-orders',
  'page-client-publish',
  'page-client-service',
  'page-client-mine'
], 0, 0);

// ========== Row 1: secondary pages ==========
let col1 = 5;
col1 = setRow([
  'page-client-service-detail',
  'page-client-search',
  'page-client-member',
  'page-client-chat',
  'page-client-quote-list',
  'page-client-worker-detail'
], 1, col1) + 1; // +1 empty col

col1 = setRow([
  'page-client-order-detail',
  'page-client-order-search',
  'page-client-order-picker'
], 1, col1) + 1;

col1 = setRow([
  'page-client-address',
  'page-client-coupon-select'
], 1, col1) + 1;

col1 = setRow([
  'page-client-customer-service',
  'page-client-ticket-submit',
  'page-client-help'
], 1, col1) + 1;

col1 = setRow([
  'page-client-profile',
  'page-client-wallet',
  'page-client-coupon',
  'page-client-annual-card',
  'page-client-points',
  'page-client-invite',
  'page-client-favorite-workers',
  'page-client-feedback',
  'page-client-insurance-claim',
  'page-client-settings',
  'page-client-history',
  'page-client-notification'
], 1, col1) + 1;

// ========== Row 2: tertiary pages ==========
let col2 = 0;
col2 = setRow([
  'page-client-order-tracking',
  'page-client-order-tracking-2',
  'page-client-payment',
  'page-client-review',
  'page-client-order-cancel',
  'page-client-refund',
  'page-client-report',
  'page-client-price-adjust',
  'page-client-order-chat',
  'page-client-review-list'
], 2, col2) + 1;

col2 = setRow([
  'page-client-address-edit',
  'page-client-map-picker'
], 2, col2) + 1;

col2 = setRow([
  'page-client-balance-transactions',
  'page-client-recharge-record',
  'page-client-withdraw-record',
  'page-client-wallet-recharge',
  'page-client-wallet-withdraw',
  'page-client-bank-cards',
  'page-client-income-stat',
  'page-client-invoice'
], 2, col2) + 1;

col2 = setRow(['page-client-coupon-detail'], 2, col2) + 1;

col2 = setRow([
  'page-client-annual-card-record',
  'page-client-refund-card'
], 2, col2) + 1;

col2 = setRow([
  'page-client-points-detail',
  'page-client-points-mall',
  'page-client-points-tasks',
  'page-client-points-product'
], 2, col2) + 1;

col2 = setRow([
  'page-client-invite-record',
  'page-client-friend-detail'
], 2, col2) + 1;

col2 = setRow([
  'page-client-policy-detail',
  'page-client-claim-result'
], 2, col2) + 1;

col2 = setRow([
  'page-client-profile-edit',
  'page-client-account-security',
  'page-client-privacy',
  'page-client-about',
  'page-client-auth',
  'page-client-login'
], 2, col2) + 1;

col2 = setRow(['page-client-message-detail'], 2, col2) + 1;

// ========== Row 3: 4th level pages ==========
let col3 = 0;
col3 = setRow([
  'page-client-payment-result',
  'page-client-exchange-result'
], 3, col3) + 1;

col3 = setRow(['page-client-transaction-detail'], 3, col3) + 1;
col3 = setRow(['page-client-bank-card-add'], 3, col3) + 1;

col3 = setRow([
  'page-client-invoice-orders',
  'page-client-invoice-title-edit',
  'page-client-invoice-detail'
], 3, col3) + 1;

col3 = setRow([
  'page-client-password',
  'page-client-bind-phone',
  'page-client-verification',
  'page-client-device-management',
  'page-client-account-cancel',
  'page-client-verification-result'
], 3, col3) + 1;

col3 = setRow(['page-client-visibility'], 3, col3) + 1;
col3 = setRow(['page-client-agreement'], 3, col3) + 1;
col3 = setRow(['page-client-refund-card-result'], 3, col3) + 1;

col3 = setRow([
  'page-client-ticket-detail',
  'page-client-feedback-detail'
], 3, col3) + 1;

col3 = setRow(['page-client-review-detail'], 3, col3) + 1;
col3 = setRow(['page-client-video'], 3, col3) + 1;

// Contrast page - row 4
layout['page-client-home-glass-neu-contrast-1'] = { row: 4, col: 0 };

// ========== Worker side - starts at row 6 ==========
const wr = 6;

// Worker row 0: 5 primary
setRow([
  'page-worker-home',
  'page-worker-orders',
  'page-worker-wallet',
  'page-worker-training',
  'page-worker-profile'
], wr, 0);

// Worker row 1
let wc1 = 0;
wc1 = setRow(['page-worker-order-detail'], wr+1, wc1) + 1;
wc1 = setRow([
  'page-worker-withdraw',
  'page-worker-transactions',
  'page-worker-income-stat',
  'page-worker-recharge'
], wr+1, wc1) + 1;
wc1 = setRow([
  'page-worker-training-exam',
  'page-worker-training-detail'
], wr+1, wc1) + 1;
wc1 = setRow([
  'page-worker-service-scope',
  'page-worker-experience',
  'page-worker-cert-manage',
  'page-worker-service-area',
  'page-worker-certification',
  'page-worker-deposit',
  'page-worker-reviews',
  'page-worker-help',
  'page-worker-settings',
  'page-worker-location-report',
  'page-worker-appeal'
], wr+1, wc1) + 1;

// Worker row 2
let wc2 = 0;
wc2 = setRow(['page-worker-experience-item-edit'], wr+2, wc2) + 1;
wc2 = setRow(['page-worker-certificate-edit'], wr+2, wc2) + 1;
wc2 = setRow([
  'page-worker-deposit-refund',
  'page-worker-deposit-pay'
], wr+2, wc2) + 1;
wc2 = setRow(['page-worker-help-category'], wr+2, wc2) + 1;
wc2 = setRow([
  'page-worker-order-setting',
  'page-worker-time-setting'
], wr+2, wc2) + 1;
wc2 = setRow(['page-worker-appeal-detail'], wr+2, wc2) + 1;
wc2 = setRow(['page-worker-withdraw-result'], wr+2, wc2) + 1;
wc2 = setRow(['page-worker-income-category-detail'], wr+2, wc2) + 1;
wc2 = setRow([
  'page-worker-quote-submit',
  'page-worker-chat',
  'page-worker-customer-profile',
  'page-worker-price-adjust-worker'
], wr+2, wc2) + 1;

// Worker row 3
layout['page-worker-exam-result'] = { row: wr+3, col: 0 };
layout['page-worker-lesson'] = { row: wr+3, col: 2 };

// Stats
let mapped = 0;
const unmapped = [];
data.data.forEach(item => {
  if (item.type === 'page') {
    if (layout[item.id]) mapped++;
    else unmapped.push(item.id);
  }
});

console.log(`Total pages: ${data.data.length}`);
console.log(`Mapped: ${mapped}`);
console.log(`Unmapped: ${unmapped.length}`);
if (unmapped.length > 0) {
  unmapped.forEach(p => console.log('  ', p));
}

// Apply
let count = 0;
data.data.forEach(item => {
  if (item.type === 'page' && layout[item.id]) {
    const { row, col } = layout[item.id];
    item.canvasData.x = startX + col * (pageW + gapX);
    item.canvasData.y = startY + row * (pageH + gapY);
    count++;
  }
});

fs.writeFileSync(designFile, JSON.stringify(data, null, 2), 'utf-8');
console.log(`\nUpdated ${count} pages. Saved.`);
