# GLM 11 条 alias confirm 交叉复核（Kimi）

只读核对 `/tmp/argus-alias-candidates.json` 与新旧 series meta；未修改仓库。逐条确认旧名在新 series 消失、新名在旧 series 不存在、目标指纹唯一，并比较完整 human/desc/default/units，而非只比较 humanName。

| id | vehicle | old→new | 决策 | 理由 |
|---:|---|---|---|---|
| 8 | copter | `PHLD_BRAKE_RATE→PHLD_BRK_RATE` | agree | 旧名消失、新名出现；`PHLD_BRK_RATE` 是唯一指纹匹配。完整 meta 与 `deg/s` 一致，仅 BRAKE→BRK 缩写，无编号或 sibling 竞争。 |
| 9 | copter | `PSC_ACCZ_SMAX→PSC_D_ACC_SMAX` | agree | 旧名消失、目标唯一、完整 meta 一致；ACCZ→D 保持垂直 slew-limit 语义，并与同组 PSC 轴命名迁移一致。 |
| 10 | copter | `PSC_JERK_XY→PSC_NE_JERK` | agree | 旧名消失、目标唯一；XY→NE 保持水平 jerk 语义，`m/s/s/s` 不变，与 PSC_JERK_Z 同步迁移。 |
| 11 | copter | `PSC_JERK_Z→PSC_D_JERK` | agree | 旧名消失、目标唯一；Z→D 保持垂直 jerk 语义，`m/s/s/s` 不变，与 PSC_JERK_XY 同步迁移。 |
| 55 | copter | `TELEM_DELAY→MAV_TELEM_DELAY` | agree | 旧名消失、新名出现；`MAV_TELEM_DELAY` 唯一匹配，完整 meta 与 `s` 一致，MAV 全局前缀不改变 telemetry startup delay 语义。 |
| 56 | copter | `WPNAV_JERK→WP_JERK` | agree | 旧名消失、目标唯一、完整 meta 一致；WPNAV→WP 同组迁移，jerk 语义及 `m/s/s/s` 不变。 |
| 57 | copter | `WPNAV_RFND_USE→WP_RFND_USE` | agree | 旧名消失、目标唯一；rangefinder/terrain-following 语义完全一致，无实例编号或其他 WP sibling 共享该指纹。 |
| 58 | copter | `WPNAV_TER_MARGIN→WP_TER_MARGIN` | agree | 旧名消失、目标唯一；terrain margin 语义与 `m` 不变，属于同一 WPNAV→WP 前缀迁移。 |
| 66 | plane | `Q_P_ACCZ_SMAX→Q_P_D_ACC_SMAX` | agree | 旧名消失、目标唯一、完整 meta 一致；Q_P 组内 ACCZ→D 保持垂直 slew-limit 语义，无 sibling 竞争。 |
| 67 | plane | `Q_P_JERK_XY→Q_P_NE_JERK` | agree | 旧名消失、目标唯一；Q_P 组内 XY→NE 保持水平 jerk 语义，`m/s/s/s` 不变。 |
| 68 | plane | `Q_P_JERK_Z→Q_P_D_JERK` | agree | 旧名消失、目标唯一；Q_P 组内 Z→D 保持垂直 jerk 语义，`m/s/s/s` 不变。 |

补充：这些条目的 default 均为 null，因此 default 未提供独立证据；结论由名称迁移、旧/新名存在性、唯一目标和完整 desc/units 共同支持。未发现 CAM/EK/SR 类实例 sibling 问题。

**计数：agree 11 / disagree 0。11 条均可进入 aliases.json。**
