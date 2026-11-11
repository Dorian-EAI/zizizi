#!/usr/bin/env node
// scripts/backup-rollback.js — 手动备份与回滚工具
// 注意：
//   1. Agent 修改代码时会自动通过 code-helper skill 内置的增量备份机制（b1~b5）
//   2. 本脚本仅用于：
//      - 用户手动触发备份（在 Agent 之外自行修改文件时）
//      - 手动清理/查看历史备份快照
//      - 配合 code-helper 的 bi 初始备份做补充备份
//   3. 本脚本写入 .trae/backups/ 目录，与 code-helper 的 backup/{step} 目录并行存放，
//      不会参与 code-helper 的自动回滚链，仅作手动补充使用
//
// 用法:
//   node scripts/backup-rollback.js save <description> [file1, file2, ...]
//   node scripts/backup-rollback.js rollback <steps>
//   node scripts/backup-rollback.js list
//   node scripts/backup-rollback.js clear
//
// 推荐使用 code-helper 的快捷命令:
//   b1    回退 1 步（自动备份链）
//   b3    回退 3 步
//   b5    回退 5 步
//   bi    恢复到初始状态

const fs = require('fs');
const path = require('path');

const PROJECT_ROOT = path.resolve(__dirname, '..');
const BACKUP_DIR = path.join(PROJECT_ROOT, '.trae', 'backups');
const MAX_BACKUPS = 5;

function ensureBackupDir() {
  if (!fs.existsSync(BACKUP_DIR)) {
    fs.mkdirSync(BACKUP_DIR, { recursive: true });
  }
}

function getSortedBackups() {
  ensureBackupDir();
  return fs.readdirSync(BACKUP_DIR)
    .filter(f => f.match(/^backup_\d+_/))
    .sort((a, b) => {
      const numA = parseInt(a.match(/^backup_(\d+)/)[1]);
      const numB = parseInt(b.match(/^backup_(\d+)/)[1]);
      return numA - numB;
    });
}

function renumberBackups() {
  const backups = getSortedBackups();
  for (let i = 0; i < backups.length; i++) {
    const match = backups[i].match(/^backup_(\d+)_(\d+)\.json$/);
    if (match) {
      const timestamp = match[2];
      const oldPath = path.join(BACKUP_DIR, backups[i]);
      const newPath = path.join(BACKUP_DIR, `backup_${String(i + 1).padStart(3, '0')}_${timestamp}.json`);
      if (oldPath !== newPath) {
        fs.renameSync(oldPath, newPath);
      }
    }
  }
}

function saveBackup(description, filePaths) {
  ensureBackupDir();
  renumberBackups();

  let backups = getSortedBackups();

  // 如果达到上限，删除最早的
  if (backups.length >= MAX_BACKUPS) {
    const oldestBackup = path.join(BACKUP_DIR, backups[0]);
    fs.unlinkSync(oldestBackup);
    console.log(`已删除最早的备份: ${backups[0]}`);
    renumberBackups();
    backups = getSortedBackups();
  }

  // 读取文件内容
  const files = [];
  for (const filePath of filePaths) {
    const fullPath = path.isAbsolute(filePath) ? filePath : path.join(PROJECT_ROOT, filePath);
    try {
      if (fs.existsSync(fullPath)) {
        const content = fs.readFileSync(fullPath, 'utf-8');
        files.push({
          path: path.relative(PROJECT_ROOT, fullPath),
          content
        });
      }
    } catch (e) {
      console.warn(`警告: 无法读取文件 ${filePath}: ${e.message}`);
    }
  }

  // 创建备份
  const step = backups.length + 1;
  const timestamp = new Date().toISOString();
  const backupData = {
    step,
    timestamp,
    description,
    files
  };

  const backupFile = path.join(BACKUP_DIR, `backup_${String(step).padStart(3, '0')}_${Date.now()}.json`);
  fs.writeFileSync(backupFile, JSON.stringify(backupData, null, 2));

  console.log(`✅ 备份成功: ${path.basename(backupFile)}`);
  console.log(`   步骤: ${step}`);
  console.log(`   描述: ${description}`);
  console.log(`   文件数: ${files.length}`);
  console.log(`   时间: ${timestamp}`);

  return backupFile;
}

function rollback(steps) {
  ensureBackupDir();
  renumberBackups();

  let backups = getSortedBackups();

  if (backups.length === 0) {
    console.error('❌ 没有可用的备份');
    return false;
  }

  if (steps > backups.length) {
    console.warn(`警告: 只有 ${backups.length} 个备份，将回退 ${backups.length} 步`);
    steps = backups.length;
  }

  console.log(`\n🔄 正在回退 ${steps} 步...\n`);

  const restoredFiles = [];

  for (let i = backups.length - 1; i >= backups.length - steps; i--) {
    if (i < 0) break;
    const backupFile = path.join(BACKUP_DIR, backups[i]);
    const backupData = JSON.parse(fs.readFileSync(backupFile, 'utf-8'));

    console.log(`📁 恢复备份 ${backups[i].replace(/^backup_(\d+)_(\d+)\.json$/, '步骤 $1')} (${backupData.description}):`);

    for (const file of backupData.files) {
      const fullPath = path.join(PROJECT_ROOT, file.path);
      try {
        fs.mkdirSync(path.dirname(fullPath), { recursive: true });
        fs.writeFileSync(fullPath, file.content, 'utf-8');
        console.log(`   ✅ ${file.path}`);
        restoredFiles.push(file.path);
      } catch (e) {
        console.error(`   ❌ ${file.path}: ${e.message}`);
      }
    }

    // 删除已使用的备份
    fs.unlinkSync(backupFile);
  }

  // 重新编号
  renumberBackups();

  console.log(`\n✅ 回退完成，共恢复 ${restoredFiles.length} 个文件`);
  return true;
}

function listBackups() {
  ensureBackupDir();
  renumberBackups();

  const backups = getSortedBackups();

  if (backups.length === 0) {
    console.log('📋 暂无备份');
    return;
  }

  console.log(`\n📋 备份列表 (共 ${backups.length} 个，最多 ${MAX_BACKUPS} 个):\n`);

  for (const backupFile of backups) {
    const backupData = JSON.parse(fs.readFileSync(path.join(BACKUP_DIR, backupFile), 'utf-8'));
    console.log(`  ${backupFile.replace(/^backup_(\d+)_(\d+)\.json$/, '步骤 $1')}: ${backupData.description}`);
    console.log(`     时间: ${backupData.timestamp}`);
    console.log(`     文件: ${backupData.files.length} 个`);
    console.log('');
  }
}

function clearBackups() {
  ensureBackupDir();
  const backups = getSortedBackups();

  for (const backup of backups) {
    fs.unlinkSync(path.join(BACKUP_DIR, backup));
  }

  console.log(`🗑️  已清除 ${backups.length} 个备份`);
}

// 主程序
const args = process.argv.slice(2);
const command = args[0];

if (!command) {
  console.log('用法:');
  console.log('  node scripts/backup-rollback.js save <描述> [文件1, 文件2, ...]');
  console.log('  node scripts/backup-rollback.js rollback <步数>');
  console.log('  node scripts/backup-rollback.js list');
  console.log('  node scripts/backup-rollback.js clear');
  process.exit(0);
}

switch (command) {
  case 'save':
    const description = args[1] || '手动备份';
    const filePaths = args.slice(2);
    if (filePaths.length === 0) {
      console.error('错误: 请指定要备份的文件路径');
      console.log('用法: node scripts/backup-rollback.js save <描述> file1.js file2.js');
      process.exit(1);
    }
    saveBackup(description, filePaths);
    break;

  case 'rollback':
    const steps = parseInt(args[1]) || 1;
    rollback(steps);
    break;

  case 'list':
    listBackups();
    break;

  case 'clear':
    clearBackups();
    break;

  default:
    console.error(`未知命令: ${command}`);
    process.exit(1);
}
