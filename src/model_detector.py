# -*- coding: utf-8 -*-
"""
TokenBurner - AI Model Detector & Registry Engine
=================================================
Detects active AI platforms and models from Windows foreground windows and browser tabs.
Attributes token consumption to specific models without collecting sensitive data.
Strictly English code per global agent rules.
"""

import os
import json
import time
import re
from typing import Dict, Any, Optional, Tuple

# Default embedded 2026 flagship model registry (can be synced remotely)
DEFAULT_MODEL_REGISTRY = {
    "version": "2026-09-13",
    "platforms": {
        "copilot": {
            "name": "GitHub Copilot",
            "tool_tag": "⚡ COPILOT",
            "process_names": ["github.exe", "copilot.exe", "m365copilot.exe"],
            "url_patterns": [r"copilot\.github\.com", r"github\.com/copilot"],
            "title_patterns": [r"github copilot", r"copilot"],
            "default_model": "Copilot Claude 3.7 / GPT-4o",
            "models": [
                {"id": "copilot-claude-3.7", "name": "Copilot Claude 3.7 Sonnet", "tier": 4, "cost_1m": 120},
                {"id": "copilot-gpt-4o", "name": "Copilot GPT-4o", "tier": 3, "cost_1m": 90},
                {"id": "copilot-o3-mini", "name": "Copilot o3-mini", "tier": 3, "cost_1m": 70}
            ]
        },
        "cursor": {
            "name": "Cursor",
            "tool_tag": "💻 CURSOR",
            "process_names": ["cursor.exe"],
            "url_patterns": [r"cursor\.com", r"cursor\.sh"],
            "title_patterns": [r"cursor", r"composer"],
            "default_model": "Cursor Composer",
            "models": [
                {"id": "cursor-composer", "name": "Cursor Composer", "tier": 4, "cost_1m": 120},
                {"id": "cursor-claude-3.7", "name": "Cursor Claude 3.7 Sonnet", "tier": 4, "cost_1m": 120},
                {"id": "cursor-tab", "name": "Cursor Tab", "tier": 2, "cost_1m": 20}
            ]
        },
        "antigravity": {
            "name": "Antigravity",
            "tool_tag": "🚀 ANTIGRAVITY",
            "process_names": ["antigravity.exe"],
            "url_patterns": [r"antigravity"],
            "title_patterns": [r"antigravity", r"token_burner"],
            "default_model": "Gemini 2.5 Flash (AGY)",
            "models": [
                {"id": "gemini-2.5-flash-agy", "name": "Gemini 2.5 Flash (AGY)", "tier": 3, "cost_1m": 30},
                {"id": "gemini-2.5-pro-agy", "name": "Gemini 2.5 Pro (AGY)", "tier": 4, "cost_1m": 80}
            ]
        },
        "windsurf": {
            "name": "Windsurf",
            "tool_tag": "🌊 WINDSURF",
            "process_names": ["windsurf.exe"],
            "url_patterns": [r"codeium\.com/windsurf"],
            "title_patterns": [r"windsurf", r"cascade"],
            "default_model": "Cascade Flow",
            "models": [
                {"id": "cascade-flow", "name": "Cascade Flow", "tier": 4, "cost_1m": 120},
                {"id": "cascade-claude", "name": "Cascade Claude 3.7", "tier": 4, "cost_1m": 120}
            ]
        },
        "trae": {
            "name": "Trae",
            "tool_tag": "⚡ TRAE",
            "process_names": ["trae.exe"],
            "url_patterns": [r"trae\.ai"],
            "title_patterns": [r"trae"],
            "default_model": "Trae Claude 3.5",
            "models": [
                {"id": "trae-claude-3.5", "name": "Trae Claude 3.5 Sonnet", "tier": 4, "cost_1m": 120},
                {"id": "trae-gpt-4o", "name": "Trae GPT-4o", "tier": 3, "cost_1m": 90}
            ]
        },
        "claude_code": {
            "name": "Claude Code",
            "tool_tag": "🔮 CLAUDE CODE",
            "process_names": ["claude.exe"],
            "url_patterns": [],
            "title_patterns": [r"claude code", r"claude-code"],
            "default_model": "Claude 3.7 Sonnet (CLI)",
            "models": [
                {"id": "claude-3.7-sonnet-cli", "name": "Claude 3.7 Sonnet (CLI)", "tier": 4, "cost_1m": 120}
            ]
        },
        "doubaowork": {
            "name": "Doubao Work",
            "tool_tag": "🌱 DOUBAO WORK",
            "process_names": ["doubaowork.exe", "doubao.exe", "saman.exe", "aha_doctor.exe"],
            "url_patterns": [r"doubao\.com/work", r"doubao\.com"],
            "title_patterns": [r"doubaowork", r"豆包工作", r"doubao", r"豆包"],
            "default_model": "Doubao-Seed-2.1-Pro",
            "models": [
                {"id": "doubao-2.1-pro", "name": "Doubao-Seed-2.1-Pro", "tier": 3, "cost_1m": 15},
                {"id": "doubao-pro-32k", "name": "Doubao-Pro-32k", "tier": 2, "cost_1m": 8},
                {"id": "doubao-lite", "name": "Doubao Lite", "tier": 1, "cost_1m": 3}
            ]
        },
        "alibaba_qoder": {
            "name": "Alibaba Qoder",
            "tool_tag": "⚡ ALIBABA QODER",
            "process_names": ["qoder.exe", "quadar.exe", "lingma.exe", "tongyi.exe", "qwen.exe"],
            "url_patterns": [r"tongyi\.aliyun\.com/lingma", r"qoder\.aliyun\.com"],
            "title_patterns": [r"qoder", r"quadar", r"通义灵码", r"lingma", r"qwen"],
            "default_model": "Qwen 2.5 Coder 32B",
            "models": [
                {"id": "qwen-2.5-coder-32b", "name": "Qwen 2.5 Coder 32B", "tier": 3, "cost_1m": 20},
                {"id": "qwen-max-coder", "name": "Qwen-Max Coder", "tier": 4, "cost_1m": 60},
                {"id": "tongyi-lingma-plus", "name": "Tongyi Lingma Plus", "tier": 2, "cost_1m": 10}
            ]
        },
        "workbuddy": {
            "name": "WorkBuddy",
            "tool_tag": "💼 WORKBUDDY",
            "process_names": ["workbuddy.exe", "work_buddy.exe"],
            "url_patterns": [r"workbuddy\.ai", r"workbuddy\.tencent\.com"],
            "title_patterns": [r"workbuddy", r"work buddy", r"腾讯workbuddy"],
            "default_model": "Hunyuan-Coder-Pro",
            "models": [
                {"id": "hunyuan-coder-pro", "name": "Hunyuan Coder Pro", "tier": 3, "cost_1m": 20},
                {"id": "hunyuan-standard", "name": "Hunyuan Standard", "tier": 2, "cost_1m": 10}
            ]
        },
        "baidu_comate": {
            "name": "Baidu Comate",
            "tool_tag": "🤖 BAIDU COMATE",
            "process_names": ["comate.exe", "baiducomate.exe"],
            "url_patterns": [r"comate\.baidu\.com"],
            "title_patterns": [r"comate", r"文心快码", r"baidu comate"],
            "default_model": "ERNIE-Code-4.0",
            "models": [
                {"id": "ernie-code-4.0", "name": "ERNIE Code 4.0", "tier": 3, "cost_1m": 25},
                {"id": "ernie-speed-code", "name": "ERNIE Speed Code", "tier": 1, "cost_1m": 4}
            ]
        },
        "codegeex": {
            "name": "CodeGeeX",
            "tool_tag": "🧠 CODEGEEX",
            "process_names": ["codegeex.exe"],
            "url_patterns": [r"codegeex\.cn"],
            "title_patterns": [r"codegeex", r"智谱代码"],
            "default_model": "CodeGeeX-4",
            "models": [
                {"id": "codegeex-4", "name": "CodeGeeX-4", "tier": 2, "cost_1m": 12}
            ]
        },
        "vscode": {
            "name": "VS Code",
            "tool_tag": "🔷 VS CODE",
            "process_names": ["code.exe"],
            "url_patterns": [],
            "title_patterns": [r"visual studio code", r"vscode"],
            "default_model": "Cline / Roo Code",
            "models": [
                {"id": "cline-roo", "name": "Cline / Roo Code", "tier": 3, "cost_1m": 60}
            ]
        },
        "deepseek": {
            "name": "DeepSeek",
            "tool_tag": "🐋 DEEPSEEK",
            "process_names": [],
            "url_patterns": [r"chat\.deepseek\.com", r"deepseek"],
            "title_patterns": [r"deepseek", r"深度求索"],
            "default_model": "DeepSeek-V4.1 Flash",
            "models": [
                {"id": "deepseek-v4.1-flash", "name": "DeepSeek-V4.1 Flash", "tier": 1, "cost_1m": 2},
                {"id": "deepseek-v4-pro", "name": "DeepSeek-V4-Pro", "tier": 2, "cost_1m": 8},
                {"id": "deepseek-r1", "name": "DeepSeek-R1", "tier": 3, "cost_1m": 16}
            ]
        },
        "kimi": {
            "name": "Kimi",
            "tool_tag": "🌙 KIMI",
            "process_names": [],
            "url_patterns": [r"kimi\.moonshot\.cn", r"kimi\.ai"],
            "title_patterns": [r"kimi", r"月之暗面"],
            "default_model": "Kimi K3",
            "models": [
                {"id": "kimi-k3", "name": "Kimi K3", "tier": 3, "cost_1m": 25},
                {"id": "kimi-k2", "name": "Kimi K2", "tier": 2, "cost_1m": 12}
            ]
        },
        "doubao": {
            "name": "Doubao",
            "tool_tag": "🌱 DOUBAO",
            "process_names": [],
            "url_patterns": [r"doubao\.com"],
            "title_patterns": [r"豆包", r"doubao"],
            "default_model": "Doubao-Seed-2.1-Pro",
            "models": [
                {"id": "doubao-2.1-pro", "name": "Doubao-Seed-2.1-Pro", "tier": 2, "cost_1m": 15},
                {"id": "doubao-lite", "name": "Doubao Lite", "tier": 1, "cost_1m": 3}
            ]
        },
        "claude": {
            "name": "Claude",
            "tool_tag": "🎭 CLAUDE",
            "process_names": [],
            "url_patterns": [r"claude\.ai"],
            "title_patterns": [r"claude"],
            "default_model": "Claude Fable 5.1",
            "models": [
                {"id": "claude-fable-5.1", "name": "Claude Fable 5.1", "tier": 5, "cost_1m": 180},
                {"id": "claude-mythos-5.1", "name": "Claude Mythos 5.1", "tier": 5, "cost_1m": 240},
                {"id": "claude-3.7-sonnet", "name": "Claude 3.7 Sonnet", "tier": 4, "cost_1m": 120}
            ]
        },
        "chatgpt": {
            "name": "ChatGPT",
            "tool_tag": "🤖 CHATGPT",
            "process_names": [],
            "url_patterns": [r"chatgpt\.com", r"chat\.openai\.com"],
            "title_patterns": [r"chatgpt", r"openai"],
            "default_model": "GPT-6 Astra",
            "models": [
                {"id": "gpt-6-astra", "name": "GPT-6 Astra", "tier": 5, "cost_1m": 200},
                {"id": "gpt-5.6-sol", "name": "GPT-5.6 Sol", "tier": 4, "cost_1m": 140},
                {"id": "gpt-4o", "name": "GPT-4o", "tier": 3, "cost_1m": 90}
            ]
        },
        "gemini": {
            "name": "Gemini",
            "tool_tag": "✨ GEMINI",
            "process_names": [],
            "url_patterns": [r"gemini\.google\.com", r"aistudio\.google\.com"],
            "title_patterns": [r"gemini"],
            "default_model": "Gemini 2.5 Pro",
            "models": [
                {"id": "gemini-2.5-pro", "name": "Gemini 2.5 Pro", "tier": 4, "cost_1m": 60},
                {"id": "gemini-2.5-flash", "name": "Gemini 2.5 Flash", "tier": 2, "cost_1m": 10}
            ]
        }
    }
}

try:
    from app_paths import get_app_data_dir
except ImportError:
    from src.app_paths import get_app_data_dir

class ModelDetector:
    """
    Identifies active AI application / webpage and tracks cumulative model token allocations.
    """
    def __init__(self, data_dir: Optional[str] = None):
        if not data_dir:
            data_dir = get_app_data_dir()
        self.data_dir = data_dir
        self.registry_file = os.path.join(data_dir, "model_registry.json")
        self.stats_file = os.path.join(data_dir, "model_usage_stats.json")
        self.registry = self._load_registry()
        self.usage_stats = self._load_usage_stats()
        self.active_platform = "copilot"
        self.active_tool = "⚡ COPILOT"
        self.active_model_name = "Copilot Claude 3.7 / GPT-4o"

    def _load_registry(self) -> Dict[str, Any]:
        if os.path.exists(self.registry_file):
            try:
                with open(self.registry_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return DEFAULT_MODEL_REGISTRY

    def _load_usage_stats(self) -> Dict[str, int]:
        if os.path.exists(self.stats_file):
            try:
                with open(self.stats_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        # Initialize default distribution for new setups
        return {
            "Copilot Claude 3.7 / GPT-4o": 3090000,
            "Gemini 2.5 Flash (AGY)": 17790000,
            "Doubao-Seed-2.1-Pro": 4030000,
            "Cursor Composer": 1125000,
            "DeepSeek-V4.1 Flash": 1800000,
            "Claude 3.7 Sonnet": 420000
        }

    def save_usage_stats(self):
        try:
            with open(self.stats_file, "w", encoding="utf-8") as f:
                json.dump(self.usage_stats, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def record_tokens(self, model_name: str, token_count: int):
        if not model_name:
            model_name = self.active_model_name
        self.usage_stats[model_name] = self.usage_stats.get(model_name, 0) + token_count
        self.save_usage_stats()

    def get_model_shares(self) -> Dict[str, float]:
        total = sum(self.usage_stats.values())
        if total == 0:
            return {self.active_model_name: 100.0}
        shares = {}
        for m, tokens in self.usage_stats.items():
            shares[m] = round((tokens / total) * 100.0, 1)
        return dict(sorted(shares.items(), key=lambda x: -x[1]))

    def get_model_info(self, model_name: str) -> Dict[str, Any]:
        for platform_key, pdata in self.registry.get("platforms", {}).items():
            for m in pdata.get("models", []):
                if m["name"].lower() == model_name.lower():
                    return {
                        "platform": pdata["name"],
                        "name": m["name"],
                        "tier": m.get("tier", 1),
                        "cost_1m": m.get("cost_1m", 5)
                    }
        return {"platform": "General AI", "name": model_name, "tier": 2, "cost_1m": 10}

    def detect_from_window(self, title: str, process_name: Optional[str] = None, url: Optional[str] = None) -> Tuple[str, str]:
        """
        Matches foreground process name, window title, or browser URL to find matching platform and model.
        Returns: (platform_name, model_name)
        """
        title_lower = (title or "").lower()
        proc_lower = (process_name or "").lower()
        url_lower = (url or "").lower()

        # 1. First priority: Match by Windows foreground process name
        if proc_lower:
            for key, pdata in self.registry.get("platforms", {}).items():
                for p_proc in pdata.get("process_names", []):
                    if p_proc.lower() in proc_lower:
                        self.active_platform = key
                        self.active_tool = pdata.get("tool_tag", pdata["name"])
                        # Check if title or url hints at specific model
                        for m in pdata.get("models", []):
                            if m["name"].lower() in title_lower or m["id"].lower() in title_lower:
                                self.active_model_name = m["name"]
                                return pdata["name"], m["name"]
                        self.active_model_name = pdata.get("default_model", "Standard")
                        return pdata["name"], self.active_model_name

        # 2. Second priority: Match by window title patterns
        if title_lower:
            for key, pdata in self.registry.get("platforms", {}).items():
                for t_pat in pdata.get("title_patterns", []):
                    if re.search(t_pat, title_lower):
                        self.active_platform = key
                        self.active_tool = pdata.get("tool_tag", pdata["name"])
                        for m in pdata.get("models", []):
                            if m["name"].lower() in title_lower or m["id"].lower() in title_lower:
                                self.active_model_name = m["name"]
                                return pdata["name"], m["name"]
                        self.active_model_name = pdata.get("default_model", "Standard")
                        return pdata["name"], self.active_model_name

        # 3. Third priority: Match by browser URL patterns
        if url_lower:
            for key, pdata in self.registry.get("platforms", {}).items():
                for u_pat in pdata.get("url_patterns", []):
                    if re.search(u_pat, url_lower):
                        self.active_platform = key
                        self.active_tool = pdata.get("tool_tag", pdata["name"])
                        for m in pdata.get("models", []):
                            if m["name"].lower() in title_lower or m["id"].lower() in url_lower:
                                self.active_model_name = m["name"]
                                return pdata["name"], m["name"]
                        self.active_model_name = pdata.get("default_model", "Standard")
                        return pdata["name"], self.active_model_name

        return "AI Copilot", self.active_model_name
