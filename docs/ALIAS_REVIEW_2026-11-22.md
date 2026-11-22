# 别名候选初筛归档（2026-11-22）

- 基线：data-v2026.11.5 / 数据 main `f5eef27`；候选来自 `meta/<vehicle>/<series>.json` 的连续系列指纹匹配。
- 候选总数 207：copter 58、plane 75、rover 58、sub 16。
- 初筛：argus-glm 负责 ids 1–104，argus-kimi 负责 105–207；两路交叉复核 21/21 agree。
- **本文件不修改 `aliases.json`**；21 条需人工确认后才进入数据版本。

## 计数

| 决策 | 数量 | 说明 |
|---|---:|---|
| confirm | 21 | 5 high / 16 medium（初筛置信度） |
| reject | 186 | 全部 high；主要是实例/sibling 错配 |
| unsure | 0 | — |

## 待人工确认的 21 条

| id | vehicle | old → new | 初筛置信度 | 复核 |
|---:|---|---|---|---|
| 8 | copter | `PHLD_BRAKE_RATE` → `PHLD_BRK_RATE` | high | agree |
| 9 | copter | `PSC_ACCZ_SMAX` → `PSC_D_ACC_SMAX` | medium | agree |
| 10 | copter | `PSC_JERK_XY` → `PSC_NE_JERK` | medium | agree |
| 11 | copter | `PSC_JERK_Z` → `PSC_D_JERK` | medium | agree |
| 55 | copter | `TELEM_DELAY` → `MAV_TELEM_DELAY` | high | agree |
| 56 | copter | `WPNAV_JERK` → `WP_JERK` | high | agree |
| 57 | copter | `WPNAV_RFND_USE` → `WP_RFND_USE` | high | agree |
| 58 | copter | `WPNAV_TER_MARGIN` → `WP_TER_MARGIN` | high | agree |
| 66 | plane | `Q_P_ACCZ_SMAX` → `Q_P_D_ACC_SMAX` | medium | agree |
| 67 | plane | `Q_P_JERK_XY` → `Q_P_NE_JERK` | medium | agree |
| 68 | plane | `Q_P_JERK_Z` → `Q_P_D_JERK` | medium | agree |
| 133 | plane | `TELEM_DELAY` → `MAV_TELEM_DELAY` | medium | agree |
| 191 | rover | `TELEM_DELAY` → `MAV_TELEM_DELAY` | medium | agree |
| 199 | sub | `NET_ENABLED` → `NET_ENABLE` | medium | agree |
| 200 | sub | `PSC_ACCZ_SMAX` → `PSC_D_ACC_SMAX` | medium | agree |
| 201 | sub | `PSC_JERK_XY` → `PSC_NE_JERK` | medium | agree |
| 202 | sub | `PSC_JERK_Z` → `PSC_D_JERK` | medium | agree |
| 204 | sub | `SIM_WIND_T_` → `SIM_WIND_T` | medium | agree |
| 205 | sub | `WPNAV_JERK` → `WP_JERK` | medium | agree |
| 206 | sub | `WPNAV_RFND_USE` → `WP_RFND_USE` | medium | agree |
| 207 | sub | `WPNAV_TER_MARGIN` → `WP_TER_MARGIN` | medium | agree |

复核：GLM 复核 Kimi 10 条（10/10 agree）；Kimi 复核 GLM 11 条（11/11 agree）。

## 186 条 reject 的构成

| 模式 | 数量 | 结论 |
|---|---:|---|
| `SRx_* → MAV9_*` | 147 | 指纹 32 个共享者，实例配对错误；真实改名族应为 `SRx_* → MAV(x+1)_*`（4.7.1 无 MAV0）。需单独生成并抽上游确认 |
| `CAM_* → CAM2_*` | 24 | CAM1/CAM2 指纹全同；旧无编号 CAM 应为主相机 `CAM1_*` |
| `EK3_* → EK2_*` | 4 | EK2/EK3 两代 sibling，不是改名 |
| `SIM_GPS_JAM → SIM_GPS4_JAM` | 4 | GPS1–4 共享指纹；主实例应为 `SIM_GPS1_JAM` |
| `TRQ*` 等 sibling | 7 | 同族共享文案，目标不唯一 |

## 合入前动作

1. 人工确认上表 21 条；PSC 分组（ACCZ→D、JERK_XY→NE、JERK_Z→D）建议对 ArduPilot 4.7 的 AP_Param 改名转换表做一次上游确认。
2. 确认后写 `aliases.json`，发 `data-v2026.11.6`，再更新 Argus lock/版本。
3. `SRx→MAV(x+1)`、`CAM→CAM1` 不要用当前候选直接写；先生成确定性映射并加测试。

原始报告：`docs/alias-reviews/2026-11-22-glm.md`、`docs/alias-reviews/2026-11-22-kimi.md`；交叉复核在 `/tmp/argus-aliases-crosscheck-*.md`（未入库）。
## 已合入

- **data-v2026.11.6**（2026-11-22）写入 `aliases.json`，共 307 条：
  - 21 条初筛确认（5 high / 16 medium；两路交叉复核 21/21 agree）
  - 266 条 `SRx_* → MAV(x+1)_*` 家族映射（由确定性规则生成，逐条校验旧名消失/新名存在/目标唯一）
  - 16 条 `CAM_* → CAM1_*`
  - 4 条 `SIM_GPS_JAM → SIM_GPS1_JAM`
- 验证：`tests/test_aliases.py` 5 项；数据 58 tests；`tools.validate --strict` 0 errors/0 warnings。
- 未采用 186 条指纹候选（SR→MAV9/CAM→CAM2/EK3→EK2/SIM_GPS→GPS4/TRQ sibling）。
- 随 Argus **v3.16.2** 发布。

