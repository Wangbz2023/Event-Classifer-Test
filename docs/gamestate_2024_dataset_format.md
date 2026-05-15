# gamestate-2024 数据集格式分析

本文档分析 SoccerNet Game State Reconstruction 数据集 `gamestate-2024` 的
`Labels-GameState.json` 格式。当前样例来自 `train/SNGS-060/Labels-GameState.json`，
用于后续事件分类、位置增强和多数据集对比分析。

官方依据：

- SoccerNet `sn-gamestate` 仓库 README: <https://github.com/SoccerNet/sn-gamestate>
- SoccerNet Game State Reconstruction Challenge Rules: <https://github.com/SoccerNet/sn-gamestate/blob/main/ChallengeRules.md>

本地样例依据：

- 当前样例文件：`data/soccernet/raw/_task/gamestate/SNGS-060/Labels-GameState.json`
- 项目下载脚本：`scripts/download_required_datasets.py`
- 项目推荐远程路径：`data/soccernet/raw/as2023/_tasks/gamestate-2024/extracted/train/SNGS-060/Labels-GameState.json`

## 1. 数据集概览

SoccerNet Game State Reconstruction, 简称 GSR, 是从单目足球转播视频中恢复比赛状态的任务。官方说明中，GSR 要抽取的高层信息包括：

- 球场上所有运动员的 2D 球场位置。
- 角色分类：`player`、`goalkeeper`、`referee`、`other`。
- 对球员和守门员识别球衣号码。
- 对球员和守门员识别球队侧：相对于相机视角的 `left` 或 `right`。

这些信息可以被渲染成 minimap、radar view 或 bird's-eye view。对本项目来说，GSR 不是主事件源，而是事件分类中的位置增强数据源。

官方 README 明确要求检查 `Labels-GameState.json` 中：

```text
info.version >= 1.3
```

当前样例满足该要求：

| 项目 | 当前样例值 |
| --- | --- |
| sequence name | `SNGS-060` |
| split | `train` |
| `info.version` | `1.3` |
| `info.action_class` | `Kick-off` |
| `info.action_position` | `895` |
| `info.frame_rate` | `25` |
| `info.seq_length` | `750` |
| `info.clip_start` | `0` |
| `info.clip_stop` | `30000` |
| `images` 数量 | `750` |
| `annotations` 数量 | `14290` |
| `object annotations` 数量 | `13540` |
| `pitch annotations` 数量 | `750` |
| `track_id` 范围 | `1..26` |

## 2. 文件层级

官方手动下载示例会得到 `gamestate-2024/{train,valid,test,challenge}.zip`。解压后，每个 split 下包含多个 30 秒片段目录，例如：

```text
gamestate-2024/
└── train/
    └── SNGS-060/
        ├── Labels-GameState.json
        └── img1/
            ├── 000001.jpg
            ├── 000002.jpg
            └── ...
```

在本项目中，`scripts/download_required_datasets.py` 使用：

```python
GAMESTATE_TASK = "gamestate-2024"
GAMESTATE_SPLITS = ["train", "valid", "test", "challenge"]
```

因此默认下载的是 SoccerNet 的 `gamestate-2024` 任务数据，而不是 Action Spotting、Camera、Caption 等其他任务。

`Labels-GameState.json` 中的 `info.im_dir = "img1"` 表示图像帧目录名；`images[*].file_name` 表示该目录下的具体帧文件名。当前样例有 750 帧，`frame_rate = 25`，对应 30 秒 clip。

## 3. 顶层 JSON 结构

`Labels-GameState.json` 是一个 JSON object，当前样例只有 4 个顶层 key：

| 顶层 key | 类型 | 含义 |
| --- | --- | --- |
| `info` | object | 片段级元数据，例如版本、片段 ID、事件类别、时间范围、帧率。 |
| `images` | array[object] | 每一帧图像的元数据，每个元素对应 `img1/` 下的一张图片。 |
| `annotations` | array[object] | 每一帧中的对象标注和球场线标注。 |
| `categories` | array[object] | 类别字典，定义 `category_id` 与类别名称、父类之间的关系。 |

从格式上看，它接近 COCO-style 标注，但为了 GSR 任务扩展了 `attributes`、`bbox_pitch`、`bbox_pitch_raw`、`lines` 等字段。

## 4. `info` 字段

`info` 描述一个 30 秒片段的整体信息。当前样例：

```json
{
  "version": "1.3",
  "game_id": "4",
  "id": "060",
  "num_tracklets": "26",
  "action_position": "895",
  "action_class": "Kick-off",
  "visibility": "visible",
  "game_time_start": "1 - 00:00",
  "game_time_stop": "1 - 00:30",
  "clip_start": "0",
  "clip_stop": "30000",
  "name": "SNGS-060",
  "im_dir": "img1",
  "frame_rate": 25,
  "seq_length": 750,
  "im_ext": ".jpg"
}
```

| key | 类型 | 当前值示例 | 含义 | 使用建议 |
| --- | --- | --- | --- | --- |
| `version` | string | `"1.3"` | 数据集标注版本。官方要求当前数据至少为 `1.3`，因为 v1.3 改进了 `bbox_pitch` 的时间一致性。 | 读取数据时必须检查。低于 `1.3` 的数据不要用于位置增强研究结论。 |
| `game_id` | string | `"4"` | SoccerNet 内部比赛 ID。 | 可作为跨片段关联线索，但不能直接等同于本项目的 `match_id`。 |
| `id` | string | `"060"` | 当前 GSR 片段 ID。 | 通常与 `name = SNGS-060` 后缀一致。 |
| `num_tracklets` | string | `"26"` | 该片段中的轨迹数量。 | 当前样例 `track_id` 范围为 `1..26`。注意该字段是字符串。 |
| `action_position` | string | `"895"` | 片段关联的 SoccerNet action 时间位置，单位通常按毫秒理解。 | 可辅助与 action event 对齐，但不能仅凭该字段完成跨数据集匹配。 |
| `action_class` | string | `"Kick-off"` | 片段关联的动作类别。 | 可与 `Labels-v2.json` 的 `label` 做弱匹配参考。 |
| `visibility` | string | `"visible"` | 关联动作在视频中的可见性。 | 可与 Action Spotting 的 `visibility` 比较，但二者来源不同。 |
| `game_time_start` | string | `"1 - 00:00"` | 片段开始的比赛时间，格式为 `half - mm:ss`。 | 对齐时需解析 half 和半场内时间。 |
| `game_time_stop` | string | `"1 - 00:30"` | 片段结束的比赛时间。 | 当前样例正好覆盖上半场第 0 到 30 秒。 |
| `clip_start` | string | `"0"` | 片段内起始毫秒。 | 当前样例为字符串形式，需要转整数。 |
| `clip_stop` | string | `"30000"` | 片段内结束毫秒。 | 与 `seq_length / frame_rate = 750 / 25 = 30s` 一致。 |
| `name` | string | `"SNGS-060"` | 片段目录名。 | 可作为 GSR clip ID。 |
| `im_dir` | string | `"img1"` | 图像帧目录。 | 与 `images[*].file_name` 拼接得到帧路径。 |
| `frame_rate` | number | `25` | 帧率，单位 fps。 | 可用帧序号换算为片段内时间。 |
| `seq_length` | number | `750` | 片段帧数。 | 当前样例与 `images.length` 一致。 |
| `im_ext` | string | `".jpg"` | 图像扩展名。 | 用于校验 `images[*].file_name`。 |

## 5. `images` 字段

`images` 是帧级元数据数组。当前样例有 750 个元素，每个元素结构一致。第一帧示例：

```json
{
  "is_labeled": true,
  "image_id": "1060000001",
  "file_name": "000001.jpg",
  "height": 1080,
  "width": 1920,
  "has_labeled_person": true,
  "has_labeled_pitch": true,
  "has_labeled_camera": true,
  "ignore_regions_y": [],
  "ignore_regions_x": []
}
```

| key | 类型 | 当前值示例 | 含义 | 使用建议 |
| --- | --- | --- | --- | --- |
| `is_labeled` | boolean | `true` | 该帧是否有标注。 | 如果为 `false`，下游应跳过该帧或标记不可用。 |
| `image_id` | string | `"1060000001"` | 帧 ID。 | 与 `annotations[*].image_id` 连接。当前样例范围为 `1060000001..1060000750`。 |
| `file_name` | string | `"000001.jpg"` | 帧图片文件名。 | 与 `info.im_dir` 拼接为 `img1/000001.jpg`。 |
| `height` | number | `1080` | 图像高度，像素。 | 解释 `bbox_image` 时使用。 |
| `width` | number | `1920` | 图像宽度，像素。 | 解释 `bbox_image` 时使用。 |
| `has_labeled_person` | boolean | `true` | 是否有人物标注。 | GSR 的对象级标注可用性标志。 |
| `has_labeled_pitch` | boolean | `true` | 是否有球场线标注。 | 若为 `false`，该帧不应依赖 `pitch` annotation。 |
| `has_labeled_camera` | boolean | `true` | 是否有相机/标定相关标注。 | 当前样例标志为 true，但 `annotations` 中没有 `camera` 类标注。 |
| `ignore_regions_x` | array | `[]` | 图像中需要忽略区域的 x 范围。 | 当前样例为空。若非空，训练或评估时应排除这些区域。 |
| `ignore_regions_y` | array | `[]` | 图像中需要忽略区域的 y 范围。 | 当前样例为空。需与 `ignore_regions_x` 配合解释。 |

## 6. `annotations` 字段总览

`annotations` 是最重要的数据区。当前样例总计 14290 条标注，分为两种实际出现的 `supercategory`：

| `supercategory` | 数量 | 含义 |
| --- | ---: | --- |
| `object` | `13540` | 球员、守门员、裁判、球等对象。 |
| `pitch` | `750` | 每帧球场线的图像归一化坐标。 |

当前样例中没有实际 `camera` annotation，但 `categories` 中保留了 `camera` 类别，说明该 schema 预留了相机标定相关类别。

### 6.1 `object` annotation

对象标注示例：

```json
{
  "id": "1060000001",
  "image_id": "1060000001",
  "track_id": 1,
  "supercategory": "object",
  "category_id": 1,
  "attributes": {
    "role": "player",
    "jersey": "10",
    "team": "left"
  },
  "bbox_image": {
    "x": 914,
    "y": 855,
    "x_center": 941.5,
    "y_center": 941,
    "w": 55,
    "h": 172
  },
  "bbox_pitch": {
    "x_bottom_left": -0.8043577233367065,
    "y_bottom_left": 24.095541188956325,
    "x_bottom_right": 0.19365378518930804,
    "y_bottom_right": 24.10328518536706,
    "x_bottom_middle": -0.3053155494888499,
    "y_bottom_middle": 24.100111551334564
  },
  "bbox_pitch_raw": {
    "x_bottom_left": -0.5618667663373333,
    "y_bottom_left": 24.046080743490077,
    "x_bottom_right": 0.0073212402595505275,
    "y_bottom_right": 24.050080078959525,
    "x_bottom_middle": -0.2772623829267213,
    "y_bottom_middle": 24.048314011381127
  }
}
```

| key | 类型 | 含义 | 使用建议 |
| --- | --- | --- | --- |
| `id` | string | 标注 ID。当前样例为字符串。 | 只作为 annotation 唯一标识，不要当作数值时间。 |
| `image_id` | string | 所属帧 ID。 | 与 `images[*].image_id` 关联。 |
| `track_id` | number | 跨帧轨迹 ID。 | 用于同一对象的时序追踪。当前样例为 `1..26`。 |
| `supercategory` | string | 父类别。对象标注为 `object`。 | 用它区分对象标注和球场线标注。 |
| `category_id` | number | 类别 ID。 | 需通过 `categories` 解释。对象类别常见为 1 到 4。 |
| `attributes` | object | 对象身份属性。 | GSR 评价中身份匹配高度依赖该字段。 |
| `bbox_image` | object | 图像像素坐标系中的检测框。 | 用于图像空间可视化，不是我们判断进攻半场的首选字段。 |
| `bbox_pitch` | object | 球场坐标系中的位置投影。 | 本项目位置增强优先使用该字段。 |
| `bbox_pitch_raw` | object | 原始或未平滑版本的球场投影。 | 可用于调试标定差异，但默认不作为事件分类主位置来源。 |

### 6.2 `attributes`

| key | 类型 | 当前样例取值 | 含义 | 可空性和注意事项 |
| --- | --- | --- | --- | --- |
| `role` | string | `player`、`goalkeeper`、`referee`、`ball` | 对象角色。 | `pitch` annotation 没有该字段。官方挑战规则要求预测中包含 `role`。 |
| `jersey` | string | `"10"`、`"30"` 等 | 球衣号码。 | 球、裁判等非球员对象通常没有有效球衣号；当前样例中大量对象没有 `jersey`。 |
| `team` | string | `left`、`right` | 球队侧，相对于相机视角。 | 不是 `home/away`。球、裁判等对象通常没有 `team`。 |

官方 README 和挑战规则都强调，GSR 的队伍侧是 `left/right`，而本项目 Action Spotting 的事件队伍字段是 `home/away/not applicable`。因此二者不能直接等同。做事件分类位置增强时，必须额外维护：

```json
{
  "match_id": "...",
  "home_team_side_by_half": {
    "1": "left",
    "2": "right"
  }
}
```

当前样例字段分布：

| 字段 | 观察结果 |
| --- | --- |
| `role=player` | `11079` |
| `role=goalkeeper` | `288` |
| `role=referee` | `1439` |
| `role=ball` | `734` |
| `team=left` | `5629` |
| `team=right` | `5738` |
| 无 `team` | `2923` |

### 6.3 `bbox_image`

`bbox_image` 是图像像素坐标系中的检测框：

| key | 类型 | 含义 | 当前样例范围 |
| --- | --- | --- | --- |
| `x` | number | 检测框左上角 x 坐标，像素。 | `0..1907` |
| `y` | number | 检测框左上角 y 坐标，像素。 | `189..1040` |
| `x_center` | number | 检测框中心 x 坐标，像素。 | `5..1913` |
| `y_center` | number | 检测框中心 y 坐标，像素。 | `213..1059` |
| `w` | number | 检测框宽度，像素。 | `9..141` |
| `h` | number | 检测框高度，像素。 | `7..185` |

注意：`bbox_image` 描述的是 2D 画面中的人或球框位置，它受镜头角度、透视、缩放影响。我们判断“是否处于进攻半场”时不应该使用它。

### 6.4 `bbox_pitch`

`bbox_pitch` 是对象从图像投影到球场坐标系后的落点，单位按官方评价说明理解为米。官方 GS-HOTA 的定位相似度使用 pitch coordinate system 中的欧氏距离，并使用 5 米容忍参数。

| key | 类型 | 含义 | 当前样例范围 |
| --- | --- | --- | --- |
| `x_bottom_left` | number | 图像检测框底部左点投影到球场后的 x 坐标。 | - |
| `y_bottom_left` | number | 图像检测框底部左点投影到球场后的 y 坐标。 | - |
| `x_bottom_right` | number | 图像检测框底部右点投影到球场后的 x 坐标。 | - |
| `y_bottom_right` | number | 图像检测框底部右点投影到球场后的 y 坐标。 | - |
| `x_bottom_middle` | number | 图像检测框底部中点投影到球场后的 x 坐标。 | `-81.99..45.95` |
| `y_bottom_middle` | number | 图像检测框底部中点投影到球场后的 y 坐标。 | `-57.87..35.01` |

本项目后续位置增强应优先使用：

```text
bbox_pitch.x_bottom_middle
bbox_pitch.y_bottom_middle
```

原因是它们直接表示对象脚下或球场接地点的中心位置，比图像框中心点更适合判断球员在球场中的空间状态。

### 6.5 `bbox_pitch_raw`

`bbox_pitch_raw` 与 `bbox_pitch` 字段形状相同，但当前样例中并非所有对象都有该字段。当前样例：

| 字段组 | 有效数量 |
| --- | ---: |
| `bbox_pitch` | `13540` |
| `bbox_pitch_raw` | `13508` |

官方 README 提到 v1.3 更新了 `bbox-pitch annotations` 以提升时间一致性。因此在研究和业务逻辑中，默认应使用 `bbox_pitch`；`bbox_pitch_raw` 更适合用于排查平滑、标定或版本差异。

### 6.6 `pitch` annotation

`pitch` annotation 用于描述每帧可见球场线在图像中的位置。当前样例每帧有 1 条 `pitch` annotation，共 750 条。

示例结构：

```json
{
  "id": "1060000019",
  "image_id": "1060000001",
  "supercategory": "pitch",
  "category_id": 5,
  "lines": {
    "Side line top": [
      {"x": 0, "y": 0.2940777777777778},
      {"x": 0.4890421875, "y": 0.2992666666666666}
    ],
    "Middle line": [
      {"x": 0.5051244791666667, "y": 0.9998490740740741}
    ],
    "Circle central": [
      {"x": 0.5028666666666667, "y": 0.6326796296296298}
    ]
  }
}
```

| key | 类型 | 含义 |
| --- | --- | --- |
| `id` | string | 球场线标注 ID。 |
| `image_id` | string | 所属帧 ID。 |
| `supercategory` | string | 固定为 `pitch`。 |
| `category_id` | number | 固定为 `5`，对应 `categories` 中的 `pitch`。 |
| `lines` | object | 每条可见球场线的点序列。 |

`lines` 中的点使用归一化图像坐标，`x` 和 `y` 通常落在 `[0, 1]` 附近。当前样例第一帧包含：

- `Side line top`
- `Middle line`
- `Circle central`

这些球场线适合用于相机标定、可视化或检查投影质量；本项目事件分类的第一版不直接依赖它们。

## 7. `categories` 字段

`categories` 是类别定义。当前样例完整类别表如下：

| `id` | `supercategory` | `name` | 当前样例实际出现数量 | 说明 |
| ---: | --- | --- | ---: | --- |
| `1` | `object` | `player` | `11079` | 普通球员。 |
| `2` | `object` | `goalkeeper` | `288` | 守门员。 |
| `3` | `object` | `referee` | `1439` | 裁判。 |
| `4` | `object` | `ball` | `734` | 足球。 |
| `5` | `pitch` | `pitch` | `750` | 球场线标注。 |
| `6` | `camera` | `camera` | `0` | schema 保留的相机类，当前样例未实际出现。 |
| `7` | `object` | `other` | `0` | schema 保留的其他对象类，当前样例未实际出现。 |

`category_id` 必须通过 `categories` 映射解释，不要在代码中只写死 `1=player`。不过在官方挑战提交格式中，预测 detection 的 `supercategory` 应为 `object`，`category_id` 设置为 `1.0`，其他类别被官方评价忽略。

## 8. 与事件分类任务的连接

本项目最终任务是从 SoccerNet Action Spotting 的 `Labels-v2.json` 生成 A/B/C/D event。GSR 数据只用于位置增强，不能替代主事件源。

推荐连接流程：

1. 从 `Labels-v2.json` 读取 action event，得到 `(match_id, half, position_ms, action_label, team)`。
2. 从 GSR 片段读取 `info.game_time_start`、`info.game_time_stop`、`info.action_position`、`info.action_class`，建立片段级索引。
3. 对候选 action event，查找同 half 且时间窗口重叠或最近的 GSR clip。
4. 在 GSR clip 内，根据 `frame_rate` 和 clip 时间范围找到最近帧。
5. 在该帧的 `object` annotations 中筛选 `attributes.role in {"player", "goalkeeper"}`。
6. 通过 `home_team_side_by_half` 把 action event 的 `home/away` 映射到 GSR 的 `left/right`。
7. 使用匹配侧球员的 `bbox_pitch.x_bottom_middle` 判断是否位于进攻半场。

本项目应优先使用以下字段：

| 目标 | 推荐字段 |
| --- | --- |
| 帧时间换算 | `info.frame_rate`、`images[*].file_name`、`images[*].image_id` |
| 片段时间范围 | `info.game_time_start`、`info.game_time_stop`、`info.clip_start`、`info.clip_stop` |
| 球员轨迹 | `annotations[*].track_id` |
| 角色筛选 | `annotations[*].attributes.role` |
| 队伍侧 | `annotations[*].attributes.team` |
| 球场空间位置 | `annotations[*].bbox_pitch.x_bottom_middle`、`annotations[*].bbox_pitch.y_bottom_middle` |

不建议直接使用以下字段做最终 event 分类判断：

| 字段 | 原因 |
| --- | --- |
| `bbox_image` | 受镜头透视影响，是图像坐标，不是球场空间坐标。 |
| `bbox_pitch_raw` | 可能缺失，且 v1.3 的重点是改进后的 `bbox_pitch`。 |
| `attributes.team` | 只是 `left/right`，不能直接等同于 `home/away`。 |
| `info.action_class` | 可辅助匹配，但不能替代 `Labels-v2.json` 的主事件标签。 |

## 9. 数据质量和注意事项

### 9.1 版本

官方 README 明确提醒当前数据集版本为 `v1.3`，并要求检查：

```text
Labels-GameState.json -> info -> version >= 1.3
```

低版本数据可能存在队伍侧或 `bbox_pitch` 时间一致性问题，不应混入当前研究结论。

### 9.2 可空字段

当前样例中，非球员对象经常没有 `team` 或 `jersey`：

- 裁判没有 `team` 和 `jersey`。
- 球没有 `team` 和 `jersey`。
- `pitch` annotation 没有 `attributes`、`bbox_image`、`bbox_pitch`。

因此代码中必须按 `supercategory` 和 `category_id` 先区分类型，再读取嵌套字段。

### 9.3 与目标比赛的覆盖关系

Game State Reconstruction 是独立任务数据集，它是 30 秒主镜头片段集合，不保证与本项目当前样例比赛 `Chelsea vs Burnley` 完全重叠。

如果 `scripts/inspect_gamestate.py` 没有找到目标比赛的路径级匹配，应将该场比赛的位置增强状态记为：

```json
{
  "position_status": "missing",
  "position_enhanced": false
}
```

### 9.4 官方评价约束

官方 Challenge Rules 说明，预测 detection 需要包含：

- `category_id`
- `image_id`
- `track_id`
- `supercategory`
- `confidence`
- `attributes.role`
- `attributes.jersey`
- `attributes.team`
- `bbox_pitch.x_bottom_middle`
- `bbox_pitch.y_bottom_middle`

这说明 GSR 的评价重点是球场位置和身份属性，而不是图像框。因此，本项目做位置增强时也应围绕 `bbox_pitch` 和 `attributes` 设计接口。

## 10. 后续多数据集分析模板

之后分析 Action Spotting、Dense Video Captioning、Camera Shot Segmentation 或其他 SoccerNet 数据集时，建议沿用以下模板，便于横向对比。

### 10.1 基本信息

| 项目 | 内容 |
| --- | --- |
| 数据集名称 | 例如 `gamestate-2024` |
| 官方来源 | GitHub / SoccerNet task 页面 / paper |
| 下载脚本 | 本项目中的脚本路径 |
| 下载 split | `train/valid/test/challenge` 或其他 |
| 样例文件 | 用于实证分析的本地文件 |
| 版本字段 | 数据集内部版本或发布日期 |

### 10.2 文件和目录结构

说明下载后的目录、核心 JSON、视频/图片文件、额外资源目录，以及它们之间的引用关系。

### 10.3 顶层 schema

列出所有顶层 key、类型、语义、是否必需、是否在当前样例中出现。

### 10.4 字段逐项解释

对每个嵌套 key 建立字段表：

| 字段 | 类型 | 示例 | 含义 | 可空性 | 下游用途 |
| --- | --- | --- | --- | --- | --- |

### 10.5 时间和坐标系统

必须明确：

- 时间单位是毫秒、帧号、半场内时间，还是全场绝对时间。
- 坐标是图像像素坐标、归一化图像坐标，还是球场米制坐标。
- 是否需要跨数据集映射，例如 `left/right` 到 `home/away`。

### 10.6 与最终任务的接口

明确该数据集在最终 event classification 中扮演的角色：

- 主标签源
- 上下文证据
- 位置增强
- 可视化/调试
- 训练辅助

### 10.7 限制和风险

记录数据不完整、版本差异、字段可空、时间无法对齐、任务定义不一致等风险，并给出降级策略。

## 11. 对本项目的结论

对 `gamestate-2024 train/SNGS-060`，我们可以确认：

- `Labels-GameState.json` 的核心顶层结构是 `info/images/annotations/categories`。
- 当前样例是 30 秒、25 fps、750 帧的 GSR clip。
- 对象位置增强应读取 `bbox_pitch.x_bottom_middle/y_bottom_middle`。
- 球队侧字段是 `left/right`，必须通过每半场配置映射到 `home/away`。
- `bbox_image` 只适合图像空间可视化，不适合直接判断进攻半场。
- `bbox_pitch_raw` 可用于调试，但默认不作为位置增强主字段。
- 若无法确认 GSR clip 与目标 Action Spotting 比赛重叠，应降级为弱标注并记录 `position_status=missing`。
