# F2-P6E 全局预算预检

## 三个条件必须同时满足

```python
1. need <= local_max_requests                  # 本地整批上限
2. observed_remaining >= need + reserve        # 权威剩余
3. rate_limit_status not in (PRIMARY, SECONDARY)  # 未处于限流
```

任一不满足 → `can_begin = False`，并给出 `block_reason`。

## 没有权威响应头时

`observed_remaining is None` → **拒绝开始整批采集**，返回 `NO_AUTHORITATIVE_REMAINING`。

这不是保守，是唯一正确的做法：不知道剩余就不能规划。P6C 那次我靠「自己数了几次」推剩余，
结果两次把配额烧光——因为**别的进程也在花同一个 IP 的额度**。

允许的动作只有一条：至多一次 `GET /rate_limit` 诊断。
诊断仍为 0 → **整批停止**。

## 预检通过不等于配额已预留

`preflight` 输出里有一条固定注解：

> 预检通过不等于配额已预留；匿名配额按 IP 共享，每次请求后须按真实响应头更新

所以 `Coordinator` 每发一次请求就调 `budget.consume()`，用真实响应头覆盖本地推断。
执行中配额被别的进程吃掉 → `can_spend` 返回 False → 抛 `BudgetExhausted` → 安全停止，保留已有资产。

## 预留

默认 `reserve_requests = 6`。不把 60 次用尽。

我在代码里留了一句话：**不能为了让验收通过而擅自把余量永久设成 0**。

## 本轮实测的配额曲线

```
17:08  remaining 0, reset 118s
17:11  remaining 0, reset 860s
17:14  remaining 0, reset 721s
```

三次都是 0，reset 还在往后走。说明**这个 IP 上有别的进程持续在花配额**。

这正是预检存在的理由：如果我照旧直接冲进采集，会第四次撞墙。
