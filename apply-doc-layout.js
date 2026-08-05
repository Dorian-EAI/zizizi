const fs = require('fs');
const f = 'c:\\Users\\12620\\Desktop\\zi\\zjrnew\\zjrnew.design';
const json = JSON.parse(fs.readFileSync(f, 'utf-8'));

const PW = 375, PH = 812, GX = 80, GY = 120, SX = 100, SY = 100;

// Exact positions from 画布页面层级排版说明.md
const pos = {
  // ===== Row 0: Client Level 1 =====
  'page-client-home-glass-neu': [0, 0],
  'page-client-orders': [0, 7],
  'page-client-publish': [0, 17],
  'page-client-service': [0, 21],
  'page-client-mine': [0, 26],

  // ===== Row 1: Client Level 2 =====
  // Home children (cols 0~5)
  'page-client-service-detail': [1, 0],
  'page-client-search': [1, 1],
  'page-client-member': [1, 2],
  'page-client-chat': [1, 3],
  'page-client-quote-list': [1, 4],
  'page-client-worker-detail': [1, 5],
  // Orders children (cols 7~9)
  'page-client-order-detail': [1, 7],
  'page-client-order-search': [1, 8],
  'page-client-order-picker': [1, 9],
  // Publish children (cols 17~18)
  'page-client-address': [1, 17],
  'page-client-coupon-select': [1, 18],
  // Service children (cols 21~23)
  'page-client-customer-service': [1, 21],
  'page-client-ticket-submit': [1, 22],
  'page-client-help': [1, 23],
  // Mine children (cols 26~37)
  'page-client-profile': [1, 26],
  'page-client-wallet': [1, 27],
  'page-client-coupon': [1, 28],
  'page-client-annual-card': [1, 29],
  'page-client-points': [1, 30],
  'page-client-invite': [1, 31],
  'page-client-favorite-workers': [1, 32],
  'page-client-feedback': [1, 33],
  'page-client-insurance-claim': [1, 34],
  'page-client-settings': [1, 35],
  'page-client-history': [1, 36],
  'page-client-notification': [1, 37],

  // ===== Row 2: Client Level 3 =====
  // worker-detail child (col 5)
  'page-client-review-list': [2, 5],
  // order-detail children (cols 7~15)
  'page-client-order-tracking': [2, 7],
  'page-client-order-tracking-2': [2, 8],
  'page-client-payment': [2, 9],
  'page-client-review': [2, 10],
  'page-client-order-cancel': [2, 11],
  'page-client-refund': [2, 12],
  'page-client-report': [2, 13],
  'page-client-price-adjust': [2, 14],
  'page-client-order-chat': [2, 15],
  // address child (col 17)
  'page-client-address-edit': [2, 17],
  // ticket-submit child (col 22)
  'page-client-ticket-detail': [2, 22],
  // profile child (col 26)
  'page-client-profile-edit': [2, 26],
  // wallet children (cols 27~33)
  'page-client-balance-transactions': [2, 27],
  'page-client-recharge-record': [2, 28],
  'page-client-withdraw-record': [2, 29],
  'page-client-wallet-recharge': [2, 30],
  'page-client-wallet-withdraw': [2, 31],
  'page-client-income-stat': [2, 32],
  'page-client-invoice': [2, 33],
  // coupon child (col 28) - wait, doc says col 28 but coupon is at col 28...
  // actually doc says "优惠券的子页面（列 28）" = coupon-detail at col 28 row 2
  // But coupon-detail is child of coupon (row1 col28), so yes same col
  'page-client-coupon-detail': [2, 28],
  // annual-card children (cols 29~30)
  'page-client-annual-card-record': [2, 29],
  'page-client-refund-card': [2, 30],
  // points children (cols 30~32)
  'page-client-points-detail': [2, 30],
  'page-client-points-mall': [2, 31],
  'page-client-points-tasks': [2, 32],
  // invite child (col 31)
  'page-client-invite-record': [2, 31],
  // feedback child (col 33)
  'page-client-feedback-detail': [2, 33],
  // insurance children (cols 34~35)
  'page-client-policy-detail': [2, 34],
  'page-client-claim-result': [2, 35],
  // settings children (cols 35~39)
  'page-client-account-security': [2, 35],
  'page-client-privacy': [2, 36],
  'page-client-about': [2, 37],
  'page-client-auth': [2, 38],
  'page-client-login': [2, 39],
  // notification child (col 37)
  'page-client-message-detail': [2, 37],

  // ===== Row 3: Client Level 4 =====
  // payment child (col 9)
  'page-client-payment-result': [3, 9],
  // review child (col 10)
  'page-client-review-detail': [3, 10],
  // address-edit child (col 17)
  'page-client-map-picker': [3, 17],
  // balance-transactions child (col 27)
  'page-client-transaction-detail': [3, 27],
  // wallet-withdraw child - bank-cards (col 31)
  'page-client-bank-cards': [3, 31],
  // invoice children (cols 33~35) - 开票订单、发票抬头编辑、发票详情
  'page-client-invoice-orders': [3, 33],
  'page-client-invoice-title-edit': [3, 34],
  'page-client-invoice-detail': [3, 35],
  // refund-card child (col 30)
  'page-client-refund-card-result': [3, 30],
  // points-mall child (col 31)
  'page-client-points-product': [3, 31],
  // points-tasks child (col 32)
  'page-client-video': [3, 32],
  // invite-record child (col 31)
  'page-client-friend-detail': [3, 31],
  // account-security children (cols 35~39)
  'page-client-password': [3, 35],
  'page-client-bind-phone': [3, 36],
  'page-client-verification': [3, 37],
  'page-client-device-management': [3, 38],
  'page-client-account-cancel': [3, 39],
  // privacy child (col 36)
  'page-client-visibility': [3, 36],
  // about child (col 37)
  'page-client-agreement': [3, 37],

  // ===== Row 4: Client Level 5 =====
  // bank-cards child (col 31)
  'page-client-bank-card-add': [4, 31],
  // points-product child (col 31)
  'page-client-exchange-result': [4, 31],
  // verification child (col 35)
  'page-client-verification-result': [4, 35],

  // ===== Row 5: Contrast =====
  'page-client-home-glass-neu-contrast-1': [5, 0],

  // Row 6: empty

  // ===== Row 7: Worker Level 1 =====
  'page-worker-home': [7, 0],
  'page-worker-orders': [7, 2],
  'page-worker-wallet': [7, 8],
  'page-worker-training': [7, 14],
  'page-worker-profile': [7, 18],

  // ===== Row 8: Worker Level 2 =====
  // order child (col 2)
  'page-worker-order-detail': [8, 2],
  // wallet children (cols 8~11)
  'page-worker-withdraw': [8, 8],
  'page-worker-transactions': [8, 9],
  'page-worker-income-stat': [8, 10],
  'page-worker-recharge': [8, 11],
  // training children (cols 14~15)
  'page-worker-training-exam': [8, 14],
  'page-worker-training-detail': [8, 15],
  // profile children (cols 18~28)
  'page-worker-service-scope': [8, 18],
  'page-worker-experience': [8, 19],
  'page-worker-cert-manage': [8, 20],
  'page-worker-service-area': [8, 21],
  'page-worker-certification': [8, 22],
  'page-worker-deposit': [8, 23],
  'page-worker-reviews': [8, 24],
  'page-worker-help': [8, 25],
  'page-worker-settings': [8, 26],
  'page-worker-location-report': [8, 27],
  'page-worker-appeal': [8, 28],

  // ===== Row 9: Worker Level 3 =====
  // order-detail children (cols 2~5)
  'page-worker-quote-submit': [9, 2],
  'page-worker-chat': [9, 3],
  'page-worker-customer-profile': [9, 4],
  'page-worker-price-adjust-worker': [9, 5],
  // withdraw child (col 8)
  'page-worker-withdraw-result': [9, 8],
  // income-stat child (col 10)
  'page-worker-income-category-detail': [9, 10],
  // exam child (col 14)
  'page-worker-exam-result': [9, 14],
  // training-detail child (col 15)
  'page-worker-lesson': [9, 15],
  // experience child (col 19)
  'page-worker-experience-item-edit': [9, 19],
  // cert-manage child (col 20)
  'page-worker-certificate-edit': [9, 20],
  // deposit children (cols 23~24)
  'page-worker-deposit-refund': [9, 23],
  'page-worker-deposit-pay': [9, 24],
  // help child (col 25)
  'page-worker-help-category': [9, 25],
  // settings children (cols 26~27)
  'page-worker-order-setting': [9, 26],
  'page-worker-time-setting': [9, 27],
  // appeal child (col 28)
  'page-worker-appeal-detail': [9, 28],
};

// Check for duplicates
const seen = {};
const duplicates = [];
for (const [id, [r, c]] of Object.entries(pos)) {
  const key = `${r},${c}`;
  if (seen[key]) {
    duplicates.push(`${id} overlaps with ${seen[key]} at row=${r} col=${c}`);
  }
  seen[key] = id;
}
console.log('Total positions:', Object.keys(pos).length);
if (duplicates.length) {
  console.log('WARNING - Overlapping positions:');
  duplicates.forEach(d => console.log('  ' + d));
}

// Apply
let count = 0, missing = [];
json.data.forEach(item => {
  if (item.type === 'page') {
    if (pos[item.id]) {
      const [row, col] = pos[item.id];
      item.canvasData.x = SX + col * (PW + GX);
      item.canvasData.y = SY + row * (PH + GY);
      count++;
    } else {
      missing.push(item.id);
    }
  }
});

json.config.autoLayout = false;

console.log('Applied:', count, 'missing:', missing.length);
if (missing.length) console.log('Missing:', missing.join(', '));

fs.writeFileSync(f, JSON.stringify(json, null, 2));
console.log('Saved. autoLayout = false');

// Verify
const v = JSON.parse(fs.readFileSync(f, 'utf-8'));
const rows = {};
v.data.filter(i=>i.type==='page').forEach(p => {
  const r = Math.round((p.canvasData.y - SY) / (PH + GY));
  if (!rows[r]) rows[r] = 0;
  rows[r]++;
});
console.log('\nRow distribution:');
Object.keys(rows).sort((a,b)=>a-b).forEach(r => {
  console.log(`  Row ${r}: ${rows[r]} pages`);
});
