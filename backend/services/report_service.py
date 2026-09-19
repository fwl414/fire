from __future__ import annotations

from datetime import datetime
from typing import List


def generate_suggestion(hazards, risk_level, knowledge_refs):
    suggestions = []

    if "明火" in hazards or "烟雾" in hazards:
        suggestions.append("立即启动应急响应，切断相关电源，疏散附近人员，必要时拨打 119。")

    if "消防通道堵塞" in hazards:
        suggestions.append("立即清理消防通道和疏散通道杂物，确保疏散和救援通道畅通。")

    if "插座过载" in hazards:
        suggestions.append("停止多插排串联和超负荷用电，重新规划用电线路。")

    if "电线杂乱" in hazards:
        suggestions.append("整理线缆并检查绝缘层，避免线路老化、短路或绊倒风险。")

    if "可燃物堆积" in hazards:
        suggestions.append("将纸箱、塑料等可燃物移离电源、配电箱和热源。")

    if "配电箱周围堆物" in hazards:
        suggestions.append("清空配电箱周边区域，保留安全操作距离。")

    if "灭火器缺失" in hazards:
        suggestions.append("按配置要求补齐灭火器，并登记型号、位置和有效期。")

    if "灭火器被遮挡" in hazards or "消防设施被遮挡" in hazards:
        suggestions.append("移除消防设施周边遮挡物，保证设施可见、可达、可操作。")

    if "电动车违规充电" in hazards:
        suggestions.append("立即停止违规充电，将电动车移至集中充电区域。")

    if risk_level in ["高风险", "严重风险"]:
        suggestions.append("建议生成整改工单，由消防安全责任人跟踪整改并复查闭环。")

    if not suggestions:
        suggestions.append("暂未发现明显隐患，建议继续保持定期巡检和记录。")

    return "\n".join([f"{i + 1}. {s}" for i, s in enumerate(suggestions)])


def build_executive_summary(hazards: List[str], risk_score: int, risk_level: str) -> str:
    if not hazards:
        return f"本次巡检未发现明显消防安全隐患，综合风险评分 {risk_score} 分，等级为{risk_level}。"

    return (
        f"本次巡检共识别 {len(hazards)} 项消防安全隐患，"
        f"综合风险评分 {risk_score} 分，等级为{risk_level}。"
        "建议按照风险等级优先处理高危隐患，并在整改后进行复查。"
    )


def generate_report(
    device,
    location,
    description,
    hazards,
    risk_score,
    risk_level,
    suggestion,
    knowledge_refs,
    agent_steps,
    hazard_items=None,
    risk_reason="",
):
    device_text = "未关联设备"

    if device:
        device_text = f"{device.device_name}（{device.device_code}，{device.device_type}）"

    hazard_items = hazard_items or []

    if hazard_items:
        hazard_text = "\n".join(
            [
                f"{i + 1}. {x.get('type')}｜类别：{x.get('category')}｜等级：{x.get('severity')}｜分值：{x.get('score')}\n"
                f"   原因：{x.get('reason')}\n"
                f"   措施：{x.get('measure')}"
                for i, x in enumerate(hazard_items)
            ]
        )
    elif hazards:
        hazard_text = "、".join(hazards)
    else:
        hazard_text = "未发现明显隐患"

    knowledge_text = "\n".join(
        [f"- {k['title']}：{k['content']}" for k in knowledge_refs]
    ) or "无"

    steps_text = "\n".join([f"{i + 1}. {s}" for i, s in enumerate(agent_steps)])

    return f"""智慧消防风险评估与应急辅助决策报告

生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
巡检地点：{location or '未填写'}
关联设备：{device_text}

一、巡检任务概述
{description or '未填写'}

二、综合结论
{build_executive_summary(hazards, risk_score, risk_level)}
{risk_reason or ''}

三、结构化隐患识别结果
{hazard_text}

四、风险评估结果
风险分数：{risk_score}
风险等级：{risk_level}

五、整改与应急辅助建议
{suggestion}

六、知识库参考
{knowledge_text}

七、Agent 工具调用过程
{steps_text}

八、闭环处理建议
1. 对高风险和严重风险隐患自动生成整改工单。
2. 整改完成后在系统中更新工单状态并保留复查记录。
3. 对重复出现的隐患区域纳入重点监管和定期复盘。
"""
