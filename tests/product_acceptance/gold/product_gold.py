"""产品级 Gold：20 个端到端场景（人工预定义预期）。"""

GOLD = [
 ("P01","BUILD","建库：本地授权仓库 → snapshot/facts/claims","SNAPSHOT_AND_FACTS"),
 ("P02","LIST","仓库列表可读","REPOSITORIES_OK"),
 ("P03","COMMIT","固定 Commit 身份正确","COMMIT_MATCH"),
 ("P04","README","README 内容知识可查","CONTENT_FOUND"),
 ("P05","MANIFEST","Manifest 依赖声明可查","DEPS_FOUND"),
 ("P06","PY_SYM","Python class/method/function","PY_SYMBOLS"),
 ("P07","TS_SYM","TS interface/type alias","TS_SYMBOLS"),
 ("P08","IMPORT","静态 Import + Evidence","IMPORTS_OK"),
 ("P09","ALIAS","tsconfig Alias → 目标路径","RELATION_RESOLVED"),
 ("P10","PROJECT","TS 项目与 include","PROJECT_VERIFIED"),
 ("P11","EVIDENCE","证据可回查","EVIDENCE_TRACEABLE"),
 ("P12","CARD","HTML 卡片可生成","CARD_OK"),
 ("P13","SECOND","二次使用复用","REUSE_OK"),
 ("P14","OFFLINE","离线零网络","NETWORK_0"),
 ("P15","MULTICOMMIT","双 Commit 隔离","ISOLATED"),
 ("P16","NOFACT","不存在的 Fact","EMPTY_NOT_FOUND"),
 ("P17","INSUFFICIENT","证据不足明确 abstain","ABSTAIN"),
 ("P18","BADBLOB","损坏 Blob 不伪造","INTEGRITY_BLOCKED"),
 ("P19","CONTRACT","写读字段契约一致","CONTRACT_OK"),
 ("P20","TRAVERSAL","路径穿越被拒绝","ESCAPE_REJECTED"),
]
