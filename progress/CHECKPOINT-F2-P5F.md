# F2-P5F（检查点）· 基线 c41e78b · Crosswalk 已复算匹配

## ★ 本轮已抓出的真缺陷
**D-15：模块名冲突重演（D-7 的翻版）**
- `src/skill_interface/content_query.py`（P5C 旧，返回 NO_CONTENT_KNOWLEDGE）
- `src/content_persistence/content_query.py`（P5E 新，真正查持久化事实）
- paths 里 `skill_interface` 排在 `content_persistence` 前 → CLI `import content_query`
  命中旧模块 → **CLI 一直在查空的旧实现，P5E 的查询从未被真正使用**
- 修复：改名为 `content_knowledge_query.py`，CLI 显式导入它
- 新增全库同名扫描（除 `__init__` 外已无重名）

**D-16：content_query 签名不接受 data_root**
CLI 传 `data_root=root` → TypeError INTERNAL_ERROR。已补参。

## 已实测（安装版 CLI）
```
query 1296269 --commit 7fd1a60b... --type content --path README
→ state=CONTENT_NOT_CAPTURED, content_availability=NOT_CAPTURED,
  network_requests=0, facts=0
```
语义正确：该仓库从未采集内容字节。

## 待做
1. README / Manifest 卡片（复用 Safe Renderer）
2. inspect --content-summary 计数口径（文件/唯一 Blob/资产/Fact 分离）
3. D-13 类型化 Subject 匹配契约 + 12 项阻断级负例
4. 三进程 E2E、多进程 Blob 回归
5. Skill 文档同步 + 全量回归
