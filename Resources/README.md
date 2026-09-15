# Resources · 定位、状态与读取

[返回总导航](../README.md)。选择一个题目，再运行筛选命令；无需先阅读大型清单。

## 唯一维护源与关联

| 文件 | 用途 / 关联键 |
| --- | --- |
| [PAPER_MANIFEST.csv](PAPER_MANIFEST.csv) | 所有论文与线索的资源事实、奖项证据及准备/阅读状态；主键 `paper_id` |
| [PROBLEM_MANIFEST.csv](PROBLEM_MANIFEST.csv) | 题面、官方附件及说明；以 `year + problem` 关联，`annual` 是全年说明 |
| [CODE_DATA_SOURCES.csv](CODE_DATA_SOURCES.csv) | 作者代码/数据来源包及已知关系；以 `year + problem` 查本题，`repo` 区分来源 |
| [RESOURCE_MANIFEST.csv](RESOURCE_MANIFEST.csv) | 代码/数据文件入口；同题键关联，`kind` 区分 Code/Data |
| [DUPLICATE_ALIASES.csv](DUPLICATE_ALIASES.csv) | 同文件的其他出处，避免重复保存 |
| [COVERAGE.csv](COVERAGE.csv) | 上述清单的派生统计；`data_status` 保留既有人工判定，不当作原始数据齐备证明 |

不新建重复学习清单。论文资源事实只修改 PAPER_MANIFEST；各题子索引保留详细入口和历史说明，获取/提取/阅读状态以清单为准。更新资源后运行 `validate_repository.py --refresh` 同步统计。

`year + problem` 只说明属于同题，**不能证明代码属于这篇论文**。仅当 `related_code_repos` 有记录，才按相同题目键与对应 `repo` 联查。`code_relationship_status`：`verified_same_file` 是既有作者PDF与主池同文件证据；`author_declared` 仅作者声明；`unverified` 不强行绑定。证据保留在 `code_relationship_evidence`、来源包的 `relationship` 和 [SOURCES](../SOURCES.md)。

## 论文清单字段

| 字段 | 说明 |
| --- | --- |
| `paper_id` | 永久定位标识；有真实队号使用 CPMCM-队号，匿名全文按既有 SHA256，线索按年份/题号/文件名的稳定散列。建立后不因标题修正而重算 |
| `team_id` / `legacy_record_id` | 真实参赛队号 / 历史占位记录标识。匿名论文 team_id 留空，不把散列伪造为队号 |
| `year, problem, title, author` | 原有作品信息；未知留空，题名待校读保持原标记 |
| `award, evidence` | 原奖项与证据，准备脚本不修改、不重复核奖 |
| `url, original_source` | 文件展示/线索地址、原始出处 |
| `sha256, bytes, hash_verification` | 既有指纹、大小及核验方式；脚本只核对选中原件，不覆盖历史证据 |
| `resource_kind` | `repository_original` 库内原件；`external_fulltext` 外部全文；`lead_only` 仅有线索 |
| `download_url` / `local_original_path` | 直接下载地址 / 库内相对路径；线索两者均空，不能把线索页面下载后当成PDF |
| `acquisition_status` | `unchecked` 未检查；`success` 曾获取成功；`failed` 获取失败；`unavailable` 只有线索，尚无原件入口 |
| `extraction_status` | `unchecked` 未逐页提取；`extracted` 已逐页提取；`needs_review` 已提取但有空文本、扫描/乱码疑点；`failed` 未完成，可继续 |
| `reading_status` / `reading_evidence` | `unchecked` 无完整阅读记录；`close_read` 已精读，须人工填写笔记或证据地址。脚本永不修改这两项 |
| `last_checked_at` | 最近一次获取/提取尝试时间，UTC ISO时间或历史核验日期；未知留空，不等于阅读日期 |
| `failure_reason` | 最近失败原因；成功重试清空；`needs_review` 的逐页疑点在临时 extraction.json 中，不冒充下载失败 |
| `related_code_repos, code_relationship_status, code_relationship_evidence` | 仅保留已知论文—代码关系，多个repo用分号分隔 |

历史“获取成功”只说明曾获得文件，**不保证本机缓存还在**。清理缓存不撤销历史成功事实；再次获取时按文件是否存在决定下载。以前仅检查封面/哈希的记录仍为 `extraction_status=unchecked`、`reading_status=unchecked`。论文准备和阅读进度严格分开。

奖项标记：NF1/NF2/NF3 为全国一/二/三等奖，需可绑定作品的证据；Excellent 为优秀论文选，不能自动升级国一；Participant 为参赛作品；Unverified 表示奖项或身份等仍缺核验证据。线索不计全文，外部全文也不等于库内保存或已经读过。

## 运行示例

在仓库根目录执行，Python 3.10+。仅提取需要安装依赖，建议在项目虚拟环境中安装：

```console
python -m pip install -r scripts/requirements.txt
python scripts/prepare_papers.py --year 2023 --problem B --limit 1 --list
python scripts/prepare_papers.py --paper-id CPMCM-B23107010043 --download
python scripts/prepare_papers.py --paper-id CPMCM-B23107010043 --extract
python scripts/validate_repository.py --refresh
python scripts/validate_repository.py
python -m unittest discover -s scripts/tests -v
```

- `--list` 不联网、不写文件；没有动作参数也只列出。即使同时传了 `--extract`，`--list` 仍优先。`--paper-id` 可重复；年份、题号、标识条件之间取交集。
- 下载/提取必须有 `--year`、`--problem` 或 `--paper-id`；单独 `--limit` 不能触发全量下载。`--limit` 限制匹配条数，不是新增下载数。推荐先列出，再选一篇。
- `--extract` 包含按需下载；每篇/每页已有合格缓存会跳过，重跑相同命令从已有页继续。下载中断的 `.part` 不作为成功文件，重试该文件从头下载。
- 默认缓存为系统临时目录下 `huaweicup-paper-cache/<paper_id>/`，可用 `--cache-dir` 指定其他临时位置。库内只允许被忽略的 `.cache/papers/`，不要把PDF或提取全文提交到仓库。
- 输出 `original.pdf`、`page-0001.json` 等及 `extraction.json`；页码为 **从1开始的PDF物理页**，含封面，不等于论文印刷页码。每页保留 paper_id、来源URL、原件SHA256和疑点标记。标准输出只报告状态，不输出论文正文。
- `possible_scan`、`empty_text`、`sparse_text`、`suspected_garbled_text` 是保守启发式提示，可能误报或漏报；没有标记也不保证文本正确。公式、图表、上下标与版式必须回查原页。不默认OCR，不调用大模型。
- 每篇后原子更新清单状态。失败写入 failure_reason 和临时 failure.json，其他选中论文继续；存在失败时退出码1，手动中断为130。重试不修改奖项、原始哈希、阅读状态。
- 默认单文件上限100MiB、网络等待60秒，用 `--max-mb` / `--timeout` 显式调整。返回HTML、大小或哈希不符均失败；已有缓存损坏时人工移走该篇缓存后重试，不覆盖清单证据。
- 清单锁避免同时运行两个准备进程，检测到外部改动时拒绝覆盖。强制终止后，先确认旧进程已停止，再仅删除遗留 `Resources/PAPER_MANIFEST.csv.lock`；保留页缓存即可恢复。

## 历史与边界

[来源及去重证据](../SOURCES.md) · [许可](../LICENSE-NOTES.md) · [缺口](GAPS.md) · [历史核验](VALIDATION.md) · [历史补搜](SEARCH-LOG.md)。本轮不重新搜索、核奖或全量下载，也不运行比赛代码。原件与提取全文遵守原许可，默认只作临时读取。
