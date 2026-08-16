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

# URL chứa dữ liệu mở của toàn bộ phương tiện War Thunder
WT_DATA_URL = "https://raw.githubusercontent.com/gszep/war-thunder-data/master/data/json/vehicles.json"
VEHICLES_DB = {}
SESSION = None

async def load_wt_database():
    global VEHICLES_DB, SESSION
    try:
        print("🔄 Đang tải dữ liệu toàn bộ xe War Thunder từ GitHub...")
        if SESSION is None or SESSION.closed:
            SESSION = aiohttp.ClientSession()
        async with SESSION.get(WT_DATA_URL, timeout=15) as res:
            if res.status == 200:
                VEHICLES_DB = await res.json()
                print(f"✅ Đã tải thành công dữ liệu War Thunder ({len(VEHICLES_DB)} phương tiện)!")
            else:
                print("⚠️ Không thể lấy dữ liệu online, chuyển sang chế độ dự phòng.")
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
    print(f"🌐 Health check server đang chạy trên cổng {port}")

@bot.event
async def on_ready():
    # Đổi trạng thái hoạt động giúp bot sáng đèn Online rõ ràng
    await bot.change_presence(
        status=discord.Status.online,
        activity=discord.Game(name="War Thunder | !wt <xe1> vs <xe2>")
    )
    print(f"🤖 Bot {bot.user} đã ONLINE và ready phân tích chiến thuật War Thunder!")

def _parse_vehicle_data(v_info: dict, query_name: str) -> dict:
    """Hàm phụ trợ bóc tách thông số xe an toàn"""
    horse_power = v_info.get("horsePower", 500)
    mass = v_info.get("mass", 30000)
    hp_ton = 16.5
    if isinstance(horse_power, (int, float)) and isinstance(mass, (int, float)) and mass > 0:
        hp_ton = round(horse_power / (mass / 1000), 1)

    return {
        "name": str(v_info.get("name") or query_name).strip().upper(),
        "br": v_info.get("economicRankArcade", 7.0),
        "hp_ton": hp_ton,
        "reload": v_info.get("reloadTime", 7.5),
        "has_stab": v_info.get("hasStabilizer", False),
        "has_aphe": v_info.get("hasAPHE", True)
    }


def _matches_word_boundary(query: str, text: str) -> bool:
    pattern = rf"(?<!\w){re.escape(query)}(?!\w)"
    return re.search(pattern, text, re.IGNORECASE) is not None


def find_vehicle(query_name: str):
    """Tìm kiếm xe thông minh trong Database 2000+ xe"""
    query_clean = query_name.strip().lower()

    if VEHICLES_DB:
        # Lượt 1: Tìm CHÍNH XÁC tên xe hoặc v_id
        for v_id, v_info in VEHICLES_DB.items():
            name = str(v_info.get("name", "")).lower()
            v_id_lower = str(v_id).lower()
            if query_clean == name or query_clean == v_id_lower:
                return _parse_vehicle_data(v_info, query_name)

        # Lượt 2: Tìm theo whole-word trước, rồi mới substring thô
        for v_id, v_info in VEHICLES_DB.items():
            name = str(v_info.get("name", "")).lower()
            v_id_lower = str(v_id).lower()
            if _matches_word_boundary(query_clean, name) or _matches_word_boundary(query_clean, v_id_lower):
                return _parse_vehicle_data(v_info, query_name)

        for v_id, v_info in VEHICLES_DB.items():
            name = str(v_info.get("name", "")).lower()
            v_id_lower = str(v_id).lower()
            if query_clean in name or query_clean in v_id_lower:
                return _parse_vehicle_data(v_info, query_name)

    return {
        "name": query_name.strip().upper(),
        "br": "N/A",
        "hp_ton": 16.5,
        "reload": 7.5,
        "has_stab": False,
        "has_aphe": True
    }

def analyze_combat(t1: dict, t2: dict) -> str:
    """Thuật toán ma trận phân tích lý do xe A thua xe B"""
    reasons = []

    # Phân tích Sát thương đạn
    if t2.get('has_aphe'):
        reasons.append(
            f"• **Sát thương đạn APHE nổ vụn:** Nếu {t2['name']} bắn đục lủng giáp {t1['name']}, "
            f"mảnh văng đạn nổ APHE sẽ quét sạch kíp lái trong buồng lái ngay lập tức."
        )

    # Phân tích Tốc độ nạp đạn
    r1 = t1.get('reload', 7.5)
    r2 = t2.get('reload', 7.5)
    if isinstance(r1, (int, float)) and isinstance(r2, (int, float)):
        if r1 > r2:
            reasons.append(
                f"• **Lợi thế tốc độ nạp đạn:** {t2['name']} nạp đạn nhanh hơn. "
                f"Trong giao tranh cận chiến (CQB), nếu {t1['name']} bắn hụt hoặc chỉ đục hỏng xích/pháo, {t2['name']} sẽ có cơ hội phản công ngay."
            )

    # Phân tích Bộ cân bằng pháo (Stabilizer)
    if not t1.get('has_stab') and t2.get('has_stab'):
        reasons.append(
            f"• **Khả năng kê tâm (Stabilizer):** {t2['name']} có Stabilizer giúp di chuyển vẫn dừng bắn được ngay. "
            f"{t1['name']} không có Stab nên khi dừng xe pháo sẽ bị nảy mạnh, mất 1-2s mới ổn định tâm."
        )

    # Phân tích Cơ động / Móc lốp
    hp1 = t1.get('hp_ton', 15)
    hp2 = t2.get('hp_ton', 15)
    if isinstance(hp1, (int, float)) and isinstance(hp2, (int, float)):
        if hp1 < hp2:
            reasons.append(
                f"• **Thế trận Móc Lốp (Flank):** {t2['name']} cơ động hơn ({hp2} HP/tấn). "
                f"Nếu biết tận dụng bản đồ đi vòng ra sườn hoặc sau lưng, giáp mặt của {t1['name']} trâu đến đâu cũng bị vô hiệu hóa."
            )

    if not reasons:
        reasons.append(
            f"• **Yếu tố Tay Nghề & Góc Kê (Angling):** Kết quả phụ thuộc vào việc ai nhìn thấy đối phương trước, "
            f"kỹ năng giấu gầm (Hull-down) và cách nghiêng giáp góc 45 độ của người chơi."
        )

    return "\n".join(reasons)

@bot.command(name="wt")
async def compare_vehicles(ctx, *, query: str):
    """Cú pháp: !wt <xe 1> vs <xe 2>"""
    query_text = query.strip()
    if not re.search(r"\s+vs\s+", query_text, flags=re.IGNORECASE):
        await ctx.send("⚠️ Vui lòng gõ đúng cú pháp: `!wt <Tên Xe 1> vs <Tên Xe 2>`\nVí dụ: `!wt leopard 1 vs m48a1`")
        return

    parts = re.split(r"\s+vs\s+", query_text, maxsplit=1, flags=re.IGNORECASE)
    if len(parts) < 2 or not parts[0].strip() or not parts[1].strip():
        await ctx.send("⚠️ Vui lòng nhập đủ tên 2 xe! Ví dụ: `!wt leopard 1 vs m48a1`")
        return

    t1 = find_vehicle(parts[0].strip())
    t2 = find_vehicle(parts[1].strip())

    embed = discord.Embed(
        title=f"⚔️ PHÂN TÍCH TÁC CHIẾN: {t1['name']} VS {t2['name']}",
        color=discord.Color.gold()
    )

    embed.add_field(
        name=f"📊 {t1['name']}",
        value=f"• BR: `{t1['br']}`\n• Tỷ lệ HP/tấn: `{t1['hp_ton']} HP/t` \n• Nạp đạn: `{t1['reload']}s`",
        inline=True
    )

    embed.add_field(
        name=f"📊 {t2['name']}",
        value=f"• BR: `{t2['br']}`\n• Tỷ lệ HP/tấn: `{t2['hp_ton']} HP/t` \n• Nạp đạn: `{t2['reload']}s`",
        inline=True
    )

    analysis = analyze_combat(t1, t2)
    embed.add_field(
        name=f"💡 Tại sao {t1['name']} vẫn có thể THUA {t2['name']}?",
        value=analysis,
        inline=False
    )

    embed.set_footer(text="War Thunder Tactical Engine • Powered by Discord Bot")
    await ctx.send(embed=embed)

# Lấy Token an toàn từ biến môi trường của Host
TOKEN = os.getenv("DISCORD_TOKEN")
if TOKEN:
    bot.run(TOKEN)
else:
    print("❌ LỖI: Chưa cấu hình DISCORD_TOKEN trong phần Environment Variables của Host!")