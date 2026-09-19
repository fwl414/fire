from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Any, Dict, List
import uuid

from services.runtime_db import connect_runtime_db

SEED_ENTRIES = [
    ("电气火灾处置原则", "电气安全", "疑似电气火灾应优先切断电源，未断电前不宜直接用水扑救。应根据现场情况选择干粉、二氧化碳等适用灭火器材，并通知专业人员排查线路。", "电气火灾,切断电源,干粉灭火器,二氧化碳灭火器,触电风险", "系统内置知识库"),
    ("插排串联与超负荷用电风险", "电气安全", "插排串联、大功率设备混接、线路老化和超负荷用电容易造成导线发热、绝缘破损和短路，应立即停止违规用电并重新规划供电线路。", "插排串联,超负荷,大功率,短路,线路老化", "系统内置知识库"),
    ("配电箱周边安全距离", "电气安全", "配电箱、配电柜前方和周边应保持操作、检修和散热空间，不应堆放纸箱、塑料、清洁用品等可燃杂物。", "配电箱,配电柜,堆物,检修空间,可燃物", "系统内置知识库"),
    ("电线私拉乱接隐患", "电气安全", "私拉乱接电线、临时线路长期使用、线缆拖地和绝缘层破损会增加短路、漏电和火灾风险，应由专业人员整改。", "私拉乱接,临时线路,线缆拖地,漏电,短路", "系统内置知识库"),
    ("机房电气异常处置", "电气安全", "机房出现焦糊味、烟雾、温度异常或设备异响时，应及时确认电源和设备状态，必要时切断相关回路并启动应急处置。", "机房,焦糊味,烟雾,温度异常,断电", "系统内置知识库"),
    ("消防通道保持畅通", "疏散安全", "消防通道、疏散通道和安全出口应保持畅通，不得堆放杂物、停放车辆或设置影响疏散的障碍物。", "消防通道,疏散通道,安全出口,堵塞,杂物", "系统内置知识库"),
    ("安全出口管理", "疏散安全", "安全出口应保持可开启状态，不应锁闭、遮挡或被占用；安全出口标识应清晰可见，便于人员紧急疏散。", "安全出口,锁闭,遮挡,疏散,逃生", "系统内置知识库"),
    ("疏散指示标志检查", "疏散安全", "疏散指示标志应安装牢固、方向正确、持续可见；发现损坏、缺失、遮挡或方向错误时应及时整改。", "疏散指示,指示标志,方向错误,遮挡,缺失", "系统内置知识库"),
    ("应急照明检查", "疏散安全", "应急照明灯应具备断电后自动点亮能力，日常巡检需检查外观、电源、试验按钮和持续照明能力。", "应急照明,断电,试验按钮,疏散,照明", "系统内置知识库"),
    ("楼梯间防火门管理", "疏散安全", "防火门应保持完好并能自行关闭，常闭防火门不得长期敞开或被物品卡住，闭门器、顺序器应有效。", "防火门,闭门器,常闭,楼梯间,自行关闭", "系统内置知识库"),
    ("灭火器配置要求", "消防设施", "灭火器应按场所火灾类别和危险等级配置，放置在明显、便于取用的位置，并保持数量充足。", "灭火器,配置,数量,取用,火灾类别", "系统内置知识库"),
    ("灭火器巡检要点", "消防设施", "灭火器巡检应关注压力表指针、铅封、喷管、瓶体锈蚀、有效期、摆放位置和是否被遮挡。", "灭火器,压力表,铅封,有效期,遮挡", "系统内置知识库"),
    ("灭火器使用步骤", "消防设施", "使用灭火器通常遵循提、拔、握、压等步骤，站在上风方向，对准火焰根部喷射，并保持安全距离。", "灭火器使用,提拔握压,上风方向,火焰根部", "系统内置知识库"),
    ("消火栓箱检查", "消防设施", "室内消火栓箱应保持箱门可开启，水带、水枪、接口等组件齐全，周边不得遮挡或堆放杂物。", "消火栓,消防栓,水带,水枪,箱门", "系统内置知识库"),
    ("消防水源和水压关注点", "消防设施", "消防水源、水泵和管网压力关系到灭火系统可用性，发现压力异常、水泵故障或阀门关闭应及时处理。", "消防水源,水泵,水压,阀门,管网", "系统内置知识库"),
    ("火灾自动报警系统", "报警联动", "火灾自动报警系统应关注探测器、手动报警按钮、声光警报器、消防联动控制器和报警主机运行状态。", "火灾自动报警,探测器,手报,声光警报器,联动控制", "系统内置知识库"),
    ("烟感探测器异常", "报警联动", "烟感探测器被遮挡、污染、拆除或离线会影响早期火情发现，应保持探测器清洁、在线和无遮挡。", "烟感,烟雾探测器,离线,遮挡,污染", "系统内置知识库"),
    ("温感探测器异常", "报警联动", "温感探测器用于感知温度异常，设备离线、损坏或安装环境不当会降低报警可靠性。", "温感,温度异常,探测器,报警,离线", "内置知识库"),
    ("消防控制室值班处置", "报警联动", "消防控制室收到报警信号后，应核实报警部位、确认火情、启动相应处置流程并做好记录。", "消防控制室,值班,报警信号,核实,记录", "系统内置知识库"),
    ("联动设备巡检", "报警联动", "防排烟、消防广播、电梯迫降、防火卷帘等联动设备应定期测试，确保火灾时能按预案动作。", "防排烟,消防广播,电梯迫降,防火卷帘,联动", "系统内置知识库"),
    ("可燃物堆放管理", "场景管理", "纸箱、塑料、泡沫、木板等可燃物应远离电源、配电箱、热源和疏散通道，避免形成火灾荷载。", "可燃物,纸箱,塑料,泡沫,热源", "系统内置知识库"),
    ("实验室消防安全", "场景管理", "实验室应规范管理电气设备、化学品、可燃物和疏散通道，发现插排串联、纸箱堆放和通道堵塞应及时整改。", "实验室,化学品,插排,纸箱,通道", "系统内置知识库"),
    ("仓库消防安全", "场景管理", "仓库应控制堆垛高度和间距，保持通道畅通，严禁堵塞消火栓和安全出口，并加强用电管理。", "仓库,堆垛,通道,消火栓,安全出口", "系统内置知识库"),
    ("宿舍消防安全", "场景管理", "宿舍内不得使用大功率违规电器、私拉乱接电线或在疏散通道停放电动车，应保持逃生通道畅通。", "宿舍,大功率电器,私拉乱接,电动车,疏散", "系统内置知识库"),
    ("厨房与餐饮场所消防", "场景管理", "厨房应加强燃气、电气、油烟管道和灭火设施管理，定期清洗油烟管道，发现燃气泄漏应立即通风并关闭阀门。", "厨房,燃气,油烟管道,阀门,泄漏", "系统内置知识库"),
    ("电动车违规充电", "电动车安全", "电动车及蓄电池不应在楼道、室内、安全出口或疏散通道停放充电，应在集中充电区域规范充电。", "电动车,蓄电池,飞线充电,室内充电,热失控", "系统内置知识库"),
    ("电池热失控风险", "电动车安全", "锂电池受挤压、过充、私自改装或高温影响可能发生热失控，出现冒烟、异味、鼓包应立即隔离处置。", "锂电池,热失控,过充,冒烟,鼓包", "系统内置知识库"),
    ("初期火灾处置", "应急处置", "发现初期火灾时，应先确保人员安全，判断火源性质，选择适用灭火器材，必要时报警并组织疏散。", "初期火灾,灭火,报警,疏散,人员安全", "系统内置知识库"),
    ("发现烟雾或焦糊味", "应急处置", "发现烟雾、焦糊味或异常发热时，应立即确认位置，切断可能相关电源，疏散周边人员并上报。", "烟雾,焦糊味,异常发热,切断电源,上报", "系统内置知识库"),
    ("人员疏散原则", "应急处置", "应急疏散应遵循就近、安全、有序原则，优先保障人员生命安全，不乘坐普通电梯，听从现场指挥。", "疏散,逃生,电梯,现场指挥,生命安全", "系统内置知识库"),
    ("报警与信息上报", "应急处置", "发生火情或重大隐患时，应按预案上报消防安全责任人，必要时拨打119并说明地点、火情、人员情况和联系方式。", "报警,119,上报,消防安全责任人,火情", "系统内置知识库"),
    ("整改工单闭环", "整改闭环", "消防隐患整改应明确责任人、整改措施、整改期限和复查要求，形成派单、整改、复查、闭环的管理过程。", "整改工单,责任人,整改期限,复查,闭环", "系统内置知识库"),
    ("高风险隐患处置时限", "整改闭环", "高风险隐患宜尽快整改并复查，涉及疏散、电气、报警联动和消防设施不可用的隐患应优先处理。", "高风险,整改时限,复查,优先处理,隐患", "系统内置知识库"),
    ("复查不通过处理", "整改闭环", "隐患复查不通过时，应退回整改并说明原因，必要时升级责任层级或采取临时管控措施。", "复查不通过,退回整改,升级,临时管控", "系统内置知识库"),
    ("风险等级解释", "风险评估", "低风险表示暂未发现明显重大隐患；中风险需安排整改；高风险需尽快处理并复查；严重风险需要立即处置并可能触发应急流程。", "低风险,中风险,高风险,严重风险,风险等级", "系统内置知识库"),
    ("多隐患叠加风险", "风险评估", "当消防通道堵塞、电气隐患、可燃物堆放和消防设施异常同时出现时，风险会叠加，应提高风险等级和处置优先级。", "多隐患,风险叠加,处置优先级,综合风险", "系统内置知识库"),
    ("硬件事件进入Agent", "硬件事件", "烟感报警、温度异常、电气火灾探测、设备离线和人工上报等事件可以作为Agent输入，触发风险评估、工单和复查流程。", "硬件事件,烟感报警,温度异常,设备离线,Agent", "系统内置知识库"),
    ("摄像头截图巡检", "硬件事件", "摄像头截图可作为视觉巡检输入，用于辅助识别通道堵塞、设施遮挡、可燃物堆放等现场隐患。", "摄像头,截图,视觉巡检,通道堵塞,设施遮挡", "系统内置知识库"),
    ("消防设施操作员理论学习", "消防学习", "消防设施操作员理论学习应覆盖消防基础知识、建筑防火、消防设施、报警联动、应急处置和安全管理等内容。", "消防设施操作员,理论考试,消防基础,建筑防火", "系统内置知识库"),
    ("消防设施操作员实操学习", "消防学习", "实操学习应关注设备识别、巡检操作、报警处置、设施测试、故障判断和记录填写等岗位能力。", "消防设施操作员,实操考试,巡检操作,报警处置,故障判断", "系统内置知识库"),
    ("错题本学习方法", "消防学习", "错题本应按知识点、模块和错误原因整理，结合课程和相似题进行复习，逐步降低薄弱模块错误率。", "错题本,薄弱知识点,复习,相似题,学习计划", "系统内置知识库"),
    ("RAG问答使用原则", "知识增强", "RAG问答应先检索知识库，再结合引用生成回答；当依据不足时应提示用户补充信息，避免编造不确定内容。", "RAG,知识库,引用,依据不足,问答", "系统内置知识库"),
    ("巡检报告留痕", "报告管理", "巡检报告应记录巡检地点、时间、隐患、风险评分、处置建议、工单状态和复查结论，便于追溯。", "巡检报告,留痕,风险评分,工单状态,复查", "系统内置知识库"),
]


def _connect():
    conn = connect_runtime_db()
    conn.execute("""
    CREATE TABLE IF NOT EXISTS rag_entries (
        id TEXT PRIMARY KEY,
        title TEXT,
        category TEXT,
        content TEXT,
        keywords TEXT,
        source TEXT,
        enabled INTEGER,
        created_at TEXT,
        updated_at TEXT
    )
    """)
    conn.commit()
    _ensure_seed_entries(conn)
    return conn


def _ensure_seed_entries(conn: sqlite3.Connection):
    """初始化或增量补齐内置知识库。即使旧版本数据库里只有3条，也会自动补齐到V11知识库规模。"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    existing = {row["title"] for row in conn.execute("SELECT title FROM rag_entries").fetchall()}
    for title, category, content, keywords, source in SEED_ENTRIES:
        if title in existing:
            continue
        conn.execute(
            "INSERT INTO rag_entries VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (f"RAG-{str(uuid.uuid4())[:8].upper()}", title, category, content, keywords, source, 1, now, now),
        )
    conn.commit()


def _row(row) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "title": row["title"],
        "category": row["category"],
        "content": row["content"],
        "keywords": row["keywords"],
        "source": row["source"],
        "enabled": bool(row["enabled"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def list_rag_entries(category: str = "", enabled: str = "") -> List[Dict[str, Any]]:
    with _connect() as conn:
        sql = "SELECT * FROM rag_entries WHERE 1=1"
        params = []
        if category:
            sql += " AND category = ?"
            params.append(category)
        if enabled != "":
            sql += " AND enabled = ?"
            params.append(1 if enabled in ["1", "true", "True", "启用"] else 0)
        sql += " ORDER BY category ASC, updated_at DESC"
        rows = conn.execute(sql, params).fetchall()
    return [_row(r) for r in rows]


def upsert_rag_entry(payload: Dict[str, Any]) -> Dict[str, Any]:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry_id = payload.get("id") or f"RAG-{str(uuid.uuid4())[:8].upper()}"
    with _connect() as conn:
        old = conn.execute("SELECT * FROM rag_entries WHERE id = ?", (entry_id,)).fetchone()
        created_at = old["created_at"] if old else now
        conn.execute(
            """
            INSERT OR REPLACE INTO rag_entries
            (id, title, category, content, keywords, source, enabled, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                entry_id,
                payload.get("title", ""),
                payload.get("category", "综合知识"),
                payload.get("content", ""),
                payload.get("keywords", ""),
                payload.get("source", "用户维护"),
                1 if payload.get("enabled", True) else 0,
                created_at,
                now,
            ),
        )
        conn.commit()
    return get_rag_entry(entry_id)


def get_rag_entry(entry_id: str) -> Dict[str, Any]:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM rag_entries WHERE id = ?", (entry_id,)).fetchone()
    return _row(row) if row else {}


def delete_rag_entry(entry_id: str) -> Dict[str, Any]:
    with _connect() as conn:
        conn.execute("DELETE FROM rag_entries WHERE id = ?", (entry_id,))
        conn.commit()
    return {"id": entry_id, "deleted": True}


def search_rag_entries(query: str = "", limit: int = 8) -> Dict[str, Any]:
    query = (query or "").strip()
    entries = list_rag_entries(enabled="1")
    scored = []
    tokens = [x for x in query.replace("，", " ").replace(",", " ").replace("、", " ").split() if x]
    for e in entries:
        text = f"{e['title']} {e['category']} {e['content']} {e['keywords']}"
        score = 0
        matched = []
        if query and query in text:
            score += 10
            matched.append(query)
        for token in tokens:
            if token in text:
                score += 4
                matched.append(token)
        # 中文短句没有空格时，兼容标题、关键词和常用消防词命中
        for kw in [k.strip() for k in (e.get('keywords') or '').replace('，', ',').split(',') if k.strip()]:
            if kw and kw in query:
                score += 6
                matched.append(kw)
        if score > 0 or not query:
            item = dict(e)
            item["score"] = score
            item["matched_keywords"] = list(dict.fromkeys(matched))[:8]
            scored.append(item)
    scored.sort(key=lambda x: x["score"], reverse=True)
    return {"query": query, "results": scored[:limit], "count": len(scored)}


def get_rag_stats() -> Dict[str, Any]:
    entries = list_rag_entries()
    enabled = [e for e in entries if e["enabled"]]
    categories: Dict[str, int] = {}
    sources: Dict[str, int] = {}
    for e in entries:
        categories[e["category"]] = categories.get(e["category"], 0) + 1
        sources[e["source"]] = sources.get(e["source"], 0) + 1
    return {
        "total": len(entries),
        "enabled": len(enabled),
        "disabled": len(entries) - len(enabled),
        "categories": [{"name": k, "count": v} for k, v in sorted(categories.items())],
        "sources": [{"name": k, "count": v} for k, v in sorted(sources.items())],
    }
