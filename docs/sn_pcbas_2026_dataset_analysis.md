# SN-PCBAS-2026 数据集接入与分析

本文档聚焦 `FOOTPASS / SN-PCBAS-2026`，目标不是泛泛介绍挑战，而是回答四个实现问题：

1. 这个数据集为什么值得作为“动作 + 位置 + 执行者”路线的首选主监督源。
2. 它现在到底怎么拿到手，访问边界在哪里。
3. 是否能直接下载单场比赛标注，如果不能，现实可行的替代方案是什么。
4. 它接入当前 [event_classification_pipeline.md](D:\Code\Event-Classifer-Test\docs\event_classification_pipeline.md) 时，最小字段映射该怎么设计。

## 1. 数据集定位

`SN-PCBAS-2026` 对应 SoccerNet 2026 的 `Player-Centric Ball Action Spotting` 挑战。和传统 Action Spotting 相比，它关注的不只是 `what happened when`，还要回答 `who did it`。

从公开挑战页、FOOTPASS 仓库与 Hugging Face 数据集页可以确认，这条任务路线的目标是把以下监督信号放进一个统一数据源里：

- 球相关动作标签
- 动作发生时间
- 动作执行者 identity
- 队伍归属
- 球衣号、角色等 player-centric 元数据
- tracking / spatiotemporal 相关信息

这与当前项目想做的“动作 + 位置 + 执行者”事件划分几乎完全对齐，因此它不是辅助源，而是主监督源候选。

## 2. 为什么它比现有 Action Spotting 更适合作主数据源

当前 pipeline 的 Action Spotting 路线以 `Labels-v2.json` 为主事件源，优点是时间轴稳定、比赛树清晰，但存在三类短板：

- 动作是谁做的，通常缺失或不稳定。
- 是否带有足够的位置监督，缺失。
- `team=home/away/not applicable` 适合弱标注，不足以表达 player-centric 事件。

`SN-PCBAS-2026` 解决的正是这三块缺口：

- 不再只到 team 级，而是往 player 级推进。
- 不再只关心稀疏动作时间，而是与 tracking / spatial data 联动。
- 更适合作为未来 adapter 的统一上游，而不是只作为 `event_rule` 的弱标签来源。

因此，如果目标是把系统升级成真正的 player-centric 事件划分器，优先级应高于继续堆叠 Action Spotting 弱规则。

## 3. 访问方式与现实约束

### 3.1 当前公开入口

当前实现默认以 Hugging Face gated dataset 作为公开入口：

- 数据集仓库：`SoccerNet/SN-PCBAS-2026`
- 访问方式：需要 Hugging Face 账号、token、并获得 gated dataset 访问批准

这和现有 `SoccerNetDownloader.downloadGame()` 完全不是一条链路，因此不应假定可以像下载 `Labels-v2.json` 那样用 SoccerNet 的单场下载接口直接拉比赛目录。

### 3.2 与视频相关的额外边界

公开说明显示数据通常拆成两类压缩包：

- `tactical_data_*.zip`
- `videos_*.zip`

其中 tactical data 是当前最关心的标注包。视频 zip 可能还伴随 SoccerNet 侧的额外访问或解压密码要求。对当前目标来说，优先级应放在标注包而不是视频包。

### 3.3 访问失败的典型原因

实现层面需要区分以下失败场景：

- 未设置 Hugging Face token
- token 对应账号未获 gated dataset 访问批准
- repo id 写错
- 远端文件名变更
- 本地环境无法联网或 `huggingface_hub` 未安装

下载脚本必须对这些情况给出可区分的错误提示，避免把所有失败都解释成“文件不存在”。

## 4. 文件组织与下载粒度判断

### 4.1 当前最现实的远端粒度

目前没有证据表明 `SN-PCBAS-2026` 提供官方的远端单场下载接口。实现时不应假定存在这类能力。

当前最现实的公开下载粒度是 split 级压缩包，例如：

- `tactical_data_TRAIN.zip`
- `tactical_data_VAL.zip`
- `tactical_data_CHALLENGE.zip`

这意味着下载入口更像：

- 先选 split
- 再整包下载 tactical data
- 最后在本地筛选和抽取单场标注

### 4.2 单场下载的现实结论

对“能否下载一场比赛的标注数据”这个问题，当前合理结论是：

- **远端直接单场下载：未确认存在，不应作为默认方案**
- **本地单场标注抽取：可设计并优先支持**

也就是说，最可行方案不是“下载单场”，而是“下载 split 级 tactical data zip 后，从 zip 内定位并提取单场相关成员”。

### 4.3 标注与视频的区别

当前应显式区分两种能力：

- **单场标注抽取**：大概率可行，只要 tactical data zip 内部存在稳定的比赛标识、目录层次，或至少存在能索引到单场的数据字段。
- **单场视频下载**：未必可行。即使可行，也不应在当前脚本里优先承诺，因为视频通常更大、权限边界也更多。

## 5. 推荐的本地数据组织

与现有 `raw/as2023/league/season/match/` 树分开存放，建议使用单独根目录：

```text
data/soccernet/raw/sn-pcbas-2026/
├── TRAIN/
│   └── tactical_data_TRAIN.zip
├── VAL/
│   └── tactical_data_VAL.zip
├── CHALLENGE/
│   └── tactical_data_CHALLENGE.zip
└── extracted/
    └── TRAIN/
        └── <match_or_game_id>/
```

这样做的理由：

- `SN-PCBAS-2026` 很可能不是当前 `league/season/match/` 这一套目录语义。
- 把它硬塞进 `raw/as2023` 容易制造“看上去兼容，实际上字段和层次不兼容”的错觉。
- 下载层与 adapter 层保持解耦，后续更容易做跨数据集对照。

## 6. 基于真实 `val_tactical_data.h5` 的结构验证

本地真实文件 [val_tactical_data.h5](D:\Code\Event-Classifer-Test\data\soccernet\raw\sn-pcbas-2026\val_tactical_data.h5) 已经可以确认 `SN-PCBAS-2026` 的一个关键事实：解压后的 tactical annotations 主体是 **HDF5 文件**，而不是单层 JSON。

### 6.1 根层结构

`val_tactical_data.h5` 的根层没有额外 attrs，包含 6 个顶层 dataset：

- `game_18_H1`
- `game_18_H2`
- `game_24_H1`
- `game_24_H2`
- `game_47_H1`
- `game_47_H2`

这与 README 中 validation split 只有 3 场比赛完全一致，也说明当前文件按“比赛 + 半场”来组织。

### 6.2 每个顶层对象的形态

每个 key 都不是 group，而是一个二维 `float32` dataset，形状是 `(N, 14)`。例如：

- `game_18_H1`: `(1656072, 14)`
- `game_18_H2`: `(1612452, 14)`
- `game_24_H1`: `(1580150, 14)`
- `game_24_H2`: `(1712370, 14)`
- `game_47_H1`: `(1622544, 14)`
- `game_47_H2`: `(1733952, 14)`

进一步统计显示：

- 每个 half 的 `unique_frames` 约为 7.1 万到 7.9 万
- `rows_per_frame_avg` 约等于 22

这意味着文件不是“每行一个事件”，而是**每行一个 frame-level player state**；一个 frame 下大约有 22 行，对应球场上的 player-centric 观测记录。

### 6.3 已验证的 14 列顺序

结合 FOOTPASS README 对 `(frame, team, jersey, class)` 的定义、仓库代码约定，以及真实样本值，可以把 14 列按下面顺序读取：

| 列索引 | 字段名 | 含义 |
| --- | --- | --- |
| 0 | `frame` | 帧编号，0-based，但在 match 时间轴上连续，不会每半场归零 |
| 1 | `player_id` | 球员 identity 编号 |
| 2 | `left_to_right` | 当前侧别，`0=left`，`1=right` |
| 3 | `shirt_number` | 球衣号 |
| 4 | `role_id` | tactical role id |
| 5 | `x_pos` | 归一化球场 x 坐标 |
| 6 | `y_pos` | 归一化球场 y 坐标 |
| 7 | `x_speed` | x 方向速度 |
| 8 | `y_speed` | y 方向速度 |
| 9 | `roi_x` | 图像 bbox 左上角 x |
| 10 | `roi_y` | 图像 bbox 左上角 y |
| 11 | `roi_width` | 图像 bbox 宽度 |
| 12 | `roi_height` | 图像 bbox 高度 |
| 13 | `cls` | 事件类别 id，`0` 表示非事件背景 |

这些值在真实样本里表现得很一致：

- `x_pos`, `y_pos` 基本落在 `[0, 1]`
- `roi_*` 是像素级图像框，部分行为 `NaN`，表示该时刻没有可见框
- `left_to_right` 在上下半场会翻转，说明它是**相对于当前画面侧别**，不是持久的 `home/away`

### 6.4 验证 split 事件数

对 `val_tactical_data.h5` 做 `cls > 0` 的计数，得到总事件行数：

- `total_event_rows = 6070`

这与 FOOTPASS README 给出的 validation split 事件总数 **6070** 完全一致。由此可以确认：

- **H5 里的每条 `cls > 0` 行就是一条 player-centric 事件锚点**
- 事件不是单独存成另一张表，而是嵌在 frame-level player state 表里

### 6.5 可见框统计

在当前 validation H5 上：

- 所有行的 bbox 可见率约为 `41.0%`
- 事件行的 bbox 可见率约为 `82.5%`

这与 README 里“81.5% 的 annotated events 有 visible bounding boxes”高度一致，说明我们对 `roi_*` 的解释也是正确的。

### 6.6 角色分布观察

README 定义了 13 个 role id，但在当前 validation 文件中，实际观测到的 role id 是：

- `1, 2, 3, 5, 6, 7, 9, 10, 11, 12, 13`

也就是说，validation 这 3 场比赛中没有出现：

- `4 = Mid Central Back`
- `8 = Defensive Midfielder`

这不代表全数据集没有这两个角色，只说明当前 validation split 的真实比赛覆盖没有碰到它们。

## 7. 标注字段分析与待验证点

### 7.1 已可合理预期的字段能力

结合挑战定义和 FOOTPASS 描述，当前可以把这些字段视为高优先级待验证项：

- 动作标签：事件类别或 ball-related action label
- 时间字段：timestamp、frame、clip-local time 或等价索引
- 执行者字段：player id、actor id 或可追溯 identity
- 队伍字段：team、side、left/right、home/away 之一
- player metadata：jersey、role
- 空间字段：tracking、bbox、pitch coordinate、spatiotemporal payload 之一

### 7.2 当前不能在文档外臆造的部分

在没有实际下载并抽样之前，不应假定：

- 真实字段名一定叫 `player_id`、`jersey`、`bbox_pitch`
- 时间表达一定是 `half + position_ms`
- tactical data 一定只有 JSON，而不是 JSONL、CSV、Parquet 或混合组织

因此实现必须以“字段存在性检查”和“目录结构枚举”为先，而不是先写死 schema。

结合已经验证过的 `val_tactical_data.h5`，其中有一条已经可以去掉不确定性：

- tactical data 的主载体至少包含 HDF5 版本，且当前本地文件不是比赛目录树，而是 `game_xx_Hy -> (N,14)` 的矩阵结构

## 8. 如何读取这份数据

### 8.1 最小可读示例

```python
import h5py

path = r"D:\Code\Event-Classifer-Test\data\soccernet\raw\sn-pcbas-2026\val_tactical_data.h5"

with h5py.File(path, "r") as f:
    print(list(f.keys()))
    arr = f["game_18_H1"][:]
    print(arr.shape)      # 例如 (1656072, 14)
    print(arr.dtype)      # float32
    print(arr[:3])        # 前 3 行原始记录
```

### 8.2 推荐读取方式

建议优先用以下三层口径读取：

1. **结构层**
   - 列出所有 sequence key
   - 检查每个 dataset 是否是 `(N,14)`

2. **统计层**
   - `unique_frames`
   - `rows_per_frame_avg`
   - `cls > 0` 的事件总数
   - `roi_*` 非空比例

3. **事件层**
   - 筛选 `cls > 0`
   - 只保留事件相关行
   - 再把 `frame/player_id/team/jersey/role/position/bbox` 组装成事件表

### 8.3 当前项目里的现成脚本

新增脚本 [inspect_sn_pcbas_h5.py](D:\Code\Event-Classifer-Test\scripts\inspect_sn_pcbas_h5.py) 就是为这个用途准备的。它会：

- 打印根层 key
- 验证 `(N,14)` 结构
- 输出每个 half 的统计摘要
- 抽样打印 `cls > 0` 的事件行

示例：

```bash
python scripts/inspect_sn_pcbas_h5.py
python scripts/inspect_sn_pcbas_h5.py --sequence game_18_H1
python scripts/inspect_sn_pcbas_h5.py --sequence game_18_H1 --sample-event-limit 20
```

## 9. 与当前 pipeline 的字段映射

当前项目想要的中间字段集合大致是：

```json
{
  "match_id": "...",
  "half_or_period": 1,
  "position_ms_or_frame": 12345,
  "action_label": "...",
  "team": "...",
  "player_id": "...",
  "jersey": "...",
  "role": "...",
  "position_payload": {}
}
```

对应关系建议如下：

| pipeline 目标字段 | SN-PCBAS-2026 中应寻找的来源 |
| --- | --- |
| `match_id` | 比赛目录名、game id、metadata 中的 match 标识 |
| `half_or_period` | period、half、clip metadata，或后续 adapter 推导 |
| `position_ms_or_frame` | timestamp / frame index / event position |
| `action_label` | player-centric ball action label |
| `team` | team / side / left-right |
| `player_id` | actor identity / player id |
| `jersey` | jersey / shirt number |
| `role` | role / position type |
| `position_payload` | tracking / bbox / pitch coordinate / spatiotemporal fields |

关键注意事项：

- 若 `team` 只有 `left/right`，不要在下载或 inspect 阶段直接强行映射成 `home/away`。
- `home/away` 与 `left/right` 的桥接仍应留给后续 adapter 或 match-level metadata。
- 当前 H5 中 `frame` 是最稳定的主时间锚点，且在 match 级时间轴上连续；后续如果要转成 `half + position_ms`，应由 adapter 显式完成，不能在读取阶段隐式丢信息。

## 10. 如何做详细分析

拿到 `*_tactical_data.h5` 之后，推荐按下面顺序做详细分析：

1. **结构确认**
   - 根层有多少个 `game_xx_Hy`
   - 每个 dataset 是否都是 `(N,14)`

2. **列语义验证**
   - `x_pos/y_pos` 是否稳定在 `[0,1]`
   - `roi_*` 是否像素级且允许 `NaN`
   - `cls > 0` 计数是否与官方 split 事件数匹配

3. **比赛级统计**
   - 每个 half 的 `unique_frames`
   - 每 half 的 `event_rows`
   - 每 half 的 `event_bbox_ratio`
   - `unique_players`, `unique_jerseys`, `unique_roles`

4. **事件级抽取**
   - 筛选 `cls > 0`
   - 输出 `frame, player_id, left_to_right, shirt_number, role_id, x_pos, y_pos, roi_*, cls`
   - 形成可供 adapter 使用的事件表

5. **跨数据集对照**
   - 与 GSR 对比：位置字段是否能映射到统一 `position_payload`
   - 与 Tracking 对比：bbox 与 player id 连续性是否可对齐
   - 与现有 pipeline 对比：`team/home-away` 桥接、时间锚转换、事件类别映射

## 11. 与 GSR / Tracking / SynLoc 的关系

### 8.1 Game State Reconstruction

`GSR` 的角色不是替代 `SN-PCBAS-2026`，而是位置定义与事件逻辑的对照源：

- `SN-PCBAS-2026` 提供主事件监督
- `GSR` 提供 pitch-level object state 语义
- 二者可用于验证“动作发生时，执行者是否处在合理空间位置”

### 8.2 Tracking

Tracking 更适合作为：

- 缺少 pitch coordinate 时的补充轨迹源
- cross-dataset 的 track/id/bbox 对照源
- 未来做 `Position Provider` 抽象时的第二实现

### 8.3 SynLoc

SynLoc 的作用更偏预训练：

- 训练从 broadcast view 恢复球场空间坐标
- 在没有显式 pitch annotation 的场景下增强位置回归能力

它不替代 `SN-PCBAS-2026` 的事件标签，也不替代 GSR 的结构化状态定义。

## 12. 接入建议

### 9.1 下载层

下载层只负责：

- split 级 zip 下载
- 本地文件摘要
- gated dataset 访问失败的明确报错

不负责：

- 字段转换
- 单场业务索引
- 事件分类逻辑

### 9.2 检查与抽取层

检查层负责：

- 枚举 zip 内结构
- 列出候选 game id 或比赛目录
- 按关键字筛选单场
- 抽样打印字段摘要
- 可选抽取单场成员到 `extracted/`

### 9.3 Adapter 层

后续真正接入 pipeline 时，建议单独实现 `SN-PCBAS adapter`，把原始数据统一转成当前事件分类中间 schema。

最小职责：

- 提取 `match_id`
- 统一时间字段
- 提取动作与执行者
- 保留 team/side 原始值
- 打包位置字段到 `position_payload`

## 13. 对当前项目的直接影响

这条新链路不会替换现有 gamestate 脚本，而是并列存在：

- `scripts/download_gamestate.py` / `inspect_gamestate.py` 继续服务位置增强路线
- 新增 `scripts/download_sn_pcbas.py` / `inspect_sn_pcbas.py` 服务主监督源接入

这样分层的好处是：

- 不把 Hugging Face gated dataset 的逻辑混进现有 SoccerNetDownloader 链路
- 不把下载、抽取、字段转换耦在一起
- 后续若 `SN-PCBAS-2026` 的目录结构与预期不一致，只需调整 inspect/adapter，不必推翻下载层

## 14. 当前结论

如果目标是“真正的动作 + 位置 + 执行者事件划分”，`SN-PCBAS-2026` 是当前最值得优先接入的主数据源。

但实现上应保持清醒：

- 现在最可信的入口是 Hugging Face gated dataset
- 当前最可信的粒度是 split 级 tactical data zip
- 当前最现实的单场能力是本地抽取单场标注，而不是远端直接下载单场

现在还可以把这个判断再收紧一层：

- tactical annotations 的核心工作载体已经确认是 `*_tactical_data.h5`
- validation split 的真实结构已经和 README 中的事件数、可见框统计、player-centric 定义对上
- 因此后续最值得优先做的，不再是继续猜 schema，而是直接写 `H5 -> pipeline intermediate schema` 的 adapter

## 15. 参考来源

- [SoccerNet 2026 Challenges](https://www.soccer-net.org/challenges/2026)
- [FOOTPASS repo](https://github.com/JeremieOchin/FOOTPASS/tree/main)
- [SN-PCBAS-2026 dataset](https://huggingface.co/datasets/SoccerNet/SN-PCBAS-2026)
- [Game State Reconstruction task](https://www.soccer-net.org/tasks/game-state-reconstruction)
- [Tracking task](https://www.soccer-net.org/tasks/tracking)
- [Spiideo SynLoc / sskit repo](https://github.com/Spiideo/sskit)
