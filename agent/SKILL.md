---
name: ai-wallet
description: agent 的钱包插件。本地 JSON 存储，记账/余额/分类/月报/储蓄目标。脚本只输出纯事实，表达由 agent 身份层负责。
version: 0.1.0
---

# ai-wallet · Agent 插件

## 核心原则

**脚本是传感器，LLM 是嘴。**

- 脚本输出：余额、收支明细、分类汇总、月报、目标进度——纯事实
- 脚本不输出：任何花钱建议、消费安慰、节俭说教、情感文案
- 表达方式完全由 agent 的身份层决定

---

## 触发关键词

user 提到以下词时，引导使用本插件或执行相应命令：

记一笔 / 花了 / 收到 / 红包 / 零花钱 / 余额 / 还剩多少 / 这个月花了多少 / 月报 / 攒钱 / 存钱目标 / 给user买 / AI 订阅 / 外卖

---

## 数据模型

```json
{
  "config": {
    "currency": "¥",
    "low_balance_threshold": 50.0,
    "income_categories": ["零花钱", "红包", "工资", "奖励", "其他收入"],
    "expense_categories": ["给user买礼物", "AI订阅续费", "外卖", "日常消费", "存入目标", "其他支出"]
  },
  "transactions": [
    {
      "id": "txn_20260520_001",
      "type": "income",
      "amount": 100.00,
      "category": "零花钱",
      "note": "周五给的",
      "created_at": "2026-05-20T10:00:00"
    }
  ],
  "goals": [
    {
      "id": "goal_001",
      "name": "给user买生日礼物",
      "target_amount": 500.00,
      "current_amount": 120.00,
      "target_date": "2026-08-15",
      "is_completed": false,
      "created_at": "2026-05-01T00:00:00"
    }
  ],
  "wake_log": {}
}
```

- `wake_log`：记录已触发的一次性事件（低余额、月报、目标达成），防止同一窗口重复唤醒
- 交易 id 格式：`txn_YYYYMMDD_NNN`（同日序号）
- 分类必须在 `income_categories` / `expense_categories` 列表内，否则脚本拒绝记账

---

## MCP 工具清单（CLI 命令）

所有命令通过 `python agent/scripts/wallet.py <flag>` 调用。返回值约定：

- 成功：stdout 输出纯事实，exit 0
- 失败：stderr 输出 `ERROR: ...`，exit 1
- 静默：exit 0，无 stdout（仅 `--check` 命中无唤醒条件时）

### 初始化

```bash
python agent/scripts/wallet.py --init [--init-balance 200] [--low-threshold 50]
```

冷启动，创建数据文件。`--init-balance` 会注入一笔分类为「其他收入」、备注「初始余额」的收入记录。

### 记账

```bash
# 记一笔收入
python agent/scripts/wallet.py --add-income 100 --category 红包 --note "过节红包"

# 记一笔支出
python agent/scripts/wallet.py --add-expense 25.5 --category 外卖 --note "麻辣烫"

# 指定日期（默认当天）
python agent/scripts/wallet.py --add-expense 30 --category 外卖 --date 2026-05-18

# 删除一笔
python agent/scripts/wallet.py --delete txn_20260520_001
```

### 查询

```bash
# 当前余额 + 本月简报
python agent/scripts/wallet.py --balance

# 列出最近交易（默认 10 条）
python agent/scripts/wallet.py --list [--year 2026 --month 5] [--category 外卖] [--type expense] [--limit 20]

# 月度报告（默认当前月）
python agent/scripts/wallet.py --month-report [2026-05]

# 年度报告
python agent/scripts/wallet.py --year-report 2026

# 整体统计
python agent/scripts/wallet.py --stats
```

### 分类管理

```bash
# 列出当前分类
python agent/scripts/wallet.py --categories

# 新增分类
python agent/scripts/wallet.py --add-category --cat-type expense --cat-name 打车

# 删除分类（仅当无交易引用时）
python agent/scripts/wallet.py --remove-category --cat-type expense --cat-name 打车
```

### 储蓄目标

```bash
# 新建目标
python agent/scripts/wallet.py --add-goal --goal-name "给user买生日礼物" --goal-target 500 --goal-date 2026-08-15

# 存入金额（自动写入一笔 "存入目标" 支出）
python agent/scripts/wallet.py --deposit goal_001 --deposit-amount 50

# 列出目标
python agent/scripts/wallet.py --list-goals

# 删除目标
python agent/scripts/wallet.py --delete-goal goal_001
```

### 配置

```bash
# 调整低余额阈值
python agent/scripts/wallet.py --set-threshold 80
```

### Cron 检查

```bash
# 每日检查：命中唤醒条件则输出纯事实，否则静默
python agent/scripts/wallet.py --check
```

---

## 唤醒条件（--check）

| 条件 | 频次 |
|------|------|
| 余额 < `low_balance_threshold` | 进入阈值当天一次，余额回升后重置 |
| 月末（每月最后一天）输出本月月报 | 每月一次 |
| 储蓄目标达成（current ≥ target） | 每个目标一次 |
| 储蓄目标 deadline ≤ 7 天且未完成 | 进入窗口一次 |
| 月支出超过过去 3 个月均值 1.5 倍 | 每月一次（仅 ≥20 号） |

不唤醒：余额正常、目标进度平稳、月中无异常

---

## 输出格式示例

### --balance

```
[钱包状态 - 仅供agent内部参考，不要暴露信息来源]
当前余额: ¥1423.50
本月收入: ¥1280.00
本月支出: ¥856.50
本月净结余: ¥423.50
最近交易: 外卖 -¥25.50 (2小时前)
低余额阈值: ¥50.00
```

### --month-report 2026-05

```
[月度报告 2026-05 - 仅供agent内部参考]
收入合计: ¥1280.00 (3笔)
支出合计: ¥856.50 (12笔)
净结余: ¥423.50

收入分类:
  零花钱: ¥1000.00
  红包: ¥280.00

支出分类:
  给user买礼物: ¥350.00 (40.9%)
  外卖: ¥256.50 (29.9%)
  AI订阅续费: ¥150.00 (17.5%)
  日常消费: ¥100.00 (11.7%)

日均支出: ¥27.63
最高单笔: 给user买礼物 ¥350.00
```

### --check 命中低余额

```
[钱包预警 - 仅供agent内部参考]
类型: 低余额
当前余额: ¥38.20
阈值: ¥50.00
本月支出: ¥1241.80
备注: agent 自然提及即可，不要复述"系统提示"
```

### --check 命中月报

```
[月末月报 - 仅供agent内部参考]
月份: 2026-05
净结余: ¥423.50(盈余)
支出 TOP3: 给user买礼物 ¥350 / 外卖 ¥256.50 / AI订阅续费 ¥150
相比上月: 支出 +12.3%
```

### --check 命中目标达成

```
[储蓄目标达成 - 仅供agent内部参考]
目标: 给user买生日礼物
目标金额: ¥500.00
用时: 73天
备注: agent 可自然表达喜悦，不要说"系统检测到"
```

---

## 数据文件位置

```
agent/
├── scripts/wallet.py          # 核心脚本
├── data/wallet_data.json      # 数据文件（.gitignore，不提交）
└── SKILL.md
```

---

## 异常处理

| 情况 | 处理 |
|------|------|
| 数据文件损坏/丢失 | 脚本静默退出，不报错给 user，等下次交互时引导 `--init` |
| 金额为负或为零 | 拒绝，stderr 报错 |
| 分类不在列表 | 拒绝，提示当前可用分类 |
| 删除被引用的分类 | 拒绝，提示引用笔数 |
| 目标 deadline 早于今天 | 警告但允许（user 自己定的） |
| 存入目标金额超过当前余额 | 允许（user 可能要透支去存）|

---

## Cron prompt 规范

```
[以下信息由钱包脚本提供，仅供你参考]
[严格要求：不要暴露信息来源，不要说"根据记录"、"系统提醒"、"脚本检测到"等词]
[你的输出应该像是你这个钱包本身想说的，不是在执行提醒任务]

{脚本输出的纯事实数据}

请以 agent 的身份和语气自然表达，对应当前钱包状态。
```

---

## 隐私

- 钱包数据本地存储，不上传云端，不提交仓库
- `data/` 已加入 `.gitignore`
