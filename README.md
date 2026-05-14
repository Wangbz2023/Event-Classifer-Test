# SoccerNet 数据目录

这份文档只推荐一种数据组织方式：

```text
data/soccernet/
├── README.md
└── raw/
    └── as2023/
        └── league/
            └── season/
                └── match/
                    ├── Labels-v2.json
                    ├── Labels-caption.json
                    ├── Labels-cameras.json
                    ├── video.ini
                    ├── 1.mkv
                    └── 2.mkv
```

请把它理解成：

```text
一个比赛一个目录
目录里同时放动作标签、caption 标签、camera 标签和上下半场视频以及所有需要用来划分事件的数据集

```

## 为什么要统一到 `raw/as2023`

输入是什么：
- SoccerNet Action Spotting 2023 的 `Labels-v2.json`
- Dense Video Captioning 的 `Labels-caption.json`
- Camera Shot Segmentation 的 `Labels-cameras.json`
- 比赛视频 `1.mkv` / `2.mkv` 和 `video.ini`

模块做什么：
- 把不同来源的数据整理到同一个 `league/season/match/` 目录

输出是什么：
- 一个可以直接喂给事件划分代码的原始比赛目录树



## 不再推荐的旧写法

下面这种写法容易产生双层同名目录：

```python
dl = SoccerNetDownloader("data/soccernet/spotting-2023")
dl.downloadDataTask("spotting-2023", ...)
```

## 单场样例下载

样例比赛固定为：

```text
england_epl/2014-2015/2015-02-21 - 18-00 Chelsea 1 - 1 Burnley
```

### 1. 下载动作标签、camera 标签和视频

```bash
conda activate streamsoccer

python -c "
from SoccerNet.Downloader import SoccerNetDownloader

root = 'data/soccernet/raw/as2023'
game = 'england_epl/2014-2015/2015-02-21 - 18-00 Chelsea 1 - 1 Burnley'

dl = SoccerNetDownloader(root)
dl.password = 'SoccerNet'
dl.downloadGame(
    game,
    files=[
        'Labels-v2.json',
        'Labels-cameras.json',
        'video.ini',
        '1.mkv',
        '2.mkv',
    ],
    spl='train'
)
"
```

### 2. 下载 caption 标签

优先尝试直接把 caption 下载到同一个比赛目录：

```bash
python -c "
from SoccerNet.Downloader import SoccerNetDownloader

root = 'data/soccernet/raw/as2023'
game = 'england_epl/2014-2015/2015-02-21 - 18-00 Chelsea 1 - 1 Burnley'

dl = SoccerNetDownloader(root)
dl.password = 'SoccerNet'
dl.downloadGame(
    game,
    files=['Labels-caption.json'],
    spl='train'
)
"
```

如果官方 caption 下载接口不能直接生成比赛树，而是产出另一种 task 目录结构，那么最终目标仍然不变：

```text
把该比赛对应的 Labels-caption.json 整理回
data/soccernet/raw/as2023/england_epl/2014-2015/2015-02-21 - 18-00 Chelsea 1 - 1 Burnley/
```



