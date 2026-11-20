# 岚桥涂层固化定点复盘

炉段员从试验工单取得双段清册，从仪表采集文件取得具名实测。领班用班初交接单上的确切入口负荷备齐定点站件。夜班质控员在源库关闭后签报，次班依据固定签号复查首停拍或登记最终安全出炉负荷。

## 工作流程

1. 在站侧 SQLite 库初始化计划、观测和发行表。按工单登记稳定计划，固定批次、双段顺序、拍位、换算和停检线。
2. 按炉段提交一整份具名观测。站端验收覆盖与质量，并按计划拍序冻结。领班取得确切修订号。
3. 如有勘误，重新提交该段完整读数并引用同段旧修订。新修订和旧修订可分别取用。
4. 用班初确切入口及前段修订领取前件。前件安全时，以其实际出口为后件入口。前件已停时，交付同计划的合法后件用于核对出处。
5. 交付有序双件，关闭站库连接。中心在自己的 SQLite 库核对封套和同计划段位，按需要核对入口交接。
6. 夜班签发报告与回执。报告记载实用父件与整程首停拍或实际安全出口。提交失败时整份回滚，可重试。
7. 次班重新连接中心库，凭固定报告号复领原裁决、双件出处和回执。

## 接口和数据口径

站库由 `plans.store.initialize_plan_store`、`source.store.initialize_observation_store`、`issuer.store.initialize_piece_store` 初始化。中心库由 `archive.store.initialize_archive_store` 初始化。各初始化接收 `sqlite3.Connection` 并可重复执行。调用方持有和关闭连接。初始化与写接口应在连接处于空闲事务状态时调用。

| 接口 | 输入与返回 |
| --- | --- |
| `plans.catalog.register_plan(db, batch, segments, calibration, stop_limit)` | `segments` 是两个有序的 `(段名, 拍名序列)`，`calibration` 是 `(倍率, 零点修正)` 或 `CalibrationSpec`。返回计划号。等值重登沿用原号，同批冲突得 `ValueError`。 |
| `plans.catalog.read_plan_record(db, plan_id)` | 返回固定计划。未知号得 `KeyError`。 |
| `source.freezes.freeze_observations(db, plan_id, segment, observations, previous_revision_id=None)` | 每行用 `Observation(beat, reading, quality)`，合格状态使用 `ok`。返回确切修订号。漏拍、重拍、错段、质量错误及非法父修订得 `ValueError`，未知计划得 `KeyError`。 |
| `source.freezes.read_frozen_revision(db, revision_id)` | 返回计划拍序下的冻结原测、段内序号及父修订。未知修订得 `KeyError`。 |
| `issuer.pieces.issue_point(db, revision_id, entry)` | 返回 `PointPiece`，含 `encoded` 字节、`stop_beat` 和 `exit_load`。等值重领复用存件。非法入口得 `ValueError`，未知修订得 `KeyError`。 |
| `replay.intake.issue_point_report(db, front_piece, rear_piece)` | 接收 `PointPiece` 或其编码字节。返回 `PointReport`，含 `report_id`、`body` 和 `receipt`。坏件、异计划、错序、同段及续行错配得 `ValueError`。提交失败传播原异常。 |
| `archive.history.read_point_report(db, report_id)` | 按固定整数号返回原报告正文及回执。未知号得 `KeyError`。 |

精确数值接受整数、`Fraction`、有限 `Decimal` 和有理数字符串，包含有限十进制文本。布尔、浮点对象、缺项和非有限值均非法。倍率和停检线须为正。入口须满足 `0 ≤ x < H`。原读数乘倍率再加零点修正得到统一负荷单位的有符号变化。每拍依清册顺序计算 `max(0, 当前负荷 + 变化)`，达到或超过 `H` 当拍停检。停检的出口为 `None`，全段安全才输出最终有理负荷。

V1 站件以规范 JSON 字节固定计划快照、炉段、修订、入口和本站裁决，并以内容摘要核对封套完整性。逐拍实测、变化和轨迹留在站端。中心在前段已停时仍核对后件封套与计划出处。续行时，后件入口必须与前件的安全出口精确相等。中心库以报告号关联正文和回执，历史领取读取签发时存值。

## 运行

使用 Python 3.11 标准库。在项目根目录运行完整确定性回归和样例。

```sh
python3 -B check_project.py
python3 -B -m examples.demo
```

回归入口运行 `tests` 包下的 `test_*.py`。样例用 `examples/runorders.json` 和 `examples/observations.json` 建立临时站库及中心库，实际签发并验证出口为 4 的安全班报和前段等号停检班报，随后重开中心领取。样例输出中的 `POINTWISE_SCENARIO` 行包含输入、手算预期、实际裁决和下游领取结果。
