from __future__ import annotations
import json
import re
from importlib.resources import files
from urllib.parse import urlsplit
from jsonschema import Draft202012Validator
from .errors import RouterError

ALIASES = {
    "social": ["社交","social","评论","小红书","知乎","reddit","bilibili","opencli"],
    "deploy": ["部署","发布网站","deploy","cloudflare","wrangler","上线"],
    "debug": ["调试","debug","错误","sentry","devtools"],
    "office": ["办公","邮件","文档","office","gmail","calendar"],
    "analytics": ["反馈","指标","analytics","posthog"],
    "commerce": ["电商","商品","shopify","订单"],
    "outsourcing": ["外包","打样","upwork","fiverr"],
    "3d": ["3d", "三维", "模型", "glb", "mesh"],
    "image": ["图片", "生图", "image", "picture", "海报", "poster"],
    "video": ["视频", "video", "动画", "clip"],
    "speech": ["语音", "配音", "旁白", "讲解", "speech", "narration", "tts", "voice"],
    "music": ["音乐", "歌曲", "music", "song", "背景音"],
    "design": ["设计", "design", "排版"],
    "image_edit": ["修图", "抠图", "image edit", "photo edit"],
    "search": ["搜索", "search", "research", "查找"],
    "scrape": ["抓取", "scrape", "markdown", "网页内容"],
    "stock": ["素材", "stock", "footage"],
    "reference_video": ["youtube", "参考视频", "引用视频", "ytb"],
    "inspect": ["检查", "inspect", "时长", "probe"],
    "audio_convert": ["转码", "convert", "转换", "mp3"],
}

class Catalog:
    def __init__(self, state=None):
        values = json.loads(files("agent_tool_maker.data").joinpath("catalog.json").read_text())
        values.extend(json.loads(files("agent_tool_maker.data").joinpath("catalog-v02.json").read_text()))
        if state:
            values.extend(state.setting("custom_browser_tools", []))
            values.extend(state.setting("custom_tools", []))
        self.tools = {}
        for t in values:
            if t["id"] in self.tools:
                raise RouterError("duplicate_tool", "Duplicate tool IDs in registry.")
            Draft202012Validator.check_schema(t["schema"])
            self.tools[t["id"]] = t

    def get(self, tool_id):
        if tool_id not in self.tools:
            raise RouterError("unknown_tool", f"Unknown tool: {tool_id}")
        return self.tools[tool_id]

    def validate(self, tool_id, inputs):
        tool = self.get(tool_id)
        if not isinstance(inputs, dict):
            raise RouterError("invalid_input", "Tool input must be a JSON object.")
        # Error paths are useful; full validation messages can echo sensitive input.
        error = next(Draft202012Validator(tool["schema"]).iter_errors(inputs), None)
        if error:
            path = ".".join(map(str, error.path)) or "input"
            raise RouterError("invalid_input", f"Invalid {path}: schema rule '{error.validator}'. See atm describe.")
        return tool

    def search(self, query="", capability=None):
        query = query.lower().strip()
        inferred = {k for k, words in ALIASES.items() if any(w in query for w in words)}
        tokens = re.findall(r"[a-z0-9_-]{2,}|[\u4e00-\u9fff]+", query)
        rows = []
        for tool in self.tools.values():
            if capability and capability not in tool["capabilities"]:
                continue
            hay = (tool["id"] + " " + tool["title"] + " " + " ".join(tool["capabilities"])).lower()
            score = 30*len(inferred.intersection(tool["capabilities"]))
            score += sum(12 for token in tokens if token in hay)
            if tool["provider"] in query:
                score += 35
            if not query or score or capability:
                rows.append({**tool, "relevance": score})
        return sorted(rows, key=lambda x: (-x["relevance"], x["id"]))


def add_browser_tool(state, tool_id, title, url, capability):
    if not re.fullmatch(r"[a-z0-9][a-z0-9_.-]{2,63}", tool_id):
        raise RouterError("bad_tool_id", "Use a lowercase tool ID with 3-64 safe characters.")
    parts = urlsplit(url)
    if parts.scheme != "https" or not parts.hostname or parts.username or parts.password or parts.port not in [None,443]:
        raise RouterError("unsafe_url", "Custom browser entry must be an ordinary HTTPS URL without credentials.")
    if tool_id in Catalog(state).tools:
        raise RouterError("duplicate_tool", "That tool ID already exists.")
    row = dict(id=tool_id,provider=tool_id.split(".")[0],title=title,adapter="browser",implementation="browser",
               capabilities=[capability],url=url,paid=True,extensions=[".png",".jpg",".webp",".mp3",".wav",".mp4",".glb",".json"],
               schema={"type":"object","required":["task"],"additionalProperties":False,
                       "properties":{"task":{"type":"string","minLength":1,"maxLength":20000}}},
               sources=[url],checked_on=None,notes="User-supplied entry, not externally verified.")
    rows = state.setting("custom_browser_tools", [])
    rows.append(row)
    state.set_setting("custom_browser_tools", rows)
    return row
