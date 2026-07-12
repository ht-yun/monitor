# -*- coding: utf-8 -*-
"""Prompt templates for PPT generation from repository data."""


PPT_PROMPT_TEMPLATE = """# PPT Generation Prompt

You are an expert in creating professional, high-density, consulting-style PowerPoint presentations.

## Instructions

1. Use ONLY the data provided in the "Repository Data" section below. Do NOT fabricate any numbers, features, metrics, or claims.
2. The PPT should follow a consulting-style format: evidence-driven, conclusion-first, high information density.
3. Make each slide title a defensible conclusion, not just a topic label.
4. Include SO WHAT / business implications on each content slide.
5. Charts and tables should use actual data from the commits and repo stats.
6. Structure the deck to tell a coherent story about the repository development activity, health, and trajectory.

## Suggested Deck Structure (8-12 slides)

1. **Cover** - Repository name, description, platform, date range of analyzed data
2. **Executive Summary** - Key metrics: total commits (in period), active branches, contributors, language, stars/forks
3. **Repository Overview** - Stars, forks, language, topics, description, creation date
4. **Branch Structure** - All branches, their latest commits, default branch
5. **Development Activity Timeline** - Commit frequency over time, busiest periods
6. **Top Contributors** - Most active commit authors, their contributions
7. **Code Base Insights** - Language breakdown, repo size indicators, README highlights
8. **Recent Development Focus** - What the team has been working on recently
9. **Quality & Risk Indicators** - Open issues, commit message clarity, development patterns
10. **SO WHAT / Strategic Implications** - What this development activity means for stakeholders

---

## Repository Data

### Basic Info
- **Repository**: {repo_full_name}
- **Platform**: {platform}
- **URL**: {repo_url}
- **Description**: {description}
- **Language**: {language}
- **Stars**: {stars}
- **Forks**: {forks}
- **Open Issues**: {open_issues}
- **Topics**: {topics}
- **Default Branch**: {default_branch}
- **Created**: {created_at}
- **Last Updated**: {updated_at}
- **Last Push**: {pushed_at}

### Branches
{recent_commits_section}

### Commit History (Recent {commit_count} Commits)
{commit_table}

### README Summary
{readme_summary}

---

**IMPORTANT**: All data above was collected from the actual repository on {generated_at}.
You MUST use this data faithfully. Do not add speculative content.
If there is insufficient data for a suggested slide, combine or omit slides as needed.
"""


SINGLE_BRANCH_TEMPLATE = """#### Branch: {branch_name}{default_label}
| Field | Value |
|---|---|
| Latest SHA | `{sha}` |
| Author | {author} |
| Committed At | {committed_at} |
| Message | {message} |
| URL | {url} |
"""


# For aggregated branch info
MULTI_BRANCH_SECTION_HEADER = "### Branches Overview ({branch_count} branches)\n\n"

COMMIT_HISTORY_ROW = "| {idx} | {date} | {author} | `{sha_short}` | {message} |\n"


STYLE_PROMPT_SECTION = """
## Visual Style: {style_name}

### Color Palette
| Role | Color |
|---|---|
| Background | `{bg}` |
| Title/Headings | `{title}` |
| Body Text | `{body}` |
| Secondary Text | `{secondary}` |
| Lines/Dividers | `{line}` |
| Accent/Highlight | `{accent}` |

### Mood & Tone
{mood}

### Suitable For
{suitable_for}

### Typography Scale (CyberPPT Standard)
{typography_scale}

### Visual Guidelines
- Use the accent color `{accent}` for key data points, highlights, callouts, and section markers
- Background `{bg}` for page base; use white `#FFFFFF` for card/surface backgrounds
- Title text `{title}` for slide titles (T2, 22-28pt); body text `{body}` for paragraphs (T7, 9.5-11pt)
- Secondary text `{secondary}` for labels, captions, metadata (T11, T14)
- Lines and dividers in `{line}`
- Charts: use accent color for primary data series, secondary color for secondary series
- Tables: header background in accent color with white text, alternating row fills using 10% opacity of accent
- Maintain high information density: each slide should carry 3-5 information zones
- All content slides must include a SO WHAT / business implication section
- Page numbers and section markers in upper-left corner (T1, 14-18pt)
- Charts must have axis labels, legends, and data callouts where appropriate
- Use the CyberPPT 15-level typography scale (C0-T14) for all text elements

### Style Sample
For a complete visual reference including page layout, chart appearance, and expected density:
![{style_name}]({preview_data})
"""

ELEMENTS_PROMPT_SECTION = """
## Selected PPT Elements

The following sections should be included in the presentation:
{selected_elements}

### Chart Types to Use
{selected_charts}
"""
