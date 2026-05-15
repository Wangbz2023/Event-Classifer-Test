# PCABS2026 Event Classification

本仓库当前只围绕 `PCABS2026 / SN-PCBAS-2026` 构建数据接入、H5 检查、事件级导出和后续粗粒度足球事件划分流程。历史 SoccerNet Action Spotting、Game State Reconstruction 等资料仍保留在 `docs/` 中作为研究备用，但不再是当前主链路。

## 当前目标

项目目标是从 PCABS2026 的 player-centric ball action 数据出发，把细粒度球员动作序列整理成更粗粒度的足球事件阶段，例如：

- `build_up`
- `chance_creation`
- `restart_phase`
- `duel_recovery`
- `transition`

当前主数据字段来自 PCABS tactical H5：

```text
frame, player_id, left_to_right, shirt_number, role_id,
x_pos, y_pos, x_speed, y_speed,
roi_x, roi_y, roi_width, roi_height,
cls
```

其中 `cls > 0` 的行是 player-centric 事件锚点。

## 数据目录

只使用一个 PCABS2026 数据根目录：

```text
data/pcbas2026/
├── raw/           # Hugging Face 下载的 zip，不入库
├── extracted/     # zip 解压后的 h5，不入库
├── processed/     # 全量解析产物，不入库
└── samples/       # 小样例，可入库
```

推荐的 validation H5 路径是：

```text
data/pcbas2026/extracted/VAL/val_tactical_data.h5
```

旧的 `data/soccernet/` 目录是早期探索留下的本地数据位置，不再作为当前主链路使用。

## 下载 PCABS2026

PCABS2026 当前通过 Hugging Face gated dataset 分发。先确认账号已获访问权限，并在环境变量里设置 token：

```bash
export HF_TOKEN="your_huggingface_token"
```

先 dry-run 检查下载计划：

```bash
python scripts/download_sn_pcbas.py --dry-run
```

下载 tactical data：

```bash
python scripts/download_sn_pcbas.py --splits TRAIN VAL
```

默认下载到：

```text
data/pcbas2026/raw/TRAIN/tactical_data_TRAIN.zip
data/pcbas2026/raw/VAL/tactical_data_VAL.zip
```

默认不下载视频。视频文件体积更大，也不是当前事件划分链路的必要输入。

## 解压与检查 zip

查看 tactical zip 结构：

```bash
python scripts/inspect_sn_pcbas.py --splits VAL --list-games
```

解压可用系统 `unzip`，也可以用 Python 自带工具。推荐把 H5 放入：

```text
data/pcbas2026/extracted/VAL/
```

示例：

```bash
mkdir -p data/pcbas2026/extracted/VAL
unzip -q data/pcbas2026/raw/VAL/tactical_data_VAL.zip -d data/pcbas2026/extracted/VAL
```

如果 zip 内部已有目录层级，解压后以实际文件位置为准；后续脚本可通过 `--h5-path` 指定。

## 检查 H5

默认检查：

```bash
python scripts/inspect_sn_pcbas_h5.py
```

检查指定半场：

```bash
python scripts/inspect_sn_pcbas_h5.py --sequence game_18_H1 --sample-event-limit 10
```

PCABS tactical H5 的结构是：

```text
game_xx_Hy -> float32 matrix with shape (N, 14)
```

例如 validation split 通常包含：

```text
game_18_H1
game_18_H2
game_24_H1
game_24_H2
game_47_H1
game_47_H2
```

## 导出可读事件文件

默认只导出 `cls > 0` 的事件行，避免把所有 frame-level player state 展开成超大文件。

导出全量事件到 `processed/`：

```bash
python scripts/inspect_sn_pcbas_h5.py \
  --sequence game_18_H1 \
  --export-format jsonl
```

生成小样例到 `samples/`：

```bash
python scripts/inspect_sn_pcbas_h5.py \
  --sequence game_18_H1 \
  --export-format jsonl \
  --export-limit 100 \
  --output-path data/pcbas2026/samples/game_18_H1_events_100.jsonl
```

支持格式：

```text
json
jsonl
csv
```

如果确实需要导出所有原始行，可以使用：

```bash
python scripts/inspect_sn_pcbas_h5.py \
  --sequence game_18_H1 \
  --export-format csv \
  --export-scope rows
```

这个输出会很大，默认不建议提交到仓库。

## Git 数据策略

仓库只提交：

- 代码脚本
- 研究文档
- 小型样例文件

仓库不提交：

- `*.zip`
- `*.h5`
- `*.mkv`
- `*.mp4`
- `data/pcbas2026/raw/`
- `data/pcbas2026/extracted/`
- `data/pcbas2026/processed/`

`data/pcbas2026/samples/` 可以提交小型 `json/jsonl/csv`，用于 README、测试和远程算力环境 smoke test。

## 本地与远程算力工作流

推荐流程：

```text
本地主机 Codex 修改代码
-> git push 到 GitHub
-> 远程算力 git pull
-> 远程算力下载/解压/解析 PCABS2026 数据
```

远程算力上更新代码：

```bash
git pull origin main
```

远程算力上重新检查数据：

```bash
python scripts/download_sn_pcbas.py --dry-run
python scripts/inspect_sn_pcbas_h5.py --sequence game_18_H1 --sample-event-limit 3
```

## 文档

- `docs/sn_pcbas_2026_dataset_analysis.md`：当前主数据集 PCABS2026 的访问、H5 结构、字段解释和接入建议。
- `docs/coarse_event_rule.md`：只依据 PCBAS 字段进行粗粒度足球事件划分的规则草案。
- `docs/soccernet_2026_dataset_analysis.md`：SoccerNet 2026 多数据集横向分析，作为备用研究材料。
- `docs/gamestate_2024_dataset_format.md`：Game State Reconstruction 格式分析，作为备用研究材料。
- `docs/event_classification_pipeline.md`：早期 Action Spotting/GSR 混合链路设计，作为历史参考。
