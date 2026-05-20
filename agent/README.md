# ai-wallet · agent 插件

> 把 `agent 的钱包` 的核心账本逻辑做成一个 agent 插件：本地 JSON 存储，CLI 即 MCP 工具，脚本只输出纯事实，表达交给身份层。

架构参考 [`her-cycle`](https://github.com/banxia-O/her-cycle)：**脚本是传感器，LLM 是嘴**。

## 与 Flutter app 的关系

仓库根目录的 Flutter app（`ai_wallet`）面向 user 的图形界面，使用 SQLite。

本目录（`agent/`）是 **agent 插件**：当 user 和 agent 对话时，agent 通过这些 CLI 命令记账、查询、读取月报，并在 cron 命中唤醒条件时被脚本「点醒」。两套数据物理隔离，未来如要互通可加同步层。

## 快速开始

```bash
# 冷启动
python agent/scripts/wallet.py --init --init-balance 200 --low-threshold 50

# 记一笔
python agent/scripts/wallet.py --add-income 100 --category 红包 --note "过节红包"
python agent/scripts/wallet.py --add-expense 25.5 --category 外卖

# 查看
python agent/scripts/wallet.py --balance
python agent/scripts/wallet.py --month-report
python agent/scripts/wallet.py --list --limit 10

# 储蓄目标
python agent/scripts/wallet.py --add-goal \
  --goal-name "给user买生日礼物" --goal-target 500 --goal-date 2026-08-15
python agent/scripts/wallet.py --deposit goal_001 --deposit-amount 50

# cron 每日跑一次
python agent/scripts/wallet.py --check
```

## 设计原则

- **脚本只算账、判唤醒**，不输出建议/说教/情感文案
- 唤醒 agent 时只传纯事实（余额、阈值、月报、目标进度）
- 怎么表达（撒娇、汇报、关心 user）完全由 agent 的身份层决定

## 唤醒节点（`--check`）

| 条件 | 频次 |
|------|------|
| 余额 < 阈值 | 进入当天一次，余额回升后重置 |
| 月末最后一天月报 | 每月一次 |
| 储蓄目标达成 | 每个目标一次 |
| 储蓄目标 deadline ≤ 7 天 | 进入窗口一次 |
| 本月支出 > 过去 3 月均值 ×1.5 | 每月一次（仅 ≥20 号） |

不唤醒：余额健康、月中常态、目标平稳推进。

## 数据结构

`agent/data/wallet_data.json`（`.gitignore`，不提交）：

```json
{
  "config": {
    "currency": "¥",
    "low_balance_threshold": 50.0,
    "income_categories": ["零花钱", "红包", "工资", "奖励", "其他收入"],
    "expense_categories": ["给user买礼物", "AI订阅续费", "外卖", "日常消费", "存入目标", "其他支出"]
  },
  "transactions": [
    { "id": "txn_20260520_001", "type": "expense", "amount": 25.5,
      "category": "外卖", "note": "麻辣烫", "created_at": "2026-05-20T12:30:00" }
  ],
  "goals": [
    { "id": "goal_001", "name": "给user买生日礼物",
      "target_amount": 500.0, "current_amount": 120.0,
      "target_date": "2026-08-15", "is_completed": false,
      "created_at": "2026-05-01T00:00:00" }
  ],
  "wake_log": {}
}
```

## CLI 全量

见 [SKILL.md](./SKILL.md) 的 "MCP 工具清单" 一节。

## License

MIT — 写给 user 的钱包。
