param(
    [string]$DesignFile = "c:\Users\12620\Desktop\zi\zjrnew\zjrnew.design",
    [string]$BackupFile = "c:\Users\12620\Desktop\zi\zjrnew\zjrnew.design.bak"
)

Copy-Item $DesignFile $BackupFile -Force
Write-Host "Backup saved: $BackupFile"

$content = Get-Content $DesignFile -Raw | ConvertFrom-Json

$pageW = 375
$pageH = 812
$gapX = 80
$gapY = 120
$startX = 100
$startY = 100

$layout = @{}

# Row 0: 5 primary pages
$row0 = @("page-client-home-glass-neu","page-client-orders","page-client-publish","page-client-service","page-client-mine")
for ($i=0;$i -lt $row0.Count;$i++) { $layout[$row0[$i]] = @(0,$i) }

# Row 1: secondary pages
$col = 5
$r1home = @("page-client-service-detail","page-client-search","page-client-member","page-client-chat","page-client-quote-list","page-client-worker-detail")
for ($i=0;$i -lt $r1home.Count;$i++) { $layout[$r1home[$i]] = @(1,$col+$i) }
$col += $r1home.Count + 1

$r1orders = @("page-client-order-detail","page-client-order-search","page-client-order-picker")
for ($i=0;$i -lt $r1orders.Count;$i++) { $layout[$r1orders[$i]] = @(1,$col+$i) }
$col += $r1orders.Count + 1

$r1pub = @("page-client-address","page-client-coupon-select")
for ($i=0;$i -lt $r1pub.Count;$i++) { $layout[$r1pub[$i]] = @(1,$col+$i) }
$col += $r1pub.Count + 1

$r1svc = @("page-client-customer-service","page-client-ticket-submit","page-client-help")
for ($i=0;$i -lt $r1svc.Count;$i++) { $layout[$r1svc[$i]] = @(1,$col+$i) }
$col += $r1svc.Count + 1

$r1mine = @("page-client-profile","page-client-wallet","page-client-coupon","page-client-annual-card","page-client-points","page-client-invite","page-client-favorite-workers","page-client-feedback","page-client-insurance-claim","page-client-settings","page-client-history","page-client-notification")
for ($i=0;$i -lt $r1mine.Count;$i++) { $layout[$r1mine[$i]] = @(1,$col+$i) }
$col += $r1mine.Count + 1

# Row 2: tertiary pages
$col2 = 0
$r2od = @("page-client-order-tracking","page-client-order-tracking-2","page-client-payment","page-client-review","page-client-order-cancel","page-client-refund","page-client-report","page-client-price-adjust","page-client-order-chat","page-client-review-list")
for ($i=0;$i -lt $r2od.Count;$i++) { $layout[$r2od[$i]] = @(2,$col2+$i) }
$col2 += $r2od.Count + 1

$r2addr = @("page-client-address-edit","page-client-map-picker")
for ($i=0;$i -lt $r2addr.Count;$i++) { $layout[$r2addr[$i]] = @(2,$col2+$i) }
$col2 += $r2addr.Count + 1

$r2wal = @("page-client-balance-transactions","page-client-recharge-record","page-client-withdraw-record","page-client-wallet-recharge","page-client-wallet-withdraw","page-client-bank-cards","page-client-income-stat","page-client-invoice")
for ($i=0;$i -lt $r2wal.Count;$i++) { $layout[$r2wal[$i]] = @(2,$col2+$i) }
$col2 += $r2wal.Count + 1

$r2coup = @("page-client-coupon-detail")
for ($i=0;$i -lt $r2coup.Count;$i++) { $layout[$r2coup[$i]] = @(2,$col2+$i) }
$col2 += $r2coup.Count + 1

$r2annual = @("page-client-annual-card-record","page-client-refund-card")
for ($i=0;$i -lt $r2annual.Count;$i++) { $layout[$r2annual[$i]] = @(2,$col2+$i) }
$col2 += $r2annual.Count + 1

$r2pts = @("page-client-points-detail","page-client-points-mall","page-client-points-tasks","page-client-points-product")
for ($i=0;$i -lt $r2pts.Count;$i++) { $layout[$r2pts[$i]] = @(2,$col2+$i) }
$col2 += $r2pts.Count + 1

$r2inv = @("page-client-invite-record","page-client-friend-detail")
for ($i=0;$i -lt $r2inv.Count;$i++) { $layout[$r2inv[$i]] = @(2,$col2+$i) }
$col2 += $r2inv.Count + 1

$r2ins = @("page-client-policy-detail","page-client-claim-result")
for ($i=0;$i -lt $r2ins.Count;$i++) { $layout[$r2ins[$i]] = @(2,$col2+$i) }
$col2 += $r2ins.Count + 1

$r2set = @("page-client-profile-edit","page-client-account-security","page-client-privacy","page-client-about","page-client-auth","page-client-login")
for ($i=0;$i -lt $r2set.Count;$i++) { $layout[$r2set[$i]] = @(2,$col2+$i) }
$col2 += $r2set.Count + 1

$r2notif = @("page-client-message-detail")
for ($i=0;$i -lt $r2notif.Count;$i++) { $layout[$r2notif[$i]] = @(2,$col2+$i) }
$col2 += $r2notif.Count + 1

# Row 3: 4th level pages
$col3 = 0
$r3pay = @("page-client-payment-result","page-client-exchange-result")
for ($i=0;$i -lt $r3pay.Count;$i++) { $layout[$r3pay[$i]] = @(3,$col3+$i) }
$col3 += $r3pay.Count + 1

$r3tx = @("page-client-transaction-detail")
for ($i=0;$i -lt $r3tx.Count;$i++) { $layout[$r3tx[$i]] = @(3,$col3+$i) }
$col3 += $r3tx.Count + 1

$r3bc = @("page-client-bank-card-add")
for ($i=0;$i -lt $r3bc.Count;$i++) { $layout[$r3bc[$i]] = @(3,$col3+$i) }
$col3 += $r3bc.Count + 1

$r3inv2 = @("page-client-invoice-orders","page-client-invoice-title-edit","page-client-invoice-detail")
for ($i=0;$i -lt $r3inv2.Count;$i++) { $layout[$r3inv2[$i]] = @(3,$col3+$i) }
$col3 += $r3inv2.Count + 1

$r3acc = @("page-client-password","page-client-bind-phone","page-client-verification","page-client-device-management","page-client-account-cancel","page-client-verification-result")
for ($i=0;$i -lt $r3acc.Count;$i++) { $layout[$r3acc[$i]] = @(3,$col3+$i) }
$col3 += $r3acc.Count + 1

$r3priv = @("page-client-visibility")
for ($i=0;$i -lt $r3priv.Count;$i++) { $layout[$r3priv[$i]] = @(3,$col3+$i) }
$col3 += $r3priv.Count + 1

$r3about = @("page-client-agreement")
for ($i=0;$i -lt $r3about.Count;$i++) { $layout[$r3about[$i]] = @(3,$col3+$i) }
$col3 += $r3about.Count + 1

$r3rc = @("page-client-refund-card-result")
for ($i=0;$i -lt $r3rc.Count;$i++) { $layout[$r3rc[$i]] = @(3,$col3+$i) }
$col3 += $r3rc.Count + 1

$r3tk = @("page-client-ticket-detail","page-client-feedback-detail")
for ($i=0;$i -lt $r3tk.Count;$i++) { $layout[$r3tk[$i]] = @(3,$col3+$i) }
$col3 += $r3tk.Count + 1

$r3rv = @("page-client-review-detail")
for ($i=0;$i -lt $r3rv.Count;$i++) { $layout[$r3rv[$i]] = @(3,$col3+$i) }
$col3 += $r3rv.Count + 1

$r3vid = @("page-client-video")
for ($i=0;$i -lt $r3vid.Count;$i++) { $layout[$r3vid[$i]] = @(3,$col3+$i) }
$col3 += $r3vid.Count + 1

# Worker side - starts at row 5
$wr = 5
$wc = 0

$wrow0 = @("page-worker-home","page-worker-orders","page-worker-wallet","page-worker-training","page-worker-profile")
for ($i=0;$i -lt $wrow0.Count;$i++) { $layout[$wrow0[$i]] = @($wr,$wc+$i) }

# Worker row 1
$w1col = 0
$w1orders = @("page-worker-order-detail")
for ($i=0;$i -lt $w1orders.Count;$i++) { $layout[$w1orders[$i]] = @($wr+1,$w1col+$i) }
$w1col += $w1orders.Count + 1

$w1wallet = @("page-worker-withdraw","page-worker-transactions","page-worker-income-stat","page-worker-recharge")
for ($i=0;$i -lt $w1wallet.Count;$i++) { $layout[$w1wallet[$i]] = @($wr+1,$w1col+$i) }
$w1col += $w1wallet.Count + 1

$w1train = @("page-worker-training-exam","page-worker-training-detail")
for ($i=0;$i -lt $w1train.Count;$i++) { $layout[$w1train[$i]] = @($wr+1,$w1col+$i) }
$w1col += $w1train.Count + 1

$w1profile = @("page-worker-service-scope","page-worker-experience","page-worker-cert-manage","page-worker-service-area","page-worker-certification","page-worker-deposit","page-worker-reviews","page-worker-help","page-worker-settings","page-worker-location-report","page-worker-appeal")
for ($i=0;$i -lt $w1profile.Count;$i++) { $layout[$w1profile[$i]] = @($wr+1,$w1col+$i) }
$w1col += $w1profile.Count + 1

# Worker row 2
$w2col = 0
$w2exp = @("page-worker-experience-item-edit")
for ($i=0;$i -lt $w2exp.Count;$i++) { $layout[$w2exp[$i]] = @($wr+2,$w2col+$i) }
$w2col += $w2exp.Count + 1

$w2cert = @("page-worker-certificate-edit")
for ($i=0;$i -lt $w2cert.Count;$i++) { $layout[$w2cert[$i]] = @($wr+2,$w2col+$i) }
$w2col += $w2cert.Count + 1

$w2dep = @("page-worker-deposit-refund","page-worker-deposit-pay")
for ($i=0;$i -lt $w2dep.Count;$i++) { $layout[$w2dep[$i]] = @($wr+2,$w2col+$i) }
$w2col += $w2dep.Count + 1

$w2help = @("page-worker-help-category")
for ($i=0;$i -lt $w2help.Count;$i++) { $layout[$w2help[$i]] = @($wr+2,$w2col+$i) }
$w2col += $w2help.Count + 1

$w2set = @("page-worker-order-setting","page-worker-time-setting")
for ($i=0;$i -lt $w2set.Count;$i++) { $layout[$w2set[$i]] = @($wr+2,$w2col+$i) }
$w2col += $w2set.Count + 1

$w2appeal = @("page-worker-appeal-detail")
for ($i=0;$i -lt $w2appeal.Count;$i++) { $layout[$w2appeal[$i]] = @($wr+2,$w2col+$i) }
$w2col += $w2appeal.Count + 1

$w2wd = @("page-worker-withdraw-result")
for ($i=0;$i -lt $w2wd.Count;$i++) { $layout[$w2wd[$i]] = @($wr+2,$w2col+$i) }
$w2col += $w2wd.Count + 1

$w2inc = @("page-worker-income-category-detail")
for ($i=0;$i -lt $w2inc.Count;$i++) { $layout[$w2inc[$i]] = @($wr+2,$w2col+$i) }
$w2col += $w2inc.Count + 1

$w2od = @("page-worker-quote-submit","page-worker-chat","page-worker-customer-profile","page-worker-price-adjust-worker")
for ($i=0;$i -lt $w2od.Count;$i++) { $layout[$w2od[$i]] = @($wr+2,$w2col+$i) }
$w2col += $w2od.Count + 1

# Worker row 3
$layout["page-worker-exam-result"] = @($wr+3,0)
$layout["page-worker-lesson"] = @($wr+3,2)

# Contrast page
$layout["page-client-home-glass-neu-contrast-1"] = @(4,0)

# Stats
$mapped = 0
$unmapped = @()
foreach ($item in $content.data) {
    if ($item.type -eq "page") {
        if ($layout.ContainsKey($item.id)) { $mapped++ } else { $unmapped += $item.id }
    }
}
Write-Host "Total pages: $($content.data.Count)"
Write-Host "Mapped: $mapped"
Write-Host "Unmapped: $($unmapped.Count)"
if ($unmapped.Count -gt 0) { $unmapped | ForEach-Object { Write-Host "  $_" } }

# Apply
$count = 0
foreach ($item in $content.data) {
    if ($item.type -eq "page" -and $layout.ContainsKey($item.id)) {
        $row = $layout[$item.id][0]
        $colIdx = $layout[$item.id][1]
        $item.canvasData.x = $startX + $colIdx * ($pageW + $gapX)
        $item.canvasData.y = $startY + $row * ($pageH + $gapY)
        $count++
    }
}

$content | ConvertTo-Json -Depth 20 | Set-Content $DesignFile -Encoding UTF8
Write-Host "Updated $count pages. Saved to $DesignFile"
