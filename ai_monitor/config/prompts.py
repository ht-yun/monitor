# -*- coding: utf-8 -*-
"""AI prompt templates for different analysis tasks."""

# Sentiment analysis prompt
SENTIMENT_ANALYSIS = """Analyze the sentiment of the following social media content.
Classify it as one of: positive, negative, or neutral.
Provide a sentiment score from 0.0 (very negative) to 1.0 (very positive).

Content:
{text}

Respond in JSON format:
{{"sentiment": "positive|negative|neutral", "score": 0.0-1.0, "reason": "brief reason in Chinese"}}"""

# Topic extraction prompt
TOPIC_EXTRACTION = """Extract the main topics and keywords from the following social media content.
Focus on key subjects, brands, products, people, and events mentioned.
Return 3-8 keywords or short phrases.

Content:
{text}

Respond in JSON format:
{{"topics": ["topic1", "topic2", ...], "entities": ["entity1", "entity2", ...]}}"""

# Batch summary prompt
BATCH_SUMMARY = """Summarize the following batch of {platform} social media posts.
Total posts: {count}
Please provide:
1. A one-paragraph overall summary in Chinese
2. Key trends and patterns observed
3. Any notable or concerning content

Posts:
{posts}

Respond in JSON format:
{{"summary": "...", "trends": ["trend1", "trend2"], "notable_items": [{{"id": "...", "reason": "..."}}]}}"""

# Anomaly detection prompt
ANOMALY_DETECTION = """Analyze the following statistics for potential anomalies:

Current period stats: {current}
Historical baseline: {baseline}

Respond in JSON format:
{{"is_anomaly": true|false, "anomaly_score": 0.0-1.0, "explanation": "brief explanation in Chinese", "affected_metrics": ["metric1", ...]}}"""

# Risk assessment prompt
RISK_ASSESSMENT = """Assess the risk level of the following content for brand monitoring purposes.
Consider factors like: negative sentiment, complaints, fraud mentions, reputation damage.

Content:
{text}

Respond in JSON format:
{{"risk_level": "low|medium|high|critical", "risk_score": 0.0-1.0, "risk_factors": ["factor1", ...], "recommended_action": "brief recommendation in Chinese"}}"""

# Alert summary prompt
ALERT_SUMMARY = """Generate a concise alert notification message based on the following trigger data.

Rule: {rule_name}
Platform: {platform}
Severity: {severity}
Matched items count: {matched_count}
Sample content: {sample}

Generate a message suitable for {channel} notification. Keep it concise but informative.
Respond in plain text (no JSON), in Chinese."""
