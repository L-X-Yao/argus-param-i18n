# Kimi confirm 10 条交叉复核（GLM，只读）

- 复核对象：/tmp/argus-alias-candidates.json ids 133/191/199/200/201/202/204/205/206/207
- 方法：对每条在对应 vehicle 的 from/to 两代 meta 上跑五项结构检查：①旧名在 from 存在 ②旧名在 to 消失 ③新名在 from 不存在 ④新名在 to 存在 ⑤新名指纹在 to 原始 meta 中唯一（=1，自身）；另查旧名指纹在 from 中的唯一性（排除实例族）。
- 结果：**10/10 五项全过，全部 agree**。

## 明细

| id | vehicle | old → new | 决策 | 置信度 | 理由 |
|---|---|---|---|---|---|
| 133 | plane | TELEM_DELAY → MAV_TELEM_DELAY | agree | high | 五项全过；与 copter 同名改名（GLM id 55 已 confirm）三机种互证，属 4.7 MAV_ 前缀归并族 |
| 191 | rover | TELEM_DELAY → MAV_TELEM_DELAY | agree | high | 同上，rover 侧五项全过 |
| 199 | sub | NET_ENABLED → NET_ENABLE | agree | medium | 五项全过；去 D 后缀的单点改名，无其他机种或上游注记佐证 |
| 200 | sub | PSC_ACCZ_SMAX → PSC_D_ACC_SMAX | agree | medium | 五项全过；与 copter PSC、plane Q_P 同一 4.7 重组（ACCZ→D），跨机种互证强，但分组映射仍是推断 |
| 201 | sub | PSC_JERK_XY → PSC_NE_JERK | agree | medium | 同上（JERK_XY→NE） |
| 202 | sub | PSC_JERK_Z → PSC_D_JERK | agree | medium | 同上（JERK_Z→D） |
| 204 | sub | SIM_WIND_T_ → SIM_WIND_T | agree | high | 五项全过；尾部多余下划线的上游笔误修复，同名同指纹无 sibling 可能性 |
| 205 | sub | WPNAV_JERK → WP_JERK | agree | high | 五项全过；WPNAV_*→WP_* 4.7 已知改名族，copter 侧同名已 confirm |
| 206 | sub | WPNAV_RFND_USE → WP_RFND_USE | agree | high | 同上 |
| 207 | sub | WPNAV_TER_MARGIN → WP_TER_MARGIN | agree | high | 同上 |

## 计数

| 决策 | high | medium | disagree |
|---|---:|---:|---:|
| agree | 7 | 3 | — |

## 建议

10 条均可进 aliases.json。medium 的 4 条（NET_ENABLE、PSC×3）建议合入前抽一条对 ArduPilot 4.7 的 AP_Param 改名转换表（GCS_MAVLink / Parameters.md release notes）做一次性上游确认，确认后全部可升 high。
