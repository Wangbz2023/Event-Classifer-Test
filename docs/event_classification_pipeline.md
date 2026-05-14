# Event Classification Pipeline

本文档解释本项目为什么需要这些脚本、每个数据处理模块的输入和输出是什么，以及 A/B/C/D event 的具体划分规则。目标是让事件划分代码在开始实现前就有清楚的数据契约，避免后续脚本“能跑但看不懂”。

## 目录约定

项目只使用一个 SoccerNet 原始数据根目录：

```text
D:\Code\event-classification-test\data\soccernet\raw\as2023
```

单场比赛目录继续遵循 README 里的规范：

```text
data/soccernet/raw/as2023/
└── england_epl/
    └── 2014-2015/
        └── 2015-02-21 - 18-00 Chelsea 1 - 1 Burnley/
            ├── Labels-v2.json
            ├── Labels-caption.json
            ├── Labels-cameras.json
            ├── video.ini
            ├── 1.mkv
            └── 2.mkv
```

Game State Reconstruction 不是按这场比赛天然存放的，所以先作为 task 数据集放在：

```text
data/soccernet/raw/as2023/
└── _tasks/
    └── gamestate-2024/
        ├── train.zip
        ├── valid.zip
        ├── test.zip
        ├── challenge.zip
        └── extracted/        # 只有运行检查脚本 --extract 时才会生成
```

## 脚本目的

### `scripts/download_gamestate.py`

目的：只下载 SoccerNet Game State Reconstruction 数据集，给后续 event 位置增强规则提供球员、球队和球场坐标。

输入：

- `--data-root`：SoccerNet 数据根目录，默认是 `data/soccernet/raw/as2023`。
- `--splits`：需要下载的 split，默认是 `train valid test challenge`。
- `--password`：SoccerNet 公共数据密码，默认是 `SoccerNet`。

处理：

- 创建 `data/soccernet/raw/as2023/_tasks/`。
- 调用 `SoccerNetDownloader.downloadDataTask(task="gamestate-2024", split=[...])`。
- 不下载 tracking、calibration、reid、jersey 等其他任务。

输出：

- `data/soccernet/raw/as2023/_tasks/gamestate-2024/train.zip`
- `data/soccernet/raw/as2023/_tasks/gamestate-2024/valid.zip`
- `data/soccernet/raw/as2023/_tasks/gamestate-2024/test.zip`
- `data/soccernet/raw/as2023/_tasks/gamestate-2024/challenge.zip`

### `scripts/inspect_gamestate.py`

目的：检查 Game State Reconstruction 是否下载成功、是否能读到 `Labels-GameState.json`、样例字段是否包含位置增强需要的内容，并粗略扫描是否有当前 Chelsea vs Burnley 比赛的路径级匹配。

输入：

- `--data-root`：SoccerNet 数据根目录，默认是 `data/soccernet/raw/as2023`。
- `--splits`：需要检查的 split，默认是 `train valid test challenge`。
- `--extract`：可选。提供后会把 zip 解压到 `_tasks/gamestate-2024/extracted/<split>/`。
- `--sample-limit`：抽样读取多少个 `Labels-GameState.json`，默认 3。
- `--match-query`：路径级匹配关键字，默认 `2015-02-21 Chelsea Burnley`。

处理：

- 检查每个 split 的 zip 是否存在。
- 可选解压 zip。
- 在解压目录和 zip 内部查找 `Labels-GameState.json`。
- 抽样读取 JSON，并打印是否存在 `bbox_pitch`、`team`、`role`、`jersey`、`track_id` 等字段。
- 用文件路径和 zip member 名称扫描目标比赛关键字。

输出：

- 终端打印 archive status。
- 终端打印 `Labels-GameState.json` 候选数量。
- 终端打印 JSON 样例摘要。
- 终端打印目标比赛路径级匹配结果。

注意：路径级匹配只是快速筛查。没有路径匹配不等于一定没有时间重叠，只能说明没有明显文件名证据。

## 数据字段含义

### `Labels-v2.json`

用途：Action Spotting 主事件源，是 A/B/C/D event 的主锚点。

顶层字段：

- `UrlLocal`：本地视频源信息。
- `UrlYoutube`：YouTube 视频源信息。
- `gameHomeTeam`：主队名称。
- `gameAwayTeam`：客队名称。
- `gameDate`：比赛日期。
- `gameScore`：比分。
- `annotations`：事件列表。

`annotations` 中的字段：

- `gameTime`：形如 `1 - 04:30`，表示第几半场和该半场内的分秒。
- `position`：半场内毫秒级时间戳，不是球员空间位置。例如 `1 - 02:29` 对应约 `149000ms`。
- `label`：17 类 Action Spotting 事件标签。
- `team`：事件所属队伍，可能是 `home`、`away`、`not applicable`。
- `visibility`：事件在画面中是否可见，常见为 `visible`、`not shown`。

### `Labels-cameras.json`

用途：镜头上下文，不作为事件分类主标签。

顶层字段与比赛元信息类似。

`annotations` 中的字段：

- `gameTime`：镜头切换发生的半场时间。
- `position`：半场内毫秒级时间戳。
- `label`：镜头类型，例如 `Main camera center`、`Close-up player or field referee`。
- `change_type`：镜头切换类型，例如 `abrupt`。
- `replay`：是否是回放，常见为 `real-time`、`replay`。

使用方式：

- 不能要求 camera timestamp 与 action timestamp 完全相等。
- 把每条 camera annotation 看作一个镜头段起点。
- 对一个 action event，取同半场中最后一个 `camera.position <= event.position` 的 camera 作为当时镜头上下文。

### `Labels-caption.json`

用途：稀疏文本解说证据，可辅助验证事件语义，不作为硬分类主标签。

顶层字段：

- `timestamp`：caption 数据生成或导出时间。
- `score`、`round`、`teams`、`lineup`、`referee`、`venue`、`attendance`：比赛信息。
- `home`、`away`：主客队结构化信息。
- `gameHomeTeam`、`gameAwayTeam`、`gameDate`：比赛元信息。
- `annotations`：解说片段列表。

`annotations` 中的字段：

- `important`：是否重要。
- `gameTime`：解说对应的半场时间。
- `position`：半场内毫秒级时间戳。
- `label`：解说类别，可能为空，也可能是 `corner`、`injury`、`y-card` 等。
- `description`：原始解说文本。
- `identified`：带实体占位符的文本。
- `anonymized`：匿名化文本。
- `visibility`：该描述是否在画面或解说中出现。

使用方式：

- Caption 是稀疏文本，不适合按同一秒强行对齐。
- 对 action event，可取同半场 `±15s` 内 caption 作为语义证据。
- 调试时可以保留 `±30s` 的候选 caption 列表。

### `Labels-GameState.json`

用途：位置增强。Game State Reconstruction 提供球员、裁判、球和球队在球场上的结构化状态。

常见顶层字段：

- `info`：数据集版本和元信息。
- `images`：帧或图像列表。
- `annotations`：每个目标在图像/球场中的标注。
- `categories`：类别定义。

`annotations` 中位置增强最关心的字段：

- `image_id`：该目标属于哪一帧或图像。
- `track_id`：跨帧跟踪 ID。
- `bbox_image`：图像坐标系中的检测框。
- `bbox_pitch`：球场坐标系中的位置。事件划分优先使用 `x_bottom_middle` 和 `y_bottom_middle`。
- `attributes.role`：目标角色，例如 player、goalkeeper、referee、ball。
- `attributes.team`：球队侧，通常是 `left` 或 `right`，不是天然的 `home` 或 `away`。
- `attributes.jersey`：球衣号码。

使用方式：

- `bbox_pitch` 才是空间位置来源。
- `team left/right` 需要通过每场每半场配置映射到 `home/away`。
- Game State 数据是 30 秒主镜头片段，不保证与当前 Action Spotting 单场比赛完全重叠。

## 时间对齐规则

所有 SoccerNet 事件标注先统一成：

```text
(match_id, half, position_ms)
```

规则：

- `half` 从 `gameTime` 左侧解析，例如 `1 - 04:30` 的 half 是 `1`。
- `position_ms` 从 `position` 读取并转成整数。
- `position_ms` 是半场内部时间，不是全场绝对时间。
- 第一半场和第二半场相同的 `position_ms` 不能混在一起，必须带 `half`。

三份 as2023 标签对齐方式：

- `Labels-v2.json`：主事件表，一条 annotation 生成一条候选 event。
- `Labels-cameras.json`：按镜头段对齐，取同半场最后一个 `camera.position <= event.position`。
- `Labels-caption.json`：按时间窗口对齐，取同半场 `abs(caption.position - event.position) <= 15000` 的 caption。

## 数据处理模块输入输出

### 模块 1：Action Event Loader

输入：

- 单场目录中的 `Labels-v2.json`。

输出：

```json
{
  "match_id": "england_epl/2014-2015/2015-02-21 - 18-00 Chelsea 1 - 1 Burnley",
  "half": 1,
  "position_ms": 270441,
  "game_time": "1 - 04:30",
  "action_label": "Shots on target",
  "team": "home",
  "visibility": "visible"
}
```

### 模块 2：Camera Context Joiner

输入：

- Action Event Loader 的输出。
- 同场目录中的 `Labels-cameras.json`。

输出：在 action event 上追加 camera context。

```json
{
  "camera_label": "Main camera center",
  "camera_replay": "real-time",
  "camera_age_ms": 7240
}
```

### 模块 3：Caption Evidence Joiner

输入：

- Action Event Loader 的输出。
- 同场目录中的 `Labels-caption.json`。

输出：在 action event 上追加 caption evidence。

```json
{
  "caption_window_ms": 15000,
  "caption_evidence": [
    {
      "position_ms": 667000,
      "label": "",
      "description": "..."
    }
  ]
}
```

### 模块 4：Game State Position Joiner

输入：

- Action Event Loader 的输出。
- Game State Reconstruction 片段索引。
- 每场每半场的 `home_team_side_by_half` 配置。

输出：在 action event 上追加位置增强字段。

```json
{
  "position_status": "matched",
  "position_enhanced": true,
  "acting_team_pitch_side": "left",
  "acting_team_attack_direction": "right",
  "in_attacking_half": true,
  "nearest_gamestate_frame": {
    "frame_id": "example_frame",
    "delta_ms": 320
  }
}
```

若没有匹配到 Game State：

```json
{
  "position_status": "missing",
  "position_enhanced": false
}
```

### 模块 5：Event Classifier

输入：

- Action Event Loader 的基础字段。
- 可选 camera context。
- 可选 caption evidence。
- 可选 Game State 位置增强字段。

输出：

```json
{
  "event_type": "A-event",
  "event_rule": "weak_team_home",
  "position_status": "missing",
  "position_enhanced": false
}
```

## Event 划分规则

### 主事件源

`Labels-v2.json` 是唯一主事件源。Camera 和 caption 只提供上下文或证据，不能覆盖 `Labels-v2.json` 的主事件时间轴。

### event-D

以下 label 一律划为 `event-D`：

- `Penalty`

### event-C

以下 label 一律划为 `event-C`：

- `Foul`
- `Yellow card`
- `Red card`
- `Yellow->red card`
- `Substitution`
- `Ball out of play`

此外，如果 A/B 候选动作的 `team` 是 `not applicable`，也划为 `event-C`。

### A/B 候选动作

以下 label 可以进入 A/B 判断：

- `Kick-off`
- `Goal`
- `Offside`
- `Shots on target`
- `Shots off target`
- `Clearance`
- `Throw-in`
- `Indirect free-kick`
- `Direct free-kick`
- `Corner`

弱标注规则：

- `team=home` -> `A-event`
- `team=away` -> `B-event`
- `team=not applicable` -> `event-C`

### 位置增强规则

当存在可匹配的 Game State 数据时，A/B 候选动作要额外验证行动队是否处于进攻半场。

需要配置：

```json
{
  "match_id": "england_epl/2014-2015/2015-02-21 - 18-00 Chelsea 1 - 1 Burnley",
  "home_team_side_by_half": {
    "1": "left",
    "2": "right"
  }
}
```

解释：

- Game State 的 `team` 通常是 `left/right`。
- Action Spotting 的 `team` 是 `home/away/not applicable`。
- 二者不能直接等同，必须通过每场每半场配置映射。
- 足球上下半场通常换边，所以这个映射必须按 half 保存。

位置判断：

- 如果行动队为 `home`，先通过配置找到该半场主队是 `left` 还是 `right`。
- 如果行动队为 `away`，使用相反侧。
- 取最近 Game State 帧中行动队 player 的 `bbox_pitch.x_bottom_middle`。
- 如果该队进攻方向为右侧，则 `x_bottom_middle` 大于球场中线时认为在进攻半场。
- 如果该队进攻方向为左侧，则 `x_bottom_middle` 小于球场中线时认为在进攻半场。

输出要求：

- 成功匹配并通过位置验证：`position_enhanced=true`，`position_status=matched`。
- 没有 Game State 匹配：`position_enhanced=false`，`position_status=missing`，保留弱标注结果。
- 有 Game State 但无法判断方向或坐标：`position_enhanced=false`，`position_status=ambiguous`。

## 当前限制

- 当前已知的 Chelsea vs Burnley 单场目录只有 `Labels-v2.json`、`Labels-cameras.json`、`Labels-caption.json`，没有 Game State 文件。
- Game State Reconstruction 是独立任务数据集，不保证包含这场比赛。
- 如果检查脚本没有找到这场比赛的路径级匹配，则当前这场比赛只能先输出弱标注，不能声称已经满足“球员位置”条件。

## 推荐执行顺序

1. 下载 Game State Reconstruction：

```bash
C:\Users\Scott\.conda\envs\streamsoccer-s0\python.exe scripts\download_gamestate.py
```

2. 检查下载内容和样例字段：

```bash
C:\Users\Scott\.conda\envs\streamsoccer-s0\python.exe scripts\inspect_gamestate.py
```

3. 如果需要把 zip 解压出来：

```bash
C:\Users\Scott\.conda\envs\streamsoccer-s0\python.exe scripts\inspect_gamestate.py --extract
```

4. 若检查结果显示没有 Chelsea vs Burnley 匹配，则不要对这场比赛启用强位置规则，只输出弱标注并记录 `position_status=missing`。
