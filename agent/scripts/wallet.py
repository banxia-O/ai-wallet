#!/usr/bin/env python3
"""agent 的钱包 v0.1 — sensor only. 纯事实输出，不带情感文案。"""

import argparse
import json
import os
import sys
from datetime import date, datetime, timedelta

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PLUGIN_ROOT = os.path.dirname(_SCRIPT_DIR)
DATA_DIR = os.path.join(_PLUGIN_ROOT, "data")
DATA_FILE = os.path.join(DATA_DIR, "wallet_data.json")

DEFAULT_INCOME_CATEGORIES = ["零花钱", "红包", "工资", "奖励", "其他收入"]
DEFAULT_EXPENSE_CATEGORIES = [
    "给user买礼物", "AI订阅续费", "外卖", "日常消费", "存入目标", "其他支出"
]
CURRENCY = "¥"


# ── I/O ────────────────────────────────────────────────────────────────────────

def load_data():
    if not os.path.exists(DATA_FILE):
        return None
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return None


def save_data(data):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def require_data():
    data = load_data()
    if data is None:
        sys.exit("ERROR: 钱包未初始化，请先运行 --init")
    return data


# ── Helpers ────────────────────────────────────────────────────────────────────

def fmt(amount):
    return f"{CURRENCY}{amount:.2f}"


def parse_date(s):
    try:
        return date.fromisoformat(s)
    except ValueError:
        sys.exit(f"ERROR: 日期格式应为 YYYY-MM-DD，收到 {s!r}")


def next_txn_id(data, when):
    prefix = f"txn_{when.strftime('%Y%m%d')}_"
    existing = [t["id"] for t in data["transactions"] if t["id"].startswith(prefix)]
    return f"{prefix}{len(existing) + 1:03d}"


def next_goal_id(data):
    n = len(data.get("goals", [])) + 1
    while any(g["id"] == f"goal_{n:03d}" for g in data.get("goals", [])):
        n += 1
    return f"goal_{n:03d}"


def month_bounds(year, month):
    start = date(year, month, 1)
    end = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
    return start, end


def in_range(txn, start, end):
    d = datetime.fromisoformat(txn["created_at"]).date()
    return start <= d < end


def balance(data):
    income = sum(t["amount"] for t in data["transactions"] if t["type"] == "income")
    expense = sum(t["amount"] for t in data["transactions"] if t["type"] == "expense")
    return income - expense


def month_summary(data, year, month):
    start, end = month_bounds(year, month)
    inc = exp = 0.0
    inc_n = exp_n = 0
    by_cat = {"income": {}, "expense": {}}
    largest = None
    for t in data["transactions"]:
        if not in_range(t, start, end):
            continue
        amt = t["amount"]
        cat = t["category"]
        if t["type"] == "income":
            inc += amt
            inc_n += 1
            by_cat["income"][cat] = by_cat["income"].get(cat, 0) + amt
        else:
            exp += amt
            exp_n += 1
            by_cat["expense"][cat] = by_cat["expense"].get(cat, 0) + amt
            if largest is None or amt > largest["amount"]:
                largest = t
    return {
        "year": year, "month": month,
        "income": inc, "expense": exp, "net": inc - exp,
        "income_count": inc_n, "expense_count": exp_n,
        "by_category": by_cat,
        "largest_expense": largest,
        "days": (end - start).days,
    }


def recent_relative_time(txn):
    """Returns Chinese relative time string for a transaction."""
    dt = datetime.fromisoformat(txn["created_at"])
    delta = datetime.now() - dt
    sec = int(delta.total_seconds())
    if sec < 60:
        return "刚刚"
    if sec < 3600:
        return f"{sec // 60}分钟前"
    if sec < 86400:
        return f"{sec // 3600}小时前"
    days = sec // 86400
    if days < 7:
        return f"{days}天前"
    return dt.strftime("%Y-%m-%d")


# ── Commands ───────────────────────────────────────────────────────────────────

def cmd_init(args):
    if os.path.exists(DATA_FILE):
        sys.exit("ERROR: 数据文件已存在，请勿重复 --init（如需重置请手动删除 data/wallet_data.json）")

    data = {
        "config": {
            "currency": CURRENCY,
            "low_balance_threshold": float(args.low_threshold) if args.low_threshold else 50.0,
            "income_categories": list(DEFAULT_INCOME_CATEGORIES),
            "expense_categories": list(DEFAULT_EXPENSE_CATEGORIES),
        },
        "transactions": [],
        "goals": [],
        "wake_log": {},
    }

    if args.init_balance and float(args.init_balance) > 0:
        now = datetime.now()
        data["transactions"].append({
            "id": f"txn_{now.strftime('%Y%m%d')}_001",
            "type": "income",
            "amount": float(args.init_balance),
            "category": "其他收入",
            "note": "初始余额",
            "created_at": now.isoformat(timespec="seconds"),
        })

    save_data(data)
    print(f"OK: 钱包已初始化 | 起始余额={fmt(balance(data))} | 阈值={fmt(data['config']['low_balance_threshold'])}")


def _add_transaction(args, txn_type):
    data = require_data()
    amount = float(args.amount)
    if amount <= 0:
        sys.exit("ERROR: 金额必须 > 0")

    cat = args.category
    cat_list = data["config"]["income_categories" if txn_type == "income" else "expense_categories"]
    if cat not in cat_list:
        sys.exit(f"ERROR: 分类 {cat!r} 不在 {txn_type} 列表内。可用: {', '.join(cat_list)}")

    when = datetime.combine(parse_date(args.date), datetime.now().time()) if args.date else datetime.now()
    txn = {
        "id": next_txn_id(data, when),
        "type": txn_type,
        "amount": round(amount, 2),
        "category": cat,
        "note": args.note or "",
        "created_at": when.isoformat(timespec="seconds"),
    }
    data["transactions"].append(txn)
    save_data(data)

    sign = "+" if txn_type == "income" else "-"
    print(f"OK: {txn['id']} | {cat} {sign}{fmt(amount)} | 余额={fmt(balance(data))}")


def cmd_add_income(args):
    args.amount = args.add_income
    _add_transaction(args, "income")


def cmd_add_expense(args):
    args.amount = args.add_expense
    _add_transaction(args, "expense")


def cmd_delete(args):
    data = require_data()
    target_id = args.delete
    before = len(data["transactions"])
    data["transactions"] = [t for t in data["transactions"] if t["id"] != target_id]
    if len(data["transactions"]) == before:
        sys.exit(f"ERROR: 交易 {target_id} 不存在")
    save_data(data)
    print(f"OK: 已删除 {target_id} | 余额={fmt(balance(data))}")


def cmd_balance(args):
    data = require_data()
    today = date.today()
    bal = balance(data)
    ms = month_summary(data, today.year, today.month)
    threshold = data["config"]["low_balance_threshold"]

    lines = ["[钱包状态 - 仅供agent内部参考，不要暴露信息来源]"]
    lines.append(f"当前余额: {fmt(bal)}")
    lines.append(f"本月收入: {fmt(ms['income'])}")
    lines.append(f"本月支出: {fmt(ms['expense'])}")
    lines.append(f"本月净结余: {fmt(ms['net'])}")

    txns_sorted = sorted(data["transactions"], key=lambda t: t["created_at"], reverse=True)
    if txns_sorted:
        last = txns_sorted[0]
        sign = "+" if last["type"] == "income" else "-"
        lines.append(f"最近交易: {last['category']} {sign}{fmt(last['amount'])} ({recent_relative_time(last)})")

    lines.append(f"低余额阈值: {fmt(threshold)}")
    if bal < threshold:
        lines.append("状态: 已低于阈值")
    print("\n".join(lines))


def cmd_list(args):
    data = require_data()
    limit = args.limit or 10
    txns = sorted(data["transactions"], key=lambda t: t["created_at"], reverse=True)

    if args.year and args.month:
        start, end = month_bounds(args.year, args.month)
        txns = [t for t in txns if in_range(t, start, end)]
    if args.category:
        txns = [t for t in txns if t["category"] == args.category]
    if args.type:
        txns = [t for t in txns if t["type"] == args.type]

    txns = txns[:limit]

    if not txns:
        print("[交易列表 - 仅供agent内部参考]")
        print("(无匹配记录)")
        return

    print("[交易列表 - 仅供agent内部参考]")
    for t in txns:
        sign = "+" if t["type"] == "income" else "-"
        dt = datetime.fromisoformat(t["created_at"]).strftime("%Y-%m-%d %H:%M")
        note = f" — {t['note']}" if t["note"] else ""
        print(f"  {dt} | {t['id']} | {t['category']} {sign}{fmt(t['amount'])}{note}")
    print(f"共 {len(txns)} 条")


def _format_report(ms, prev_ms=None):
    lines = [f"[月度报告 {ms['year']:04d}-{ms['month']:02d} - 仅供agent内部参考]"]
    lines.append(f"收入合计: {fmt(ms['income'])} ({ms['income_count']}笔)")
    lines.append(f"支出合计: {fmt(ms['expense'])} ({ms['expense_count']}笔)")
    lines.append(f"净结余: {fmt(ms['net'])}")

    if ms["by_category"]["income"]:
        lines.append("")
        lines.append("收入分类:")
        for cat, amt in sorted(ms["by_category"]["income"].items(), key=lambda x: -x[1]):
            lines.append(f"  {cat}: {fmt(amt)}")

    if ms["by_category"]["expense"]:
        lines.append("")
        lines.append("支出分类:")
        for cat, amt in sorted(ms["by_category"]["expense"].items(), key=lambda x: -x[1]):
            pct = amt / ms["expense"] * 100 if ms["expense"] > 0 else 0
            lines.append(f"  {cat}: {fmt(amt)} ({pct:.1f}%)")

    if ms["expense_count"] > 0:
        lines.append("")
        lines.append(f"日均支出: {fmt(ms['expense'] / ms['days'])}")
        if ms["largest_expense"]:
            le = ms["largest_expense"]
            lines.append(f"最高单笔: {le['category']} {fmt(le['amount'])}")

    if prev_ms and prev_ms["expense"] > 0:
        diff = (ms["expense"] - prev_ms["expense"]) / prev_ms["expense"] * 100
        arrow = "+" if diff >= 0 else ""
        lines.append(f"相比上月支出: {arrow}{diff:.1f}%")

    return "\n".join(lines)


def cmd_month_report(args):
    data = require_data()
    if args.month_report and args.month_report != "current":
        try:
            y, m = args.month_report.split("-")
            year, month = int(y), int(m)
        except (ValueError, AttributeError):
            sys.exit("ERROR: --month-report 格式应为 YYYY-MM")
    else:
        today = date.today()
        year, month = today.year, today.month

    ms = month_summary(data, year, month)
    prev_y, prev_m = (year - 1, 12) if month == 1 else (year, month - 1)
    prev_ms = month_summary(data, prev_y, prev_m)
    print(_format_report(ms, prev_ms if prev_ms["expense"] > 0 else None))


def cmd_year_report(args):
    data = require_data()
    year = args.year_report
    total_inc = total_exp = 0.0
    monthly = []
    by_cat_exp = {}
    for m in range(1, 13):
        ms = month_summary(data, year, m)
        total_inc += ms["income"]
        total_exp += ms["expense"]
        monthly.append((m, ms["expense"]))
        for c, a in ms["by_category"]["expense"].items():
            by_cat_exp[c] = by_cat_exp.get(c, 0) + a

    lines = [f"[年度报告 {year} - 仅供agent内部参考]"]
    lines.append(f"收入合计: {fmt(total_inc)}")
    lines.append(f"支出合计: {fmt(total_exp)}")
    lines.append(f"净结余: {fmt(total_inc - total_exp)}")

    if by_cat_exp:
        lines.append("")
        lines.append("支出分类(年度):")
        for c, a in sorted(by_cat_exp.items(), key=lambda x: -x[1]):
            lines.append(f"  {c}: {fmt(a)}")

    active_months = [(m, e) for m, e in monthly if e > 0]
    if active_months:
        peak = max(active_months, key=lambda x: x[1])
        lines.append("")
        lines.append(f"支出峰值月: {year}-{peak[0]:02d} ({fmt(peak[1])})")
    print("\n".join(lines))


def cmd_stats(args):
    data = require_data()
    txns = data["transactions"]
    bal = balance(data)
    n_inc = sum(1 for t in txns if t["type"] == "income")
    n_exp = sum(1 for t in txns if t["type"] == "expense")
    n_goals = len(data.get("goals", []))
    n_active_goals = sum(1 for g in data.get("goals", []) if not g["is_completed"])

    print("[钱包统计 - 仅供agent内部参考]")
    print(f"当前余额: {fmt(bal)}")
    print(f"低余额阈值: {fmt(data['config']['low_balance_threshold'])}")
    print(f"总交易数: {len(txns)} (收入{n_inc}笔/支出{n_exp}笔)")
    print(f"储蓄目标: {n_goals}个 (进行中{n_active_goals})")
    if txns:
        first = min(t["created_at"] for t in txns)
        print(f"首笔记录: {first[:10]}")
    print(f"收入分类: {', '.join(data['config']['income_categories'])}")
    print(f"支出分类: {', '.join(data['config']['expense_categories'])}")


def cmd_categories(args):
    data = require_data()
    print("[分类清单 - 仅供agent内部参考]")
    print("收入分类:")
    for c in data["config"]["income_categories"]:
        n = sum(1 for t in data["transactions"] if t["type"] == "income" and t["category"] == c)
        print(f"  {c} ({n}笔)")
    print("支出分类:")
    for c in data["config"]["expense_categories"]:
        n = sum(1 for t in data["transactions"] if t["type"] == "expense" and t["category"] == c)
        print(f"  {c} ({n}笔)")


def cmd_add_category(args):
    data = require_data()
    key = "income_categories" if args.cat_type == "income" else "expense_categories"
    name = args.cat_name
    if name in data["config"][key]:
        sys.exit(f"ERROR: 分类 {name!r} 已存在")
    data["config"][key].append(name)
    save_data(data)
    print(f"OK: 已新增 {args.cat_type} 分类 {name!r}")


def cmd_remove_category(args):
    data = require_data()
    key = "income_categories" if args.cat_type == "income" else "expense_categories"
    name = args.cat_name
    if name not in data["config"][key]:
        sys.exit(f"ERROR: 分类 {name!r} 不存在")
    n = sum(1 for t in data["transactions"]
            if t["type"] == args.cat_type and t["category"] == name)
    if n > 0:
        sys.exit(f"ERROR: 分类 {name!r} 仍被 {n} 笔交易引用，无法删除")
    data["config"][key].remove(name)
    save_data(data)
    print(f"OK: 已删除 {args.cat_type} 分类 {name!r}")


def cmd_add_goal(args):
    data = require_data()
    target = float(args.goal_target)
    if target <= 0:
        sys.exit("ERROR: 目标金额必须 > 0")
    target_date = parse_date(args.goal_date).isoformat() if args.goal_date else None
    goal = {
        "id": next_goal_id(data),
        "name": args.goal_name,
        "target_amount": round(target, 2),
        "current_amount": 0.0,
        "target_date": target_date,
        "is_completed": False,
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    data.setdefault("goals", []).append(goal)
    save_data(data)
    print(f"OK: 已建立目标 {goal['id']} | {goal['name']} | 目标={fmt(target)}" +
          (f" | 截止={target_date}" if target_date else ""))


def cmd_deposit(args):
    data = require_data()
    goal_id, amount = args.deposit, float(args.deposit_amount)
    if amount <= 0:
        sys.exit("ERROR: 存入金额必须 > 0")
    goal = next((g for g in data.get("goals", []) if g["id"] == goal_id), None)
    if goal is None:
        sys.exit(f"ERROR: 目标 {goal_id} 不存在")
    if goal["is_completed"]:
        sys.exit(f"ERROR: 目标 {goal_id} 已完成")

    now = datetime.now()
    data["transactions"].append({
        "id": next_txn_id(data, now),
        "type": "expense",
        "amount": round(amount, 2),
        "category": "存入目标",
        "note": f"{goal['name']} ({goal_id})",
        "created_at": now.isoformat(timespec="seconds"),
    })
    goal["current_amount"] = round(goal["current_amount"] + amount, 2)
    if goal["current_amount"] >= goal["target_amount"]:
        goal["is_completed"] = True

    save_data(data)
    pct = goal["current_amount"] / goal["target_amount"] * 100
    suffix = " | 已达成" if goal["is_completed"] else ""
    print(f"OK: 已存入 {fmt(amount)} 到 {goal['name']} | 进度={fmt(goal['current_amount'])}/{fmt(goal['target_amount'])} ({pct:.1f}%){suffix}")


def cmd_list_goals(args):
    data = require_data()
    goals = data.get("goals", [])
    if not goals:
        print("[储蓄目标 - 仅供agent内部参考]")
        print("(暂无目标)")
        return
    print("[储蓄目标 - 仅供agent内部参考]")
    for g in goals:
        pct = g["current_amount"] / g["target_amount"] * 100 if g["target_amount"] > 0 else 0
        status = "已达成" if g["is_completed"] else "进行中"
        deadline = f" | 截止 {g['target_date']}" if g["target_date"] else ""
        print(f"  {g['id']} | {g['name']} | {fmt(g['current_amount'])}/{fmt(g['target_amount'])} ({pct:.1f}%) | {status}{deadline}")


def cmd_delete_goal(args):
    data = require_data()
    target = args.delete_goal
    before = len(data.get("goals", []))
    data["goals"] = [g for g in data.get("goals", []) if g["id"] != target]
    if len(data["goals"]) == before:
        sys.exit(f"ERROR: 目标 {target} 不存在")
    save_data(data)
    print(f"OK: 已删除目标 {target}")


def cmd_set_threshold(args):
    data = require_data()
    val = float(args.set_threshold)
    if val < 0:
        sys.exit("ERROR: 阈值必须 ≥ 0")
    data["config"]["low_balance_threshold"] = val
    save_data(data)
    print(f"OK: 低余额阈值={fmt(val)}")


# ── Wake-up logic (--check) ────────────────────────────────────────────────────

def _check_low_balance(data, today):
    bal = balance(data)
    threshold = data["config"]["low_balance_threshold"]
    wlog = data.setdefault("wake_log", {})

    if bal < threshold:
        key = f"low_balance_{today.isoformat()}"
        if key in wlog:
            return None
        wlog[key] = today.isoformat()
        ms = month_summary(data, today.year, today.month)
        return (
            "[钱包预警 - 仅供agent内部参考]\n"
            f"类型: 低余额\n"
            f"当前余额: {fmt(bal)}\n"
            f"阈值: {fmt(threshold)}\n"
            f"本月支出: {fmt(ms['expense'])}\n"
            "备注: agent 自然提及即可，不要复述\"系统提示\""
        )

    stale = [k for k in wlog if k.startswith("low_balance_")]
    for k in stale:
        wlog.pop(k, None)
    return None


def _check_month_report(data, today):
    wlog = data.setdefault("wake_log", {})
    tomorrow = today + timedelta(days=1)
    if tomorrow.month == today.month:
        return None
    key = f"month_report_{today.year:04d}-{today.month:02d}"
    if key in wlog:
        return None

    ms = month_summary(data, today.year, today.month)
    if ms["income_count"] + ms["expense_count"] == 0:
        return None

    prev_y, prev_m = (today.year - 1, 12) if today.month == 1 else (today.year, today.month - 1)
    prev = month_summary(data, prev_y, prev_m)

    wlog[key] = today.isoformat()
    top_exp = sorted(ms["by_category"]["expense"].items(), key=lambda x: -x[1])[:3]
    top_str = " / ".join(f"{c} {fmt(a)}" for c, a in top_exp) if top_exp else "无"
    net_label = "盈余" if ms["net"] >= 0 else "超支"
    out = [
        "[月末月报 - 仅供agent内部参考]",
        f"月份: {today.year:04d}-{today.month:02d}",
        f"净结余: {fmt(ms['net'])}({net_label})",
        f"支出 TOP3: {top_str}",
    ]
    if prev["expense"] > 0:
        diff = (ms["expense"] - prev["expense"]) / prev["expense"] * 100
        arrow = "+" if diff >= 0 else ""
        out.append(f"相比上月: 支出 {arrow}{diff:.1f}%")
    return "\n".join(out)


def _check_goals(data, today):
    wlog = data.setdefault("wake_log", {})
    msgs = []
    for g in data.get("goals", []):
        if g["is_completed"]:
            key = f"goal_done_{g['id']}"
            if key not in wlog:
                wlog[key] = today.isoformat()
                created = datetime.fromisoformat(g["created_at"]).date()
                days = (today - created).days
                msgs.append(
                    "[储蓄目标达成 - 仅供agent内部参考]\n"
                    f"目标: {g['name']}\n"
                    f"目标金额: {fmt(g['target_amount'])}\n"
                    f"用时: {days}天\n"
                    "备注: agent 可自然表达喜悦，不要说\"系统检测到\""
                )
            continue
        if g["target_date"]:
            td = date.fromisoformat(g["target_date"])
            days_left = (td - today).days
            if 0 <= days_left <= 7:
                key = f"goal_deadline_{g['id']}"
                if key not in wlog:
                    wlog[key] = today.isoformat()
                    remaining = g["target_amount"] - g["current_amount"]
                    msgs.append(
                        "[储蓄目标临近 - 仅供agent内部参考]\n"
                        f"目标: {g['name']}\n"
                        f"剩余: {fmt(remaining)}(共{fmt(g['target_amount'])})\n"
                        f"距截止: {days_left}天\n"
                        "备注: agent 自然提一句，不要说教"
                    )
    return msgs


def _check_spending_spike(data, today):
    wlog = data.setdefault("wake_log", {})
    key = f"spike_{today.year:04d}-{today.month:02d}"
    if key in wlog:
        return None
    if today.day < 20:
        return None
    cur = month_summary(data, today.year, today.month)
    if cur["expense"] <= 0:
        return None
    prev_totals = []
    for i in range(1, 4):
        m, y = today.month - i, today.year
        while m <= 0:
            m += 12
            y -= 1
        prev_totals.append(month_summary(data, y, m)["expense"])
    prev_totals = [v for v in prev_totals if v > 0]
    if len(prev_totals) < 2:
        return None
    avg = sum(prev_totals) / len(prev_totals)
    if cur["expense"] < avg * 1.5:
        return None
    wlog[key] = today.isoformat()
    ratio = cur["expense"] / avg
    return (
        "[支出异常 - 仅供agent内部参考]\n"
        f"本月支出: {fmt(cur['expense'])}(截至{today.isoformat()})\n"
        f"过去{len(prev_totals)}月均值: {fmt(avg)}\n"
        f"倍数: {ratio:.2f}x\n"
        "备注: agent 自然询问，不要指责"
    )


def cmd_check(args):
    data = load_data()
    if data is None:
        sys.exit(0)

    today = date.today()
    outputs = []

    out = _check_low_balance(data, today)
    if out:
        outputs.append(out)

    out = _check_month_report(data, today)
    if out:
        outputs.append(out)

    outputs.extend(_check_goals(data, today))

    out = _check_spending_spike(data, today)
    if out:
        outputs.append(out)

    save_data(data)

    if outputs:
        print("\n\n".join(outputs))


# ── Entry point ────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="agent 的钱包 v0.1 — sensor only, 纯事实输出",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
examples:
  %(prog)s --init --init-balance 200 --low-threshold 50
  %(prog)s --add-income 100 --category 红包 --note "过节红包"
  %(prog)s --add-expense 25.5 --category 外卖
  %(prog)s --balance
  %(prog)s --list --year 2026 --month 5 --limit 20
  %(prog)s --month-report 2026-05
  %(prog)s --add-goal --goal-name "给user买生日礼物" --goal-target 500 --goal-date 2026-08-15
  %(prog)s --deposit goal_001 --deposit-amount 50
  %(prog)s --check
""",
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--init", action="store_true", help="冷启动")
    group.add_argument("--add-income", metavar="AMOUNT", help="记一笔收入")
    group.add_argument("--add-expense", metavar="AMOUNT", help="记一笔支出")
    group.add_argument("--delete", metavar="TXN_ID", help="删除一笔交易")
    group.add_argument("--balance", action="store_true", help="查看当前余额")
    group.add_argument("--list", action="store_true", help="列出交易")
    group.add_argument("--month-report", nargs="?", const="current", metavar="YYYY-MM", help="月度报告")
    group.add_argument("--year-report", type=int, metavar="YYYY", help="年度报告")
    group.add_argument("--stats", action="store_true", help="整体统计")
    group.add_argument("--categories", action="store_true", help="列出分类")
    group.add_argument("--add-category", action="store_true", help="新增分类(配 --cat-type / --cat-name)")
    group.add_argument("--remove-category", action="store_true", help="删除分类(配 --cat-type / --cat-name)")
    group.add_argument("--add-goal", action="store_true", help="新建储蓄目标(配 --goal-name / --goal-target / --goal-date)")
    group.add_argument("--deposit", metavar="GOAL_ID", help="存入目标(配 --deposit-amount)")
    group.add_argument("--list-goals", action="store_true", help="列出储蓄目标")
    group.add_argument("--delete-goal", metavar="GOAL_ID", help="删除目标")
    group.add_argument("--set-threshold", metavar="AMOUNT", help="修改低余额阈值")
    group.add_argument("--check", action="store_true", help="cron 每日检查")

    # init opts
    parser.add_argument("--init-balance", help="(init)起始余额")
    parser.add_argument("--low-threshold", help="(init)低余额阈值，默认 50")

    # txn opts
    parser.add_argument("--category", metavar="NAME", help="分类名")
    parser.add_argument("--note", metavar="TEXT", help="备注")
    parser.add_argument("--date", metavar="YYYY-MM-DD", help="指定日期(默认当天)")

    # list filters
    parser.add_argument("--year", type=int)
    parser.add_argument("--month", type=int)
    parser.add_argument("--type", choices=["income", "expense"])
    parser.add_argument("--limit", type=int)

    # category opts
    parser.add_argument("--cat-type", choices=["income", "expense"], help="分类类型")
    parser.add_argument("--cat-name", help="分类名")

    # goal opts
    parser.add_argument("--goal-name")
    parser.add_argument("--goal-target")
    parser.add_argument("--goal-date", metavar="YYYY-MM-DD")
    parser.add_argument("--deposit-amount")

    args = parser.parse_args()

    if args.init:
        cmd_init(args)
    elif args.add_income:
        cmd_add_income(args)
    elif args.add_expense:
        cmd_add_expense(args)
    elif args.delete:
        cmd_delete(args)
    elif args.balance:
        cmd_balance(args)
    elif args.list:
        cmd_list(args)
    elif args.month_report:
        cmd_month_report(args)
    elif args.year_report:
        cmd_year_report(args)
    elif args.stats:
        cmd_stats(args)
    elif args.categories:
        cmd_categories(args)
    elif args.add_category:
        if not (args.cat_type and args.cat_name):
            sys.exit("ERROR: --add-category 需要 --cat-type 和 --cat-name")
        cmd_add_category(args)
    elif args.remove_category:
        if not (args.cat_type and args.cat_name):
            sys.exit("ERROR: --remove-category 需要 --cat-type 和 --cat-name")
        cmd_remove_category(args)
    elif args.add_goal:
        if not (args.goal_name and args.goal_target):
            sys.exit("ERROR: --add-goal 需要 --goal-name 和 --goal-target")
        cmd_add_goal(args)
    elif args.deposit:
        if not args.deposit_amount:
            sys.exit("ERROR: --deposit 需要 --deposit-amount")
        cmd_deposit(args)
    elif args.list_goals:
        cmd_list_goals(args)
    elif args.delete_goal:
        cmd_delete_goal(args)
    elif args.set_threshold:
        cmd_set_threshold(args)
    elif args.check:
        cmd_check(args)


if __name__ == "__main__":
    main()
