# SoccerNet 2026 数据集分析与事件划分适配性评估

本文档面向当前 [event_classification_pipeline.md](D:\Code\Event-Classifer-Test\docs\event_classification_pipeline.md) 所定义的任务: 基于足球直播流，结合动作标签与空间位置信息，完成 A/B/C/D 事件划分。目标不是泛泛罗列 SoccerNet 2026 挑战，而是判断哪些数据集适合充当主数据源、位置增强源、训练迁移源，哪些只适合作为旁路子模块。

本文档只做选型和设计支持，不在这一轮下载大体量数据集，也不修改现有 pipeline 代码。

## 1. 任务需求基线

当前 pipeline 对数据的最低需求不是单一的 `event timestamp`，而是以下字段组合:

| 维度 | 当前需求 |
| --- | --- |
| 动作时间锚点 | `match_id`, `half`, `position_ms` |
| 动作标签 | `action_label` |
| 队伍归属 | `team`，至少能区分 `home/away` 或可映射的 `left/right` |
| 空间信息 | 至少一类可对齐的位置表示: `bbox`、`tracklet`、`pitch coordinate` |
| 执行动作主体 | 最好能提供 player identity、jersey 或稳定 track id |
| 广播流上下文 | 最好来自全场直播流，而不是单帧静态图或纯合成数据 |

据此，候选数据集应按四档看待:

- 最适配: 同时提供动作、时间、执行者、队伍、位置。
- 可补强: 提供位置、检测、追踪或球场坐标，但不提供完整动作标签。
- 动作源但位置不足: 提供事件标签和时间，但空间信息不够。
- 基本不适配主任务: 可支持别的子任务，但不能直接服务当前事件划分主链路。

## 2. SoccerNet 2026 六个挑战概览

### 2.1 SynLoc

- 2026 挑战页将 SynLoc 定义为单帧世界坐标检测与定位任务: 检测所有球员并预测其球场位置，使用 synthetic + real broadcast data，评价指标为 `mAP-LocSim`。
- `sskit` 开发包说明其数据可通过 `SoccerNetDownloader.downloadDataTask(task="SpiideoSynLoc", ...)` 下载，结果以 COCO 风格存储，并用 `position_on_pitch` 表示以米为单位的 3D 球场坐标。
- 这类数据是位置监督数据，不是事件监督数据。它能训练“从广播画面恢复球场世界坐标”的模块，但不能直接训练 A/B/C/D 事件分类器。

### 2.2 Ball Action Anticipation

- 2026 挑战页说明该任务要求预测未来 5 秒内将发生的球相关动作的时间和类型，输入是 anticipation window 之前的 30 秒 gameplay video，类别数为 10。
- `ActionAnticipation` 数据集说明它来自 SoccerNet Ball Action Spotting 2024 数据集的 30 秒滑窗切分，重点是未来动作预测，不是当前时刻动作归因。
- 这套数据对预判或提前告警有价值，但对当前 pipeline 的事件划分主任务并不直接，因为我们要做的是对已发生动作进行分型与位置增强，而不是未来动作 anticipation。

### 2.3 VQA

- 2026 VQA 数据集是多模态多选问答，覆盖 14 个足球理解任务，训练/验证集约 10k QA 对，材料包含文本、图片和视频。
- 每条样本的核心字段是问题 `Q`、素材路径 `materials`、选项 `O1...O4`，评价指标是准确率。
- 这类数据有助于构建高层语义问答或 agent 系统，但不提供可直接消费的事件时间轴、执行者轨迹或球场位置。

### 2.4 Player-Centric Ball Action Spotting

- 2026 挑战页明确说明该任务不仅要识别“何时发生什么”，还要识别“是谁做的”。
- FOOTPASS 仓库将其定义为首个 player-centric、multi-modal、multi-agent 的逐回合动作 spotting 数据集，并明确强调其对齐了 broadcast video、player-centric ball-related actions、team/jersey/role 信息，以及 tracking 和 spatiotemporal data。
- 这是目前公开描述里与当前 pipeline 最对口的一套数据，因为它同时覆盖动作时间、主体身份和空间信息。

### 2.5 Novel View Synthesis

- SN-NVS 仓库说明数据集包含 5 个由 Blender 生成的场景，每个场景划分 train/challenge 两部分，train 提供 broadcast images 与已知相机参数，challenge 只提供 novel views 的位姿，不提供真实图像。
- 评价以 `PSNR` 为主，目标是从少量视角重建新视角图像。
- 这套数据主要服务几何重建与视角生成，不包含可直接用于动作事件划分的监督标签。

### 2.6 FIFA Skeletal Tracking Light

- 2026 挑战页说明该任务关注仅用主转播机位进行单相机 skeletal tracking，解决遮挡、运动模糊和动态相机带来的难题。
- Starter kit 说明其输入组织围绕 `cameras/`, `boxes/`, `skel_2d/`, `skel_3d/`, `images/`, `videos/`，并提供基于 bounding boxes、skeletal data 和 camera parameters 的 3D pose baseline。
- 这套数据能帮助做人姿、朝向、动作细粒度建模，但不自带当前 pipeline 所需的动作事件标签。

## 3. 与当前 pipeline 直接相关的非 2026 基础任务

2026 挑战之外，当前 pipeline 已经依赖或强相关的 SoccerNet 任务仍然是下面几类，因为它们能提供事件时间轴或位置增强字段。

### 3.1 Action Spotting

- `sn-spotting` 和任务页说明该数据集包含 500 场完整比赛、17 类动作事件、完整直播视频和 `Labels-v2.json`。
- 这正是当前 `event_classification_pipeline.md` 的主事件源。
- 优点是覆盖面广、标签成熟、比赛树结构清晰。
- 局限是动作是稀疏事件，缺少明确执行者与球场位置。

### 3.2 Ball Action Spotting

- `sn-spotting` 和任务页说明其是更密集的 12 类 ball actions 数据集，公开标注比赛数远少于 Action Spotting，且强调 1 秒级严格定位。
- 它比传统 Action Spotting 更接近“球相关动作流”，更适合训练细粒度时序检测。
- 但标准任务本身仍然主要提供时间与动作类型，不足以单独支撑“动作 + 位置 + 主体”的完整链路。

### 3.3 Team Ball Action Spotting 2025

- `sn-teamspotting` 说明该任务直接扩展自 Ball Action Spotting，沿用相同 games 和 actions，但新增“由左队还是右队完成动作”的标注。
- 这说明 SoccerNet 社区已从“动作何时发生”走向“哪支队做的动作”，是 2026 player-centric 任务的重要前身。
- 对当前 pipeline 而言，它比原始 BAS 更接近 `team` 字段需求，但仍缺少 player identity 和充分空间监督。

### 3.4 Tracking

- 跟踪任务页说明其发布了主机位 30 秒片段数据，包含 player/referee/ball 等类别，核心是多目标轨迹恢复。
- 公开描述指出数据是 100 个 30 秒片段，来自主机位 1080p 视频，并包含 left/right 队侧等对象类别。
- Tracking 能提供 `bbox`、`track_id`、时间连续性，是非常实用的位置增强源，但不提供动作语义主标签。

### 3.5 Game State Reconstruction

- 任务页与论文都表明，GSR 的输出目标是球场上的人物位置、角色、队伍与球衣号。
- 公开任务页给出 57 train、59 validation、50 test 的 30 秒主机位片段；论文则进一步说明 SoccerNet-GSR 源于 Tracking，新增了 9.37M pitch line points 与 2.36M athlete positions on pitch，并附带 role、team、jersey。
- 这类数据几乎正好对应当前 pipeline 的 `Labels-GameState.json` 使用方式，是位置增强的第一候选。

## 4. 字段级对齐分析

### 4.1 当前 pipeline 关键字段

| pipeline 字段 | 作用 |
| --- | --- |
| `action_label` | 决定进入 A/B/C/D 哪条规则分支 |
| `team` | `home/away/not applicable` 弱标注基础 |
| `position_ms` | 事件时间对齐主锚点 |
| `player/jersey/track_id` | 理想情况下用于确定是谁执行动作 |
| `bbox_pitch` / `position_on_pitch` | 判断是否处于进攻半场 |
| `left/right` 与 `home/away` 映射 | 空间数据接入时的必要桥接 |

### 4.2 各数据集覆盖情况

| 数据集 | 动作标签 | 时间锚 | 队伍 | 执行者 | 空间位置 | 直播流兼容性 | 结论 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Action Spotting | 强 | 强 | 中 | 弱 | 无 | 强 | 主事件源，但位置不足 |
| Ball Action Spotting | 强 | 强 | 弱 | 弱 | 无 | 强 | 细粒度动作源，但位置不足 |
| Team Ball Action Spotting | 强 | 强 | 中到强 | 弱 | 无 | 强 | 比 BAS 更接近当前任务 |
| Ball Action Anticipation | 中 | 中 | 弱 | 弱 | 无 | 强 | 偏预测任务，不适合直接做主源 |
| FOOTPASS / SN-PCBAS-2026 | 强 | 强 | 强 | 强 | 强 | 强 | 当前最适合主数据源 |
| Tracking | 无 | 强 | 中 | 中 | 强 | 中到强 | 很好的位置增强源 |
| Game State Reconstruction | 无 | 强 | 强 | 强 | 强 | 中到强 | 最适合做位置增强 |
| SynLoc | 无 | 弱 | 弱 | 弱 | 强 | 中 | 可训练定位模块，但非主任务数据 |
| VQA | 弱 | 弱 | 弱 | 弱 | 弱 | 中 | 不适合作主链路 |
| SN-NVS | 无 | 弱 | 无 | 无 | 间接 | 弱 | 不适合作主链路 |
| FIFA Skeletal Tracking Light | 无 | 强 | 弱 | 中 | 中到强 | 中 | 可作姿态子模块，不作主源 |

说明:

- “强”表示公开描述已明确支持当前字段。
- “中”表示需要额外映射、重建或与其他任务拼接。
- “弱”表示字段存在但不是主设计目标，或难以稳定对接当前 pipeline。

## 5. 分组结论

### 5.1 可直接用于事件划分主数据源

#### FOOTPASS / SN-PCBAS-2026

这是最值得优先投入的数据源。

原因:

- 任务定义天然包含 `what + when + who`。
- 仓库明确提到 `team/jersey/role information` 与 `tracking and spatiotemporal data`。
- 与当前 pipeline 的升级方向一致: 先保留事件时间轴，再把队伍、球员、位置引入强约束。
- 即使其目录结构不完全等同于当前 `league/season/match/` 树，也比从 Action Spotting + Tracking + GSR 手工对齐更接近最终目标。

风险:

- Hugging Face 页面显示数据集文件需要接受访问条件，且体量约 235 GB。
- 暂无公开 dataset card，真实标注文件结构需要后续抽样确认。

建议定位:

- 作为未来 `v2` 或 `vNext` 的主训练数据。
- 若样本中的时间表示不是 `half + position_ms`，需要先做一层 adapter。

### 5.2 可作为位置增强源

#### Game State Reconstruction

这是当前 pipeline 最顺手的位置增强候选，因为字段语义与现有文档最一致。

适合做什么:

- 提供 `bbox_pitch` 或等价的 pitch coordinate。
- 提供 `role`、`team left/right`、`jersey`、`track_id`。
- 支持当前 `position_status = matched/missing/ambiguous` 的设计。

主要问题:

- 它是 30 秒片段任务，不保证覆盖当前 Action Spotting 比赛。
- `team` 是 `left/right`，不是天然的 `home/away`，仍需半场级映射。

#### Tracking

Tracking 是 GSR 的上游补充，适合作为以下场景的替代方案:

- 没有 pitch coordinate 时，先用 `bbox` + camera side 近似恢复空间关系。
- 需要更稳定的 `track_id` 连续性时，先训练或复用 tracking 模型。

主要问题:

- 只有图像坐标和轨迹时，离“进攻半场判断”还差一步 field mapping。

#### SynLoc

SynLoc 的价值不在直接接入事件分类器，而在于:

- 训练单帧球场世界坐标回归。
- 在没有 GSR 标注的比赛上，把检测框投到球场坐标。
- 作为 real broadcast + synthetic domain adaptation 的预训练源。

主要问题:

- 单帧任务，没有动作标签，也不强调时序连续性。
- 更适合做定位模型预训练或 calibration 辅助，而不是直接拿来跑 event classifier。

### 5.3 可作为动作训练或迁移源

#### Action Spotting

- 继续作为当前规则系统的主事件锚点最合理。
- 对 A/B/C/D 的弱标注规则依旧有直接价值。
- 适合做 coarse event discovery。

#### Ball Action Spotting

- 更适合训练细粒度的球相关动作时序检测。
- 若未来 A/B 候选动作更多依赖“球动作流”而不是“稀疏比赛事件”，BAS 会比传统 AS 更贴题。

#### Ball Action Anticipation

- 可用于未来加一条“提前 5 秒预警”的旁路。
- 不建议混入当前事件划分主训练集，否则任务目标会从 spotting 漂移到 anticipation。

### 5.4 不建议纳入 v1 pipeline 主链路

#### VQA

- 数据组织是 QA 而不是事件轨迹。
- 更适合做解释型系统、查询式分析和高层 agent。

#### Novel View Synthesis

- 数据是 5 个 Blender 场景，服务于新视角渲染。
- 即使可辅助多视角想象，也不提供当前需要的事件监督。

#### FIFA Skeletal Tracking Light

- 能增强姿态表达，但缺少主事件语义。
- 适合以后在 shot/pass/body orientation 上做细化，不适合作为当前主数据源。

## 6. 推荐的数据路线

### 路线 A: 保守迭代，最贴近当前实现

1. 保留 Action Spotting 作为主事件源。
2. 优先补 Game State Reconstruction 作为位置增强源。
3. 以 Tracking 作为 GSR 缺失时的替代来源。
4. 仅在需要训练位置回归模型时再引入 SynLoc。

适用场景:

- 想尽快把 `event_classification_pipeline.md` 变成可运行代码。
- 接受主链路仍然是弱标注 + 部分位置增强。

### 路线 B: 升级主数据源，向 player-centric 靠拢

1. 抽样验证 FOOTPASS / SN-PCBAS-2026 标注结构。
2. 若其字段确实覆盖 `action + player + team + spatiotemporal data`，则把它作为新主数据源。
3. 将现有 Action Spotting 退居为预训练或补充弱标注源。
4. 用 GSR 或 Tracking 做跨数据集位置定义对照。

适用场景:

- 目标不只是完成当前规则系统，而是把事件划分升级为 player-centric 事件理解。
- 可以接受较大的下载体量与 adapter 成本。

### 路线 C: 不推荐

- 直接把 VQA、NVS、FIFA Skeletal Tracking Light 混进当前主训练集。
- 原因是监督目标差异太大，会增加工程复杂度，却不直接改善事件划分主任务。

## 7. 对当前 pipeline 的具体影响

### 7.1 当前文档仍然成立的部分

- `Labels-v2.json` 作为主事件源的设计，在 Action Spotting 路线下仍然成立。
- Camera 和 caption 作为上下文证据而非主标签的定位仍然合理。
- `home/away` 与 `left/right` 不能直接等同，这一点在 GSR、Tracking、Team BAS、FOOTPASS 上都成立。

### 7.2 需要为后续升级预留的抽象

- `Action Event Loader` 不应假定唯一输入永远是 `Labels-v2.json`。
- `Game State Position Joiner` 最好抽象成通用 `Position Provider` 接口，以便接 GSR、Tracking 或未来 FOOTPASS 自带空间字段。
- `team` 字段应允许三类来源:
  - 原始 `home/away/not applicable`
  - `left/right`
  - player-centric identity 推导出的 team
- 时间对齐层最好允许:
  - `half + position_ms`
  - clip-local timestamp
  - frame index / fps

### 7.3 编码注意事项

本地读取 `docs/event_classification_pipeline.md` 时，`-Encoding UTF8` 能正常显示中文，而 `-Encoding Default` 会出现乱码。这说明后续若需要改动该文件，应继续按 UTF-8 处理，避免无关编码扰动。

## 8. 最终判断

如果目标是尽快把现有规则链路做通:

- 首选组合: `Action Spotting + Game State Reconstruction`
- 备选补充: `Tracking`

如果目标是把任务做成真正的“动作 + 位置 + 执行者”事件划分:

- 首选主数据源: `FOOTPASS / SN-PCBAS-2026`
- 对照位置源: `Game State Reconstruction` 或 `Tracking`
- 预训练定位源: `SynLoc`

如果只考虑 2026 六个挑战本身，与当前任务最相关的排序是:

1. Player-Centric Ball Action Spotting
2. SynLoc
3. Ball Action Anticipation
4. FIFA Skeletal Tracking Light
5. VQA
6. Novel View Synthesis

这个排序衡量的是“对当前动作 + 位置事件划分主任务的帮助”，不是挑战本身的学术价值高低。

## 9. 后续建议

建议下一步优先做三件事:

1. 抽样查看 `SN-PCBAS-2026` / FOOTPASS 的真实标注文件结构，确认时间字段、identity 字段、空间字段、比赛树组织方式。
2. 继续用现有 `inspect_gamestate.py` 验证 GSR 是否能与当前示例比赛发生路径级或时间级对齐。
3. 为 `Action Spotting`, `GSR`, `FOOTPASS` 各写一个最小 adapter 设计草案，统一输出到当前 pipeline 所需的中间 schema。

## 10. 参考来源

- [SoccerNet 2026 Challenges](https://www.soccer-net.org/challenges/2026)
- [FOOTPASS repo](https://github.com/JeremieOchin/FOOTPASS/tree/main)
- [SN-PCBAS-2026 dataset](https://huggingface.co/datasets/SoccerNet/SN-PCBAS-2026)
- [FAANTRA / Ball Action Anticipation repo](https://github.com/MohamadDalal/FAANTRA)
- [SoccerNet Action Anticipation dataset](https://huggingface.co/datasets/SoccerNet/ActionAnticipation)
- [Spiideo SynLoc / sskit repo](https://github.com/Spiideo/sskit)
- [SoccerNet Action Spotting task](https://www.soccer-net.org/tasks/action-spotting)
- [SoccerNet Ball Action Spotting task](https://www.soccer-net.org/tasks/ball-action-spotting)
- [SoccerNet Team Ball Action Spotting repo](https://github.com/SoccerNet/sn-teamspotting)
- [SoccerNet Tracking task](https://www.soccer-net.org/tasks/tracking)
- [SoccerNet Game State Reconstruction task](https://www.soccer-net.org/tasks/game-state-reconstruction)
- [SoccerNet Game State Reconstruction paper](https://arxiv.org/abs/2404.11335)
- [SN-VQA-2026 dataset](https://huggingface.co/datasets/SoccerNet/SN-VQA-2026)
- [SN-NVS-2026 dataset](https://huggingface.co/datasets/SoccerNet/SN-NVS-2026)
- [SN-NVS repo](https://github.com/SoccerNet/sn-nvs)
- [FIFA Skeletal Tracking starter kit](https://github.com/FIFA-Skeletal-Light-Tracking-Challenge/FIFA-Skeletal-Tracking-Starter-Kit-2026)
