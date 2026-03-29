"""Knowledge extraction from chapter content for database population.

Enhanced with RPG-inspired data structures:
- item_history: Item transfer records
- character_relations: Character relationships with trust/tension
- chapter_snapshots: Chapter state snapshots
- cultivation_techniques: Structured cultivation system
"""

import re
import json
import sqlite3
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field


# New enhanced dataclass with RPG-style data
@dataclass
class ExtractedKnowledge:
    characters: List[Dict[str, Any]] = field(default_factory=list)
    items: List[Dict[str, Any]] = field(default_factory=list)
    locations: List[Dict[str, Any]] = field(default_factory=list)
    events: List[Dict[str, Any]] = field(default_factory=list)
    plot_threads: List[Dict[str, Any]] = field(default_factory=list)
    item_transfers: List[Dict[str, Any]] = field(default_factory=list)
    character_relations: List[Dict[str, Any]] = field(default_factory=list)
    cultivation_techniques: List[Dict[str, Any]] = field(default_factory=list)
    character_techniques: List[Dict[str, Any]] = field(default_factory=list)


# SQL for all tables
NEW_TABLE_SQL = """
-- Characters table
CREATE TABLE IF NOT EXISTS characters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    alias TEXT,
    gender TEXT,
    age TEXT,
    appearance TEXT,
    personality TEXT,
    background TEXT,
    cultivation_realm TEXT,
    faction TEXT,
    status TEXT DEFAULT 'alive',
    first_appearance_chapter INTEGER,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Items table
CREATE TABLE IF NOT EXISTS items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    type TEXT NOT NULL,
    description TEXT,
    properties TEXT,
    owner_id INTEGER,
    origin TEXT,
    current_location TEXT,
    chapter_obtained INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (owner_id) REFERENCES characters(id)
);

-- Locations table
CREATE TABLE IF NOT EXISTS locations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    type TEXT,
    parent_location TEXT,
    description TEXT,
    significance TEXT,
    first_appearance_chapter INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Events table
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chapter INTEGER NOT NULL,
    sequence_in_chapter INTEGER,
    title TEXT,
    description TEXT,
    location_id INTEGER,
    timestamp_in_story TEXT,
    significance TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (location_id) REFERENCES locations(id)
);

-- Timeline table
CREATE TABLE IF NOT EXISTS timeline (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chapter INTEGER NOT NULL,
    sequence INTEGER,
    relative_time TEXT,
    season TEXT,
    description TEXT,
    key_events TEXT
);

-- Plot threads table
CREATE TABLE IF NOT EXISTS plot_threads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    status TEXT DEFAULT 'active',
    started_chapter INTEGER,
    resolved_chapter INTEGER,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Character events junction
CREATE TABLE IF NOT EXISTS character_events (
    character_id INTEGER NOT NULL,
    event_id INTEGER NOT NULL,
    role TEXT,
    outcome TEXT,
    PRIMARY KEY (character_id, event_id),
    FOREIGN KEY (character_id) REFERENCES characters(id),
    FOREIGN KEY (event_id) REFERENCES events(id)
);

-- Character items junction
CREATE TABLE IF NOT EXISTS character_items (
    character_id INTEGER NOT NULL,
    item_id INTEGER NOT NULL,
    acquired_chapter INTEGER,
    manner_acquired TEXT,
    is_current_owner BOOLEAN DEFAULT 1,
    PRIMARY KEY (character_id, item_id),
    FOREIGN KEY (character_id) REFERENCES characters(id),
    FOREIGN KEY (item_id) REFERENCES items(id)
);

-- Character locations junction
CREATE TABLE IF NOT EXISTS character_locations (
    character_id INTEGER NOT NULL,
    location_id INTEGER NOT NULL,
    chapter_from INTEGER,
    chapter_to INTEGER,
    purpose TEXT,
    PRIMARY KEY (character_id, location_id),
    FOREIGN KEY (character_id) REFERENCES characters(id),
    FOREIGN KEY (location_id) REFERENCES locations(id)
);

-- Indexes for original tables
CREATE INDEX IF NOT EXISTS idx_characters_name ON characters(name);
CREATE INDEX IF NOT EXISTS idx_items_name ON items(name);
CREATE INDEX IF NOT EXISTS idx_items_owner ON items(owner_id);
CREATE INDEX IF NOT EXISTS idx_events_chapter ON events(chapter);
CREATE INDEX IF NOT EXISTS idx_character_events_char ON character_events(character_id);

-- Item transfer history (who had the item before)
CREATE TABLE IF NOT EXISTS item_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id INTEGER NOT NULL,
    from_character_id INTEGER,
    to_character_id INTEGER,
    chapter INTEGER NOT NULL,
    reason TEXT,
    transfer_type TEXT DEFAULT 'unknown',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (item_id) REFERENCES items(id),
    FOREIGN KEY (from_character_id) REFERENCES characters(id),
    FOREIGN KEY (to_character_id) REFERENCES characters(id)
);

-- Character relationships with trust/tension tracking
CREATE TABLE IF NOT EXISTS character_relations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    character1_id INTEGER NOT NULL,
    character2_id INTEGER NOT NULL,
    relation_type TEXT DEFAULT 'unknown',
    trust_level INTEGER DEFAULT 50,
    tension_level INTEGER DEFAULT 0,
    notes TEXT,
    updated_chapter INTEGER,
    UNIQUE(character1_id, character2_id),
    FOREIGN KEY (character1_id) REFERENCES characters(id),
    FOREIGN KEY (character2_id) REFERENCES characters(id)
);

-- Chapter state snapshots for continuity
CREATE TABLE IF NOT EXISTS chapter_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chapter INTEGER UNIQUE NOT NULL,
    character_states TEXT,
    world_states TEXT,
    plot_threads_active TEXT,
    key_decisions TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Cultivation techniques system
CREATE TABLE IF NOT EXISTS cultivation_techniques (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    realm TEXT NOT NULL,
    stage INTEGER,
    effects TEXT,
    side_effects TEXT,
    prerequisites TEXT,
    origin TEXT
);

-- Character technique mastery
CREATE TABLE IF NOT EXISTS character_techniques (
    character_id INTEGER NOT NULL,
    technique_id INTEGER NOT NULL,
    mastery_level TEXT DEFAULT 'beginner',
    chapter_learned INTEGER,
    notes TEXT,
    PRIMARY KEY (character_id, technique_id),
    FOREIGN KEY (character_id) REFERENCES characters(id),
    FOREIGN KEY (technique_id) REFERENCES cultivation_techniques(id)
);

-- Indexes for new tables
CREATE INDEX IF NOT EXISTS idx_item_history_item ON item_history(item_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_item_history_unique ON item_history(item_id, chapter, transfer_type);
CREATE INDEX IF NOT EXISTS idx_character_relations_char1 ON character_relations(character1_id);
CREATE INDEX IF NOT EXISTS idx_character_relations_char2 ON character_relations(character2_id);
CREATE INDEX IF NOT EXISTS idx_chapter_snapshots_chapter ON chapter_snapshots(chapter);
CREATE INDEX IF NOT EXISTS idx_cultivation_techniques_realm ON cultivation_techniques(realm);
"""


class KnowledgeExtractor:
    """Extract structured knowledge from chapter content."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_new_tables()

    def _init_new_tables(self):
        """Initialize new tables if they don't exist."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.executescript(NEW_TABLE_SQL)
            conn.commit()
        finally:
            conn.close()

    def extract_from_chapter(
        self,
        chapter_num: int,
        content: str,
        title: str = ""
    ) -> ExtractedKnowledge:
        """Extract knowledge from a single chapter."""
        characters = self._extract_characters(content, chapter_num)
        items = self._extract_items(content, chapter_num)
        locations = self._extract_locations(content, chapter_num)
        events = self._extract_events(content, chapter_num, title)
        plot_threads = self._extract_plot_threads(content, chapter_num)
        item_transfers = self._extract_item_transfers(content, chapter_num)
        character_relations = self._extract_character_relations(content, chapter_num)
        cultivation_techniques = self._extract_cultivation_techniques(content, chapter_num)
        character_techniques = self._extract_character_techniques(content, chapter_num)

        return ExtractedKnowledge(
            characters=characters,
            items=items,
            locations=locations,
            events=events,
            plot_threads=plot_threads,
            item_transfers=item_transfers,
            character_relations=character_relations,
            cultivation_techniques=cultivation_techniques,
            character_techniques=character_techniques,
        )

    def _extract_characters(self, content: str, chapter: int) -> List[Dict[str, Any]]:
        """Extract character information from content."""
        characters = []
        seen = set()

        # Known character patterns - cultivation realm mentions
        realm_patterns = [
            (r"韩林.*?(凝元境|灵海境|筑基|炼气)", "韩林"),
            (r"叶尘.*?(凝元境|灵海境|筑基|炼气)", "叶尘"),
            (r"韩烈.*?(筑基|凝元境|金丹)", "韩烈"),
            (r"玄袍魔尊|魔尊.*?(残魂|三千年)", "玄袍魔尊"),
            (r"柳如烟", "柳如烟"),
            (r"韩家.*?家主", "韩烈"),
        ]

        # Character name mentions with context
        character_contexts = {
            "韩林": {
                "alias": "叶尘口中的废物",
                "gender": "男",
                "background": "韩家被逐子弟，三年前测灵大典受辱",
                "faction": "无",
                "first_appearance_chapter": 1,
            },
            "叶尘": {
                "alias": "叶家天才",
                "gender": "男",
                "background": "凝元境巅峰，叶家第一天才",
                "faction": "叶家",
                "first_appearance_chapter": 1,
            },
            "韩烈": {
                "alias": "韩家家主，韩林叔父",
                "gender": "男",
                "background": "三年前将韩林逐出韩家",
                "faction": "韩家",
                "first_appearance_chapter": 2,
            },
            "玄袍魔尊": {
                "alias": "前世残魂",
                "gender": "男",
                "background": "自称被困三千年，传授逆仙录",
                "faction": "魔道",
                "first_appearance_chapter": 1,
            },
            "柳如烟": {
                "alias": "翠微峰某女修",
                "gender": "女",
                "background": "叶尘心中的白月光",
                "faction": "青云宗",
                "first_appearance_chapter": 3,
            },
        }

        for name, info in character_contexts.items():
            if name in content and name not in seen:
                characters.append({
                    "name": name,
                    "alias": info["alias"],
                    "gender": info["gender"],
                    "background": info["background"],
                    "cultivation_realm": self._extract_realm(content, name),
                    "faction": info["faction"],
                    "first_appearance_chapter": info.get("first_appearance_chapter", chapter),
                    "status": "alive",
                })
                seen.add(name)

        return characters

    def _extract_realm(self, content: str, character: str) -> str:
        """Extract cultivation realm for a character."""
        chinese_nums = {'一': '1', '二': '2', '三': '3', '四': '4', '五': '5',
                        '六': '6', '七': '7', '八': '8', '九': '9', '十': '10'}

        # Build patterns manually
        p1 = character + r".*?凝元境"
        p2 = character + r".*?灵海境"
        p3 = character + r".*?筑基"
        p4 = character + r".*?金丹境"
        # Chinese number pattern with capturing group
        p5 = character + r".*?炼气([" + ''.join(chinese_nums.keys()) + r"])层"
        p6 = character + r".*?炼气(\d)"

        patterns = [
            (p1, "凝元境"),
            (p2, "灵海境"),
            (p3, "筑基"),
            (p4, "金丹境"),
            (p5, self._convert_realm),
            (p6, r"炼气\1层"),
        ]
        for pattern, realm in patterns:
            match = re.search(pattern, content)
            if match:
                if callable(realm):
                    return realm(match.group(1))
                return realm
        return "unknown"

    def _convert_realm(self, num: str) -> str:
        """Convert Chinese number to realm string."""
        chinese_nums = {'一': '1', '二': '2', '三': '3', '四': '4', '五': '5',
                        '六': '6', '七': '7', '八': '8', '九': '9', '十': '10'}
        if num in chinese_nums:
            return f"炼气{chinese_nums[num]}层"
        return f"炼气{num}层"

    def _extract_items(self, content: str, chapter: int) -> List[Dict[str, Any]]:
        """Extract items/artifacts from content."""
        items = []
        seen = set()

        item_definitions = {
            "逆仙录玉简": {
                "type": "功法玉简",
                "description": "漆黑玉简，记载《逆仙录》功法，暗金色纹路",
                "properties": "内含魔尊残魂，激活后可修炼逆仙录",
                "origin": "韩家祖传宝物",
            },
            "逆仙录": {
                "type": "功法",
                "description": "共九重，每一重对应一个大境界",
                "properties": "逆脉→逆骨→逆血→逆脏→逆髓→逆脑→逆神→逆虚→逆道",
                "origin": "上古魔帝所创",
            },
            "诛魔阵": {
                "type": "阵法",
                "description": "韩家专门克制魔道功法的阵法",
                "properties": "需要筑基后期才能布阵",
                "origin": "韩家祖传",
            },
            "护身符": {
                "type": "护身符",
                "description": "母亲缝进韩林衣领的护身符",
                "properties": "来历不明",
                "origin": "韩林母亲",
            },
        }

        for item_name, info in item_definitions.items():
            if item_name in content and item_name not in seen:
                items.append({
                    "name": item_name,
                    "type": info["type"],
                    "description": info["description"],
                    "properties": info["properties"],
                    "origin": info["origin"],
                    "chapter_obtained": self._get_item_chapter(content, item_name, chapter),
                })
                seen.add(item_name)

        return items

    def _get_item_chapter(self, content: str, item: str, default: int) -> int:
        """Determine which chapter an item was obtained."""
        if item == "逆仙录玉简":
            if "七日前" in content or "七日来" in content:
                return max(1, default - 1)
        return default

    def _extract_locations(self, content: str, chapter: int) -> List[Dict[str, Any]]:
        """Extract locations from content."""
        locations = []
        seen = set()

        location_definitions = {
            "青云宗": {
                "type": "宗门",
                "description": "修仙门派，韩林所在的宗门",
                "significance": "韩林拜入的外门",
            },
            "后山废弃药圃": {
                "type": "修炼地",
                "parent_location": "青云宗",
                "description": "杂草丛生，偏僻安静",
                "significance": "韩林偷偷修炼的地方",
            },
            "翠微峰": {
                "type": "山峰",
                "parent_location": "青云宗",
                "description": "某女修所在",
                "significance": "柳如烟所在",
            },
            "破庙": {
                "type": "废弃建筑",
                "description": "韩林七日前激活玉简的地方",
                "significance": "逆仙录玉简激活地点",
            },
            "韩家大宅": {
                "type": "家族驻地",
                "description": "韩家祖宅，韩林三年前被逐出",
                "significance": "韩烈的势力范围",
            },
            "韩家祖地": {
                "type": "秘境",
                "description": "藏有韩林父亲遗骸和玉简秘密",
                "significance": "魔尊需要韩林去的地方",
            },
            "青云城": {
                "type": "城市",
                "description": "叶家所在的城市",
                "significance": "叶尘的家族所在地",
            },
            "山谷": {
                "type": "野外",
                "description": "韩林与叶尘对峙的地方",
                "significance": "第二次遭遇战地点",
            },
        }

        for loc_name, info in location_definitions.items():
            if loc_name in content and loc_name not in seen:
                loc_data = {
                    "name": loc_name,
                    "type": info.get("type", "unknown"),
                    "parent_location": info.get("parent_location", ""),
                    "description": info.get("description", ""),
                    "significance": info.get("significance", ""),
                    "first_appearance_chapter": chapter,
                }
                locations.append(loc_data)
                seen.add(loc_name)

        return locations

    def _extract_events(self, content: str, chapter: int, title: str) -> List[Dict[str, Any]]:
        """Extract major events from content."""
        events = []

        # Common event patterns
        event_patterns = [
            (r"测灵大典", "测灵大典", "韩林受辱被逐"),
            (r"激活.*?玉简|以血激活", "玉简激活", "韩林激活逆仙录玉简"),
            (r"逆脉.*?大成|第一重.*?大成", "逆脉境大成", "韩林修炼逆仙录第一重"),
            (r"韩烈.*?追杀|三日之后.*?韩烈", "韩烈追杀", "韩烈将在三日后追杀韩林"),
            (r"叶尘.*?威胁|叶尘.*?凝元境", "叶尘威胁", "叶尘威胁韩林"),
            (r"魔尊.*?残魂|梦境.*?魔尊", "魔尊残魂", "玄袍魔尊在梦中现身"),
            (r"诛魔阵", "诛魔阵预告", "韩烈将带诛魔阵追杀"),
            (r"逆骨", "逆骨修炼", "韩林开始修炼第二重"),
        ]

        for pattern, event_title, desc in event_patterns:
            if re.search(pattern, content):
                events.append({
                    "chapter": chapter,
                    "title": event_title,
                    "description": desc,
                    "sequence_in_chapter": len(events) + 1,
                    "significance": "major" if "追杀" in event_title or "威胁" in event_title else "normal",
                })

        return events

    def _extract_plot_threads(self, content: str, chapter: int) -> List[Dict[str, Any]]:
        """Extract ongoing plot threads."""
        threads = []

        thread_patterns = [
            (r"逆仙录", "逆仙录之谜", "逆仙录的真正来历和魔尊的身份"),
            (r"韩林.*?父亲|父亲.*?遗骸|韩家祖地", "韩林身世之谜", "韩林父亲之死和韩家秘密"),
            (r"叶尘.*?柳如烟|柳如烟", "三角关系", "叶尘对柳如烟的感情"),
            (r"三日之后|韩烈.*?诛魔阵", "三日危机", "韩烈三日后带诛魔阵追杀韩林"),
            (r"青云宗.*?外门|外门.*?扬名", "外门崛起", "韩林在青云宗外门的成长"),
        ]

        for pattern, name, desc in thread_patterns:
            if re.search(pattern, content):
                threads.append({
                    "name": name,
                    "description": desc,
                    "status": "active",
                    "started_chapter": chapter,
                })

        return threads

    def _extract_item_transfers(self, content: str, chapter: int) -> List[Dict[str, Any]]:
        """Extract item transfer events (who gave what to whom)."""
        transfers = []

        transfer_patterns = [
            # 逆仙录玉简 transfers
            (r"韩林.*?激活.*?玉简|以血激活.*?玉简", "韩林", None, "激活玉简", "find"),
            (r"韩烈.*?想要.*?玉简|韩烈.*?夺回.*?玉简", "韩烈", "韩林", "韩烈欲夺取玉简", "take"),
            # 护身符 transfers
            (r"母亲.*?缝进.*?衣领|护身符.*?母亲", "韩林母亲", "韩林", "母亲给韩林护身符", "give"),
        ]

        item_names = ["逆仙录玉简", "护身符"]
        for pattern, from_char, to_char, reason, transfer_type in transfer_patterns:
            if re.search(pattern, content):
                for item_name in item_names:
                    if item_name in content:
                        transfers.append({
                            "item_name": item_name,
                            "from_character": from_char,
                            "to_character": to_char,
                            "chapter": chapter,
                            "reason": reason,
                            "transfer_type": transfer_type,
                        })
                        break

        return transfers

    def _extract_character_relations(self, content: str, chapter: int) -> List[Dict[str, Any]]:
        """Extract character relationships."""
        relations = []

        relation_definitions = [
            ("韩林", "叶尘", "rival", 20, 80, "叶尘视韩林为废物，多次威胁", chapter),
            ("韩林", "韩烈", "enemy", 0, 100, "韩烈三年前逐出韩林，将追杀韩林", chapter),
            ("韩林", "玄袍魔尊", "master", 40, 20, "魔尊传授逆仙录", chapter),
            ("叶尘", "柳如烟", "romantic", 80, 0, "叶尘心中的白月光", chapter),
            ("韩林", "柳如烟", "unknown", 30, 10, "同门关系", chapter),
        ]

        for char1, char2, rel_type, trust, tension, notes, ch in relation_definitions:
            if char1 in content and char2 in content:
                relations.append({
                    "character1": char1,
                    "character2": char2,
                    "relation_type": rel_type,
                    "trust_level": trust,
                    "tension_level": tension,
                    "notes": notes,
                    "updated_chapter": ch,
                })

        return relations

    def _extract_cultivation_techniques(self, content: str, chapter: int) -> List[Dict[str, Any]]:
        """Extract cultivation techniques from content."""
        techniques = []

        technique_definitions = {
            "逆仙录": {
                "realm": "通用",
                "stage": 9,
                "effects": "逆转经脉修炼，爆发式力量增长",
                "side_effects": "可能入魔",
                "prerequisites": "需逆元根骨",
                "origin": "上古魔帝所创",
            },
            "引气诀": {
                "realm": "炼气",
                "stage": 1,
                "effects": "引气入体，基础修炼功法",
                "side_effects": "无",
                "prerequisites": "无",
                "origin": "青云宗基础功法",
            },
            "逆脉": {
                "realm": "炼气",
                "stage": 1,
                "effects": "逆转经脉运行之法",
                "side_effects": "痛苦剧烈",
                "prerequisites": "需修炼逆仙录",
                "origin": "逆仙录第一重",
            },
            "逆骨": {
                "realm": "炼气",
                "stage": 2,
                "effects": "以逆元之力淬炼骨骼，脱胎换骨",
                "side_effects": "骨骼碎裂风险",
                "prerequisites": "逆脉境大成",
                "origin": "逆仙录第二重",
            },
        }

        for tech_name, info in technique_definitions.items():
            if tech_name in content:
                techniques.append({
                    "name": tech_name,
                    "realm": info["realm"],
                    "stage": info["stage"],
                    "effects": info["effects"],
                    "side_effects": info["side_effects"],
                    "prerequisites": info["prerequisites"],
                    "origin": info["origin"],
                })

        return techniques

    def _extract_character_techniques(self, content: str, chapter: int) -> List[Dict[str, Any]]:
        """Extract which characters learned which techniques."""
        char_techs = []

        # 逆仙录 techniques
        if "逆脉境大成" in content or "第一重" in content:
            char_techs.append({
                "character": "韩林",
                "technique": "逆仙录",
                "mastery_level": "intermediate",
                "chapter_learned": chapter,
                "notes": "逆脉境大成",
            })

        if "逆骨" in content and chapter >= 6:
            char_techs.append({
                "character": "韩林",
                "technique": "逆骨",
                "mastery_level": "beginner",
                "chapter_learned": chapter,
                "notes": "开始修炼第二重",
            })

        if "引气诀" in content:
            char_techs.append({
                "character": "韩林",
                "technique": "引气诀",
                "mastery_level": "advanced",
                "chapter_learned": 1,
                "notes": "三年修炼",
            })

        return char_techs

    def save_to_database(self, knowledge: ExtractedKnowledge, chapter: int):
        """Save extracted knowledge to database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            # Insert characters
            for char in knowledge.characters:
                cursor.execute("""
                    INSERT OR REPLACE INTO characters
                    (name, alias, gender, background, cultivation_realm, faction,
                     status, first_appearance_chapter)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    char.get("name"),
                    char.get("alias"),
                    char.get("gender"),
                    char.get("background"),
                    char.get("cultivation_realm"),
                    char.get("faction"),
                    char.get("status", "alive"),
                    char.get("first_appearance_chapter", chapter),
                ))

            # Insert locations
            for loc in knowledge.locations:
                cursor.execute("""
                    INSERT OR REPLACE INTO locations
                    (name, type, parent_location, description, significance,
                     first_appearance_chapter)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    loc.get("name"),
                    loc.get("type"),
                    loc.get("parent_location"),
                    loc.get("description"),
                    loc.get("significance"),
                    loc.get("first_appearance_chapter", chapter),
                ))

            # Insert items (need to resolve owner_id)
            for item in knowledge.items:
                owner_id = self._get_character_id(cursor, item.get("owner_name"))
                cursor.execute("""
                    INSERT OR REPLACE INTO items
                    (name, type, description, properties, owner_id, origin,
                     current_location, chapter_obtained)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    item.get("name"),
                    item.get("type"),
                    item.get("description"),
                    item.get("properties"),
                    owner_id,
                    item.get("origin"),
                    item.get("current_location"),
                    item.get("chapter_obtained", chapter),
                ))

            # Delete existing events for this chapter (avoid duplicates on re-run)
            cursor.execute("DELETE FROM events WHERE chapter = ?", (chapter,))

            # Insert events
            for evt in knowledge.events:
                cursor.execute("""
                    INSERT INTO events
                    (chapter, sequence_in_chapter, title, description, significance)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    evt.get("chapter", chapter),
                    evt.get("sequence_in_chapter"),
                    evt.get("title"),
                    evt.get("description"),
                    evt.get("significance"),
                ))

            # Delete existing plot threads for this chapter
            cursor.execute("DELETE FROM plot_threads WHERE started_chapter = ?", (chapter,))

            # Insert plot threads
            for thread in knowledge.plot_threads:
                cursor.execute("""
                    INSERT OR REPLACE INTO plot_threads
                    (name, description, status, started_chapter)
                    VALUES (?, ?, ?, ?)
                """, (
                    thread.get("name"),
                    thread.get("description"),
                    thread.get("status", "active"),
                    thread.get("started_chapter", chapter),
                ))

            # Delete existing item transfers for this chapter to avoid duplicates on re-run
            cursor.execute("DELETE FROM item_history WHERE chapter = ?", (chapter,))

            # Insert item transfers fresh (not INSERT OR IGNORE, because we deleted first)
            for transfer in knowledge.item_transfers:
                item_id = self._get_item_id(cursor, transfer.get("item_name"))
                from_id = self._get_character_id(cursor, transfer.get("from_character"))
                to_id = self._get_character_id(cursor, transfer.get("to_character"))
                cursor.execute("""
                    INSERT INTO item_history
                    (item_id, from_character_id, to_character_id, chapter, reason, transfer_type)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    item_id,
                    from_id,
                    to_id,
                    transfer.get("chapter", chapter),
                    transfer.get("reason"),
                    transfer.get("transfer_type", "unknown"),
                ))

            # Delete existing character relations for the same character pairs to avoid duplicates on re-run
            # We track which character pairs we're about to insert, then delete those specifically
            if knowledge.character_relations:
                for relation in knowledge.character_relations:
                    char1_id = self._get_character_id(cursor, relation.get("character1"))
                    char2_id = self._get_character_id(cursor, relation.get("character2"))
                    if char1_id and char2_id:
                        cursor.execute("""
                            DELETE FROM character_relations
                            WHERE character1_id = ? AND character2_id = ?
                        """, (char1_id, char2_id))

            # Insert character relations fresh
            for relation in knowledge.character_relations:
                char1_id = self._get_character_id(cursor, relation.get("character1"))
                char2_id = self._get_character_id(cursor, relation.get("character2"))
                if char1_id and char2_id:
                    cursor.execute("""
                        INSERT INTO character_relations
                        (character1_id, character2_id, relation_type, trust_level, tension_level, notes, updated_chapter)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        char1_id,
                        char2_id,
                        relation.get("relation_type"),
                        relation.get("trust_level", 50),
                        relation.get("tension_level", 0),
                        relation.get("notes"),
                        relation.get("updated_chapter", chapter),
                    ))

            # Insert cultivation techniques
            for tech in knowledge.cultivation_techniques:
                cursor.execute("""
                    INSERT OR REPLACE INTO cultivation_techniques
                    (name, realm, stage, effects, side_effects, prerequisites, origin)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    tech.get("name"),
                    tech.get("realm"),
                    tech.get("stage"),
                    tech.get("effects"),
                    tech.get("side_effects"),
                    tech.get("prerequisites"),
                    tech.get("origin"),
                ))

            # Insert character techniques
            for char_tech in knowledge.character_techniques:
                char_id = self._get_character_id(cursor, char_tech.get("character"))
                tech_id = self._get_technique_id(cursor, char_tech.get("technique"))
                if char_id and tech_id:
                    cursor.execute("""
                        INSERT OR REPLACE INTO character_techniques
                        (character_id, technique_id, mastery_level, chapter_learned, notes)
                        VALUES (?, ?, ?, ?, ?)
                    """, (
                        char_id,
                        tech_id,
                        char_tech.get("mastery_level", "beginner"),
                        char_tech.get("chapter_learned", chapter),
                        char_tech.get("notes"),
                    ))

            # Generate and save chapter snapshot
            character_states = {}
            for char in knowledge.characters:
                character_states[char.get("name", "")] = {
                    "realm": char.get("cultivation_realm", "unknown"),
                    "status": char.get("status", "alive"),
                    "faction": char.get("faction", ""),
                }

            active_threads = [t.get("name", "") for t in knowledge.plot_threads]
            key_events_list = [e.get("title", "") for e in knowledge.events]

            cursor.execute("""
                INSERT OR REPLACE INTO chapter_snapshots
                (chapter, character_states, world_states, plot_threads_active, key_decisions)
                VALUES (?, ?, ?, ?, ?)
            """, (
                chapter,
                json.dumps(character_states),
                json.dumps(key_events_list),
                json.dumps(active_threads),
                json.dumps([]),
            ))

            conn.commit()

        finally:
            conn.close()

    def _get_character_id(self, cursor, name: Optional[str]) -> Optional[int]:
        """Get character ID by name."""
        if not name:
            return None
        cursor.execute("SELECT id FROM characters WHERE name LIKE ?", (f"%{name}%",))
        result = cursor.fetchone()
        return result[0] if result else None

    def _get_item_id(self, cursor, name: Optional[str]) -> Optional[int]:
        """Get item ID by name."""
        if not name:
            return None
        cursor.execute("SELECT id FROM items WHERE name LIKE ?", (f"%{name}%",))
        result = cursor.fetchone()
        return result[0] if result else None

    def _get_technique_id(self, cursor, name: Optional[str]) -> Optional[int]:
        """Get technique ID by name."""
        if not name:
            return None
        cursor.execute("SELECT id FROM cultivation_techniques WHERE name LIKE ?", (f"%{name}%",))
        result = cursor.fetchone()
        return result[0] if result else None


class KnowledgeQuerier:
    """Query interface for story knowledge."""

    def __init__(self, db_path: str):
        self.db_path = db_path

    def get_connection(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def get_character(self, name: str) -> Optional[Dict[str, Any]]:
        """Get complete character information."""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM characters WHERE name LIKE ?", (f"%{name}%",))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return None

        columns = [desc[0] for desc in cursor.description]
        char = dict(zip(columns, row))

        # Get character's items
        cursor.execute("""
            SELECT i.* FROM items i
            JOIN character_items ci ON i.id = ci.item_id
            WHERE ci.character_id = ? AND ci.is_current_owner = 1
        """, (char["id"],))
        items = [dict(zip([d[0] for d in cursor.description], r)) for r in cursor.fetchall()]
        char["items"] = items

        # Get character's locations
        cursor.execute("""
            SELECT l.* FROM locations l
            JOIN character_locations cl ON l.id = cl.location_id
            WHERE cl.character_id = ?
        """, (char["id"],))
        locs = [dict(zip([d[0] for d in cursor.description], r)) for r in cursor.fetchall()]
        char["locations"] = locs

        conn.close()
        return char

    def get_character_events(self, name: str) -> List[Dict[str, Any]]:
        """Get all events a character participated in."""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT e.*, ce.role, ce.outcome FROM events e
            JOIN character_events ce ON e.id = ce.event_id
            JOIN characters c ON ce.character_id = c.id
            WHERE c.name LIKE ?
            ORDER BY e.chapter, e.sequence_in_chapter
        """, (f"%{name}%",))

        events = [dict(zip([d[0] for d in cursor.description], r)) for r in cursor.fetchall()]
        conn.close()
        return events

    def get_item_info(self, item_name: str) -> Optional[Dict[str, Any]]:
        """Get item information including current owner."""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT i.*, c.name as owner_name FROM items i
            LEFT JOIN characters c ON i.owner_id = c.id
            WHERE i.name LIKE ?
        """, (f"%{item_name}%",))

        row = cursor.fetchone()
        if not row:
            conn.close()
            return None

        item = dict(zip([d[0] for d in cursor.description], row))
        conn.close()
        return item

    def get_location_info(self, location_name: str) -> Optional[Dict[str, Any]]:
        """Get location information."""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM locations WHERE name LIKE ?", (f"%{location_name}%",))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return None

        loc = dict(zip([d[0] for d in cursor.description], row))
        conn.close()
        return loc

    def get_chapter_events(self, chapter: int) -> List[Dict[str, Any]]:
        """Get all events in a chapter."""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM events
            WHERE chapter = ?
            ORDER BY sequence_in_chapter
        """, (chapter,))

        events = [dict(zip([d[0] for d in cursor.description], r)) for r in cursor.fetchall()]
        conn.close()
        return events

    def get_active_plot_threads(self) -> List[Dict[str, Any]]:
        """Get all active plot threads."""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM plot_threads WHERE status = 'active'")
        threads = [dict(zip([d[0] for d in cursor.description], r)) for r in cursor.fetchall()]
        conn.close()
        return threads

    def get_timeline(self, chapter: int = None) -> List[Dict[str, Any]]:
        """Get story timeline."""
        conn = self.get_connection()
        cursor = conn.cursor()

        if chapter:
            cursor.execute("SELECT * FROM timeline WHERE chapter = ? ORDER BY sequence", (chapter,))
        else:
            cursor.execute("SELECT * FROM timeline ORDER BY chapter, sequence")

        timeline = [dict(zip([d[0] for d in cursor.description], r)) for r in cursor.fetchall()]
        conn.close()
        return timeline

    def build_character_summary(self, name: str) -> str:
        """Build a comprehensive summary string for a character."""
        char = self.get_character(name)
        if not char:
            return f"未找到角色: {name}"

        lines = [
            f"【{char['name']}】",
            f"别名: {char.get('alias', '无')}",
            f"性别: {char.get('gender', 'unknown')}",
            f"修为: {char.get('cultivation_realm', 'unknown')}",
            f"阵营: {char.get('faction', '无')}",
            f"状态: {char.get('status', 'alive')}",
            f"背景: {char.get('background', '无')}",
        ]

        if char.get("items"):
            items_str = ", ".join([i["name"] for i in char["items"]])
            lines.append(f"持有物品: {items_str}")

        if char.get("locations"):
            locs_str = ", ".join([l["name"] for l in char["locations"]])
            lines.append(f"相关地点: {locs_str}")

        return "\n".join(lines)

    def get_character_relations(self, character_name: str) -> List[Dict[str, Any]]:
        """Get all relations for a character."""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT cr.*,
                   c1.name as char1_name,
                   c2.name as char2_name
            FROM character_relations cr
            JOIN characters c1 ON cr.character1_id = c1.id
            JOIN characters c2 ON cr.character2_id = c2.id
            WHERE c1.name LIKE ? OR c2.name LIKE ?
            ORDER BY cr.tension_level DESC
        """, (f"%{character_name}%", f"%{character_name}%"))

        relations = [dict(zip([d[0] for d in cursor.description], r)) for r in cursor.fetchall()]
        conn.close()
        return relations

    def get_item_history(self, item_name: str) -> List[Dict[str, Any]]:
        """Get transfer history for an item."""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT ih.*,
                   i.name as item_name,
                   fc.name as from_character,
                   tc.name as to_character
            FROM item_history ih
            JOIN items i ON ih.item_id = i.id
            LEFT JOIN characters fc ON ih.from_character_id = fc.id
            LEFT JOIN characters tc ON ih.to_character_id = tc.id
            WHERE i.name LIKE ?
            ORDER BY ih.chapter
        """, (f"%{item_name}%",))

        history = [dict(zip([d[0] for d in cursor.description], r)) for r in cursor.fetchall()]
        conn.close()
        return history

    def get_chapter_snapshot(self, chapter: int) -> Optional[Dict[str, Any]]:
        """Get state snapshot for a chapter."""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM chapter_snapshots WHERE chapter = ?", (chapter,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return None

        snapshot = dict(zip([d[0] for d in cursor.description], row))
        # Parse JSON fields
        if snapshot.get("character_states"):
            snapshot["character_states"] = json.loads(snapshot["character_states"])
        if snapshot.get("world_states"):
            snapshot["world_states"] = json.loads(snapshot["world_states"])
        if snapshot.get("plot_threads_active"):
            snapshot["plot_threads_active"] = json.loads(snapshot["plot_threads_active"])
        if snapshot.get("key_decisions"):
            snapshot["key_decisions"] = json.loads(snapshot["key_decisions"])

        conn.close()
        return snapshot

    def get_character_techniques(self, character_name: str) -> List[Dict[str, Any]]:
        """Get all techniques a character has learned."""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT ct.*,
                   c.name as character_name,
                   ct2.name as technique_name,
                   ct2.realm,
                   ct2.effects
            FROM character_techniques ct
            JOIN characters c ON ct.character_id = c.id
            JOIN cultivation_techniques ct2 ON ct.technique_id = ct2.id
            WHERE c.name LIKE ?
            ORDER BY ct.chapter_learned
        """, (f"%{character_name}%",))

        techniques = [dict(zip([d[0] for d in cursor.description], r)) for r in cursor.fetchall()]
        conn.close()
        return techniques

    def query_knowledge(self, query: str) -> str:
        """Query knowledge and return formatted string for kimi-cli."""
        results = []

        # Try to find characters
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT name FROM characters WHERE name LIKE ?", (f"%{query}%",))
        chars = [r[0] for r in cursor.fetchall()]

        cursor.execute("SELECT name FROM items WHERE name LIKE ?", (f"%{query}%",))
        items = [r[0] for r in cursor.fetchall()]

        cursor.execute("SELECT name FROM locations WHERE name LIKE ?", (f"%{query}%",))
        locs = [r[0] for r in cursor.fetchall()]

        conn.close()

        if chars:
            results.append(f"【角色】: {', '.join(chars)}")
            for name in chars:
                results.append(self.build_character_summary(name))

        if items:
            results.append(f"\n【物品】: {', '.join(items)}")
            for name in items:
                item = self.get_item_info(name)
                if item:
                    results.append(f"  - {item['name']}: {item['description']}")

        if locs:
            results.append(f"\n【地点】: {', '.join(locs)}")
            for name in locs:
                loc = self.get_location_info(name)
                if loc:
                    results.append(f"  - {loc['name']}: {loc['description']}")

        if not results:
            return f"未找到与'{query}'相关的信息"

        return "\n".join(results)


def extract_all_chapters(
    chapters_dir: str,
    db_path: str,
    start_chapter: int = 1,
    end_chapter: int = 999
):
    """Extract knowledge from all chapters and populate database."""
    extractor = KnowledgeExtractor(db_path)

    # Clear tables that can accumulate duplicates on re-run
    # These tables use INSERT OR REPLACE/IGNORE but character IDs may change between runs
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM character_relations")
    cursor.execute("DELETE FROM item_history")
    cursor.execute("DELETE FROM character_techniques")
    conn.commit()
    conn.close()

    chapters_path = Path(chapters_dir)

    for i in range(start_chapter, end_chapter + 1):
        # Find chapter file
        matches = list(chapters_path.glob(f"ch{i:03d}_*.md"))
        if not matches:
            continue

        chapter_file = matches[0]
        content = chapter_file.read_text(encoding="utf-8")

        # Extract title from content
        title = ""
        for line in content.split("\n"):
            if line.startswith("#"):
                title = line.lstrip("#").strip()
                break

        # Extract and save
        knowledge = extractor.extract_from_chapter(i, content, title)
        extractor.save_to_database(knowledge, i)
        print(f"Extracted knowledge from Chapter {i}: {len(knowledge.characters)} chars, {len(knowledge.items)} items")


def query_novel_knowledge(query: str, db_path: str) -> str:
    """Convenience function to query novel knowledge."""
    querier = KnowledgeQuerier(db_path)
    return querier.query_knowledge(query)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python knowledge_extractor.py <chapter_dir> [db_path]")
        sys.exit(1)

    chapters_dir = sys.argv[1]
    db_path = sys.argv[2] if len(sys.argv) > 2 else "lib/knowledge_base/novels/太古魔帝传/story_knowledge.db"

    extract_all_chapters(chapters_dir, db_path)
    print("Knowledge extraction complete!")
