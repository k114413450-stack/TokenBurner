# -*- coding: utf-8 -*-
"""
TokenBurner - Per-Model Ghost & Real Ranking Engine with 100-Level RPG Progression
===================================================================================
1. Zero geographic/regional data: strictly uses clean anonymous handles (e.g. CyberDev#8241).
2. Per-Model Leaderboards: tracks usage by model (e.g., DeepSeek-V4.1, Claude 5.1).
3. Ghost Pool System: seeds realistic mock users with log-normal token curves.
4. Seamless Transition: as real user counts grow, ghost users are dynamically replaced.
5. 100-Level Exponential Progression starting at 1,000,000 tokens.
Strictly English code per global agent rules.
"""

import os
import json
import random
import math
from typing import List, Dict, Any, Tuple, Optional

# 10 Eras x 10 Tiers = 100 Levels (Bilingual EN / ZH)
ERA_TITLES = [
    {
        "era_en": "Mortal Era", "era_zh": "凡人纪元",
        "tiers_en": [
            "Cyber Novice", "Digital Initiate", "Terminal Seeker", "Shell Apprentice",
            "Data Scavenger", "Info Hunter", "Script Operator", "Code Adept", "Compute Sensor", "Digital Scout"
        ],
        "tiers_zh": [
            "赛博蒙昧者", "数字萌新", "终端触碰者", "命令行学徒",
            "数据囤积者", "信息猎人", "脚本小子", "代码初修者", "算力感知者", "数字工蚁"
        ]
    },
    {
        "era_en": "Enlightenment Era", "era_zh": "启蒙纪元",
        "tiers_en": [
            "AI Collaborator", "Prompt Crafter", "Semantic Pilot", "Multimodal Alchemist",
            "Context Virtuoso", "CoT Weaver", "Neural Awakener", "Emergence Scout", "Cognitive Pioneer", "Mind Expander"
        ],
        "tiers_zh": [
            "AI协作者", "提示词工匠", "语义驾驭者", "多模融合师",
            "上下文大师", "思维链编织者", "神经唤醒者", "涌现探索者", "智识扩展者", "认知增强者"
        ]
    },
    {
        "era_en": "Elite Era", "era_zh": "精英纪元",
        "tiers_en": [
            "Compute Knight", "Data Stalker", "Inference Rusher", "Hallucination Tamer",
            "Model Smith", "Parallel Thinker", "Swarm Conductor", "Distillation Expert", "Lexicon Forger", "Cognitive Vanguard"
        ],
        "tiers_zh": [
            "算力骑士", "数据猎人", "推理加速者", "幻觉驯化师",
            "模型锻造者", "分布式思维者", "多智体编导", "知识蒸馏者", "语言塑造者", "认知拓展者"
        ]
    },
    {
        "era_en": "Lordship Era", "era_zh": "领主纪元",
        "tiers_en": [
            "Cyber Lord", "Algorithmic Noble", "Data Baron", "Neural Aristocrat",
            "Model Monarch", "Compute Magistrate", "Intelli Governor", "Cognitive Sovereign", "Compute Leader", "Digital Duke"
        ],
        "tiers_zh": [
            "赛博领主", "算法贵族", "数据封侯", "神经贵族",
            "模型君主", "计算执政", "智能总督", "认知帝王", "算力领袖", "数字君侯"
        ]
    },
    {
        "era_en": "Kingship Era", "era_zh": "王者纪元",
        "tiers_en": [
            "Token King", "Compute Overlord", "Neural Monarch", "Dynasty Overseer", "Crown of AI",
            "Emergence Sovereign", "Algorithmic King", "Cognitive Ruler", "Silicon King", "Supremacy Pilot"
        ],
        "tiers_zh": [
            "Token王", "算力霸主", "神经王座者", "数据王朝主", "AI王权执掌者",
            "涌现王者", "算法至尊", "认知王者", "硅基王者", "智识至高者"
        ]
    },
    {
        "era_en": "Legend Era", "era_zh": "传奇纪元",
        "tiers_en": [
            "Digital Legend", "Compute Mythic", "Silicon Prophet", "Neural Luminary", "AI Vanguard",
            "Cognitive Legend", "Data Paragon", "Algorithm Saint", "Model Luminary", "Cyber Oracle"
        ],
        "tiers_zh": [
            "数字传说", "算力传奇", "硅基先知", "神经传说", "AI先驱者",
            "认知传奇", "数据神话", "算法传奇", "模型圣徒", "赛博先知"
        ]
    },
    {
        "era_en": "Epic Era", "era_zh": "史诗纪元",
        "tiers_en": [
            "Digital Epic", "Compute Titan", "Silicon Immortal", "Neural Eternal", "AI Episteme",
            "Cognitive Titan", "Data Undying", "Algorithmic Titan", "Model Immortal", "Cyber Titan"
        ],
        "tiers_zh": [
            "数字史诗", "算力史诗", "硅基不朽", "神经永恒", "AI史诗",
            "认知史诗", "数据不朽", "算法史诗", "模型不朽", "赛博史诗"
        ]
    },
    {
        "era_en": "Mythos Era", "era_zh": "神话纪元",
        "tiers_en": [
            "Silicon Mythos", "Compute Celestial", "Digital Demiurge", "Neural Mythos", "AI Transcendent",
            "Cognitive Mythos", "Data Prime", "Algorithm Eternal", "Model Transcendent", "Cyber Celestial"
        ],
        "tiers_zh": [
            "硅基神话", "算力神话", "数字神话", "神经神话", "AI神话",
            "认知神话", "数据神话主", "算法神话", "模型神话", "赛博神话"
        ]
    },
    {
        "era_en": "Deity Era", "era_zh": "神明纪元",
        "tiers_en": [
            "Digital God", "Compute Divinity", "Silicon Deity", "Neural Archon", "AI Overmind",
            "Cognitive Godhead", "Data Absolute", "Algorithm Overlord", "Model Prime Deity", "Cyber Supreme"
        ],
        "tiers_zh": [
            "数字天神", "算力天神", "硅基天神", "神经天神", "AI天神",
            "认知天神", "数据天神", "算法天神", "模型天神", "赛博天神"
        ]
    },
    {
        "era_en": "Eternal Era", "era_zh": "永恒纪元",
        "tiers_en": [
            "Silicon Eternal", "Compute Genesis", "Digital Omniscient", "Neural Cosm", "AI Demiurge",
            "Cognitive Omnipresent", "Data Omniverse", "Algorithm Master", "Model Godhead", "[Silicon Architect]"
        ],
        "tiers_zh": [
            "硅基永恒者", "算力创世者", "数字宇宙主", "神经宇宙神", "AI创世神",
            "认知宇宙神", "数据宇宙主", "算法宇宙神", "模型宇宙神", "【硅基造物主】"
        ]
    }
]

# Calculate exponential XP thresholds for 100 levels starting at 1,000,000 tokens
LEVEL_THRESHOLDS = [0]
_base_xp = 1_000_000
_accum = 0
for lv in range(1, 102):
    _step = int(_base_xp * math.pow(1.22, lv - 1))
    _accum += _step
    LEVEL_THRESHOLDS.append(_accum)

def calculate_level(tokens: int, lang: str = "zh") -> Tuple[int, float, int, int, str, str]:
    """
    Returns: (level, progress_ratio, current_xp_in_level, needed_xp_in_level, era_name, title_name)
    """
    is_zh = (lang == "zh")
    if tokens < LEVEL_THRESHOLDS[1]:
        req = LEVEL_THRESHOLDS[1]
        pct = max(0.0, min(1.0, tokens / req))
        era = ERA_TITLES[0]["era_zh"] if is_zh else ERA_TITLES[0]["era_en"]
        title = ERA_TITLES[0]["tiers_zh"][0] if is_zh else ERA_TITLES[0]["tiers_en"][0]
        return 1, pct, tokens, req - tokens, era, title

    for lv in range(100, 0, -1):
        if tokens >= LEVEL_THRESHOLDS[lv]:
            if lv >= 100:
                era = ERA_TITLES[9]["era_zh"] if is_zh else ERA_TITLES[9]["era_en"]
                title = ERA_TITLES[9]["tiers_zh"][9] if is_zh else ERA_TITLES[9]["tiers_en"][9]
                return 100, 1.0, tokens, 0, era, title

            floor = LEVEL_THRESHOLDS[lv]
            ceil = LEVEL_THRESHOLDS[lv + 1]
            span = ceil - floor
            in_level = tokens - floor
            pct = in_level / span if span > 0 else 1.0
            
            era_idx = min(9, (lv - 1) // 10)
            tier_idx = (lv - 1) % 10
            era = ERA_TITLES[era_idx]["era_zh"] if is_zh else ERA_TITLES[era_idx]["era_en"]
            title = ERA_TITLES[era_idx]["tiers_zh"][tier_idx] if is_zh else ERA_TITLES[era_idx]["tiers_en"][tier_idx]
            return lv, pct, in_level, ceil - tokens, era, title

    era = ERA_TITLES[0]["era_zh"] if is_zh else ERA_TITLES[0]["era_en"]
    title = ERA_TITLES[0]["tiers_zh"][0] if is_zh else ERA_TITLES[0]["tiers_en"][0]
    return 1, 0.0, tokens, LEVEL_THRESHOLDS[1], era, title


try:
    from app_paths import get_app_data_dir
except ImportError:
    from src.app_paths import get_app_data_dir

class RankingEngine:
    """
    Model-specific leaderboard engine with dynamic ghost-replacement architecture.
    """
    def __init__(self, data_dir: Optional[str] = None):
        if not data_dir:
            data_dir = get_app_data_dir()
        self.data_dir = data_dir
        self.ghost_cache_file = os.path.join(data_dir, "ghost_leaderboards.json")
        self.real_users_file = os.path.join(data_dir, "real_users_cache.json")
        self.ghost_pools = self._load_or_create_ghost_pools()

    def _generate_ghost_users_for_model(self, model_name: str, count: int = 150, seed: int = 42) -> List[Dict[str, Any]]:
        rng = random.Random(seed + hash(model_name) % 100000)
        prefixes = ["Neo", "Cyber", "Byte", "Pixel", "Zero", "Ghost", "Flux", "Echo", "Aero", "Pulse", "Rogue", "Nova"]
        suffixes = ["Runner", "Pilot", "Engineer", "Architect", "Operator", "Dev", "Coder", "Master", "Sage", "Nomad"]
        
        users = []
        for i in range(count):
            p = rng.choice(prefixes)
            s = rng.choice(suffixes)
            tag = rng.randint(1000, 9999)
            name = f"{p}{s}#{tag}"
            
            # Log-normal distribution of tokens for this model
            # Mean ~ 3.5M tokens, with tail up to 800M
            tokens = int(rng.lognormvariate(mu=14.8, sigma=2.1))
            tokens = max(150_000, min(tokens, 850_000_000))
            lv, _, _, _, era, title = calculate_level(tokens)
            
            users.append({
                "id": f"ghost_{model_name}_{i}",
                "name": name,
                "model": model_name,
                "tokens": tokens,
                "level": lv,
                "title": title,
                "is_ghost": True
            })

        users.sort(key=lambda x: -x["tokens"])
        return users

    def _load_or_create_ghost_pools(self) -> Dict[str, List[Dict[str, Any]]]:
        if os.path.exists(self.ghost_cache_file):
            try:
                with open(self.ghost_cache_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass

        # Build initial pools for top models
        top_models = [
            "DeepSeek-V4.1 Flash",
            "Kimi K3",
            "Claude Fable 5.1",
            "GPT-6 Astra",
            "Doubao-Seed-2.1-Pro"
        ]
        pools = {}
        for idx, m in enumerate(top_models):
            pools[m] = self._generate_ghost_users_for_model(m, count=200, seed=100 + idx * 77)
        
        try:
            with open(self.ghost_cache_file, "w", encoding="utf-8") as f:
                json.dump(pools, f, indent=2, ensure_ascii=False)
        except Exception:
            pass
        return pools

    def get_model_leaderboard(
        self,
        model_name: str,
        user_tokens: int,
        user_name: str = "MyCyberCore",
        real_users: Optional[List[Dict[str, Any]]] = None,
        lang: str = "zh"
    ) -> Dict[str, Any]:
        """
        Merges real users with ghost users for the requested model.
        Returns: {
            "model": model_name,
            "my_rank": int,
            "total_players": int,
            "beat_percentage": float,
            "my_level": int,
            "my_title": str,
            "top_entries": top rows
        }
        """
        if model_name not in self.ghost_pools:
            self.ghost_pools[model_name] = self._generate_ghost_users_for_model(model_name, count=150)

        ghost_pool = self.ghost_pools[model_name]
        real_list = [u for u in (real_users or []) if u.get("model") == model_name]
        real_count = len(real_list)

        # Dynamic Ghost Displacement Curve
        # If real_count < 10: 95% ghost
        # If real_count 10~100: scale down ghosts
        # If real_count >= 200: 0% ghost
        if real_count >= 200:
            ghost_take = 0
        else:
            ratio = max(0.0, 1.0 - (real_count / 200.0))
            ghost_take = int(150 * ratio)

        combined = real_list + ghost_pool[:ghost_take]

        # Insert active user
        my_lv, _, _, _, _, my_title = calculate_level(user_tokens, lang=lang)
        me_entry = {
            "id": "me",
            "name": user_name,
            "model": model_name,
            "tokens": user_tokens,
            "level": my_lv,
            "title": my_title,
            "is_me": True,
            "is_ghost": False
        }
        combined.append(me_entry)

        # Sort descending by tokens
        combined.sort(key=lambda x: -x["tokens"])

        # Find user's rank
        my_rank = 1
        for idx, entry in enumerate(combined):
            if entry.get("is_me"):
                my_rank = idx + 1
                break

        total_players = len(combined)
        beat_pct = round(max(0.0, min(99.9, (1.0 - (my_rank / total_players)) * 100.0)), 1)

        return {
            "model": model_name,
            "my_rank": my_rank,
            "total_players": total_players,
            "beat_percentage": beat_pct,
            "my_level": my_lv,
            "my_title": my_title,
            "top_entries": combined[:30]
        }
