#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
讯飞虚拟人 - 知识库操作工具 v2

覆盖 docqa 知识库的完整生命周期：查询 / 建库 / 建标签 / 上传文档 / 关联场景 / 发布。
接口字段以真实抓包 + 实测返回为准（顶层 items、对象主键统一为 id/name）。

命令总览
  只读查询
    list [页码] [每页] [名称]            列出知识库
    labels                              列出标签
    models                              列出可用向量/LLM 模型
    versions <libId>                    某库的版本及状态
    categories <libId> [version]        某库的分类列表
    docs <libId> [version] [页码] [每页] 某库的文档列表
    status <sceneId>                    查场景当前 docqa 知识库配置

  创建（写）
    create-label <name>                 创建标签
    create-kb <name> [--label L] [--desc D] [--vector V] [--llm M]
                                        创建知识库（返回 libId）
    create-category <libId> <name> [--parent PID] [--version N]
                                        创建分类（顶级或子分类）

  上传文档（写，会产生真实数据）
    upload <libId> <文件路径...> [--version N] [--category CID]
           [--split 7] [--file-type text|qa] [--wait]
                                        重名检查→上传→拆分（--wait 轮询到就绪）
                                        --file-type qa 表示问答对 Excel 模板
                                        --split: 2=分隔符 3=自动目录 5=不拆分 7=智能(默认) 9=自定义目录

  删除（写，不可逆）
    delete-doc <docId>                  删除文档（按文档 id，非 fileID）
    delete-kb <libId>                   删除知识库（慎用）

  关联场景（写）
    enable <sceneId> <libId...> [--no-publish] [--chain docqa,xinghuo]
                                        一条龙：关联知识库 + 设调用链 + 发布
    disable <sceneId>                   关闭知识库（保留配置，仅 nlpStatus=0）
    chain <sceneId> <order>             设语义调用顺序，如 docqa,xinghuo
    publish <sceneId>                   发布场景配置（生效）

说明
  - 官方向量模型: emb_v1_1024；LLM: xhdmx1(星火v3.5) / xhdmx2(星火v4.0)
  - splitType 拆分策略: 2=分隔符 3=自动目录 5=不拆分 7=智能拆分(推荐) 9=自定义目录
    文档类型推荐: 普通文章→7 | 有章节→3 | Q&A对话→2 | 整篇不拆→5 | 问答Excel→fileType=qa+split=7
  - 调用链 nlpAssistantInfo: docqa,xinghuo=先查库再问星火；xinghuo,docqa=反之；
    docqa=只用库；xinghuo=只用大模型
  - enable/disable/chain 后需 publish 才生效（enable 默认已含 publish）
"""
import sys

# Windows 下强制 stdout/stderr 使用 UTF-8，避免中文输出乱码
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

import json
import time
import xfyun_common as xc

# ==================== API 端点 ====================
# docqa 相关走 agent 代理网关
_DOC = "https://virtual-man.xfyun.cn/agent/proxyApi/flames-docqa/doc"
API_LIB_PAGE = _DOC + "/semantic-doc/lib/page"
API_LIB_CREATE = _DOC + "/semantic-doc/lib/create"
API_LIB_VERSION_PAGE = _DOC + "/semantic-doc/lib/version/page"
API_LABEL_LIST = _DOC + "/semantic-doc/label/list"
API_LABEL_CREATE = _DOC + "/semantic-doc/label/create"
API_MODEL_CONFIG = _DOC + "/model/config/list"
API_RENAME_CHECK = _DOC + "/semantic-doc/document/renameCheck"
API_FILE_UPLOAD = _DOC + "/semantic-doc/document/files/upload"
API_DOC_SPLIT = _DOC + "/semantic-doc/document"          # POST 拆分/向量化
API_CATEGORY_LIST = _DOC + "/semantic-doc/category/list"
API_CATEGORY_CREATE = _DOC + "/semantic-doc/category"   # POST 创建分类
API_DOC_PAGE = _DOC + "/semantic-doc/document/page"
API_DOC_DELETE = _DOC + "/semantic-doc/document"        # DELETE 删除文档
API_LIB_DELETE = _DOC + "/semantic-doc/lib"             # DELETE 删除知识库

# 场景配置走 zs_web
API_NLP_QUERY = "https://virtual-man.xfyun.cn/zs_web/nlp/query"
API_NLP_UPSERT = "https://virtual-man.xfyun.cn/zs_web/nlp/createOrUpdate"
API_INTERACT_UPSERT = "https://virtual-man.xfyun.cn/zs_web/interact/createOrUpdate"
API_SCENE_PUBLISH = "https://virtual-man.xfyun.cn/zs_web/scene/publish"

# ==================== 默认参数 ====================
DEFAULT_VECTOR_ID = "emb_v1_1024"
DEFAULT_LLM_ID = "xhdmx1"
DEFAULT_SPLIT_TYPE = 7            # 智能拆分
DEFAULT_DOMAIN = "generalv3.5"    # docqa nlpExtra 的 domain

# 拆分策略常量（splitType）
SPLIT_AUTO = 7          # 智能拆分（推荐，适用普通文章/说明书）
SPLIT_AUTO_TOC = 3      # 自动目录（有明确章节的文档）
SPLIT_CUSTOM_TOC = 9    # 自定义目录（自定义标题格式）
SPLIT_SEPARATOR = 2     # 分隔符拆分（纯 Q&A 对话格式，如"//"）
SPLIT_NONE = 5          # 不拆分（整篇作为一个知识单元）
SPLIT_QA_EXCEL = 7      # 问答对 Excel（fileType="qa" + splitType=7）

# 知识库问答默认提示词模板（${DOC_CONTENT} 检索文本占位、${USER_CONTENT} 用户问题占位）
DEFAULT_PROMPT_TEMPLATE = (
    "# 角色\n你是AI虚拟人智能助理，擅长总结问题或通过一定的推理计算得出答案。"
    "你的主要任务是通过理解输入的知识文本内容和历史会话信息，通过一定的推理计算回答用户提出的相关问题。\n"
    "## 知识文本：\n${DOC_CONTENT}\n"
    "## 用户的问题：\n${USER_CONTENT}\n"
    "## 回复要求：\n"
    "- 有条理地进行回复，回复的语句要工整、规范；\n"
    "- 请注意回复内容不要改变知识文本原本意思；\n"
    "- 回复尽量简洁。"
)

# docqa nlpExtra 的检索参数默认值
DEFAULT_NLP_EXTRA = {
    "embeddingTop": 5,        # 向量检索返回 Top N 段落
    "esTop": 0,               # 全文检索 Top N（0=不启用）
    "thresholdScore": 0.2,    # 相似度阈值 0-1，越高越严格
    "qqEmbThresholdScore": 0.8,
    "dialogueTop": 5,         # 最多使用几段历史对话
    "promptToken": 4096,
    "answerToken": 4096,
    "historyToken": 4096,
}


def _ok(resp):
    """docqa 网关返回 retcode==200；zs_web 返回 flag==True。统一判定成功。"""
    if not isinstance(resp, dict):
        return False
    if "retcode" in resp:
        return resp.get("retcode") == 200
    return bool(resp.get("flag"))


def _fail_desc(resp):
    if not isinstance(resp, dict):
        return "无响应"
    return resp.get("desc") or resp.get("message") or resp.get("msg") or str(resp)


# ==================== 只读查询 ====================
def list_kb(session, page_number=1, page_size=8, name=""):
    """知识库列表。返回 (items, total)。"""
    r = xc.get(session, API_LIB_PAGE, params={
        "pageNumber": page_number, "pageSize": page_size, "name": name,
        "tenantId": "", "account": "", "label": "",
    })
    if not _ok(r):
        return [], 0
    return r.get("items", []), r.get("total", 0)


def list_labels(session):
    r = xc.get(session, API_LABEL_LIST)
    return r.get("data", []) if _ok(r) else []


def list_models(session):
    """返回 {'vector': [...], 'llm': [...]}。"""
    r = xc.get(session, API_MODEL_CONFIG)
    if not _ok(r):
        return {"vector": [], "llm": []}
    data = r.get("data") or {}
    return {"vector": data.get("vector", []), "llm": data.get("llm", [])}


def list_versions(session, lib_id):
    r = xc.get(session, API_LIB_VERSION_PAGE, params={
        "name": "", "libId": lib_id, "pageSize": 10000, "pageNumber": 1,
    })
    return r.get("items", []) if _ok(r) else []


def list_categories(session, lib_id, version=1):
    r = xc.post(session, API_CATEGORY_LIST, {
        "name": "", "libId": lib_id, "version": version,
    })
    return r.get("data", []) if _ok(r) else []


def create_category(session, lib_id, name, parent="", version=1):
    """
    创建分类（可创建顶级或子分类）。
    parent: 父分类 id（空串=顶级分类）。
    返回创建的分类 dict（含 id）或 None。
    """
    r = xc.post(session, API_CATEGORY_CREATE, {
        "name": name, "parent": parent, "libId": lib_id, "version": version,
    })
    return r.get("data") if _ok(r) else None


def delete_document(session, doc_id):
    """删除文档（按文档 id，不是 fileID）。返回 True/False。"""
    r = xc.delete(session, f"{API_DOC_DELETE}/{doc_id}")
    return _ok(r)


def delete_lib(session, lib_id):
    """删除知识库。返回 True/False。"""
    r = xc.delete(session, f"{API_LIB_DELETE}/{lib_id}")
    return _ok(r)



def list_docs(session, lib_id, version=1, page_number=1, page_size=10,
              category="", file_extension="", status=None, name=""):
    r = xc.post(session, API_DOC_PAGE, {
        "libId": lib_id, "version": version, "category": category,
        "fileExtension": file_extension, "status": status or [], "name": name,
        "pageSize": page_size, "pageNumber": page_number,
    })
    if not _ok(r):
        return [], 0
    return r.get("items", []), r.get("total", 0)


def query_scene_nlp(session, scene_id):
    """查场景的 nlp 配置列表（含 docqa/大模型各条）。返回 list。"""
    r = xc.post(session, API_NLP_QUERY, {"sceneId": scene_id})
    if not _ok(r):
        return []
    data = r.get("data")
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return [data]
    return []


def find_docqa_config(session, scene_id):
    """在场景 nlp 配置里找 docqa 那一条，返回该条 dict 或 None。"""
    for item in query_scene_nlp(session, scene_id):
        if item.get("nlpType") == "docqa" or item.get("value") == "docqa":
            return item
    return None


# ==================== 创建（写） ====================
def create_label(session, name):
    r = xc.post(session, API_LABEL_CREATE, {"name": name})
    return r if _ok(r) else None


def create_kb(session, name, label="", desc="", icon="",
              vector_id=DEFAULT_VECTOR_ID, llm_id=DEFAULT_LLM_ID):
    """
    创建知识库。真实负载结构（抓包确认）：
      name/label/desc/icon 顶层，llmId 嵌在 config.spark.llmId，vectorId 顶层。
    icon 可空。返回响应 dict（data.id 为新 libId）。
    """
    payload = {
        "name": name,
        "label": label,
        "desc": desc,
        "icon": icon,
        "config": {"spark": {"llmId": llm_id}},
        "vectorId": vector_id,
    }
    r = xc.post(session, API_LIB_CREATE, payload)
    return r if _ok(r) else None


def _extract_lib_id(resp):
    """从 create_kb 响应里尽量取出 libId（不同网关字段可能不同）。"""
    if not isinstance(resp, dict):
        return None
    data = resp.get("data")
    if isinstance(data, dict):
        return data.get("libId") or data.get("id")
    if isinstance(data, str):   # 有些接口直接把 id 放在 data
        return data
    return None


# ==================== 上传文档流程（写） ====================
def rename_check(session, lib_id, filenames, version=1):
    """重名检查。返回重名文件名列表（空=无重名）。"""
    r = xc.post(session, API_RENAME_CHECK, {
        "libId": lib_id, "list": filenames, "version": version,
    })
    if not _ok(r):
        return None   # None 表示请求失败
    return r.get("data", [])


def upload_file(session, lib_id, file_path, file_type="text"):
    """
    上传单个文件（multipart/form-data）。
    注意：不能用 xc.post（它发 JSON），这里直接用 session 发 multipart，
    并临时去掉 Content-Type: application/json 头，让 requests 自动带 boundary。
    返回上传接口的 data（通常含 fileID）。
    """
    from pathlib import Path
    p = Path(file_path)
    if not p.exists():
        print(f"[错误] 文件不存在: {file_path}")
        return None

    # 关键：session 级 headers 里有 Content-Type: application/json，
    # 若不显式覆盖，会盖掉 requests 为 multipart 自动生成的 boundary 头，
    # 导致服务端收到 application/json 而报“系统异常”。
    # requests 约定：请求级 header 值为 None 时删除该头，从而自动生成 multipart 边界。
    headers = {"Content-Type": None}
    # 按扩展名猜文件的 Content-Type（浏览器实际发的是 text/markdown 等）
    import mimetypes
    ctype = mimetypes.guess_type(p.name)[0] or "application/octet-stream"
    if p.suffix.lower() == ".md":
        ctype = "text/markdown"
    files = {"file": (p.name, p.open("rb"), ctype)}
    data = {"fileType": file_type, "libId": lib_id}
    try:
        resp = session.post(API_FILE_UPLOAD, files=files, data=data,
                            headers=headers, timeout=120)
        if resp.status_code != 200:
            print(f"[错误] 上传 HTTP {resp.status_code}: {resp.text[:200]}")
            return None
        j = resp.json()
        if j.get("code") == 80000:
            print("[警告] 登录已失效，请删除 xfyun_cookies.json 后重新运行")
            return None
        if not _ok(j):
            print(f"[失败] 上传返回: {_fail_desc(j)}")
            return None
        return j.get("data", [])
    except Exception as e:
        print(f"[错误] 上传异常: {e}")
        return None
    finally:
        try:
            files["file"][1].close()
        except Exception:
            pass


def split_documents(session, lib_id, file_ids, version=1, category_id="",
                    file_type="text", split_type=DEFAULT_SPLIT_TYPE,
                    separator="", custom_menu=None):
    """对已上传的 fileID 列表做拆分/向量化。"""
    payload = {
        "libId": lib_id,
        "version": version,
        "categoryID": category_id,
        "fileType": file_type,
        "splitType": split_type,
        "customMenu": custom_menu or [],
        "separator": separator,
        "fileID": file_ids,
    }
    r = xc.post(session, API_DOC_SPLIT, payload)
    return r if _ok(r) else None


def wait_docs_ready(session, lib_id, version=1, timeout=600, interval=10):
    """
    轮询文档状态直到全部到达终态。实测：文档级 status 才反映处理进度
    （-2 处理中 → 1 就绪 / -3 采编异常），版本级 status 在处理期间恒为 -1，不可靠。
    返回 (all_ok: bool, summary: str)。all_ok 仅当所有文档 status==1。
    """
    start = time.time()
    summary = ""
    while time.time() - start < timeout:
        docs, total = list_docs(session, lib_id, version=version,
                                page_size=100, page_number=1)
        if not docs:
            time.sleep(interval)
            continue
        codes = [d.get("status") for d in docs]
        summary = ", ".join(f"{d.get('fileName')}:{_status_text(d.get('status'))}"
                            for d in docs)
        # 终态：不再有处理中(0/-2)
        pending = [c for c in codes if c in (0, -2, None)]
        if not pending:
            all_ok = all(c == 1 for c in codes)
            return all_ok, summary
        time.sleep(interval)
    return False, summary or "超时无文档状态"


# 兼容旧名
wait_version_ready = wait_docs_ready


# ==================== 关联场景（写） ====================
def _build_nlp_extra(db_list, template=None, base=None):
    """构建 docqa 的 nlpExtra dict。db_list: [{'name':libId,'version':None|int}]。"""
    extra = dict(DEFAULT_NLP_EXTRA)
    if base:  # 复用现有配置里的检索参数
        for k in DEFAULT_NLP_EXTRA:
            if k in base:
                extra[k] = base[k]
    # domain 必须非空（空会触发 "domain can not be blank"）。
    # 用 or 而非 .get(默认) —— 现有配置里 domain 若是空串也要兜底到默认。
    extra["domain"] = (base or {}).get("domain") or DEFAULT_DOMAIN
    extra["promptTemplate"] = template or (base or {}).get("promptTemplate") or DEFAULT_PROMPT_TEMPLATE
    extra["dbList"] = db_list
    return extra


def set_docqa_config(session, scene_id, db_list, nlp_status=1, template=None):
    """
    写入/更新场景的 docqa 知识库配置（nlp/createOrUpdate）。
    - 会先查现有 docqa 配置，带上其 id 走更新（避免重复创建/丢失原配置）
    - nlp_status: 1=开启 0=关闭
    db_list: [{'name': libId, 'version': None or int}, ...]
    """
    existing = find_docqa_config(session, scene_id)
    base_extra = {}
    if existing and existing.get("nlpExtra"):
        try:
            base_extra = json.loads(existing["nlpExtra"])
        except Exception:
            base_extra = {}

    nlp_extra = _build_nlp_extra(db_list, template=template, base=base_extra)

    payload = {
        "sceneId": scene_id,
        "nlpType": "docqa",
        "nlpStatus": nlp_status,
        "label": "知识库",
        "value": "docqa",
        "collapsed": False,
        "nlpExtra": json.dumps(nlp_extra, ensure_ascii=False),
    }
    if existing and existing.get("id") is not None:
        payload["id"] = existing["id"]

    r = xc.post(session, API_NLP_UPSERT, payload)
    return r if _ok(r) else None


def set_chain(session, scene_id, order="docqa,xinghuo", default_reply=""):
    """设置语义调用顺序（interact/createOrUpdate 的 nlpAssistantInfo）。"""
    r = xc.post(session, API_INTERACT_UPSERT, {
        "sceneId": scene_id,
        "nlpAssistantInfo": order,
        "defaultReply": default_reply,
    })
    return r if _ok(r) else None


def publish_scene(session, scene_id):
    r = xc.post(session, API_SCENE_PUBLISH, {"sceneId": scene_id})
    return _ok(r)


# ==================== CLI 辅助 ====================
def _parse_opts(argv):
    """把 --key value / --flag 拆成 (positional_list, opts_dict)。"""
    pos, opts = [], {}
    i = 0
    while i < len(argv):
        a = argv[i]
        if a.startswith("--"):
            key = a[2:]
            if i + 1 < len(argv) and not argv[i + 1].startswith("--"):
                opts[key] = argv[i + 1]
                i += 2
            else:
                opts[key] = True  # 布尔开关
                i += 1
        else:
            pos.append(a)
            i += 1
    return pos, opts


def _status_text(code):
    """把文档/版本状态数字翻译成人话（实测：1就绪 0/-2处理中 -1初始 -3采编异常）。"""
    return {1: "就绪", 0: "处理中", -1: "未训练/初始",
            -2: "处理中", -3: "采编异常"}.get(code, f"状态码{code}")


USAGE = __doc__


# ==================== 命令实现 ====================
def cmd_list(session, argv):
    pos, _ = _parse_opts(argv)
    page = int(pos[0]) if len(pos) > 0 else 1
    size = int(pos[1]) if len(pos) > 1 else 8
    name = pos[2] if len(pos) > 2 else ""
    items, total = list_kb(session, page, size, name)
    print(f"\n[知识库] 共 {total} 个，当前页 {len(items)} 个：\n")
    for i, it in enumerate(items, 1):
        print(f"{i}. {it.get('name')}")
        print(f"   libId:   {it.get('id')}")
        print(f"   标签:    {it.get('labelName') or '无'} ({it.get('label') or '-'})")
        print(f"   描述:    {it.get('desc') or '无'}")
        print(f"   版本:    v{it.get('version')}")
        print()


def cmd_labels(session, argv):
    labels = list_labels(session)
    print(f"\n[标签] 共 {len(labels)} 个：\n")
    for lb in labels:
        print(f"  {lb.get('name')}  (id={lb.get('id')})")


def cmd_models(session, argv):
    m = list_models(session)
    print("\n[向量模型]")
    for v in m["vector"]:
        dim = (v.get("config") or {}).get("dim")
        print(f"  {v.get('id')}  {v.get('name')}  (dim={dim})")
    print("\n[LLM 模型]")
    for l in m["llm"]:
        print(f"  {l.get('id')}  {l.get('name')}")


def cmd_versions(session, argv):
    pos, _ = _parse_opts(argv)
    if not pos:
        print("用法: versions <libId>")
        return
    vers = list_versions(session, pos[0])
    print(f"\n[版本] libId={pos[0]} 共 {len(vers)} 个：\n")
    for v in vers:
        print(f"  v{v.get('version')}  {v.get('name')}  "
              f"[{_status_text(v.get('status'))}]  "
              f"文档{v.get('docCount')} 段落{v.get('paraCount')}  "
              f"published={v.get('published')}")


def cmd_categories(session, argv):
    pos, _ = _parse_opts(argv)
    if not pos:
        print("用法: categories <libId> [version]")
        return
    version = int(pos[1]) if len(pos) > 1 else 1
    cats = list_categories(session, pos[0], version)
    print(f"\n[分类] libId={pos[0]} v{version} 共 {len(cats)} 个：\n")
    for c in cats:
        print(f"  {c.get('name')}  (categoryID={c.get('id')})")


def cmd_docs(session, argv):
    pos, _ = _parse_opts(argv)
    if not pos:
        print("用法: docs <libId> [version] [页码] [每页]")
        return
    version = int(pos[1]) if len(pos) > 1 else 1
    page = int(pos[2]) if len(pos) > 2 else 1
    size = int(pos[3]) if len(pos) > 3 else 10
    docs, total = list_docs(session, pos[0], version, page, size)
    print(f"\n[文档] libId={pos[0]} v{version} 共 {total} 个，当前页 {len(docs)} 个：\n")
    for d in docs:
        line = (f"  {d.get('fileName')}  [{_status_text(d.get('status'))}]  "
                f"{d.get('fileExtension')}  段落{d.get('docParagraphsCount')}  "
                f"{d.get('size')}B")
        print(line)
        if d.get("errorMsg"):
            print(f"      错误: {d.get('errorMsg')}")


def cmd_status(session, argv):
    pos, _ = _parse_opts(argv)
    if not pos:
        print("用法: status <sceneId>")
        return
    cfg = find_docqa_config(session, pos[0])
    if not cfg:
        print(f"[空] 场景 {pos[0]} 暂无 docqa 知识库配置")
        return
    print(f"\n[场景 docqa 配置] sceneId={pos[0]}")
    print(f"  配置id:    {cfg.get('id')}")
    print(f"  nlpStatus: {cfg.get('nlpStatus')} ({'开启' if cfg.get('nlpStatus') == 1 else '关闭'})")
    try:
        extra = json.loads(cfg.get("nlpExtra") or "{}")
        dbs = extra.get("dbList", [])
        print(f"  关联知识库({len(dbs)}):")
        for db in dbs:
            print(f"    - {db.get('name')}  (version={db.get('version')})")
        print(f"  检索参数:  embeddingTop={extra.get('embeddingTop')} "
              f"thresholdScore={extra.get('thresholdScore')} "
              f"dialogueTop={extra.get('dialogueTop')}")
    except Exception:
        print(f"  nlpExtra(原始): {cfg.get('nlpExtra')}")


def cmd_create_label(session, argv):
    pos, _ = _parse_opts(argv)
    if not pos:
        print("用法: create-label <name>")
        return
    r = create_label(session, pos[0])
    if r:
        data = r.get("data") or {}
        print(f"[OK] 标签已创建: {pos[0]}  (id={data.get('id') or data.get('labelId')})")
    else:
        print(f"[失败] {_fail_desc(r)}")


def cmd_create_kb(session, argv):
    pos, opts = _parse_opts(argv)
    if not pos:
        print("用法: create-kb <name> [--label 标签id] [--desc 描述] "
              "[--vector emb_v1_1024] [--llm xhdmx1]")
        return
    r = create_kb(session, pos[0],
                  label=opts.get("label", ""),
                  desc=opts.get("desc", ""),
                  vector_id=opts.get("vector", DEFAULT_VECTOR_ID),
                  llm_id=opts.get("llm", DEFAULT_LLM_ID))
    if r:
        lib_id = _extract_lib_id(r)
        print(f"[OK] 知识库已创建: {pos[0]}")
        print(f"     libId: {lib_id}")
        print(f"     下一步: python xfyun_knowledge.py upload {lib_id} <文件...> --wait")
    else:
        print(f"[失败] {_fail_desc(r)}")


def cmd_create_category(session, argv):
    """创建分类（顶级或子分类）。"""
    pos, opts = _parse_opts(argv)
    if len(pos) < 2:
        print("用法: create-category <libId> <name> [--parent 父分类id] [--version 1]")
        return
    lib_id, name = pos[0], pos[1]
    parent = opts.get("parent", "")
    version = int(opts.get("version", 1))
    r = create_category(session, lib_id, name, parent=parent, version=version)
    if r:
        cat_id = r.get("id")
        cat_type = "子分类" if parent else "顶级分类"
        print(f"[OK] {cat_type}已创建: {name}")
        print(f"     categoryId: {cat_id}")
        if not parent:
            print(f"     下一步创建子分类: python xfyun_knowledge.py create-category {lib_id} <子名> --parent {cat_id}")
    else:
        print(f"[失败] 创建分类失败")



def cmd_upload(session, argv):
    pos, opts = _parse_opts(argv)
    if len(pos) < 2:
        print("用法: upload <libId> <文件路径...> [--version N] "
              "[--category 分类id] [--split 7] [--file-type text|qa] [--wait]")
        print("说明: --file-type qa 表示问答对 Excel (.xlsx)，第一列=问题，第二列=答案")
        print("      --split: 2=分隔符 3=自动目录 5=不拆分 7=智能(默认) 9=自定义目录")
        return
    from pathlib import Path
    lib_id = pos[0]
    files = pos[1:]
    version = int(opts.get("version", 1))
    category_id = opts.get("category", "")
    split_type = int(opts.get("split", DEFAULT_SPLIT_TYPE))
    file_type = opts.get("file-type", "text")  # text | qa

    # categoryID 必填：为空会导致后端向量化一直卡在“处理中”。
    # 未显式指定时，自动取该库第一个分类的 id。
    if not category_id:
        cats = list_categories(session, lib_id, version)
        if not cats:
            print(f"[失败] 该库无可用分类，无法拆分。请先在平台为库 {lib_id} 建分类，"
                  f"或用 --category 指定")
            return
        category_id = cats[0].get("id")
        print(f"[信息] 未指定分类，自动使用默认分类: {cats[0].get('name')} "
              f"(categoryID={category_id})")

    names = [Path(f).name for f in files]

    # 1) 重名检查
    print(f"\n[步骤1] 重名检查 ({len(names)} 个文件)...")
    dup = rename_check(session, lib_id, names, version)
    if dup is None:
        print("[失败] 重名检查请求失败，终止")
        return
    if dup:
        print(f"[警告] 以下文件在库中已存在，仍会继续上传（可能产生重复）: {dup}")

    # 2) 逐个上传，收集 fileID
    print(f"\n[步骤2] 上传文件...")
    file_ids = []
    for f in files:
        print(f"  上传 {f} ...")
        data = upload_file(session, lib_id, f, file_type=file_type)
        if not data:
            print(f"  [失败] {f} 上传失败，终止后续步骤")
            return
        for item in (data if isinstance(data, list) else [data]):
            fid = item.get("fileID") or item.get("fileId") or item.get("id")
            if fid:
                file_ids.append(fid)
                print(f"    -> fileID={fid}")
    if not file_ids:
        print("[失败] 未获得任何 fileID，终止")
        return

    # 3) 拆分/向量化
    print(f"\n[步骤3] 拆分并向量化 (splitType={split_type})...")
    r = split_documents(session, lib_id, file_ids, version=version,
                        category_id=category_id, split_type=split_type)
    if not r:
        print(f"[失败] 拆分请求失败: {_fail_desc(r)}")
        return
    print("[OK] 已提交拆分/向量化任务")

    # 4) 可选：轮询文档处理到终态
    if opts.get("wait"):
        wait_timeout = int(opts.get("timeout", 600))
        print(f"\n[步骤4] 轮询文档处理状态直到就绪（最多 {wait_timeout}s）...")
        all_ok, summary = wait_docs_ready(session, lib_id, version,
                                          timeout=wait_timeout)
        if all_ok:
            print(f"[OK] 文档处理完成，知识库已就绪  ({summary})")
        else:
            print(f"[未完成] 状态: {summary}")
            print(f"         可稍后用: python xfyun_knowledge.py docs {lib_id}")
    else:
        print(f"\n[提示] 文档正在后台处理，用以下命令查看进度:")
        print(f"        python xfyun_knowledge.py docs {lib_id}")


def cmd_enable(session, argv):
    """一条龙：关联知识库 + 设调用链 + 发布，让场景真正“打开知识库对话”。

    用法两种：
      enable <sceneId> <libId...>   关联指定库并开启
      enable <sceneId>              不指定库时，沿用场景现有已关联的库，仅打开对话
    “打开知识库对话”在讯飞需两个条件同时成立：docqa 的 nlpStatus=1，
    且 interact.nlpAssistantInfo 里含 docqa（本命令的调用链默认 docqa,xinghuo 已满足）。
    """
    pos, opts = _parse_opts(argv)
    if len(pos) < 1:
        print("用法: enable <sceneId> [libId...] [--chain docqa,xinghuo] [--no-publish]")
        return
    scene_id = pos[0]
    lib_ids = pos[1:]
    chain = opts.get("chain", "docqa,xinghuo")

    if lib_ids:
        db_list = [{"name": lid, "version": None} for lid in lib_ids]
        print(f"\n[开启知识库] 场景 {scene_id} <- {len(lib_ids)} 个知识库")
        for lid in lib_ids:
            print(f"    - {lid}")
    else:
        # 未指定库：沿用现有 docqa 配置里已关联的 dbList
        existing = find_docqa_config(session, scene_id)
        db_list = []
        if existing and existing.get("nlpExtra"):
            try:
                db_list = json.loads(existing["nlpExtra"]).get("dbList", [])
            except Exception:
                db_list = []
        if not db_list:
            print(f"[失败] 场景 {scene_id} 尚未关联任何知识库，请指定 libId：")
            print(f"        python xfyun_knowledge.py enable {scene_id} <libId...>")
            return
        print(f"\n[开启知识库] 场景 {scene_id}，沿用现有已关联的 {len(db_list)} 个知识库")
        for db in db_list:
            print(f"    - {db.get('name')}")

    # 步骤1: nlp 关联 + 开启（docqa.nlpStatus=1）
    print("\n[步骤1] 开启知识库检索 (nlp/createOrUpdate, docqa nlpStatus=1)...")
    r1 = set_docqa_config(session, scene_id, db_list, nlp_status=1)
    if not r1:
        print(f"[失败] 关联失败: {_fail_desc(r1)}")
        return
    print("[OK] 知识库检索已开启")

    # 步骤2: 设调用链
    print(f"\n[步骤2] 设置语义调用顺序: {chain} ...")
    r2 = set_chain(session, scene_id, order=chain)
    if not r2:
        print(f"[失败] 调用链设置失败: {_fail_desc(r2)}")
        return
    print("[OK] 调用链已设置")

    # 步骤3: 发布
    if opts.get("no-publish"):
        print(f"\n[提示] 已跳过发布，运行以下命令生效:")
        print(f"        python xfyun_knowledge.py publish {scene_id}")
        return
    print("\n[步骤3] 发布配置 (scene/publish)...")
    if publish_scene(session, scene_id):
        print("[OK] 配置已发布，知识库现已生效！")
    else:
        print("[失败] 发布失败，配置未生效")


def cmd_disable(session, argv):
    """关闭知识库：读现有配置，仅把 nlpStatus 翻成 0，保留 dbList 不变。"""
    pos, opts = _parse_opts(argv)
    if not pos:
        print("用法: disable <sceneId> [--no-publish]")
        return
    scene_id = pos[0]
    cfg = find_docqa_config(session, scene_id)
    if not cfg:
        print(f"[提示] 场景 {scene_id} 没有 docqa 配置，无需关闭")
        return

    # 复用现有 dbList
    try:
        extra = json.loads(cfg.get("nlpExtra") or "{}")
        db_list = extra.get("dbList", [])
    except Exception:
        db_list = []

    print(f"\n[关闭知识库] 场景 {scene_id}（保留 {len(db_list)} 个库的配置，仅关闭）")
    r = set_docqa_config(session, scene_id, db_list, nlp_status=0)
    if not r:
        print(f"[失败] {_fail_desc(r)}")
        return
    print("[OK] 知识库已关闭 (nlpStatus=0)")

    if not opts.get("no-publish"):
        if publish_scene(session, scene_id):
            print("[OK] 已发布，关闭生效")
        else:
            print("[警告] 发布失败，请手动 publish")


def cmd_chain(session, argv):
    pos, _ = _parse_opts(argv)
    if len(pos) < 2:
        print("用法: chain <sceneId> <order>")
        print("  order 取值: docqa,xinghuo | xinghuo,docqa | docqa | xinghuo")
        return
    r = set_chain(session, pos[0], order=pos[1])
    if r:
        print(f"[OK] 调用顺序已设为: {pos[1]}")
        print(f"[提示] 运行 publish {pos[0]} 使其生效")
    else:
        print(f"[失败] {_fail_desc(r)}")


def cmd_publish(session, argv):
    pos, _ = _parse_opts(argv)
    if not pos:
        print("用法: publish <sceneId>")
        return
    if publish_scene(session, pos[0]):
        print(f"[OK] 场景 {pos[0]} 配置已发布，现已生效！")
    else:
        print(f"[失败] 发布失败")


def cmd_delete_doc(session, argv):
    """删除文档（不可逆）。"""
    pos, _ = _parse_opts(argv)
    if not pos:
        print("用法: delete-doc <docId>")
        print("说明: docId 是文档的 id（从 docs 命令获取），不是 fileID")
        return
    doc_id = pos[0]
    confirm = input(f"[警告] 即将删除文档 {doc_id}，此操作不可逆！输入 yes 确认: ").strip()
    if confirm.lower() != "yes":
        print("[取消] 未删除")
        return
    if delete_document(session, doc_id):
        print(f"[OK] 文档 {doc_id} 已删除")
    else:
        print(f"[失败] 删除失败")


def cmd_delete_kb(session, argv):
    """删除知识库（不可逆）。"""
    pos, _ = _parse_opts(argv)
    if not pos:
        print("用法: delete-kb <libId>")
        return
    lib_id = pos[0]
    confirm = input(f"[警告] 即将删除知识库 {lib_id} 及其所有文档，此操作不可逆！输入库 ID 确认: ").strip()
    if confirm != lib_id:
        print("[取消] 未删除")
        return
    if delete_lib(session, lib_id):
        print(f"[OK] 知识库 {lib_id} 已删除")
    else:
        print(f"[失败] 删除失败")


# ==================== 入口 ====================
_COMMANDS = {
    "list": cmd_list,
    "labels": cmd_labels,
    "models": cmd_models,
    "versions": cmd_versions,
    "categories": cmd_categories,
    "docs": cmd_docs,
    "status": cmd_status,
    "create-label": cmd_create_label,
    "create-kb": cmd_create_kb,
    "create-category": cmd_create_category,
    "upload": cmd_upload,
    "enable": cmd_enable,
    "disable": cmd_disable,
    "chain": cmd_chain,
    "publish": cmd_publish,
    "delete-doc": cmd_delete_doc,
    "delete-kb": cmd_delete_kb,
}


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help", "help"):
        print(USAGE)
        return
    cmd = sys.argv[1]
    handler = _COMMANDS.get(cmd)
    if not handler:
        print(f"未知命令: {cmd}\n")
        print(USAGE)
        sys.exit(1)

    session = xc.get_session()
    if not session:
        print("[错误] 登录失败")
        sys.exit(1)

    handler(session, sys.argv[2:])


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[中断] 用户中断")
    except Exception as e:
        print(f"\n[错误] {e}")
        import traceback
        traceback.print_exc()








