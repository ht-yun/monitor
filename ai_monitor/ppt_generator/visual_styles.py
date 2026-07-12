# -*- coding: utf-8 -*-
"""CyberPPT 8 visual style definitions for PPT prompt generation."""


CYBERPPT_STYLES = [
    {
        "id": 1,
        "name": "经典深红咨询风",
        "name_en": "Classic Crimson",
        "bg": "#F3F4EF",
        "title": "#111111",
        "body": "#111111",
        "secondary": "#555555",
        "line": "#D6D6D2",
        "accent": "#8B1E1E",
        "suitable_for": "战略、竞品分析、行业研究、商业计划",
        "mood": "专业、权威、经典",
        "palette_img": "palette-01.png",
        "preview_url": "/static/ppt-styles/palette-01.png",
    },
    {
        "id": 2,
        "name": "冷灰 + 勃艮第红",
        "name_en": "Cool Gray + Burgundy",
        "bg": "#F5F5F2",
        "title": "#000000",
        "body": "#151515",
        "secondary": "#6B6B6B",
        "line": "#D9D9D6",
        "accent": "#7A1F2B",
        "suitable_for": "财务、投研、咨询、风险分析",
        "mood": "冷静、严谨、数据驱动",
        "palette_img": "palette-02.png",
        "preview_url": "/static/ppt-styles/palette-02.png",
    },
    {
        "id": 3,
        "name": "暖象牙白 + 暗酒红",
        "name_en": "Warm Ivory + Dark Red",
        "bg": "#F4F1EA",
        "title": "#121212",
        "body": "#2B2B2B",
        "secondary": "#77736C",
        "line": "#D8D3CA",
        "accent": "#8A1538",
        "suitable_for": "品牌战略、消费品、电商、用户研究",
        "mood": "温暖、精致、叙事感",
        "palette_img": "palette-03.png",
        "preview_url": "/static/ppt-styles/palette-03.png",
    },
    {
        "id": 4,
        "name": "象牙白 + 深蓝强调",
        "name_en": "Ivory + Navy",
        "bg": "#F7F6F0",
        "title": "#101820",
        "body": "#303030",
        "secondary": "#6F7275",
        "line": "#C9CDD1",
        "accent": "#12355B",
        "suitable_for": "科技、SaaS、B2B、企业数字化、AI Agent",
        "mood": "清晰、逻辑、现代",
        "palette_img": "palette-04.png",
        "preview_url": "/static/ppt-styles/palette-04.png",
    },
    {
        "id": 5,
        "name": "浅灰白 + 墨绿",
        "name_en": "Light Gray + Teal",
        "bg": "#F2F3EF",
        "title": "#111111",
        "body": "#333333",
        "secondary": "#666666",
        "line": "#D7D9D3",
        "accent": "#1F5B4D",
        "suitable_for": "可持续、海外市场、增长战略、长期趋势",
        "mood": "自然、稳健、长期主义",
        "palette_img": "palette-05.png",
        "preview_url": "/static/ppt-styles/palette-05.png",
    },
    {
        "id": 6,
        "name": "纸张米色 + 铜棕",
        "name_en": "Paper Beige + Copper",
        "bg": "#F4F0E8",
        "title": "#161616",
        "body": "#2F2F2F",
        "secondary": "#76716A",
        "line": "#D8D5CE",
        "accent": "#9A5A2E",
        "suitable_for": "消费、零售、奢侈品、商业模式分析",
        "mood": "质感、优雅、高级",
        "palette_img": "palette-06.png",
        "preview_url": "/static/ppt-styles/palette-06.png",
    },
    {
        "id": 7,
        "name": "纯净浅灰 + 黑金",
        "name_en": "Pure Gray + Black Gold",
        "bg": "#F6F6F4",
        "title": "#000000",
        "body": "#252525",
        "secondary": "#707070",
        "line": "#DADADA",
        "accent": "#A87932",
        "suitable_for": "高管汇报、融资材料、年度战略、董事会材料",
        "mood": "高端、精致、重量级",
        "palette_img": "palette-07.png",
        "preview_url": "/static/ppt-styles/palette-07.png",
    },
    {
        "id": 8,
        "name": "冷白灰 + 深紫",
        "name_en": "Cool White + Deep Purple",
        "bg": "#F4F5F6",
        "title": "#111111",
        "body": "#303030",
        "secondary": "#6D7175",
        "line": "#C8CCD0",
        "accent": "#4B2E83",
        "suitable_for": "AI、技术趋势、产品战略、创新研究",
        "mood": "前沿、创新、科技感",
        "palette_img": "palette-08.png",
        "preview_url": "/static/ppt-styles/palette-08.png",
    },
]


SLIDE_ELEMENTS = {
    "default_elements": [
        "cover", "executive_summary", "overview", "branch_structure",
        "development_activity", "contributors", "code_insights",
        "recent_focus", "quality_risks", "strategic_implications",
        "appendix"
    ],
    "chart_types": [
        {"id": "line", "name": "折线图 (时间趋势)"},
        {"id": "bar", "name": "柱状图 (对比)"},
        {"id": "table", "name": "数据表格"},
        {"id": "timeline", "name": "时间线"},
        {"id": "compare", "name": "对比矩阵"},
        {"id": "pie", "name": "饼图/占比"},
    ],
    "element_options": [
        {"id": "cover", "name": "封面", "default": True},
        {"id": "executive_summary", "name": "执行摘要", "default": True},
        {"id": "overview", "name": "仓库概览", "default": True},
        {"id": "branch_structure", "name": "分支结构", "default": True},
        {"id": "development_activity", "name": "开发活动时间线", "default": True},
        {"id": "contributors", "name": "贡献者分析", "default": True},
        {"id": "code_insights", "name": "代码洞察", "default": True},
        {"id": "recent_focus", "name": "近期开发重点", "default": True},
        {"id": "quality_risks", "name": "质量与风险指标", "default": True},
        {"id": "strategic_implications", "name": "战略含义与 SO WHAT", "default": True},
        {"id": "appendix", "name": "附录/数据源", "default": False},
    ],
}


TYPOGRAPHY_SCALE = """
| 层级 | 名称 | 典型位置 | 字号范围 |
|---|---|---|---|
| C0 | 封面/章节幕标题 | 封面主标题 | 32-44pt |
| T1 | 页码/章节徽章 | 左上角页码徽章 | 14-18pt |
| T2 | 页面主标题/结论标题 | 每页顶部结论句 | 22-28pt |
| T3 | 页面副标题/语境说明 | 主标题下方 subtitle | 10-12pt |
| T4 | 模块标题/图表标题 | 图表标题、面板标题 | 11-14pt |
| T5 | 证据编号/轻量标签 | E02/E05 标签 | 7.5-8.5pt |
| T6 | 证据块标题/小节标题 | 段落小标题 | 11-13pt |
| T7 | 正文解释段落 | 证据解释、解读正文 | 9.5-11pt |
| T8 | 结论条文字/核心结论 | 结论条、总结框 | 10-12pt |
| T9 | SO WHAT 标签 | SO WHAT 标签 | 10-12pt |
| T10 | SO WHAT 正文/业务含义 | SO WHAT 正文 | 9.5-11pt |
| T11 | 图表轴/图例/刻度 | 坐标轴、图例 | 7.5-9pt |
| T12 | 图表数据标签 | 折线点值、柱形标签 | 8.5-11pt |
| T13 | 关键 KPI/大数字 | 关键指标大号数字 | 18-28pt |
| T14 | 注释/口径/来源/页脚 | 页脚、来源 | 6.5-8pt |
"""



