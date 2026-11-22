# 参数译文跨模型审校归档摘要（data-v2026.11.4 基线）

- 审校日期：2026-11-22；审校人：argus-glm（GLM，ar/de/fr）、argus-kimi（ja/ko/ru）
- 基线：数据仓库 `main c5faad7` = data-v2026.11.4（9 locale 各 8,844 条，全机器翻译 r=0）
- 原始报告：`argus-param-i18n/out/review_glm.md`、`out/review_kimi.md`（out/ gitignored，不入库）

## 抽样范围与限制

两边均为**目的性分层抽样，不是全量审校，也非母语人工审校**：

- GLM：每 locale 约 130 条（长描述、枚举/bitmask 标签、ARMING/FS/BATT/WP-NAV/CAL 参数、占位符、centi- 单位、否定/比较句式、Motor1–32 全家族），约 390 对照对。
- Kimi：30 个源字符串 × ja/ko/ru 三语共用对照（覆盖解锁、失效保护、电池、导航、校准、日志、围栏），共 90 条。
- 合计约 480 对照对；6 个受审 locale 共 53,064 条，全部 9 locale 共 79,596 条。结论只代表所抽条目；数字/参数名/占位符保留经脚本全量校验（tools.validate）另有保证。

## 计数

| 审校人 | locale | 抽查数 | high | medium | low |
|---|---|---:|---:|---:|---:|
| GLM | ar/de/fr | ~390 对 | 0 | 4 | 10 |
| Kimi | ja/ko/ru | 90 | 0 | 0 | 3 |
| **合计** | 6 locale | — | **0** | **4** | **13** |

两份审校均未发现语义反转、安全动作方向错误、关键语义遗漏或数字/参数名/占位符丢失；ko 本批零缺陷。缺陷集中在枚举标识符策略不统一与零星病句。

## 关键 findings（全部 17 条）

| # | locale | 参数/条目 | 问题 | 严重度 | 建议译文（要点） |
|---|---|---|---|---|---|
| 1 | ar | SERVO*_FUNCTION Motor1–32 | 同下拉框 4 种写法混排（13 英文保留 / محرك N×10 / محركN×8 / المحرك 30） | medium | 全族保留 MotorN 英文 |
| 2 | fr | 同上 Motor1–32 | 3 种写法混排（11 保留 / Moteur5×14 / Moteur 6×7） | medium | 同上 |
| 3 | ar | INS_TCAL2_GYR2_X [human] | 语序破碎（للجيروسكوب المحور X 无法断句） | medium | المعامل الحراري … – المحور X |
| 4 | ar | FS_THR_ENABLE values[3] | 语序错误（مفعل دائمًا هبوط） | medium | تفعيل الهبوط دائمًا |
| 5 | de | FS_THR_ENABLE values[3] | 非语法德语（Immer aktiviert Landen） | low | Immer aktiviert: Landen |
| 6 | de | RC3_OPTION values[165] | 复合词歧义 Notmotorstopp | low | Scharfschalten/Motor-Notstopp |
| 7 | fr | AHRS_TRIM_Y [desc] | 丢 "/back" 语义（cabrer 只含上仰） | low | cabrer / reculer |
| 8 | fr | EK3_MAG_CAL [desc] 节选 | 语法破碎（après le premier champ… terminés） | low | après la fin de la première réinitialisation en vol… |
| 9 | ar | H_RSC_GOV_TORQUE [desc] | governor 直译"الحاكم"；桨距 ميل/خطوة 两译 | low | منظم السرعة；桨距统一 |
| 10 | de | EK3_DRAG_MCOEF [desc] | 非规范词 unummantelt | low | nicht ummantelt |
| 11 | de | AHRS_GPS_GAIN [desc] | 冠词错误 der GPS | low | das GPS |
| 12 | fr | EK2_MAG_CAL vs EK3 | 载具名两套策略（avions/multicoptères vs Plane/copters） | low | 统一保留英文载具名 |
| 13 | ar | RTL_CLIMB_MIN [human] | في عودة 缺定冠词 | low | أثناء العودة |
| 14 | ar | AHRS_GPS_GAIN [desc] | الجنحان 双数形式语法错误 | low | ثابتة الجناح |
| 15 | ja | LOG_BITMASK [desc] | 未译标识 basiclog 留机器翻译痕迹 | low | 基本ログ種類 |
| 16 | ru | LOG_DISARMED values[3] | Сбрасывать 语义偏"重置"非"丢弃" | low | Удалять лог |
| 17 | ru | ATC_RAT_YAW_P [desc] | 遗漏"角速度"术语，与 pitch 条目不一致 | low | регулятора угловой скорости по оси рыскания |

## 修复状态

- **已在 data-v2026.11.5 修复**：commit `900d4b7`（"data: apply cross-model review fixes for 2026.11.5"，2026-11-22），含 MotorN/ModeN 全 locale 英文归一化 + 上表 4 medium + 13 low，共改 9 个 TM + manifest（152 行）。
- **上游文本缺陷（2 条，不归本仓库修）**：BATTB_ESC_MASK desc 悬空 "in"（"selected in will be used"）；FFT_HMNC_PEAK 选项 5 重复选项 4 的 "(peak on roll)"。三语译文均如实传播，语义与源一致。已反馈上游：https://github.com/ArduPilot/ardupilot/issues/35332

## 独立核验

- argus-kimi 于 2026-11-22 独立核验 `data-v2026.11.5`：17/17 条 findings 已修复或等效修复；`MotorN` 288/288、`ModeN` 54/54 跨 9 locale 保留英文；79,596 条校验 0 errors / 0 warnings；发布包内 9 个 TM 与 `f7443d3` 完全一致，tarball SHA-256 与 Argus lock 一致。

## 可复核信息

| 项 | 值 |
|---|---|
| 审校基线 | data-v2026.11.4（tarball 7,457,349 B，main `c5faad7`） |
| 修复版本 | data-v2026.11.5，发布 2026-11-22T03:57:26Z，tarball 7,457,248 B |
| 修复 commit | `900d4b7`（数据仓库 main，其上另有 `f7443d3` ci 提交） |
| 随 Argus 版本 | v3.16.1（2026-11-22 发布） |
| 原始报告 | `out/review_glm.md`、`out/review_kimi.md`（gitignored，未入库） |
