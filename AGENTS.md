# AGENTS.md

本文件面向 AI agent，说明 `ai-wallet` 插件的用途与接入方式。

## 这是什么

`ai-wallet` 是一个 agent 侧的钱包插件，帮助 agent 为 user 管理日常账单。

架构原则：**脚本是传感器，agent 是嘴**。

- `agent/scripts/wallet.py` 只输出纯事实（余额、收支、月报、目标进度）
- 如何用这些数据说话，完全由 agent 的身份层决定

## 适用场景

当 user 和 agent 对话，提到以下话题时，agent 使用本插件：

- 记账：花了 / 收到 / 红包 / 零花钱
- 查询：余额 / 还剩多少 / 这个月花了多少 / 月报
- 储蓄：攒钱 / 存钱目标

## 安装

```bash
# 1. 进入仓库根目录
# 2. 初始化钱包（仅首次）
python agent/scripts/wallet.py --init --init-balance 200 --low-threshold 50
```

数据存储在 `agent/data/wallet_data.json`（已加入 `.gitignore`，不提交仓库）。

## 常用命令

```bash
# 记收入
python agent/scripts/wallet.py --add-income 100 --category 红包 --note "过节红包"

# 记支出
python agent/scripts/wallet.py --add-expense 25.5 --category 外卖

# 查余额
python agent/scripts/wallet.py --balance

# 月报
python agent/scripts/wallet.py --month-report

# 设置储蓄目标（把下面的名称替换成实际内容）
python agent/scripts/wallet.py --add-goal \
  --goal-name "给user买生日礼物" --goal-target 500 --goal-date 2026-08-15

# 每日 cron 检查（有唤醒条件则输出，否则静默）
python agent/scripts/wallet.py --check
```

完整命令列表见 [`agent/SKILL.md`](agent/SKILL.md)。

## 个性化

接入时，把以下占位符替换成实际名字：

| 占位符 | 说明 | 示例 |
|--------|------|------|
| `agent` | agent 自己的名字/身份 | 小艾、Aria |
| `user` | 对话 user 的名字 | 小明、Tom |

替换位置：

- `agent/SKILL.md`：触发关键词、Cron prompt 规范
- `agent/README.md`：设计说明、数据结构示例
- 默认支出分类 `给user买礼物`：可用 `--add-category` / `--remove-category` 调整

## 唤醒节点

`--check` 命中以下条件时，脚本输出纯事实，agent 自然表达：

| 条件 | 频次 |
|------|------|
| 余额 < 阈值 | 当天一次，余额回升后重置 |
| 月末最后一天 | 每月一次 |
| 储蓄目标达成 | 每个目标一次 |
| 目标 deadline ≤ 7 天 | 进入窗口一次 |
| 本月支出 > 近 3 月均值 ×1.5（≥20 号） | 每月一次 |

## 隐私

钱包数据本地存储，不上传云端，不提交仓库（`data/` 在 `.gitignore`）。
