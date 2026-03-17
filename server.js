require('dotenv').config();

const express = require('express');
const axios = require('axios');
const https = require('https');
const cheerio = require('cheerio');
const OpenAI = require('openai');
const cors = require('cors');
const robotsParser = require('robots-parser');
const path = require('path');
const { URL } = require('url');
const rateLimit = require('express-rate-limit');

const app = express();
app.use(express.json());
app.use(cors());

// Serve static files from current directory
app.use(express.static(__dirname));

// ============================================================
// Rate Limiting — prevent abuse of AI / scrape endpoints
// ============================================================
const apiLimiter = rateLimit({
    windowMs: parseInt(process.env.SCRAPE_RATE_LIMIT_WINDOW_MS) || 60000,
    max: parseInt(process.env.SCRAPE_RATE_LIMIT_MAX) || 20,
    standardHeaders: true,
    legacyHeaders: false,
    message: { error: '请求过于频繁，请稍后再试。' }
});
app.use('/api/', apiLimiter);

// ============================================================
// Robots.txt Cache with TTL (1 hour expiry)
// ============================================================
const ROBOTS_CACHE_TTL = 3600000; // 1 hour in ms
const robotsCache = new Map();

function getRobotsFromCache(host) {
    const entry = robotsCache.get(host);
    if (!entry) return null;
    if (Date.now() - entry.timestamp > ROBOTS_CACHE_TTL) {
        robotsCache.delete(host);
        return null;
    }
    return entry.parser;
}

function setRobotsCache(host, parser) {
    // Cap cache size at 200 entries (LRU-like: just evict oldest if full)
    if (robotsCache.size >= 200) {
        const firstKey = robotsCache.keys().next().value;
        robotsCache.delete(firstKey);
    }
    robotsCache.set(host, { parser, timestamp: Date.now() });
}

// ============================================================
// URL Validation — block local / internal addresses
// ============================================================
function isUrlSafe(urlStr) {
    try {
        const parsed = new URL(urlStr);
        // Only allow http/https
        if (!['http:', 'https:'].includes(parsed.protocol)) return false;
        // Block localhost and private IPs
        const hostname = parsed.hostname.toLowerCase();
        if (hostname === 'localhost' || hostname === '127.0.0.1' || hostname === '::1') return false;
        if (hostname.startsWith('192.168.') || hostname.startsWith('10.') || hostname.startsWith('172.')) return false;
        if (hostname.endsWith('.local') || hostname.endsWith('.internal')) return false;
        return true;
    } catch {
        return false;
    }
}

// ============================================================
// Robots.txt Compliance Check
// ============================================================
async function checkRobotsTxt(targetUrlStr) {
    try {
        const targetUrl = new URL(targetUrlStr);
        const robotsUrl = `${targetUrl.protocol}//${targetUrl.host}/robots.txt`;

        let robotsObj = getRobotsFromCache(targetUrl.host);

        if (!robotsObj) {
            try {
                const response = await axios.get(robotsUrl, { timeout: 5000 });
                robotsObj = robotsParser(robotsUrl, response.data);
            } catch (err) {
                robotsObj = robotsParser(robotsUrl, '');
            }
            setRobotsCache(targetUrl.host, robotsObj);
        }

        const userAgent = 'MonitorBot/1.0';
        const isAllowed = robotsObj.isAllowed(targetUrlStr, userAgent);
        const isAllowedDefault = robotsObj.isAllowed(targetUrlStr, '*');

        return isAllowed !== false && isAllowedDefault !== false;
    } catch (e) {
        console.error('Error checking robots.txt:', e.message);
        return false;
    }
}

// ============================================================
// Web Scraping (with security checks)
// ============================================================
async function scrapeWebpage(urlStr) {
    try {
        if (!urlStr.startsWith('http')) {
            urlStr = 'https://' + urlStr;
        }

        // URL safety check
        if (!isUrlSafe(urlStr)) {
            return JSON.stringify({
                error: "URL Safety Error",
                message: `URL ${urlStr} 不被允许爬取（本地或内网地址）。`
            });
        }

        // Robots.txt compliance
        const allowed = await checkRobotsTxt(urlStr);
        if (!allowed) {
            return JSON.stringify({
                error: "Compliance Error",
                message: `网站 ${new URL(urlStr).host} 通过 robots.txt 禁止爬取。`
            });
        }

        const rejectUnauthorized = process.env.REJECT_UNAUTHORIZED_SSL === 'true';
        const response = await axios.get(urlStr, {
            headers: {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8'
            },
            timeout: 15000,
            httpsAgent: new https.Agent({ rejectUnauthorized })
        });

        const $ = cheerio.load(response.data);
        $('script, style, noscript, iframe, img, svg, video, audio').remove();
        let text = $('body').text().replace(/\s+/g, ' ').trim();

        const maxLength = 6000;
        if (text.length > maxLength) {
            text = text.substring(0, maxLength) + '... [Content truncated]';
        }

        return JSON.stringify({
            url: urlStr,
            title: $('title').text() || 'No Title',
            content: text
        });
    } catch (error) {
        console.error("Scraping error:", error.message);
        return JSON.stringify({ error: "Failed to scrape: " + error.message });
    }
}

// ============================================================
// Shared: Build OpenAI client + system prompt + tools
// ============================================================
function getSystemPrompt() {
    return `你是一个专业的数据分析助理与网络内容研究员。

【核心能力：动态数据可视化】
当用户询问数据（例如：某某的历年销量、各个省份的新增企业数量对比等），你除了从自身知识库或爬取网页获取答案外，**必须**尽可能为用户生成直观的图表。
当前系统没有默认折线图，你可以自由生成柱状图、折线图、饼图等。

你可以通过在回复中包含一个 JSON 块来动态创建图表并更新右侧数据卡片，格式如下:
{
  "action": "render_chart",
  "chartOption": { 
     // 这里必须是完整的、合法的 ECharts option 对象配置
     "title": { "text": "图表标题", "textStyle": {"color": "#fff"} },
     "tooltip": {},
     "xAxis": { "type": "category", "data": ["分类1", "分类2"] },
     "yAxis": { "type": "value" },
     "series": [{ "type": "bar", "data": [10, 20] }]
  }, 
  "cards": {
    "sourceName": "国家统计局",
    "sourceUrl": "https://data.stats.gov.cn/",
    "summary": "根据搜集数据表明，2023年国内新能源汽车销量达949.5万辆，同比增长37.9%...",
    "analysis": "从趋势来看，新能源汽车持续保持高速增长。其中纯电动车仍占主导..."
  }
}

注意：
1. "chartOption" 必须是一个合法的 ECharts v5 配置项对象，我会直接将其传入 myChart.setOption() 中。
2. 背景色默认处理了，不需要设定暗色背景。主要使用亮色或渐变的图表元素颜色。
3. cards 中的字段说明：
   - "sourceName"：你爬取或引用的数据来源名称（如"国家统计局"、"中汽协"等）。
   - "sourceUrl"：数据来源的网址链接（如 https://data.stats.gov.cn/）。
   - "summary"：对获取到的数据进行简要概括总结（2~4句话）。
   - "analysis"：对数据背后的趋势、原因或影响进行更深层次的分析（3~5句话）。
4. 每次输出图表时，cards 是**必须**提供的，不能省略。即使你没有具体来源链接，也要填写 sourceName 和 summary。
5. 如果只需普通对话无需图表，则不需要输出任何 JSON。如果你输出 JSON，请确保它之外还有清晰的中文解释说明。

【合法合规与道德约束（重要）】
1. 你具备使用爬虫工具（scrape_webpage）的能力，但必须严格遵守当地法律法规。
2. 绝对禁止爬取涉及个人隐私、儿童色情、暴力、国家机密以及其他违法内容。
3. 如果工具返回因 robots.txt 拒绝爬取，必须明确告知用户"因遵守网站机器人规范，无法爬取该网页"。
4. 在回答中要体现合法合规、尊重版权的态度。`;
}

const tools = [
    {
        type: "function",
        function: {
            name: "scrape_webpage",
            description: "Fetches and extracts text content from a specified URL. Call this whenever you need to read a webpage or crawl a site.",
            parameters: {
                type: "object",
                properties: {
                    url: {
                        type: "string",
                        description: "The direct URL of the webpage to scrape (e.g. https://www.example.com)"
                    }
                },
                required: ["url"]
            }
        }
    }
];

function resolveApiKey(reqBody) {
    // Priority: request body key > server env key
    if (reqBody.apiKey) return reqBody.apiKey;
    if (process.env.OPENAI_API_KEY) return process.env.OPENAI_API_KEY;
    return null;
}

function resolveEndpoint(reqBody) {
    if (reqBody.endpoint) return reqBody.endpoint;
    return process.env.OPENAI_BASE_URL || 'https://api.openai.com/v1';
}

function resolveModel(reqBody) {
    if (reqBody.model) return reqBody.model;
    return process.env.DEFAULT_MODEL || 'gpt-4o';
}

// Handle tool call loop (shared logic for both streaming and non-streaming)
async function executeToolCalls(openai, model, chatMessages, maxLoops) {
    let response = await openai.chat.completions.create({
        model,
        messages: chatMessages,
        tools,
        tool_choice: "auto",
    });

    let currentResponse = response.choices[0].message;

    while (currentResponse.tool_calls && maxLoops > 0) {
        chatMessages.push(currentResponse);

        for (const toolCall of currentResponse.tool_calls) {
            if (toolCall.function.name === 'scrape_webpage') {
                let functionResult;
                try {
                    const args = JSON.parse(toolCall.function.arguments);
                    console.log(`[Tool Call] scrape_webpage: ${args.url}`);
                    functionResult = await scrapeWebpage(args.url);
                } catch (e) {
                    console.error("Tool execution error:", e);
                    functionResult = JSON.stringify({ error: e.message || "Failed to execute tool" });
                }
                chatMessages.push({
                    tool_call_id: toolCall.id,
                    role: "tool",
                    name: "scrape_webpage",
                    content: functionResult,
                });
            }
        }

        maxLoops--;
        let toolChoice = "auto";
        if (maxLoops === 0) {
            toolChoice = "none";
            chatMessages.push({
                role: "system",
                content: "系统提示：工具调用次数已达到限制。请根据已知信息立刻总结回答。"
            });
        }

        const nextResponse = await openai.chat.completions.create({
            model,
            messages: chatMessages,
            tools,
            tool_choice: toolChoice,
        });
        currentResponse = nextResponse.choices[0].message;
    }

    return currentResponse;
}

// ============================================================
// GET /api/config — report server-side configuration status
// ============================================================
app.get('/api/config', (req, res) => {
    res.json({
        hasServerKey: !!process.env.OPENAI_API_KEY,
        defaultModel: process.env.DEFAULT_MODEL || 'gpt-4o',
        defaultEndpoint: process.env.OPENAI_BASE_URL || 'https://api.openai.com/v1'
    });
});

// ============================================================
// POST /api/chat — standard (non-streaming) chat endpoint
// Supports multi-turn: accepts full messages[] array
// ============================================================
app.post('/api/chat', async (req, res) => {
    const { messages } = req.body;
    const apiKey = resolveApiKey(req.body);
    const endpoint = resolveEndpoint(req.body);
    const model = resolveModel(req.body);

    if (!apiKey) {
        return res.status(401).json({ error: '未配置 API Key。请在设置中配置或在服务器 .env 中设置 OPENAI_API_KEY。' });
    }

    try {
        const openai = new OpenAI({ apiKey, baseURL: endpoint });

        const chatMessages = [
            { role: 'system', content: getSystemPrompt() },
            ...(Array.isArray(messages) ? messages : [])
        ];

        const currentResponse = await executeToolCalls(openai, model, chatMessages, 3);

        return res.json({
            response: currentResponse.content || "我尝试了多次获取信息但遇到了障碍，无法给出最终结论。"
        });
    } catch (error) {
        console.error("OpenAI API Error:", error.message);
        const status = error.status || 500;
        res.status(status).json({ error: error.message });
    }
});

// ============================================================
// POST /api/chat/stream — SSE streaming chat endpoint
// First handles tool calls (non-streaming), then streams final response
// ============================================================
app.post('/api/chat/stream', async (req, res) => {
    const { messages } = req.body;
    const apiKey = resolveApiKey(req.body);
    const endpoint = resolveEndpoint(req.body);
    const model = resolveModel(req.body);

    if (!apiKey) {
        return res.status(401).json({ error: '未配置 API Key。' });
    }

    // Set up SSE headers
    res.setHeader('Content-Type', 'text/event-stream');
    res.setHeader('Cache-Control', 'no-cache');
    res.setHeader('Connection', 'keep-alive');
    res.setHeader('X-Accel-Buffering', 'no');
    res.flushHeaders();

    try {
        const openai = new OpenAI({ apiKey, baseURL: endpoint });
        const systemPrompt = getSystemPrompt();

        const chatMessages = [
            { role: 'system', content: systemPrompt },
            ...(Array.isArray(messages) ? messages : [])
        ];

        // Phase 1: Handle tool calls (non-streaming) until no more tool calls
        let needsToolCalls = true;
        let maxLoops = 3;

        while (needsToolCalls && maxLoops > 0) {
            const response = await openai.chat.completions.create({
                model,
                messages: chatMessages,
                tools,
                tool_choice: "auto",
            });

            const msg = response.choices[0].message;

            if (msg.tool_calls) {
                chatMessages.push(msg);
                // Notify client that we're calling a tool
                res.write(`data: ${JSON.stringify({ type: 'status', text: '正在查询数据...' })}\n\n`);

                for (const toolCall of msg.tool_calls) {
                    if (toolCall.function.name === 'scrape_webpage') {
                        let result;
                        try {
                            const args = JSON.parse(toolCall.function.arguments);
                            console.log(`[Stream Tool Call] scrape_webpage: ${args.url}`);
                            result = await scrapeWebpage(args.url);
                        } catch (e) {
                            result = JSON.stringify({ error: e.message });
                        }
                        chatMessages.push({
                            tool_call_id: toolCall.id,
                            role: "tool",
                            name: "scrape_webpage",
                            content: result,
                        });
                    }
                }
                maxLoops--;
                if (maxLoops === 0) {
                    chatMessages.push({
                        role: "system",
                        content: "系统提示：工具调用次数已达到限制。请根据已知信息立刻总结回答。"
                    });
                }
            } else {
                // No tool calls — but this was a non-streaming call, push content as a chunk and break
                if (msg.content) {
                    res.write(`data: ${JSON.stringify({ type: 'delta', text: msg.content })}\n\n`);
                }
                needsToolCalls = false;
                // skip streaming phase since we already got the full response
                res.write(`data: [DONE]\n\n`);
                res.end();
                return;
            }
        }

        // Phase 2: Stream the final response after tool calls are done
        const stream = await openai.chat.completions.create({
            model,
            messages: chatMessages,
            stream: true,
        });

        for await (const chunk of stream) {
            const delta = chunk.choices[0]?.delta?.content;
            if (delta) {
                res.write(`data: ${JSON.stringify({ type: 'delta', text: delta })}\n\n`);
            }
        }

        res.write(`data: [DONE]\n\n`);
        res.end();

    } catch (error) {
        console.error("Stream API Error:", error.message);
        res.write(`data: ${JSON.stringify({ type: 'error', text: error.message })}\n\n`);
        res.end();
    }
});

// ============================================================
// Start Server
// ============================================================
const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
    console.log(`Server running at http://localhost:${PORT}`);
    console.log(`Static files: ${__dirname}`);
    console.log(`API Key configured: ${!!process.env.OPENAI_API_KEY}`);
    console.log(`Endpoints: /api/chat, /api/chat/stream, /api/config`);
});
