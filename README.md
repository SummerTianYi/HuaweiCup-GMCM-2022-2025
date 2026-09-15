# HuaweiCup-GMCM-2022-2025

2022–2025 华为杯中国研究生数学建模竞赛（CPMCM）的原件定位与按需读取索引；只收研究生全国赛。

**当前阶段：资料准备与结构整理。尚未开展论文精读或蒸馏。** 库内主要是来源和元数据，获取、提取、阅读分别记录；历史获奖核验不等于学习进度。

## Agent 从这里开始

**选择题目或论文 → 定位清单记录 → 获取原件 → 按需提取。** 不需要先通读所有 README 或大型 CSV。

1. 从下表进入一道题的简短 README，按需打开题面、论文、代码或数据子索引。
2. 用下方 `--list` 找到稳定 `paper_id`；只读取匹配记录。字段及状态见 [Resources](Resources/README.md)。
3. 对选中的一篇运行 `--download` 或 `--extract`。原件、逐页文本放临时缓存，不自动提交；返回 PDF 原页检查公式、图表和版式。

```console
python scripts/prepare_papers.py --year 2022 --problem A --limit 2 --list
python scripts/prepare_papers.py --paper-id CPMCM-A22100070190 --extract
```

提取需要 Python 3.10+ 和 [pypdf 依赖](scripts/requirements.txt)；列出和下载仅需标准库。[运行、恢复与缓存说明](Resources/README.md)。

## 四年 A–F 导航

| 年份 | A | B | C | D | E | F |
| --- | --- | --- | --- | --- | --- | --- |
| 2022 | [A](2022/A/README.md) | [B](2022/B/README.md) | [C](2022/C/README.md) | [D](2022/D/README.md) | [E](2022/E/README.md) | [F](2022/F/README.md) |
| 2023 | [A](2023/A/README.md) | [B](2023/B/README.md) | [C](2023/C/README.md) | [D](2023/D/README.md) | [E](2023/E/README.md) | [F](2023/F/README.md) |
| 2024 | [A](2024/A/README.md) | [B](2024/B/README.md) | [C](2024/C/README.md) | [D](2024/D/README.md) | [E](2024/E/README.md) | [F](2024/F/README.md) |
| 2025 | [A](2025/A/README.md) | [B](2025/B/README.md) | [C](2025/C/README.md) | [D](2025/D/README.md) | [E](2025/E/README.md) | [F](2025/F/README.md) |

## 目录与状态概览

- `年份/题号/README.md`：单题入口；`Problem`、`Excellent-Papers`、已有 `Code`/`Data` 为详细子索引，没有资源不建空目录。
- `Resources/`：资源清单、状态字段、覆盖表、历史核验和缺口。
- `scripts/`：筛选、获取、逐页提取与离线校验；不运行比赛代码。
- `Templates/STUDY-NOTE.md`：未来学习笔记的空白模板。

<!-- manifest-stats:start -->
- 论文记录：库内原件 **0**，外部全文 **130**（NF1 125、Participant 5），仅线索 **21**。线索不计全文。
- 题目入口 **24**；代码来源包 **23**，覆盖 **16** 题；数据含原始/派生/外部线索，详见各题。
- 状态记录：曾获取成功 **9**；逐页提取完成 **2**（其中 **2** 待人工检查）；已精读 **0**。成功记录不保证临时缓存仍在。
<!-- manifest-stats:end -->

统计由 `python scripts/validate_repository.py --refresh` 从现有清单生成。获奖 NF1/NF2/NF3、Excellent、Participant、Unverified 及准备状态的含义集中在 [Resources](Resources/README.md)。

[来源与奖项证据](SOURCES.md) · [许可边界](LICENSE-NOTES.md) · [资料缺口](Resources/GAPS.md) · [历史核验](Resources/VALIDATION.md) · [历史补搜](Resources/SEARCH-LOG.md) · [学习模板](Templates/STUDY-NOTE.md)

未来确有人工审读/蒸馏成果时，可放在对应题目下 `Notes/<paper_id>.md`，使用学习模板并标注证据；现在不创建该目录或任何学习成果。
