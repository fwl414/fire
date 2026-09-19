from __future__ import annotations

from typing import Any, Dict, List


def get_competition_overview() -> Dict[str, Any]:
    return {
        "project_name": "智慧消防管理系统",
        "competition_track": "研电赛方向一：智能模型与智能体系统",
        "version": "V1.0.0",
        "positioning": "智慧消防管理系统，覆盖巡检、风险评估、知识检索、决策支持和消防学习。",
        "not_positioning": [
            "不是普通消防 CRUD 后台",
            "不是单纯设备管理系统",
            "不是硬件采集项目",
            "不是单一问答机器人"
        ],
        "core_value": [
            "用 Agent 将多模态巡检、知识检索、风险评分和应急决策串联成可解释流程",
            "用 RAG 降低智能模型幻觉并提供消防知识依据",
            "用学习 Agent 将消防知识、题库和错题分析转化为智能学习闭环",
            "硬件接口仅作为可扩展数据源预留，不改变软件智能体主线"
        ],
        "one_sentence": "面向智慧消防场景的管理系统，支持任务调度、工具调用、知识检索、多源数据融合、风险解释和应急决策。"
    }


def get_technical_route() -> Dict[str, Any]:
    return {
        "pipeline": [
            {
                "step": 1,
                "name": "多源输入",
                "description": "接收文字描述、现场图片、设备信息、历史记录和预留硬件事件。"
            },
            {
                "step": 2,
                "name": "Agent任务理解",
                "description": "识别任务类型、场景地点、输入模态和目标输出。"
            },
            {
                "step": 3,
                "name": "自动选择工具",
                "description": "根据输入自动选择文本规则识别、视觉模型、RAG检索、风险引擎、报告生成等工具。"
            },
            {
                "step": 4,
                "name": "多源隐患融合",
                "description": "融合规则、智能模型、视觉模型和硬件事件结果，形成结构化隐患列表。"
            },
            {
                "step": 5,
                "name": "RAG知识增强",
                "description": "检索消防知识库、题库和学习资源，提供依据和解释。"
            },
            {
                "step": 6,
                "name": "风险评估",
                "description": "根据隐患类型、数量、场景和严重程度计算风险分数和等级。"
            },
            {
                "step": 7,
                "name": "应急辅助决策",
                "description": "生成整改建议、责任角色、处置时限、升级条件和闭环要求。"
            },
            {
                "step": 8,
                "name": "可解释输出",
                "description": "输出 Agent Trace、工具调用记录、RAG引用、风险解释和报告。"
            }
        ],
        "architecture_layers": [
            {
                "layer": "应用展示层",
                "items": ["Dashboard", "智能巡检", "消防学习中心", "实验评估", "项目展示"]
            },
            {
                "layer": "任务编排层",
                "items": ["任务规划", "工具选择", "工具调用", "执行轨迹", "决策优化"]
            },
            {
                "layer": "AI能力层",
                "items": ["文本智能模型", "视觉智能模型", "RAG检索", "学习Agent", "风险解释"]
            },
            {
                "layer": "业务算法层",
                "items": ["隐患识别", "多源融合", "风险评分", "整改闭环", "实验评估"]
            },
            {
                "layer": "数据资源层",
                "items": ["消防知识库", "中级消防题库", "巡检记录", "设备数据", "视频资源索引"]
            }
        ]
    }


def get_innovation_points() -> List[Dict[str, Any]]:
    return [
        {
            "title": "消防巡检工具链编排",
            "description": "根据文本、图片、硬件事件和问答任务选择工具，形成可解释的执行链路。",
            "evidence": ["tool_selection", "agent_trace", "agent_tool_calls"]
        },
        {
            "title": "RAG增强的消防知识解释",
            "description": "将消防隐患识别、问答和学习都接入知识库检索，减少智能模型幻觉，并将引用依据展示给用户。",
            "evidence": ["RAG知识库", "学习RAG检索", "消防问答引用"]
        },
        {
            "title": "多源隐患融合与风险可解释评分",
            "description": "融合规则识别、文本智能模型、视觉模型和硬件预留事件，输出风险分数、等级和判断依据。",
            "evidence": ["隐患列表", "风险评分", "风险解释"]
        },
        {
            "title": "应急辅助决策优化",
            "description": "不仅识别隐患，还生成整改时限、责任角色、升级条件和闭环工单建议。",
            "evidence": ["optimized_decision", "整改闭环", "报告生成"]
        },
        {
            "title": "消防学习 Agent",
            "description": "将中级消防题库、理论/实操考试、知识图谱和学习分析融合，使系统从风险评估延伸到消防能力提升。",
            "evidence": ["中级题库", "理论考试", "实操考试", "学习Agent解析"]
        }
    ]


def get_demo_script() -> List[Dict[str, Any]]:
    return [
        {
            "order": 1,
            "title": "首页展示项目定位",
            "page": "/dashboard",
            "talking_points": [
                "说明项目面向研电赛方向一：智能模型与智能体系统。",
                "强调系统不是普通消防后台，而是 Agent 风险评估与辅助决策系统。"
            ]
        },
        {
            "order": 2,
            "title": "智能巡检演示",
            "page": "/inspection",
            "talking_points": [
                "输入消防通道堵塞、电线杂乱、灭火器遮挡等场景。",
                "展示 Agent 自动选择工具、隐患识别、风险评分、RAG引用和应急决策。"
            ]
        },
        {
            "order": 3,
            "title": "Agent能力展示",
            "page": "/agent-lab",
            "talking_points": [
                "展示任务理解、工具选择、工具调用、RAG检索、风险评分和决策优化。",
                "说明 Agent Trace 是可公开执行摘要，不是隐藏思维链。"
            ]
        },
        {
            "order": 4,
            "title": "RAG知识库和消防问答",
            "page": "/qa",
            "talking_points": [
                "提问电气火灾为何不能直接用水扑灭。",
                "展示 RAG 知识引用和智能模型回答。"
            ]
        },
        {
            "order": 5,
            "title": "消防学习中心",
            "page": "/learning",
            "talking_points": [
                "展示中级消防设施操作员理论/实操题库。",
                "演示刷题、学习 Agent 解析、错题分析和知识图谱/RAG检索。"
            ]
        },
        {
            "order": 6,
            "title": "实验评估",
            "page": "/evaluation",
            "talking_points": [
                "展示规则识别、智能模型识别和融合识别对比。",
                "说明融合方案在复杂场景下更稳定。"
            ]
        },
        {
            "order": 7,
            "title": "硬件接口预留",
            "page": "/hardware",
            "talking_points": [
                "说明硬件只是可扩展数据源，不是项目主线。",
                "展示烟感、温感、电气火灾探测器和摄像头如何进入 Agent。"
            ]
        }
    ]


def get_agent_evaluation_matrix() -> Dict[str, Any]:
    rows = [
        {
            "capability": "任务理解",
            "baseline": "固定表单提交",
            "agent": "根据输入类型识别巡检、问答、学习、硬件事件等任务",
            "value": "提升系统泛化能力"
        },
        {
            "capability": "工具选择",
            "baseline": "固定调用所有模块",
            "agent": "根据是否有文本、图片、硬件事件自动选择工具",
            "value": "减少无效调用，突出智能体编排"
        },
        {
            "capability": "知识增强",
            "baseline": "纯智能模型回答",
            "agent": "RAG检索消防知识库和题库资源后再回答",
            "value": "降低幻觉，提高可追溯性"
        },
        {
            "capability": "风险判断",
            "baseline": "单一规则评分",
            "agent": "融合规则、智能模型、视觉、硬件事件和历史信息",
            "value": "适合复杂多隐患场景"
        },
        {
            "capability": "决策生成",
            "baseline": "简单整改建议",
            "agent": "生成责任角色、处置时限、升级条件、闭环要求",
            "value": "从识别走向应急辅助决策"
        },
        {
            "capability": "学习辅导",
            "baseline": "静态题库刷题",
            "agent": "题目级Agent解析、错题知识点映射、学习建议",
            "value": "形成智能化消防学习闭环"
        }
    ]
    return {
        "title": "Agent能力对比矩阵",
        "rows": rows,
        "conclusion": "与传统固定流程系统相比，本系统通过工具编排、知识增强和决策优化实现业务目标。"
    }


def get_paper_materials() -> Dict[str, Any]:
    return {
        "abstract": "针对传统消防巡检系统在风险解释和应急决策方面的不足，本系统通过工具编排、知识检索、多源数据融合和风险评分，实现消防巡检任务的隐患识别、风险评估和应急决策。",
        "keywords": ["智能模型", "智能体", "智慧消防", "RAG", "风险评估", "应急辅助决策"],
        "outline": [
            "引言",
            "相关技术",
            "系统需求分析",
            "系统总体设计",
            "Agent与工具链编排",
            "RAG知识库与消防学习知识图谱",
            "风险评估与应急辅助决策",
            "系统实现与功能展示",
            "实验评估",
            "总结与展望"
        ],
        "innovation_summary": [
            "提出面向智慧消防巡检的智能模型 Agent 工具链编排方案。",
            "构建消防知识库、题库和学习资源融合的 RAG 增强机制。",
            "设计多源隐患融合、风险解释和应急辅助决策流程。",
            "将消防题库学习引入 Agent 系统，形成风险评估与知识学习闭环。"
        ]
    }
