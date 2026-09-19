from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Any, Tuple


KNOWLEDGE_DIR = Path(__file__).resolve().parent.parent / "data" / "fire_knowledge"

SYNONYMS: Dict[str, List[str]] = {
    "消防通道堵塞": ["消防通道", "疏散通道", "安全出口", "逃生通道", "堵塞", "占用", "杂物"],
    "消防设施被遮挡": ["消火栓", "消防栓", "消防箱", "报警按钮", "遮挡", "设施可用"],
    "灭火器缺失": ["灭火器", "缺失", "配置", "补齐"],
    "灭火器被遮挡": ["灭火器", "遮挡", "取用", "可见"],
    "插座过载": ["插排", "插座", "超负荷", "大功率", "串联", "电气火灾"],
    "电线杂乱": ["电线", "线路", "线缆", "私拉乱接", "绝缘", "短路"],
    "配电箱周围堆物": ["配电箱", "配电柜", "堆物", "检修空间", "电气"],
    "可燃物堆积": ["可燃物", "易燃物", "纸箱", "塑料", "泡沫", "火灾荷载"],
    "电动车违规充电": ["电动车", "电瓶车", "蓄电池", "飞线充电", "违规充电", "热失控"],
    "明火": ["明火", "火情", "初期火灾", "报警", "疏散"],
    "烟雾": ["烟雾", "焦糊味", "火情", "切断电源", "报警", "疏散"],
}

GENERAL_TERMS = [
    "消防通道", "疏散通道", "安全出口", "灭火器", "消火栓", "消防设施",
    "电气火灾", "插排", "插座", "超负荷", "电线", "配电箱", "明火", "烟雾",
    "焦糊味", "电动车", "违规充电", "可燃物", "纸箱", "塑料", "实验室",
    "宿舍", "机房", "报警", "疏散", "应急", "整改", "复查"
]


def _parse_front_matter(text: str) -> Tuple[Dict[str, str], str]:
    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text

    meta_text = parts[1]
    body = parts[2].strip()
    meta: Dict[str, str] = {}
    for line in meta_text.splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip()
    return meta, body


def _load_documents() -> List[Dict[str, Any]]:
    docs: List[Dict[str, Any]] = []
    if not KNOWLEDGE_DIR.exists():
        return docs

    for p in sorted(list(KNOWLEDGE_DIR.glob("*.txt")) + list(KNOWLEDGE_DIR.glob("*.md"))):
        raw = p.read_text(encoding="utf-8", errors="ignore").strip()
        if not raw:
            continue

        meta, body = _parse_front_matter(raw)
        title = meta.get("title", p.stem)
        category = meta.get("category", "通用知识")
        source = meta.get("source", "系统内置消防知识库")
        keyword_text = meta.get("keywords", "")
        keywords = [x.strip() for x in re.split(r"[,，]", keyword_text) if x.strip()]

        if body.startswith("标题："):
            first, _, rest = body.partition("\n")
            title = first.replace("标题：", "").strip()
            body = rest.strip() or body

        docs.append({
            "doc_id": p.stem,
            "title": title,
            "category": category,
            "content": body,
            "source": p.name,
            "source_type": source,
            "keywords": keywords,
        })

    return docs


def _make_chunk(doc: Dict[str, Any], text: str, idx: int) -> Dict[str, Any]:
    return {
        "chunk_id": f"{doc['doc_id']}#{idx}",
        "doc_id": doc["doc_id"],
        "title": doc["title"],
        "category": doc["category"],
        "content": text,
        "source": doc["source"],
        "source_type": doc["source_type"],
        "keywords": doc.get("keywords", []),
    }


def _split_chunks(doc: Dict[str, Any], max_chars: int = 360) -> List[Dict[str, Any]]:
    text = doc["content"]
    blocks = re.split(r"\n(?=## |\# |\d+\. |- )", text)
    chunks: List[Dict[str, Any]] = []
    current = ""

    for block in blocks:
        block = block.strip()
        if not block:
            continue

        if len(current) + len(block) <= max_chars:
            current = (current + "\n" + block).strip()
        else:
            if current:
                chunks.append(_make_chunk(doc, current, len(chunks)))
            current = block

    if current:
        chunks.append(_make_chunk(doc, current, len(chunks)))

    return chunks


def _expand_query(query: str, hazards: List[str] | None = None) -> List[str]:
    terms = set()
    query = query or ""

    for t in GENERAL_TERMS:
        if t in query:
            terms.add(t)

    for h in hazards or []:
        if h:
            terms.add(h)
            for s in SYNONYMS.get(h, []):
                terms.add(s)

    for word in re.split(r"[，,。；;、\s]+", query):
        word = word.strip()
        if len(word) >= 2:
            terms.add(word)

    return list(terms)


def _score_chunk(chunk: Dict[str, Any], terms: List[str], hazards: List[str] | None = None) -> Tuple[float, List[str], List[str]]:
    haystack = f"{chunk['title']} {chunk['category']} {' '.join(chunk.get('keywords', []))} {chunk['content']}"
    matched: List[str] = []
    reasons: List[str] = []
    score = 0.0

    for term in terms:
        if term and term in haystack:
            matched.append(term)
            if term in chunk["title"]:
                score += 4
                reasons.append(f"标题命中：{term}")
            elif term in chunk["category"]:
                score += 3
                reasons.append(f"类别命中：{term}")
            elif term in chunk.get("keywords", []):
                score += 3
                reasons.append(f"关键词命中：{term}")
            else:
                score += 1.5
                reasons.append(f"正文命中：{term}")

    for h in hazards or []:
        if h and h in chunk["content"]:
            score += 4
            matched.append(h)
            reasons.append(f"隐患直接命中：{h}")
        for syn in SYNONYMS.get(h, []):
            if syn in haystack:
                score += 1
                matched.append(syn)

    for scene in ["实验室", "宿舍", "机房", "配电"]:
        if scene in " ".join(terms) and scene in haystack:
            score += 2
            reasons.append(f"场景匹配：{scene}")

    matched = list(dict.fromkeys(matched))
    reasons = list(dict.fromkeys(reasons))
    return score, matched, reasons


def retrieve_fire_knowledge(query: str, hazards: List[str] | None = None, limit: int = 5) -> List[Dict[str, Any]]:
    docs = _load_documents()
    chunks: List[Dict[str, Any]] = []
    for doc in docs:
        chunks.extend(_split_chunks(doc))

    terms = _expand_query(query, hazards)
    scored: List[Dict[str, Any]] = []

    for chunk in chunks:
        raw_score, matched, reasons = _score_chunk(chunk, terms, hazards)
        if raw_score <= 0:
            continue

        item = dict(chunk)
        item["raw_score"] = round(raw_score, 2)
        item["score"] = round(min(raw_score / 18, 1.0), 2)
        item["matched_keywords"] = matched[:10]
        item["match_reasons"] = reasons[:8]
        item["citation"] = f"{chunk['source']} / {chunk['title']}"
        scored.append(item)

    scored.sort(key=lambda x: (x["score"], x["raw_score"]), reverse=True)

    results: List[Dict[str, Any]] = []
    seen_chunks = set()
    for item in scored:
        if item["chunk_id"] in seen_chunks:
            continue
        seen_chunks.add(item["chunk_id"])
        results.append(item)
        if len(results) >= limit:
            break

    if not results:
        for doc in docs[:limit]:
            chunk = _make_chunk(doc, doc["content"][:360], 0)
            chunk["raw_score"] = 0
            chunk["score"] = 0.1
            chunk["matched_keywords"] = []
            chunk["match_reasons"] = ["未命中关键词，作为通用知识兜底返回"]
            chunk["citation"] = f"{chunk['source']} / {chunk['title']}"
            results.append(chunk)

    return results


def build_rag_context(refs: List[Dict[str, Any]]) -> str:
    lines = []
    for i, r in enumerate(refs, start=1):
        lines.append(
            f"【引用{i}】{r['title']}｜类别：{r.get('category', '')}｜来源：{r.get('source', '')}｜得分：{r.get('score', 0)}\n"
            f"匹配原因：{'；'.join(r.get('match_reasons', []))}\n"
            f"{r['content']}"
        )
    return "\n\n".join(lines)


def get_knowledge_overview() -> Dict[str, Any]:
    docs = _load_documents()
    categories: Dict[str, int] = {}
    for d in docs:
        categories[d["category"]] = categories.get(d["category"], 0) + 1

    chunks = []
    for d in docs:
        chunks.extend(_split_chunks(d))

    return {
        "doc_count": len(docs),
        "chunk_count": len(chunks),
        "categories": [{"name": k, "count": v} for k, v in sorted(categories.items())],
        "documents": [
            {
                "doc_id": d["doc_id"],
                "title": d["title"],
                "category": d["category"],
                "source": d["source"],
                "keywords": d.get("keywords", []),
            }
            for d in docs
        ],
    }


def debug_retrieve(query: str, hazards: List[str] | None = None) -> Dict[str, Any]:
    terms = _expand_query(query, hazards)
    refs = retrieve_fire_knowledge(query, hazards, limit=8)
    return {
        "query": query,
        "hazards": hazards or [],
        "expanded_terms": terms,
        "results": refs,
    }



def build_retrieval_summary(refs: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not refs:
        return {"top_title": "", "avg_score": 0, "categories": [], "summary": "未检索到相关知识。"}

    categories: Dict[str, int] = {}
    total = 0.0
    for r in refs:
        category = r.get("category", "其他")
        categories[category] = categories.get(category, 0) + 1
        total += float(r.get("score", 0))

    top = refs[0]
    avg_score = round(total / len(refs), 2)
    return {
        "top_title": top.get("title", ""),
        "avg_score": avg_score,
        "categories": [{"name": k, "count": v} for k, v in categories.items()],
        "summary": f"共检索到 {len(refs)} 条相关知识，最高匹配为《{top.get('title', '')}》，平均相关度 {avg_score}。"
    }
