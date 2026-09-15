# 资源与机器可读清单

- [覆盖表](COVERAGE.csv)：24题的全文、线索、代码与数据状态。
- [论文清单](PAPER_MANIFEST.csv)：125条NF1、5条Participant，含作者、原始来源、SHA256及核验方式。
- [正式资料指纹](PROBLEM_MANIFEST.csv)：119个文件实际下载校验。
- [代码/数据文件](RESOURCE_MANIFEST.csv)：按Git blob与字节数去重；SHA256为空表示未下载核算，不是缺失文件或虚造指纹。
- [代码/数据来源包](CODE_DATA_SOURCES.csv)：逐题原作者路径、固定版本、环境说明和关系。
- [重复别名](DUPLICATE_ALIASES.csv)：保留其他出处，不保存重复文件。
- [补搜记录](SEARCH-LOG.md) · [缺口](GAPS.md) · [验收](VALIDATION.md)

## 下载与指纹核对

在文件链接打开后使用Raw / Download。下载后的PowerShell校验：

```powershell
Get-FileHash -Algorithm SHA256 -LiteralPath '下载文件.pdf'
```

将结果与清单sha256列比较。Git blob SHA-1含Git对象头，不能用普通文件SHA-1命令直接比较。分卷必须齐全，参照Data页和年度官方公告解压。
