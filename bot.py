import os
import re
import asyncio
import difflib
from decimal import Decimal, ROUND_HALF_UP
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
        self.session: aiohttp.ClientSession | None = None
        self.db_ready = False
        self.db_loading = False
        self.vehicles_db = {}
        self.vehicle_index = {}
        self._db_lock = asyncio.Lock()
        self.web_runner: web.AppRunner | None = None

    async def ensure_session(self) -> aiohttp.ClientSession:
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session

    async def start_web_server(self):
        app = web.Application()
        app.router.add_get('/', lambda r: web.Response(text="Bot War Thunder is running!"))
        self.web_runner = web.AppRunner(app)
        await self.web_runner.setup()
        port = int(os.environ.get("PORT", 8080))
        site = web.TCPSite(self.web_runner, '0.0.0.0', port)
        await site.start()
        print(f"🌐 Web server keep-alive đã khởi chạy tại port {port}")

    async def load_wt_database(self):
        async with self._db_lock:
            if self.db_loading:
                return

            self.db_loading = True
            self.db_ready = False
            try:
                print("🔄 Đang tải dữ liệu toàn bộ xe War Thunder...")
                session = await self.ensure_session()
                timeout = aiohttp.ClientTimeout(total=25)

                async with session.get(WT_DATA_URL, timeout=timeout) as res:
                    if res.status == 200:
                        payload = await res.json()
                        if isinstance(payload, list):
                            self.vehicles_db = {
                                str(item.get("id") or item.get("identifier") or item.get("loc_name") or item.get("name") or idx): item
                                for idx, item in enumerate(payload)
                                if isinstance(item, dict)
                            }
                        elif isinstance(payload, dict):
                            self.vehicles_db = payload
                        else:
                            self.vehicles_db = {}

                        self.vehicle_index = _build_vehicle_index(self.vehicles_db)
                        self.db_ready = bool(self.vehicle_index)
                        print(f"✅ Đã tải thành công dữ liệu ({len(self.vehicles_db)} phương tiện)!")
                        print(f"✅ Đã tạo index tìm kiếm cho {len(self.vehicle_index)} alias xe.")
                    else:
                        print(f"⚠️ Không thể tải dữ liệu. HTTP Code: {res.status}")
            except asyncio.TimeoutError:
                print("❌ Lỗi: Kết nối tới wt-db bị timeout!")
                self.db_ready = False
            except Exception as e:
                print(f"❌ Lỗi khi tải dữ liệu: {e}")
                self.db_ready = False
            finally:
                self.db_loading = False

    async def setup_hook(self):
        await self.ensure_session()
        asyncio.create_task(self.start_web_server())
        await self.load_wt_database()

    async def close(self):
        if self.web_runner is not None:
            await self.web_runner.cleanup()
            self.web_runner = None

        if self.session is not None and not self.session.closed:
            await self.session.close()
            await asyncio.sleep(0.25)
        self.session = None
        self.db_ready = False
        self.db_loading = False
        await super().close()


bot = WTBot()

WT_DATA_URL = "https://raw.githubusercontent.com/wt-db/wt-db/main/db/units.json"


def _format_br(rank_value):
    try:
        rank_num = int(rank_value)
    except (TypeError, ValueError):
        return "N/A"

    if rank_num < 0:
        return "N/A"

    whole = rank_num // 3
    remainder = rank_num % 3
    br_value = Decimal(whole) + (Decimal(remainder) / Decimal(3))
    br_value += Decimal("1")
    return format(br_value.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP), "f")

DEFAULT_VEHICLE = {
    "name": "UNKNOWN VEHICLE",
    "br": "6.7",
    "hp_ton": 12.5,
    "reload": 10.0,
    "has_stab": False,
    "has_aphe": True,
}


def _coerce_number(value):
    if value is None:
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    if isinstance(value, str):
        cleaned = value.strip()
        if not cleaned or cleaned.lower() in {"n/a", "na", "unknown"}:
            return None
        try:
            return float(cleaned)
        except ValueError:
            return None
    return None


def _normalize_vehicle_key(value) -> str:
    """Loại bỏ prefix quốc gia, đuôi năm sản xuất, khoảng trắng và ký tự đặc biệt"""
    if not value:
        return ""
    text = str(value).lower()
    text = re.sub(r'^(ussr_|germ_|us_|uk_|jp_|cn_|it_|fr_|se_)', '', text)
    text = re.sub(r'_\d{4}$', '', text)
    return re.sub(r"[\s\-_]", "", text).replace("\u00a0", "")


def _should_replace_index_alias(existing_alias, new_alias):
    if existing_alias is None:
        return True
    return len(str(new_alias or "")) > len(str(existing_alias or ""))


def _iter_vehicle_entries(db):
    if isinstance(db, dict):
        for v_id, v_info in db.items():
            if isinstance(v_info, dict):
                yield str(v_id), v_info
        return

    if isinstance(db, list):
        for idx, v_info in enumerate(db):
            if not isinstance(v_info, dict):
                continue
            v_id = v_info.get("id") or v_info.get("identifier") or v_info.get("loc_name") or v_info.get("name") or str(idx)
            yield str(v_id), v_info


def _build_vehicle_index(db):
    """Xây dựng Index tìm kiếm thông minh hỗ trợ mọi alias/tên gốc của xe"""
    index = {}
    alias_map = {}
    if not isinstance(db, (dict, list)):
        return index

    for v_id, v_info in _iter_vehicle_entries(db):
        if not isinstance(v_info, dict):
            continue

        raw_aliases = [
            str(v_id),
            v_info.get("loc_name"),
            v_info.get("name"),
            v_info.get("identifier"),
            v_info.get("id"),
        ]

        for alias in raw_aliases:
            if not alias:
                continue

            norm_key = _normalize_vehicle_key(alias)
            if norm_key:
                if norm_key not in index or _should_replace_index_alias(alias_map.get(norm_key), alias):
                    index[norm_key] = v_info
                    alias_map[norm_key] = alias

            raw_clean = re.sub(r"[\s\-_]", "", str(alias).lower())
            if raw_clean:
                if raw_clean not in index or _should_replace_index_alias(alias_map.get(raw_clean), alias):
                    index[raw_clean] = v_info
                    alias_map[raw_clean] = alias

    return index


@bot.event
async def on_ready():
    await bot.change_presence(
        status=discord.Status.online,
        activity=discord.Game(name="War Thunder | !wt <xe>")
    )
    print(f"🤖 Bot {bot.user} đã ONLINE!")


def _vehicle_strengths(vehicle: dict) -> list[str]:
    strengths = []
    if vehicle.get("has_stab"):
        strengths.append("• **Kê tâm tốt:** Vừa di chuyển vừa bắn chính xác")
    if vehicle.get("has_aphe"):
        strengths.append("• **Đạn APHE:** Sát thương sau xuyên vượt trội")

    reload_value = _coerce_number(vehicle.get("reload"))
    if reload_value is not None and 0 < reload_value <= 7.5:
        strengths.append(f"• **Nạp đạn nhanh:** `{reload_value}s` / viên")

    hp_ton = _coerce_number(vehicle.get("hp_ton"))
    if hp_ton is not None and hp_ton >= 20:
        strengths.append(f"• **Cơ động cao:** `{hp_ton} HP/tấn`")

    if not strengths:
        strengths.append("• **Phụ thuộc kỹ năng:** Đòi hỏi góc kê và đọc bản đồ tốt")

    return strengths


def _finalize_vehicle(vehicle: dict) -> dict:
    if not isinstance(vehicle, dict):
        return vehicle
    normalized = dict(vehicle)
    normalized["strengths"] = _vehicle_strengths(normalized)
    return normalized


def _scan_nested_values(obj, keys):
    values = []
    if isinstance(obj, dict):
        for key in keys:
            if key in obj and obj[key] not in (None, 0, "", [], {}):
                values.append(obj[key])
        for value in obj.values():
            values.extend(_scan_nested_values(value, keys))
    elif isinstance(obj, list):
        for item in obj:
            values.extend(_scan_nested_values(item, keys))
    return values


def _scan_nested_items(obj, keys):
    items = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key in keys and value not in (None, 0, "", [], {}):
                items.append((key, value))
            items.extend(_scan_nested_items(value, keys))
    elif isinstance(obj, list):
        for item in obj:
            items.extend(_scan_nested_items(item, keys))
    return items


def _extract_reload_seconds(v_info: dict):
    if not isinstance(v_info, dict):
        return None

    candidates = _scan_nested_items(v_info, ("reloadTime", "reload_time", "shotFreq", "shot_freq"))

    for key, value in candidates:
        normalized_key = str(key).lower()
        if isinstance(value, str):
            cleaned = value.strip()
            if not cleaned:
                continue
            try:
                numeric = float(cleaned)
            except ValueError:
                continue
        elif isinstance(value, (int, float)) and not isinstance(value, bool):
            numeric = float(value)
        else:
            continue

        if numeric <= 0:
            continue

        if "shot" in normalized_key or "freq" in normalized_key:
            if numeric < 100:
                return round(60 / numeric, 1)
            return round(numeric, 1)

        return round(numeric, 1)

    return None


def _parse_vehicle_data(v_info: dict, query_name: str) -> dict:
    name = v_info.get("loc_name") or v_info.get("name") or query_name

    rank_val = v_info.get("economicRankHistorical")
    if rank_val is None:
        rank_val = v_info.get("economicRankArcade", 0)

    br = _format_br(rank_val)

    engine_hp = 0
    engine_data = v_info.get("engine") or v_info.get("horsePower") or 0
    if isinstance(engine_data, dict):
        engine_hp = engine_data.get("horsePower", 0) or engine_data.get("power", 0)
    else:
        engine_hp = engine_data

    mass_kg = v_info.get("mass") or v_info.get("weight") or 0

    try:
        hp_num = float(engine_hp)
        mass_num = float(mass_kg)
        hp_ton = round(hp_num / (mass_num / 1000), 1) if (hp_num > 0 and mass_num > 0) else "N/A"
    except (ValueError, TypeError):
        hp_ton = "N/A"

    reload_candidates = [
        v_info.get("reloadTime"),
        v_info.get("reload_time"),
    ]
    weapons = v_info.get("weapons") or []
    if isinstance(weapons, list):
        for w in weapons:
            if isinstance(w, dict):
                reload_candidates.extend([w.get("reloadTime"), w.get("reload_time")])

    reload_time = _extract_reload_seconds(v_info)
    if reload_time is None:
        reload_time = next((item for item in reload_candidates if item not in (None, 0, "", [])), 0)
    try:
        reload_val = float(reload_time)
        reload_sec = round(reload_val, 1) if reload_val > 0 else "N/A"
    except (ValueError, TypeError):
        reload_sec = "N/A"

    has_stab = bool(v_info.get("hasStabilizer") or v_info.get("stabilizer", False))
    has_aphe = bool(v_info.get("hasAPHE") or "aphe" in str(v_info.get("ammo", "")).lower())

    data = {
        "name": str(name).replace("_", " ").upper(),
        "br": br,
        "hp_ton": hp_ton,
        "reload": reload_sec,
        "has_stab": has_stab,
        "has_aphe": has_aphe,
    }
    return _finalize_vehicle(data)


def _resolve_asset_url(raw_url):
    if not raw_url or not isinstance(raw_url, str):
        return None

    value = raw_url.strip()
    if value.startswith(("http://", "https://")):
        return value

    cleaned = value.replace("\\", "/").lstrip("./!")
    if not cleaned:
        return None

    candidates = []
    if cleaned.startswith(("asset/", "ui/", "units/", "images/")):
        candidates.append(cleaned)
    else:
        candidates.append(cleaned)

    # Wt-db sometimes stores paths without extension or in folder names that need an image suffix.
    for suffix in ("", ".png", ".jpg", ".jpeg", ".webp", ".gif"):
        if not suffix and cleaned.endswith((".png", ".jpg", ".jpeg", ".webp", ".gif")):
            continue
        candidate = cleaned if suffix == "" else f"{cleaned}{suffix}"
        if candidate.startswith(("asset/", "ui/", "units/", "images/")) or candidate.endswith((".png", ".jpg", ".jpeg", ".webp", ".gif")):
            candidates.append(candidate)

    seen = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        url = f"https://raw.githubusercontent.com/wt-db/wt-db/main/{candidate}"
        return url

    return None


def _find_vehicle_suggestion(query_name: str, index: dict | None = None, limit: int = 3):
    if not query_name:
        return None

    target_index = index if isinstance(index, dict) else getattr(bot, 'vehicle_index', {})
    q_clean = _normalize_vehicle_key(query_name)
    if not q_clean or not isinstance(target_index, dict):
        return None

    scored = []
    for key, v_info in target_index.items():
        if not key or key == q_clean:
            continue

        # So sánh trên key đã chuẩn hóa, tránh đánh giá sai vì chuỗi khác nhau về khoảng trắng hoặc ký tự đặc biệt.
        ratio = difflib.SequenceMatcher(None, q_clean, key).ratio()
        if q_clean in key or key in q_clean or ratio >= 0.68:
            name = v_info.get("loc_name") or v_info.get("name") or v_info.get("identifier") or v_info.get("id") or str(v_info)
            if name:
                scored.append((ratio, str(name)))

    if not scored:
        return None

    scored.sort(key=lambda item: item[0], reverse=True)
    suggestions = []
    seen = set()
    for _, name in scored:
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        suggestions.append(name)
        if len(suggestions) >= limit:
            break

    return suggestions[0] if suggestions else None


def find_vehicle(query_name: str, index: dict | None = None):
    target_index = index if isinstance(index, dict) else getattr(bot, 'vehicle_index', {})
    q_clean = _normalize_vehicle_key(query_name)

    if target_index:
        exact_match = target_index.get(q_clean)
        if exact_match:
            return _parse_vehicle_data(exact_match, query_name)

        matches = []
        for key, v_info in target_index.items():
            if q_clean in key:
                matches.append((key, v_info))

        if matches:
            matches.sort(key=lambda x: len(x[0]))
            return _parse_vehicle_data(matches[0][1], query_name)

    fallback = dict(DEFAULT_VEHICLE)
    fallback["name"] = query_name.strip().upper()
    suggestion = _find_vehicle_suggestion(query_name, target_index)
    if suggestion:
        fallback["suggestion"] = suggestion
    return _finalize_vehicle(fallback)


def _format_strengths_for_embed(strengths, limit=150) -> str:
    cleaned = [str(item).strip() for item in strengths[:2] if item]
    if not cleaned:
        return "• **Không rõ**"

    result = "\n".join(cleaned)
    if len(result) > limit:
        truncated = result[:limit].rsplit(' ', 1)[0]
        if truncated:
            return truncated + "..."
        return result[:limit] + "..."
    return result


def analyze_combat(t1: dict, t2: dict) -> str:
    reasons = []
    if t2.get('has_aphe'):
        reasons.append(f"• **Sát thương đạn APHE:** {t2['name']} bắn đục giáp sẽ quét sạch kíp lái {t1['name']}.")

    r1 = _coerce_number(t1.get('reload'))
    r2 = _coerce_number(t2.get('reload'))
    if r1 is not None and r2 is not None and r1 > r2:
        reasons.append(f"• **Tốc độ bắn:** {t2['name']} nạp đạn nhanh hơn (`{r2}s` vs `{r1}s`), dễ bắn bồi trong CQB.")

    if not t1.get('has_stab') and t2.get('has_stab'):
        reasons.append(f"• **Kê tâm (Stabilizer):** {t2['name']} vừa chạy vừa bắn được ngay, {t1['name']} phải chờ nảy tâm 1-2s.")

    hp1 = _coerce_number(t1.get('hp_ton'))
    hp2 = _coerce_number(t2.get('hp_ton'))
    if hp1 is not None and hp2 is not None and hp1 < hp2:
        reasons.append(f"• **Cơ động (Flank):** {t2['name']} cơ động hơn (`{hp2}` vs `{hp1}` HP/t), dễ móc sườn {t1['name']}.")

    if not reasons:
        reasons.append("• **Kỹ năng người chơi:** Phụ thuộc vào góc kê (Angling) và ai nhìn thấy đối phương trước.")

    return "\n".join(reasons)


def _get_vehicle_image_url(v_info: dict):
    if not isinstance(v_info, dict):
        return None

    for key in ("image", "image_url", "thumbnail", "icon", "small_image", "smallIcon"):
        value = v_info.get(key)
        if value:
            return str(value)

    images = v_info.get("images") or v_info.get("image_data") or {}
    if isinstance(images, dict):
        for key in ("small", "thumb", "thumbnail", "icon"):
            value = images.get(key)
            if value:
                return str(value)

    return None


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

    if not getattr(bot, "db_ready", False):
        if getattr(bot, "db_loading", False):
            await asyncio.sleep(0.5)
        if not getattr(bot, "db_ready", False):
            await ctx.send("⏳ Database xe đang tải, vui lòng thử lại sau vài giây.")
            return

    if re.search(r"\s+vs\s+", query_text, flags=re.IGNORECASE):
        parts = re.split(r"\s+vs\s+", query_text, maxsplit=1, flags=re.IGNORECASE)
        t1 = find_vehicle(parts[0].strip(), bot.vehicle_index)
        t2 = find_vehicle(parts[1].strip(), bot.vehicle_index)

        suggestion_notes = []
        if t1.get("suggestion"):
            suggestion_notes.append(f"{parts[0].strip()} → **{t1['suggestion']}**")
        if t2.get("suggestion"):
            suggestion_notes.append(f"{parts[1].strip()} → **{t2['suggestion']}**")

        str1 = _format_strengths_for_embed(t1.get('strengths', []), limit=150)
        str2 = _format_strengths_for_embed(t2.get('strengths', []), limit=150)

        reload1_str = f"`{t1['reload']}s`" if _coerce_number(t1['reload']) is not None else "`N/A`"
        reload2_str = f"`{t2['reload']}s`" if _coerce_number(t2['reload']) is not None else "`N/A`"

        hp1_str = f"`{t1['hp_ton']} HP/t`" if _coerce_number(t1['hp_ton']) is not None else "`N/A`"
        hp2_str = f"`{t2['hp_ton']} HP/t`" if _coerce_number(t2['hp_ton']) is not None else "`N/A`"

        val1 = f"• BR: `{t1['br']}`\n• HP/tấn: {hp1_str}\n• Nạp: {reload1_str}\n**Ưu điểm:**\n{str1}"
        val2 = f"• BR: `{t2['br']}`\n• HP/tấn: {hp2_str}\n• Nạp: {reload2_str}\n**Ưu điểm:**\n{str2}"

        embed = discord.Embed(title=f"⚔️ PHÂN TÍCH: {t1['name']} VS {t2['name']}", color=discord.Color.gold())
        if suggestion_notes:
            embed.description = "🔍 Gợi ý gần đúng:\n" + "\n".join(f"- {item}" for item in suggestion_notes)
        embed.add_field(name=f"📊 {t1['name'][:25]}", value=val1[:1024], inline=True)
        embed.add_field(name=f"📊 {t2['name'][:25]}", value=val2[:1024], inline=True)

        combat_analysis = analyze_combat(t1, t2)
        embed.add_field(name=f"💡 Tại sao {t1['name'][:20]} có thể THUA {t2['name'][:20]}?", value=combat_analysis[:1024], inline=False)
        await ctx.send(embed=embed)
        return

    t = find_vehicle(query_text, bot.vehicle_index)
    embed_single = discord.Embed(title=f"🛡️ THÔNG SỐ: {t['name']}", color=discord.Color.green())
    if t.get("suggestion"):
        embed_single.description = f"🔍 Không tìm thấy xe. Có phải bạn muốn: **{t['suggestion']}**?"

    matched_vehicle = bot.vehicle_index.get(_normalize_vehicle_key(query_text))
    if matched_vehicle is None and t.get("suggestion"):
        matched_vehicle = bot.vehicle_index.get(_normalize_vehicle_key(t["suggestion"]))
    image_url = _get_vehicle_image_url(matched_vehicle)
    if image_url:
        resolved_image = _resolve_asset_url(image_url)
        if resolved_image:
            embed_single.set_thumbnail(url=resolved_image)

    embed_single.add_field(name="🎯 Battle Rating (BR)", value=f"`{t['br']}`", inline=True)
    embed_single.add_field(
        name="⚡ Tỷ lệ HP/tấn",
        value=f"`{t['hp_ton']} HP/t`" if _coerce_number(t['hp_ton']) is not None else "`N/A`",
        inline=True,
    )
    embed_single.add_field(
        name="⏱️ Tốc độ nạp đạn",
        value=f"`{t['reload']}s`" if _coerce_number(t['reload']) is not None else "`N/A`",
        inline=True,
    )
    embed_single.add_field(name="🎯 Stabilizer", value="✅ Có" if t['has_stab'] else "❌ Không", inline=True)
    embed_single.add_field(name="💥 Đạn APHE", value="✅ Có" if t['has_aphe'] else "❌ Không", inline=True)

    strengths_text = "\n".join(t.get("strengths", []))
    embed_single.add_field(name="✅ Ưu điểm", value=strengths_text[:1024], inline=False)
    await ctx.send(embed=embed_single)


TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    print("⚠️ CẢNH BÁO: DISCORD_TOKEN chưa được đặt. Hãy export DISCORD_TOKEN=<token> trước khi chạy bot.")
else:
    bot.run(TOKEN)
