from __future__ import annotations

from typing import Dict, List, Any, Optional
from datetime import datetime
from services.text_analyzer import analyze_text, merge_hazards
from services.image_analyzer import analyze_image
from services.telemetry_analyzer import analyze_multiple_telemetry, interpret_device_alert
from services.risk_engine import calculate_risk as calculate_risk_base, build_hazard_items
from services.enhanced_risk_engine import calculate_building_risk, build_risk_factors_from_data, EnhancedRiskEngine
from services.rag_engine import retrieve_fire_knowledge, build_rag_context


class MultiModalAgent:
    """多模态输入分析Agent，融合文本、图片、设备遥测数据"""
    
    def __init__(self):
        self.risk_engine = EnhancedRiskEngine()
    
    async def analyze(
        self,
        description: str = "",
        image_paths: List[str] = None,
        telemetry_data: List[Dict[str, Any]] = None,
        db = None,
        building_info: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """执行多模态分析的主入口"""
        start_time = datetime.now()
        
        # 步骤1：分解任务意图
        analysis_plan = self._decompose_task(description, image_paths, telemetry_data)
        
        # 步骤2：执行各模态分析
        results = await self._execute_analysis(analysis_plan, description, image_paths, telemetry_data, db)
        
        # 步骤3：多源融合
        fusion_result = self._fusion_results(results)
        
        # 步骤4：知识检索
        rag_references = self._retrieve_knowledge(fusion_result.get("hazards", []), description)
        
        # 步骤5：风险评估
        risk_result = self._assess_risk(fusion_result, telemetry_data, building_info)
        
        # 步骤6：生成处置建议
        decision_result = self._generate_decision(fusion_result, risk_result, rag_references)
        
        # 步骤7：记录决策日志
        decision_log = self._log_decision(results, fusion_result, risk_result, decision_result)
        
        # 构建最终输出
        total_time = (datetime.now() - start_time).total_seconds()
        
        return {
            "analysis_plan": analysis_plan,
            "individual_results": results,
            "fusion_result": fusion_result,
            "rag_references": rag_references,
            "risk_result": risk_result,
            "decision_result": decision_result,
            "decision_log": decision_log,
            "execution_time": round(total_time, 2),
            "summary": self._build_summary(fusion_result, risk_result, decision_result)
        }
    
    def _decompose_task(self, description, image_paths, telemetry_data) -> List[Dict[str, Any]]:
        """分解任务意图，生成分析计划"""
        plan = []
        
        if description:
            plan.append({
                "step": 1,
                "name": "文本分析",
                "type": "text",
                "description": "从巡检描述中提取消防隐患关键词",
                "status": "pending"
            })
        
        if image_paths and len(image_paths) > 0:
            plan.append({
                "step": 2,
                "name": "图像分析",
                "type": "image",
                "description": f"分析{len(image_paths)}张现场照片中的隐患",
                "status": "pending"
            })
        
        if telemetry_data and len(telemetry_data) > 0:
            plan.append({
                "step": 3,
                "name": "设备遥测分析",
                "type": "telemetry",
                "description": f"分析{len(telemetry_data)}项设备数据",
                "status": "pending"
            })
        
        plan.extend([
            {
                "step": len(plan) + 1,
                "name": "多源融合",
                "type": "fusion",
                "description": "融合各模态分析结果，去重统一",
                "status": "pending"
            },
            {
                "step": len(plan) + 2,
                "name": "知识检索",
                "type": "rag",
                "description": "检索消防知识库获取处置依据",
                "status": "pending"
            },
            {
                "step": len(plan) + 3,
                "name": "风险评估",
                "type": "risk",
                "description": "计算综合风险评分",
                "status": "pending"
            },
            {
                "step": len(plan) + 4,
                "name": "决策建议",
                "type": "decision",
                "description": "生成处置建议和工单优先级",
                "status": "pending"
            }
        ])
        
        return plan
    
    async def _execute_analysis(self, plan, description, image_paths, telemetry_data, db):
        """执行各模态分析步骤"""
        results = {}
        
        # 文本分析
        if description:
            text_result = analyze_text(description)
            results["text"] = {
                "type": "text",
                "hazards": text_result["hazards"],
                "risk_reasons": text_result["risk_reasons"],
                "evidence": text_result["evidence"],
                "provider": "rule_based",
                "status": "success"
            }
        
        # 图像分析
        if image_paths and len(image_paths) > 0:
            image_results = []
            for path in image_paths[:3]:  # 最多分析3张图片
                img_result = await analyze_image(db, path)
                image_results.append(img_result)
            
            results["image"] = {
                "type": "image",
                "hazards": merge_hazards(*[r.get("hazards", []) for r in image_results]),
                "details": image_results,
                "provider": image_results[0].get("provider") if image_results else "unknown",
                "status": "success" if image_results else "failed"
            }
        
        # 设备遥测分析
        if telemetry_data and len(telemetry_data) > 0:
            tele_result = analyze_multiple_telemetry(telemetry_data)
            results["telemetry"] = {
                "type": "telemetry",
                "hazards": tele_result.get("hazard_types", []),
                "individual_results": tele_result.get("individual_results", {}),
                "overall_risk": tele_result.get("overall_risk"),
                "summary": tele_result.get("summary"),
                "status": "success"
            }
        
        return results
    
    def _fusion_results(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """多源隐患融合"""
        all_hazards = []
        sources = []
        
        # 收集各来源隐患
        if "text" in results:
            all_hazards.extend(results["text"].get("hazards", []))
            sources.append({"source": "text", "hazards": results["text"].get("hazards", [])})
        
        if "image" in results:
            all_hazards.extend(results["image"].get("hazards", []))
            sources.append({"source": "image", "hazards": results["image"].get("hazards", [])})
        
        if "telemetry" in results:
            all_hazards.extend(results["telemetry"].get("hazards", []))
            sources.append({"source": "telemetry", "hazards": results["telemetry"].get("hazards", [])})
        
        # 去重统一
        unique_hazards = merge_hazards(all_hazards)
        hazard_items = build_hazard_items(unique_hazards)
        
        return {
            "hazards": unique_hazards,
            "hazard_items": hazard_items,
            "sources": sources,
            "rule_hazards": results.get("text", {}).get("hazards", []),
            "vision_llm_hazards": results.get("image", {}).get("hazards", []),
            "text_llm_hazards": results.get("text", {}).get("hazards", []),
            "telemetry_hazards": results.get("telemetry", {}).get("hazards", []),
            "fusion_method": "union_deduplication",
            "confidence": self._calculate_confidence(results)
        }
    
    def _calculate_confidence(self, results: Dict[str, Any]) -> float:
        """计算融合结果的置信度"""
        scores = []
        
        if "text" in results and len(results["text"].get("hazards", [])) > 0:
            scores.append(0.7)
        
        if "image" in results:
            if results["image"].get("used_vision_api"):
                scores.append(0.85)
            else:
                scores.append(0.4)
        
        if "telemetry" in results:
            scores.append(0.9)
        
        if not scores:
            return 0.5
        
        return round(sum(scores) / len(scores), 2)
    
    def _retrieve_knowledge(self, hazards: List[str], query: str) -> List[Dict[str, Any]]:
        """检索消防知识库"""
        if not hazards and not query:
            return []
        
        refs = retrieve_fire_knowledge(query or "", hazards, limit=5)
        return refs
    
    def _assess_risk(
        self,
        fusion_result: Dict[str, Any],
        telemetry_data: List[Dict[str, Any]] = None,
        building_info: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """执行风险评估"""
        hazard_items = fusion_result.get("hazard_items", [])
        
        # 使用增强版风险引擎
        environment_info = building_info.get("environment") if building_info else None
        inspection_stats = building_info.get("inspection_stats") if building_info else None
        
        risk_result = calculate_building_risk(
            building_id=building_info.get("id", "unknown"),
            hazard_items=hazard_items,
            telemetry_data=telemetry_data,
            inspection_stats=inspection_stats,
            environment_info=environment_info,
            history_accidents=building_info.get("history_accidents", 0),
            last_accident_days=building_info.get("last_accident_days", 365)
        )
        
        return risk_result
    
    def _generate_decision(
        self,
        fusion_result: Dict[str, Any],
        risk_result: Dict[str, Any],
        rag_references: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """生成处置决策建议"""
        risk_level = risk_result.get("risk_level", "低风险")
        score = risk_result.get("risk_score", 0)
        hazards = fusion_result.get("hazards", [])
        
        # 确定优先级
        priority = "low"
        need_alarm = False
        need_ticket = len(hazards) > 0
        
        if score >= 85 or risk_level == "严重风险":
            priority = "critical"
            need_alarm = True
        elif score >= 60 or risk_level == "高风险":
            priority = "high"
            need_alarm = True if any(h in ["明火", "烟雾"] for h in hazards) else False
        elif score >= 35 or risk_level == "中风险":
            priority = "medium"
        
        # 生成处置建议
        recommendations = risk_result.get("recommendations", [])
        
        # 从知识库补充建议
        rag_context = build_rag_context(rag_references)
        if rag_context:
            recommendations.append({
                "priority": "参考",
                "action": "根据知识库建议处理",
                "reference_count": len(rag_references),
                "context_summary": rag_context[:500] + "..." if len(rag_context) > 500 else rag_context
            })
        
        return {
            "priority": priority,
            "priority_label": self._priority_label(priority),
            "need_alarm": need_alarm,
            "need_ticket": need_ticket,
            "need_evacuation": score >= 85 or any(h in ["明火", "烟雾"] for h in hazards),
            "recommendations": recommendations,
            "decision_reason": self._build_decision_reason(risk_result, hazards),
            "knowledge_support": len(rag_references) > 0
        }
    
    def _priority_label(self, priority: str) -> str:
        labels = {
            "critical": "紧急",
            "high": "高",
            "medium": "中",
            "low": "低"
        }
        return labels.get(priority, priority)
    
    def _build_decision_reason(self, risk_result: Dict[str, Any], hazards: List[str]) -> str:
        """构建决策理由"""
        parts = []
        
        score = risk_result.get("risk_score", 0)
        level = risk_result.get("risk_level", "低风险")
        
        parts.append(f"风险评分为{score}分，等级为{level}")
        
        if hazards:
            parts.append(f"识别到{len(hazards)}项隐患")
        
        explanation = risk_result.get("explanation", "")
        if explanation:
            parts.append(explanation)
        
        return "；".join(parts)
    
    def _log_decision(
        self,
        results: Dict[str, Any],
        fusion_result: Dict[str, Any],
        risk_result: Dict[str, Any],
        decision_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """记录决策日志"""
        return {
            "timestamp": datetime.now().isoformat(),
            "input_sources": [k for k in results.keys()],
            "hazard_count": len(fusion_result.get("hazards", [])),
            "risk_score": risk_result.get("risk_score", 0),
            "risk_level": risk_result.get("risk_level", ""),
            "priority": decision_result.get("priority", ""),
            "need_alarm": decision_result.get("need_alarm", False),
            "need_ticket": decision_result.get("need_ticket", False),
            "confidence": fusion_result.get("confidence", 0),
            "recommendation_count": len(decision_result.get("recommendations", []))
        }
    
    def _build_summary(
        self,
        fusion_result: Dict[str, Any],
        risk_result: Dict[str, Any],
        decision_result: Dict[str, Any]
    ) -> str:
        """构建分析总结"""
        parts = []
        
        hazard_count = len(fusion_result.get("hazards", []))
        if hazard_count > 0:
            parts.append(f"共识别到{hazard_count}项消防安全隐患")
        else:
            parts.append("未识别到明显消防安全隐患")
        
        score = risk_result.get("risk_score", 0)
        level = risk_result.get("risk_level", "")
        parts.append(f"综合风险评分为{score}分，等级为{level}")
        
        priority = decision_result.get("priority_label", "")
        parts.append(f"建议处置优先级：{priority}")
        
        return "；".join(parts)
    
    def interpret_device_alert(
        self,
        device_id: str,
        alert_type: str,
        telemetry_history: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """解释设备告警"""
        return interpret_device_alert(device_id, alert_type, telemetry_history)
    
    def update_risk_score(
        self,
        current_score: int,
        improvement_items: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """根据整改进度更新风险评分"""
        return self.risk_engine.update_score(current_score, improvement_items)


# 示例用法
async def example_usage():
    agent = MultiModalAgent()
    
    # 模拟输入数据
    description = "巡检发现西侧疏散通道有杂物堆放，部分灭火器被遮挡，配电箱周围有纸箱"
    image_paths = ["/path/to/image1.jpg", "/path/to/image2.jpg"]
    telemetry_data = [
        {"metric_type": "temperature", "value": 58, "unit": "°C", "timestamp": "2024-01-15T10:30:00"},
        {"metric_type": "smoke", "value": 0.4, "unit": "mg/m³", "timestamp": "2024-01-15T10:30:00"},
        {"metric_type": "pressure", "value": 0.35, "unit": "MPa", "timestamp": "2024-01-15T10:30:00"}
    ]
    building_info = {
        "id": "building_001",
        "environment": {"has_lab": True, "has_chemicals": False, "has_ev_charging": True},
        "inspection_stats": {"rectification_rate": 0.75, "pending_tasks": 3, "overdue_tasks": 1},
        "history_accidents": 1,
        "last_accident_days": 180
    }
    
    # 执行分析
    result = await agent.analyze(
        description=description,
        image_paths=image_paths,
        telemetry_data=telemetry_data,
        db=None,
        building_info=building_info
    )
    
    print("分析总结:", result["summary"])
    print("风险评分:", result["risk_result"]["risk_score"])
    print("风险等级:", result["risk_result"]["risk_level"])
    print("评分解释:", result["risk_result"]["explanation"])
    print("处置建议:", result["decision_result"]["recommendations"])
    
    return result


if __name__ == "__main__":
    import asyncio
    asyncio.run(example_usage())
