可以，但要先把目标说清楚：

**只依据 PCBAS/FOOTPASS 数据时，不适合复刻 `Labels-v2` 那种“比赛规则型”事件体系**，因为它没有 `foul / offside / penalty / card / substitution` 这些标签。  
更合适的是做一套 **以球员动作链和球权阶段为核心的粗粒度事件划分**。

我会参考 [Event-VStream](https://huggingface.co/papers/2601.15655) 的核心思想：  
**不要按固定时间窗切段，而要在“语义状态发生变化”时切段。**  
对 PCBAS 来说，这些“状态变化”只能来自它自己已有的字段：

- `cls`：动作类别
- `frame`：时间锚
- `team_side / left_to_right`：当前左右侧
- `player_id / shirt_number / role_id`：执行者变化
- `x_pos / y_pos / x_speed / y_speed`：空间与运动变化
- `roi_*`：是否可见、画面框位置

---

## 1. 先定义最小事件单元

PCBAS 的最小原子事件就是每一条 `cls > 0` 的记录：

```text
(frame, player_id, team_side, role_id, x_pos, y_pos, cls)
```

建议把 8 个原子类先分成 5 个**细粒度动作族**：

| PCBAS 类 | 动作族 | 用途 |
| --- | --- | --- |
| `Drive` | `carry` | 持球推进 |
| `Pass` | `circulate` | 传递/组织 |
| `Cross` | `deliver` | 向禁区输送 |
| `Shot`, `Header` | `finish` | 终结 |
| `Throw-in` | `restart` | 重启/边线恢复 |
| `Tackle`, `Block` | `disrupt` | 防守破坏/争夺 |

这一步很重要，因为**粗粒度划分最好先从动作族而不是直接从 8 个类开始聚合**。

来源：
- [FOOTPASS README](https://raw.githubusercontent.com/JeremieOchin/FOOTPASS/main/README.md)
- [Event-VStream paper page](https://huggingface.co/papers/2601.15655)

---

## 2. 用 PCBAS 自己能提供的“边界信号”来切段

借 Event-VStream 的思路，边界不是固定 5 秒一刀，而是当这些信号发生明显变化时切：

### 强边界
满足任一条就直接切新段：

1. `team_side` 改变  
   含义：球权大概率转换或进入对抗后的新阶段。

2. 当前动作属于 `restart`  
   例如 `Throw-in`。它天然是新段起点。

3. 当前动作属于 `finish`  
   `Shot` 或 `Header` 通常应视为一个阶段的收束点。

4. 相邻两条事件时间差过大  
   建议：
   - `Δframe > 75` 切段
   - 25 fps 下约等于 `3s`

### 中边界
满足两条以上再切：

1. `player_id` 改变
2. 动作族改变，例如 `carry -> deliver`、`circulate -> finish`
3. 归一化前进坐标出现大跳变  
   建议定义：
   ```text
   x_attack = x_pos                  if team_side == left
   x_attack = 1 - x_pos             if team_side == right
   ```
   如果 `|x_attack_t - x_attack_{t-1}| > 0.25`，说明阶段位置明显切换。

4. 速度型态突变  
   例如：
   - 前一条是低速 `Pass`
   - 下一条变成高速 `Drive`
   - 或从推进突然转成 `Block/Tackle`

---

## 3. 推荐的粗粒度事件类型

如果你的最终目标是“更粗粒度的事件划分”，我建议直接做下面这 6 类，比 A/B/C/D 更贴 PCBAS：

### 1. `build_up`
**组织推进段**

规则：
- 动作只来自 `Drive`、`Pass`
- 同一 `team_side`
- 相邻事件 `Δframe <= 75`
- 没有被 `Throw-in / Shot / Header / team switch` 打断

### 2. `delivery_attack`
**输送进攻段**

规则：
- 段内出现 `Cross`
- 前 1 到 3 条动作中至少有一个 `Drive` 或 `Pass`
- 同一 `team_side`
- 若 `Cross` 后 50 帧内接 `Shot/Header`，整段升级为 `chance_creation`

### 3. `chance_creation`
**机会形成段**

规则：
- 同一 `team_side`
- 段尾是 `Shot` 或 `Header`
- 前 50 帧内至少有 `Pass` / `Cross` / `Drive` 之一
- 可以把 `Cross -> Header`、`Pass -> Shot` 都归到这一类

### 4. `restart_phase`
**重启段**

规则：
- 以 `Throw-in` 开始
- 后续 25 到 50 帧内同队的第一次 `Pass/Drive` 仍并入该段
- 再往后进入 `build_up` 或 `delivery_attack`

### 5. `duel_recovery`
**对抗/回收段**

规则：
- 段首是 `Tackle` 或 `Block`
- 如果后 25 帧内同侧马上出现 `Pass/Drive`，说明回收成功
- 若下一条事件是对侧动作，则这一段只保留 `Tackle/Block` 本身

### 6. `transition`
**攻防转换段**

规则：
- 前一段和后一段 `team_side` 不同
- 切换后 50 帧内新持球队出现 `Drive` 或 `Pass`
- `x_attack` 呈明显向前推进

---

## 4. 比 6 类更“硬”的细粒度规则

如果你要先做细粒度再聚粗，可以用这套：

### 4.1 原子层
- `Drive`
- `Pass`
- `Cross`
- `Shot`
- `Header`
- `Throw-in`
- `Tackle`
- `Block`

### 4.2 微阶段层
- `carry_progression`：连续 `Drive`
- `pass_circulation`：连续 `Pass`
- `wide_delivery`：`Cross`
- `finishing`：`Shot` / `Header`
- `restart`：`Throw-in`
- `defensive_disruption`：`Tackle` / `Block`

### 4.3 粗阶段层
- `build_up`
- `delivery_attack`
- `chance_creation`
- `restart_phase`
- `duel_recovery`
- `transition`

这样你后面如果想改粗粒度，不必重做底层解析。

---

## 5. 一个可直接落地的切段算法

按时间排序所有 `cls > 0` 行后，顺序扫描：

1. 把每条 `cls` 映射成动作族
2. 维护当前段 `current_segment`
3. 遇到下面条件就关闭当前段并开新段：
   - `team_side` 改变
   - `cls in {Throw-in, Shot, Header}`
   - `Δframe > 75`
   - `disrupt` 后进入对方动作
4. 否则把当前动作并入当前段
5. 段结束后按内部动作模式打粗标签：
   - 只含 `Drive/Pass` -> `build_up`
   - 含 `Cross` 不含 `Shot/Header` -> `delivery_attack`
   - 末尾 `Shot/Header` -> `chance_creation`
   - 以 `Throw-in` 起 -> `restart_phase`
   - 以 `Tackle/Block` 起 -> `duel_recovery`
   - 发生队伍切换且新队快速推进 -> `transition`

---

## 6. 只用 PCBAS 时不要做的规则

这些规则不建议只靠 PCBAS 硬做：

- `foul / card / offside / penalty`
- `ball out of play`
- `goal confirmed`
- `home / away` 级别强语义
- “是否进入禁区”这种精确球场语义，如果你没有额外球门方向映射

原因是 PCBAS 当前给你的核心是：
- player-centric action
- 左右侧
- 空间位置
- tracking/bbox

它不是完整的比赛规则事件日志。

---

## 7. 对你当前项目最合适的版本

如果你的目标是“先做一个稳的粗粒度事件划分器”，我建议第一版就做这 5 类：

- `build_up`
- `chance_creation`
- `restart_phase`
- `duel_recovery`
- `transition`

具体映射：

- `Drive/Pass` 主导 -> `build_up`
- `Cross/Shot/Header` 主导 -> `chance_creation`
- `Throw-in` 主导 -> `restart_phase`
- `Tackle/Block` 主导 -> `duel_recovery`
- 队伍切换后快速推进 -> `transition`

这套规则和 PCBAS 的数据能力是匹配的，而且后面很容易接 `GSR/Tracking` 做位置增强。

## 8. 当前仓库里的可运行实现

当前规则已经落成脚本：

```bash
python scripts/build_pcbas_clip_manifest.py
```

脚本做四件事：

1. 从 H5 里筛选 `cls > 0` 的 player-centric action anchor。
2. 依据 `team_side` 切换、动作族变化、`Δframe`、位置跳变等信号切成粗语义段。
3. 把粗语义段投影到固定 4 秒 clip。
4. 为每个 clip 输出 `primary_coarse_event` 与 `memory_update`。

推荐先在单个半场上验证：

```bash
python scripts/build_pcbas_clip_manifest.py --sequences game_18_H1
```

生成小样例：

```bash
python scripts/build_pcbas_clip_manifest.py \
  --sequences game_18_H1 \
  --events-only \
  --clip-limit 30 \
  --output-path data/pcbas2026/samples/game_18_H1_clip_manifest_4s_30.jsonl
```

输出的 `memory_update` 目前是规则弱监督：当 clip 内出现新语义段起点，或 `primary_coarse_event` 相对上一 clip 变化时置为 `true`。等视频可用后，可以直接用同一份 manifest 对齐 4 秒视频 clip。
