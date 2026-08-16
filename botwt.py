import os
import requests
import discord
from discord.ext import commands

# Kích hoạt Intents đọc tin nhắn
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# URL chứa dữ liệu mở của toàn bộ phương tiện War Thunder
WT_DATA_URL = "https://raw.githubusercontent.com/gszep/war-thunder-data/master/data/json/vehicles.json"
VEHICLES_DB = {}

def load_wt_database():
    global VEHICLES_DB
    try:
        print("🔄 Đang tải dữ liệu toàn bộ xe War Thunder từ GitHub...")
        res = requests.get(WT_DATA_URL, timeout=10)
        if res.status_code == 200:
            VEHICLES_DB = res.json()
            print(f"✅ Đã tải thành công dữ liệu War Thunder!")
        else:
            print("⚠️ Không thể lấy dữ liệu online, chuyển sang chế độ dữ liệu động.")
    except Exception as e:
        print(f"❌ Lỗi khi tải dữ liệu: {e}")

@bot.event
async def on_ready():
    load_wt_database()
    print(f"🤖 Bot {bot.user} đã sẵn sàng phân tích chiến thuật War Thunder!")

def find_vehicle(query_name: str):
    """Tìm kiếm xe thông minh trong Database 2000+ xe"""
    query_clean = query_name.strip().lower()
    
    # 1. Tìm chính xác hoặc tương đối trong Database
    if VEHICLES_DB:
        for v_id, v_info in VEHICLES_DB.items():
            name = v_info.get("name", "").lower()
            if query_clean in name or query_clean in v_id.lower():
                return {
                    "name": v_info.get("name", query_name.upper()),
                    "br": v_info.get("economicRankArcade", 7.0),
                    "hp_ton": round(v_info.get("horsePower", 500) / (v_info.get("mass", 30000) / 1000), 1),
                    "reload": v_info.get("reloadTime", 7.5),
                    "has_stab": v_info.get("hasStabilizer", False),
                    "has_aphe": v_info.get("hasAPHE", True)
                }

    # 2. Dự phòng nếu tên xe quá mới hoặc không có trong JSON
    return {
        "name": query_name.upper(),
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
    if "vs" not in query.lower():
        await ctx.send("⚠️ Vui lòng gõ đúng cú pháp: `!wt <Tên Xe 1> vs <Tên Xe 2>`\nVí dụ: `!wt leopard 1 vs m48a1`")
        return

    parts = query.lower().split("vs")
    t1 = find_vehicle(parts[0])
    t2 = find_vehicle(parts[1])

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