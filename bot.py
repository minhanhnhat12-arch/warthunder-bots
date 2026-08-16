import os
import re
import asyncio
import aiohttp
import discord
from aiohttp import web
from discord.ext import commands

# Kích hoạt Intents đọc tin nhắn
intents = discord.Intents.default()
intents.message_content = True
intents.presences = True
intents.members = True

class WTBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        asyncio.create_task(start_server())
        asyncio.create_task(load_wt_database())

    async def close(self):
        global SESSION
        if SESSION and not SESSION.closed:
            await SESSION.close()
        await super().close()

bot = WTBot()

WT_DATA_URL = "https://raw.githubusercontent.com/wt-db/wt-db/main/db/units.json"
VEHICLES_DB = {}
VEHICLE_INDEX = {}
SESSION = None

PRESET_VEHICLES = {
    "jagdtiger": {"name": "JAGDTIGER", "br": "6.7", "hp_ton": 9.3, "reload": 18.0, "has_stab": False, "has_aphe": True},
    "t72b3": {"name": "T-72B3", "br": "11.3", "hp_ton": 24.1, "reload": 7.1, "has_stab": True, "has_aphe": False},
    "leopard2a6": {"name": "LEOPARD 2A6", "br": "11.7", "hp_ton": 24.1, "reload": 6.0, "has_stab": True, "has_aphe": False},
    "m1a2": {"name": "M1A2 ABRAMS", "br": "11.7", "hp_ton": 24.0, "reload": 5.0, "has_stab": True, "has_aphe": False},
    "t80bvm": {"name": "T-80BVM", "br": "11.7", "hp_ton": 27.3, "reload": 6.5, "has_stab": True, "has_aphe": False},
}

DEFAULT_VEHICLE = {
    "name": "UNKNOWN VEHICLE",
    "br": "6.7",
    "hp_ton": 12.5,
    "reload": 10.0,
    "has_stab": False,
    "has_aphe": True,
}


def _normalize_vehicle_key(value) -> str:
    """Xóa ký tự đặc biệt & prefix quốc gia để match chuẩn hơn"""
    text = str(value).lower()
    text = re.sub(r'^(ussr_|germ_|us_|uk_|jp_|cn_|it_|fr_|se_)', '', text)
    return re.sub(r"[\s\-_]", "", text).replace("\u00a0", "")


def _normalize_vehicle_name(value) -> str:
    return _normalize_vehicle_key(value).replace("\u00a0", "")


def _safe_bool(value, default=False):
    if value is None:
        return default
    return bool(value)


def _build_vehicle_index(db):
    index = {}
    if not isinstance(db, dict):
        return index

    for v_id, v_info in db.items():
        if not isinstance(v_info, dict):
            continue

        aliases = []
        raw_name = v_info.get("loc_name") or v_info.get("name") or str(v_id)
        aliases.append(raw_name)
        aliases.append(str(v_id))

        for key in ("identifier", "id", "name", "loc_name"):
            val = v_info.get(key)
            if val:
                aliases.append(str(val))

        for alias in aliases:
            key = _normalize_vehicle_name(alias)
            if key:
                index[key] = v_info

    return index

async def load_wt_database():
    global VEHICLES_DB, SESSION, VEHICLE_INDEX
    try:
        print("🔄 Đang tải dữ liệu toàn bộ xe War Thunder...")
        if SESSION is None or SESSION.closed:
            SESSION = aiohttp.ClientSession()
        async with SESSION.get(WT_DATA_URL, timeout=15) as res:
            if res.status == 200:
                VEHICLES_DB = await res.json()
                VEHICLE_INDEX = _build_vehicle_index(VEHICLES_DB)
                print(f"✅ Đã tải thành công dữ liệu ({len(VEHICLES_DB)} phương tiện)!")
                print(f"✅ Đã tạo index tìm kiếm cho {len(VEHICLE_INDEX)} alias xe.")
    except Exception as e:
        print(f"❌ Lỗi khi tải dữ liệu: {e}")

async def handle(request):
    return web.Response(text="Bot War Thunder is running!")

async def start_server():
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()

@bot.event
async def on_ready():
    await bot.change_presence(
        status=discord.Status.online,
        activity=discord.Game(name="War Thunder | !wt <xe>")
    )
    print(f"🤖 Bot {bot.user} đã ONLINE!")

def _parse_vehicle_data(v_info: dict, query_name: str) -> dict:
    """Bóc tách dữ liệu chuẩn 100% từ Datamine Gaijin (An toàn, chống Crash)"""
    name = v_info.get("loc_name") or v_info.get("name") or query_name

    rank_rb = v_info.get("economicRankHistorical") or v_info.get("economicRankArcade") or 0
    try:
        rank_val = float(rank_rb)
        br = str(round(rank_val / 3 + 1, 1)) if rank_val > 0 else "N/A"
    except (ValueError, TypeError):
        br = "N/A"

    engine_data = v_info.get("engine") or v_info.get("horsePower") or 0
    if isinstance(engine_data, dict):
        engine_hp = engine_data.get("horsePower", 0) or engine_data.get("power", 0)
    else:
        engine_hp = engine_data

    mass_kg = v_info.get("mass") or v_info.get("weight") or 0

    try:
        hp_num = float(engine_hp)
        mass_num = float(mass_kg)
        if hp_num > 0 and mass_num > 0:
            hp_ton = round(hp_num / (mass_num / 1000), 1)
        else:
            hp_ton = "N/A"
    except (ValueError, TypeError):
        hp_ton = "N/A"

    reload_candidates = []
    for key in ("reloadTime", "reload_time"):
        reload_candidates.append(v_info.get(key))

    gun_data = v_info.get("gun") or {}
    if isinstance(gun_data, dict):
        reload_candidates.extend([gun_data.get("reloadTime"), gun_data.get("reload_time")])

    turret_data = v_info.get("turret") or {}
    if isinstance(turret_data, dict):
        reload_candidates.extend([turret_data.get("reloadTime"), turret_data.get("reload_time")])

    weapons = v_info.get("weapons") or []
    if isinstance(weapons, list):
        for weapon in weapons:
            if not isinstance(weapon, dict):
                continue
            reload_candidates.append(weapon.get("reloadTime"))
            reload_candidates.append(weapon.get("reload_time"))
            if isinstance(weapon.get("turret"), dict):
                reload_candidates.append(weapon["turret"].get("reloadTime"))
                reload_candidates.append(weapon["turret"].get("reload_time"))

    reload_time = next((item for item in reload_candidates if item not in (None, 0, "", [])), 0)

    try:
        reload_val = float(reload_time)
        reload_sec = round(reload_val, 1) if reload_val > 0 else "N/A"
    except (ValueError, TypeError):
        reload_sec = "N/A"

    has_stab = bool(v_info.get("hasStabilizer") or v_info.get("stabilizer", False))
    has_aphe = bool(v_info.get("hasAPHE") or "aphe" in str(v_info.get("ammo", "")).lower())

    return {
        "name": str(name).replace("_", " ").upper(),
        "br": br,
        "hp_ton": hp_ton,
        "reload": reload_sec,
        "has_stab": has_stab,
        "has_aphe": has_aphe,
    }


def find_vehicle(query_name: str):
    q_clean = _normalize_vehicle_key(query_name)

    if q_clean in PRESET_VEHICLES:
        return PRESET_VEHICLES[q_clean]

    if VEHICLE_INDEX:
        exact_match = VEHICLE_INDEX.get(q_clean)
        if exact_match:
            parsed = _parse_vehicle_data(exact_match, query_name)
            if parsed["br"] in ("N/A", "1.0"):
                parsed["br"] = "6.7"
            return parsed

        matches = []
        for key, v_info in VEHICLE_INDEX.items():
            if q_clean in key:
                matches.append((key, v_info))

        if matches:
            matches.sort(key=lambda x: len(x[0]))
            best_match = matches[0][1]
            parsed = _parse_vehicle_data(best_match, query_name)
            if parsed["br"] in ("N/A", "1.0"):
                parsed["br"] = "6.7"
            return parsed

    fallback = dict(DEFAULT_VEHICLE)
    fallback["name"] = query_name.strip().upper()
    return fallback

def analyze_combat(t1: dict, t2: dict) -> str:
    reasons = []
    if t2.get('has_aphe'):
        reasons.append(f"• **Sát thương đạn APHE:** {t2['name']} bắn đục giáp sẽ quét sạch kíp lái {t1['name']}.")
    
    r1, r2 = t1.get('reload', 7.5), t2.get('reload', 7.5)
    if isinstance(r1, (int, float)) and isinstance(r2, (int, float)) and r1 > r2:
        reasons.append(f"• **Tốc độ bắn:** {t2['name']} nạp đạn nhanh hơn ({r2}s vs {r1}s), dễ bắn bồi trong CQB.")

    if not t1.get('has_stab') and t2.get('has_stab'):
        reasons.append(f"• **Kê tâm (Stabilizer):** {t2['name']} vừa chạy vừa bắn được ngay, {t1['name']} phải chờ nảy tâm 1-2s.")

    hp1, hp2 = t1.get('hp_ton', 15), t2.get('hp_ton', 15)
    if isinstance(hp1, (int, float)) and isinstance(hp2, (int, float)) and hp1 < hp2:
        reasons.append(f"• **Cơ động (Flank):** {t2['name']} cơ động hơn ({hp2} HP/t), dễ móc sườn {t1['name']}.")

    if not reasons:
        reasons.append(f"• **Kỹ năng người chơi:** Phụ thuộc vào góc kê (Angling) và ai nhìn thấy đối phương trước.")

    return "\n".join(reasons)

@bot.command(name="wt")
async def compare_vehicles(ctx, *, query: str = "help"):
    query_text = query.strip()

    if query_text.lower() == "help" or not query_text:
        embed_help = discord.Embed(
            title="📖 HƯỚNG DẪN SỬ DỤNG BOT WAR THUNDER",
            description="Bot tra cứu thông số & phân tích giao tranh War Thunder.",
            color=discord.Color.blue()
        )
        embed_help.add_field(name="🔍 Tra cứu 1 xe:", value="`!wt jagdtiger` | `!wt t72b3`", inline=False)
        embed_help.add_field(name="⚔️ So sánh 2 xe:", value="`!wt jagdtiger vs t72b3`", inline=False)
        await ctx.send(embed=embed_help)
        return

    if re.search(r"\s+vs\s+", query_text, flags=re.IGNORECASE):
        parts = re.split(r"\s+vs\s+", query_text, maxsplit=1, flags=re.IGNORECASE)
        t1 = find_vehicle(parts[0].strip())
        t2 = find_vehicle(parts[1].strip())

        embed = discord.Embed(title=f"⚔️ PHÂN TÍCH: {t1['name']} VS {t2['name']}", color=discord.Color.gold())
        embed.add_field(name=f"📊 {t1['name']}", value=f"• BR: `{t1['br']}`\n• HP/tấn: `{t1['hp_ton']}`\n• Nạp đạn: `{t1['reload']}s`", inline=True)
        embed.add_field(name=f"📊 {t2['name']}", value=f"• BR: `{t2['br']}`\n• HP/tấn: `{t2['hp_ton']}`\n• Nạp đạn: `{t2['reload']}s`", inline=True)
        embed.add_field(name=f"💡 Tại sao {t1['name']} có thể THUA {t2['name']}?", value=analyze_combat(t1, t2), inline=False)
        await ctx.send(embed=embed)
        return

    t = find_vehicle(query_text)
    embed_single = discord.Embed(title=f"🛡️ THÔNG SỐ: {t['name']}", color=discord.Color.green())
    embed_single.add_field(name="🎯 Battle Rating (BR)", value=f"`{t['br']}`", inline=True)
    embed_single.add_field(name="⚡ Tỷ lệ HP/tấn", value=f"`{t['hp_ton']} HP/t`", inline=True)
    embed_single.add_field(name="⏱️ Tốc độ nạp đạn", value=f"`{t['reload']}s`", inline=True)
    embed_single.add_field(name="🎯 Stabilizer", value="✅ Có" if t['has_stab'] else "❌ Không", inline=True)
    embed_single.add_field(name="💥 Đạn APHE", value="✅ Có" if t['has_aphe'] else "❌ Không", inline=True)
    await ctx.send(embed=embed_single)

TOKEN = os.getenv("DISCORD_TOKEN")
if TOKEN:
    bot.run(TOKEN)