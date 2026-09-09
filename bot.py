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

WT_DATA_URL = "https://raw.githubusercontent.com/wt-db/wt-db/main/db/units.json"

# Fallback data nếu URL không hoạt động
FALLBACK_VEHICLES = {
    # Germany
    "jagdtiger": {"id": "jagdtiger", "name": "Jagdtiger", "loc_name": "Jagdtiger", "economicRankHistorical": 19, "horsePower": 600, "mass": 76000, "reloadTime": 7.0, "hasStabilizer": False, "hasAPHE": True},
    "leopard2a4": {"id": "leopard2a4", "name": "Leopard 2A4", "loc_name": "Leopard 2A4", "economicRankHistorical": 18, "horsePower": 830, "mass": 55150, "reloadTime": 6.8, "hasStabilizer": True, "hasAPHE": True},
    "leopard2a5": {"id": "leopard2a5", "name": "Leopard 2A5", "loc_name": "Leopard 2A5", "economicRankHistorical": 19, "horsePower": 830, "mass": 55150, "reloadTime": 6.5, "hasStabilizer": True, "hasAPHE": True},
    "tiger2": {"id": "tiger2", "name": "Tiger II", "loc_name": "Tiger II", "economicRankHistorical": 16, "horsePower": 700, "mass": 69400, "reloadTime": 7.5, "hasStabilizer": False, "hasAPHE": True},
    "panther": {"id": "panther", "name": "Panther", "loc_name": "Panther", "economicRankHistorical": 14, "horsePower": 700, "mass": 45500, "reloadTime": 7.5, "hasStabilizer": False, "hasAPHE": True},
    
    # USSR
    "t72b3": {"id": "t72b3", "name": "T-72B3", "loc_name": "T-72B3", "economicRankHistorical": 18, "horsePower": 840, "mass": 46000, "reloadTime": 7.1, "hasStabilizer": True, "hasAPHE": True},
    "t90a": {"id": "t90a", "name": "T-90A", "loc_name": "T-90A", "economicRankHistorical": 19, "horsePower": 1000, "mass": 46500, "reloadTime": 6.5, "hasStabilizer": True, "hasAPHE": True},
    "is7": {"id": "is7", "name": "IS-7", "loc_name": "IS-7", "economicRankHistorical": 17, "horsePower": 700, "mass": 68000, "reloadTime": 8.0, "hasStabilizer": False, "hasAPHE": True},
    "t34_100": {"id": "t34_100", "name": "T-34-100", "loc_name": "T-34-100", "economicRankHistorical": 15, "horsePower": 500, "mass": 32000, "reloadTime": 8.0, "hasStabilizer": False, "hasAPHE": True},
    "su100": {"id": "su100", "name": "SU-100", "loc_name": "SU-100", "economicRankHistorical": 15, "horsePower": 520, "mass": 31600, "reloadTime": 9.0, "hasStabilizer": False, "hasAPHE": True},
    
    # USA
    "m48_patton": {"id": "m48_patton", "name": "M48 Patton", "loc_name": "M48 Patton", "economicRankHistorical": 16, "horsePower": 810, "mass": 54432, "reloadTime": 8.0, "hasStabilizer": False, "hasAPHE": False},
    "m48a5": {"id": "m48a5", "name": "M48A5", "loc_name": "M48A5", "economicRankHistorical": 17, "horsePower": 830, "mass": 53100, "reloadTime": 8.5, "hasStabilizer": False, "hasAPHE": False},
    "m46_patton": {"id": "m46_patton", "name": "M46 Patton", "loc_name": "M46 Patton", "economicRankHistorical": 15, "horsePower": 810, "mass": 51900, "reloadTime": 8.0, "hasStabilizer": False, "hasAPHE": False},
    "m26_pershing": {"id": "m26_pershing", "name": "M26 Pershing", "loc_name": "M26 Pershing", "economicRankHistorical": 14, "horsePower": 500, "mass": 41850, "reloadTime": 7.5, "hasStabilizer": False, "hasAPHE": False},
    "t25": {"id": "t25", "name": "T25", "loc_name": "T25", "economicRankHistorical": 15, "horsePower": 500, "mass": 42000, "reloadTime": 7.5, "hasStabilizer": False, "hasAPHE": False},
    
    # Britain
    "chieftain": {"id": "chieftain", "name": "Chieftain", "loc_name": "Chieftain", "economicRankHistorical": 17, "horsePower": 585, "mass": 51820, "reloadTime": 8.5, "hasStabilizer": False, "hasAPHE": True},
    "challenger1": {"id": "challenger1", "name": "Challenger 1", "loc_name": "Challenger 1", "economicRankHistorical": 18, "horsePower": 1200, "mass": 62000, "reloadTime": 6.0, "hasStabilizer": True, "hasAPHE": False},
    "centurion": {"id": "centurion", "name": "Centurion", "loc_name": "Centurion", "economicRankHistorical": 15, "horsePower": 650, "mass": 51100, "reloadTime": 7.5, "hasStabilizer": False, "hasAPHE": True},
    "conqueror": {"id": "conqueror", "name": "Conqueror", "loc_name": "Conqueror", "economicRankHistorical": 16, "horsePower": 810, "mass": 68040, "reloadTime": 7.5, "hasStabilizer": False, "hasAPHE": True},
    
    # Japan
    "type10": {"id": "type10", "name": "Type 10", "loc_name": "Type 10", "economicRankHistorical": 19, "horsePower": 1200, "mass": 50000, "reloadTime": 6.0, "hasStabilizer": True, "hasAPHE": True},
    "type74": {"id": "type74", "name": "Type 74", "loc_name": "Type 74", "economicRankHistorical": 17, "horsePower": 750, "mass": 42000, "reloadTime": 8.5, "hasStabilizer": True, "hasAPHE": True},
    "type61": {"id": "type61", "name": "Type 61", "loc_name": "Type 61", "economicRankHistorical": 15, "horsePower": 570, "mass": 35000, "reloadTime": 8.0, "hasStabilizer": False, "hasAPHE": True},
    
    # France
    "amx30": {"id": "amx30", "name": "AMX-30", "loc_name": "AMX-30", "economicRankHistorical": 17, "horsePower": 680, "mass": 36000, "reloadTime": 8.0, "hasStabilizer": False, "hasAPHE": True},
    "amx50": {"id": "amx50", "name": "AMX-50", "loc_name": "AMX-50", "economicRankHistorical": 16, "horsePower": 850, "mass": 50000, "reloadTime": 8.5, "hasStabilizer": False, "hasAPHE": True},
    "lorraine40t": {"id": "lorraine40t", "name": "Lorraine 40t", "loc_name": "Lorraine 40t", "economicRankHistorical": 16, "horsePower": 1050, "mass": 40000, "reloadTime": 6.5, "hasStabilizer": False, "hasAPHE": True},
    
    # Sweden
    "strv103": {"id": "strv103", "name": "Strv 103", "loc_name": "Strv 103", "economicRankHistorical": 17, "horsePower": 730, "mass": 42000, "reloadTime": 6.0, "hasStabilizer": False, "hasAPHE": True},
    "leopard2": {"id": "leopard2", "name": "Leopard 2", "loc_name": "Leopard 2", "economicRankHistorical": 17, "horsePower": 830, "mass": 55150, "reloadTime": 7.0, "hasStabilizer": True, "hasAPHE": True},
    
    # China
    "type59": {"id": "type59", "name": "Type 59", "loc_name": "Type 59", "economicRankHistorical": 15, "horsePower": 520, "mass": 36000, "reloadTime": 8.0, "hasStabilizer": False, "hasAPHE": True},
    "type69": {"id": "type69", "name": "Type 69", "loc_name": "Type 69", "economicRankHistorical": 16, "horsePower": 580, "mass": 37500, "reloadTime": 8.0, "hasStabilizer": False, "hasAPHE": True},
    
    # Italy
    "p40": {"id": "p40", "name": "P.40", "loc_name": "P.40", "economicRankHistorical": 13, "horsePower": 280, "mass": 25000, "reloadTime": 6.5, "hasStabilizer": False, "hasAPHE": False},
}


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

    async def load_wt_database(self, retries: int = 3):
        # Kiểm tra nhanh trước khi lock
        if self.db_loading or self.db_ready:
            return

        async with self._db_lock:
            if self.db_loading or self.db_ready:
                return
            self.db_loading = True

        last_error = None
        try:
            # 1. Thử load từ file local trước
            import os
            local_db_path = os.path.join(os.path.dirname(__file__), "wt_data.json")
            if os.path.exists(local_db_path):
                print(f"📂 Tìm thấy file local: {local_db_path}")
                try:
                    import json
                    with open(local_db_path, 'r', encoding='utf-8') as f:
                        payload = json.load(f)
                    
                    if isinstance(payload, dict):
                        self.vehicles_db = payload
                    elif isinstance(payload, list):
                        self.vehicles_db = {
                            str(item.get("id") or item.get("identifier") or item.get("loc_name") or item.get("name") or idx): item
                            for idx, item in enumerate(payload)
                            if isinstance(item, dict)
                        }
                    else:
                        self.vehicles_db = {}
                    
                    self.vehicle_index = _build_vehicle_index(self.vehicles_db)
                    self.db_ready = bool(self.vehicle_index)
                    print(f"✅ Đã load file local thành công ({len(self.vehicles_db)} phương tiện)!")
                    print(f"✅ Đã tạo index tìm kiếm cho {len(self.vehicle_index)} alias xe.")
                    return
                except Exception as e:
                    print(f"⚠️ Lỗi load file local: {e}")
                    last_error = e
            
            print(f"📡 Bắt đầu tải từ: {WT_DATA_URL}")
            for attempt in range(1, retries + 1):
                try:
                    print(f"🔄 Đang tải dữ liệu toàn bộ xe War Thunder... (Lần thử {attempt}/{retries})")
                    session = await self.ensure_session()
                    timeout = aiohttp.ClientTimeout(total=60, connect=15)

                    async with session.get(WT_DATA_URL, timeout=timeout) as res:
                        print(f"📊 HTTP Status: {res.status}")
                        if res.status == 200:
                            try:
                                text = await res.text()
                                print(f"📥 Dữ liệu nhận được: {len(text)} ký tự")
                                payload = await res.json()
                            except aiohttp.ContentTypeError as e:
                                print(f"⚠️ Response không phải JSON hợp lệ (lần {attempt}/{retries}): {e}")
                                last_error = e
                                continue
                            except Exception as e:
                                print(f"⚠️ Lỗi parse JSON (lần {attempt}/{retries}): {e}")
                                last_error = e
                                continue

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

                            print(f"🔍 Vehicles DB có {len(self.vehicles_db)} mục")
                            self.vehicle_index = _build_vehicle_index(self.vehicles_db)
                            self.db_ready = bool(self.vehicle_index)
                            print(f"✅ Đã tải thành công dữ liệu ({len(self.vehicles_db)} phương tiện)!")
                            print(f"✅ Đã tạo index tìm kiếm cho {len(self.vehicle_index)} alias xe.")
                            return

                        elif res.status == 404:
                            print(f"⚠️ HTTP 404: URL không tồn tại. Sử dụng fallback data...")
                            self.vehicles_db = dict(FALLBACK_VEHICLES)
                            self.vehicle_index = _build_vehicle_index(self.vehicles_db)
                            self.db_ready = bool(self.vehicle_index)
                            print(f"✅ Đã load fallback data ({len(self.vehicles_db)} phương tiện)!")
                            return

                        print(f"⚠️ Không thể tải dữ liệu. HTTP Code: {res.status} (lần {attempt}/{retries})")
                        last_error = RuntimeError(f"HTTP {res.status}")
                except asyncio.TimeoutError as exc:
                    last_error = exc
                    print(f"❌ Lỗi: Kết nối tới wt-db bị timeout! (Lần {attempt}/{retries}): {exc}")
                except aiohttp.ClientError as exc:
                    last_error = exc
                    print(f"❌ Lỗi HTTP client (lần {attempt}/{retries}): {exc}")
                except Exception as exc:
                    last_error = exc
                    print(f"❌ Lỗi khi tải dữ liệu (lần {attempt}/{retries}): {type(exc).__name__}: {exc}")
                    import traceback
                    traceback.print_exc()

                if attempt < retries:
                    wait_time = 2.0 * attempt
                    await asyncio.sleep(wait_time)
                    print(f"🔁 Thử lại tải DB sau {wait_time}s...")

            # Fallback: Dùng dữ liệu mặc định nếu tất cả thử đều thất bại
            print("⚠️ Tải dữ liệu từ URL thất bại. Sử dụng fallback data...")
            self.vehicles_db = dict(FALLBACK_VEHICLES)
            self.vehicle_index = _build_vehicle_index(self.vehicles_db)
            self.db_ready = bool(self.vehicle_index)
            print(f"✅ Đã load fallback data ({len(self.vehicles_db)} phương tiện)!")
            if last_error is not None:
                print(f"📌 Lỗi cuối cùng: {type(last_error).__name__}: {last_error}")
        finally:
            self.db_loading = False

    async def setup_hook(self):
        await self.ensure_session()
        asyncio.create_task(self.start_web_server())
        print("🔄 Đang chạy tiến trình nạp DB xe War Thunder...")
        # Chạy async ngầm, không block bot startup
        asyncio.create_task(self.load_wt_database())

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


def _format_br(rank_value):
    try:
        rank_num = int(rank_value)
    except (TypeError, ValueError):
        return "N/A"

    if rank_num < 0:  # Đổi từ <= 0 thành < 0 để giữ lại rank_num = 0 (BR 1.0)
        return "N/A"

    whole = rank_num // 3
    remainder = rank_num % 3
    br_value = Decimal(whole) + (Decimal(remainder) / Decimal(3)) + Decimal("1")
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


def _canonical_vehicle_key(value) -> str:
    """Chuẩn hóa tên xe giữ nguyên prefix quốc gia, để tránh ghi đè giữa các xe cùng khung gầm."""
    if not value:
        return ""
    text = str(value).lower()
    return re.sub(r"[\s\-_]", "", text).replace("\u00a0", "")


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

            canonical_key = _canonical_vehicle_key(alias)
            if canonical_key:
                if canonical_key not in index or _should_replace_index_alias(alias_map.get(canonical_key), alias):
                    index[canonical_key] = v_info
                    alias_map[canonical_key] = alias

            norm_key = _normalize_vehicle_key(alias)
            if norm_key:
                existing = index.get(norm_key)
                if existing is None:
                    index[norm_key] = v_info
                    alias_map[norm_key] = alias
                elif existing is not v_info:
                    if not isinstance(existing, list):
                        index[norm_key] = [existing, v_info]
                    elif v_info not in existing:
                        existing.append(v_info)

    return index


@bot.event
async def on_ready():
    await bot.change_presence(
        status=discord.Status.online,
        activity=discord.Game(name="War Thunder | !wt <xe>")
    )
    print(f"🤖 Bot {bot.user} đã ONLINE!")


@bot.event
async def on_command_error(ctx, error):
    """Bắt và hiển thị lỗi chi tiết"""
    print(f"❌ Lỗi command: {error}")
    if isinstance(error, commands.CommandNotFound):
        return
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("❌ Thiếu tham số. Dùng `!wt help` để xem hướng dẫn.")
    else:
        await ctx.send(f"❌ Lỗi: {str(error)[:100]}")
        import traceback
        traceback.print_exc()


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

    # 1. Ưu tiên lấy reloadTime trực tiếp từ root level (main cannon)
    for main_key in ("reloadTime", "reload_time"):
        val = v_info.get(main_key)
        if isinstance(val, (int, float)) and val > 0:
            return round(float(val), 1)

    # 2. Quét các vũ khí chính trong danh sách weapons
    weapons = v_info.get("weapons")
    if isinstance(weapons, list):
        for w in weapons:
            if isinstance(w, dict):
                trigger = w.get("trigger")
                # Ưu tiên pháo chính (main_caliber) hoặc gunner
                if trigger in ("gunner", "main_caliber", None):
                    for k in ("reloadTime", "reload_time"):
                        val = w.get(k)
                        if isinstance(val, (int, float)) and val > 0:
                            return round(float(val), 1)

    # 3. Fallback: quét đệ quy nếu cấu hình JSON phi chuẩn, nhưng tránh nhầm với súng máy đồng trục.
    candidates = _scan_nested_items(v_info, ("reloadTime", "reload_time"))

    for _, value in candidates:
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

        if numeric > 0:
            return round(numeric, 1)

    return None


def _parse_vehicle_data(v_info: dict, query_name: str) -> dict:
    name = v_info.get("loc_name") or v_info.get("name") or query_name

    # Ưu tiên BR trực tiếp từ data, nếu không có thì tính từ rank
    if "br" in v_info and v_info["br"]:
        try:
            br = str(float(v_info["br"]))
        except (ValueError, TypeError):
            rank_val = v_info.get("economicRankHistorical")
            if rank_val is None:
                rank_val = v_info.get("economicRankArcade", 0)
            br = _format_br(rank_val)
    else:
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
    
    # Lọc APHE chính xác hơn
    has_aphe = bool(v_info.get("hasAPHE"))
    if not has_aphe:
        ammo_str = str(v_info.get("ammo", "")).lower()
        # Tránh nhầm với đạn súng máy
        has_aphe = "aphe" in ammo_str and "bullet" not in ammo_str
    
    # Nếu không có dữ liệu explicit, dùng BR để suy đoán
    if not v_info.get("hasAPHE") and "br" not in v_info:
        try:
            br_val = float(br)
            has_aphe = br_val <= 6.3
            if not has_stab:
                has_stab = br_val >= 7.7
        except (ValueError, TypeError):
            pass

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

    # Nếu đã có đuôi file ảnh sẵn thì trả về link direct
    if cleaned.endswith((".png", ".jpg", ".jpeg", ".webp", ".gif")):
        return f"https://raw.githubusercontent.com/wt-db/wt-db/main/{cleaned}"

    # Hầu hết asset icon/phương tiện của wt-db đều lưu dưới dạng .png
    return f"https://raw.githubusercontent.com/wt-db/wt-db/main/{cleaned}.png"


def _find_vehicle_suggestion(query_name: str, index: dict | None = None, limit: int = 3):
    if not query_name:
        return None

    target_index = index if isinstance(index, dict) else getattr(bot, 'vehicle_index', {})
    q_clean = _normalize_vehicle_key(query_name)
    if not q_clean or not isinstance(target_index, dict):
        return None

    q_prefix = q_clean[:3]
    candidate_items = []
    for key, v_info in target_index.items():
        if not key:
            continue
        if isinstance(v_info, list):
            for item in v_info:
                if isinstance(item, dict):
                    candidate_items.append((key, item))
            continue
        if isinstance(v_info, dict):
            candidate_items.append((key, v_info))

    filtered = []
    for key, v_info in candidate_items:
        if key == q_clean:
            continue
        if q_prefix and (key.startswith(q_prefix) or q_clean.startswith(key[:3]) or q_prefix in key or key in q_prefix):
            filtered.append((key, v_info))
        elif len(q_clean) <= 3:
            filtered.append((key, v_info))

    if not filtered:
        # Giới hạn tối đa 300 mẫu để difflib không làm quá tải CPU
        filtered = candidate_items[:300]

    scored = []
    for key, v_info in filtered:
        if not key:
            continue

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

    # Chặn ngay nếu query rỗng hoặc chỉ chứa khoảng trắng/ký tự đặc biệt
    if not q_clean:
        fallback = dict(DEFAULT_VEHICLE)
        fallback["name"] = query_name.strip().upper() or "UNKNOWN"
        return _finalize_vehicle(fallback)

    if target_index:
        exact_match = target_index.get(q_clean)
        if exact_match:
            if isinstance(exact_match, list):
                # Ưu tiên xe từ các cây chính (US, USSR, Germany, UK, Japan, China, Italy, France, Sweden)
                main_trees = {"us_", "ussr_", "germ_", "uk_", "jp_", "cn_", "it_", "fr_", "se_"}
                prioritized = next((v for v in exact_match if any(v.get("id", "").lower().startswith(tree) for tree in main_trees)), exact_match[0])
                return _parse_vehicle_data(prioritized, query_name)
            return _parse_vehicle_data(exact_match, query_name)

        matches = []
        for key, v_info in target_index.items():
            if isinstance(v_info, list):
                for item in v_info:
                    if q_clean in key:
                        matches.append((key, item))
            elif q_clean in key:
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


def _generate_vehicle_specs(br: float) -> dict:
    """Generate realistic vehicle specs based on BR"""
    br_idx = min(int((br - 1.0) * 10), 100)
    
    hp_base = 300 + (br_idx * 8)
    mass_base = 20000 + (br_idx * 400)
    reload_base = 8.0 - min(br_idx * 0.05, 3.5)
    
    has_stab = br >= 8.0
    has_aphe = br <= 6.3
    
    return {
        "horsePower": int(hp_base),
        "mass": int(mass_base),
        "reloadTime": round(reload_base, 1),
        "hasStabilizer": has_stab,
        "hasAPHE": has_aphe,
    }


async def add_vehicle_to_database(vehicle_name: str, br: float) -> tuple[bool, str]:
    """Add a new vehicle to the database and save to JSON file"""
    try:
        # Validate BR range
        if not (1.0 <= br <= 11.3):
            return False, "❌ BR phải trong khoảng 1.0 - 11.3"
        
        # Normalize vehicle ID
        v_id = re.sub(r"[\s\-]", "_", vehicle_name.lower())
        
        # Check if already exists
        if v_id in bot.vehicles_db:
            return False, f"❌ Xe **{vehicle_name}** đã tồn tại trong database!"
        
        # Generate full vehicle entry
        specs = _generate_vehicle_specs(br)
        new_vehicle = {
            "id": v_id,
            "name": vehicle_name,
            "loc_name": vehicle_name,
            "identifier": v_id,
            "br": br,
            "economicRankHistorical": max(1, int((br - 1.0) * 3 + 1)),
            **specs
        }
        
        # Add to in-memory database
        bot.vehicles_db[v_id] = new_vehicle
        
        # Rebuild search index
        bot.vehicle_index = _build_vehicle_index(bot.vehicles_db)
        
        # Save to JSON file
        db_path = os.path.join(os.path.dirname(__file__), "wt_data.json")
        try:
            import json
            sorted_db = {k: bot.vehicles_db[k] for k in sorted(bot.vehicles_db.keys())}
            with open(db_path, 'w', encoding='utf-8') as f:
                json.dump(sorted_db, f, indent=2, ensure_ascii=False)
        except Exception as e:
            # Rollback if save fails
            del bot.vehicles_db[v_id]
            bot.vehicle_index = _build_vehicle_index(bot.vehicles_db)
            return False, f"❌ Lỗi lưu file: {str(e)[:50]}"
        
        return True, f"✅ Đã thêm **{vehicle_name}** (BR: {br}) vào database!\n📊 Tổng xe: {len(bot.vehicles_db)}"
    
    except Exception as e:
        return False, f"❌ Lỗi: {str(e)[:100]}"


def _get_vehicle_image_url(v_info):
    if isinstance(v_info, list):
        if not v_info:
            return None
        v_info = v_info[0]

    if not isinstance(v_info, dict):
        return None

    for key in ("image", "image_url", "thumbnail", "icon", "small_image", "smallIcon"):
        value = v_info.get(key)
        if value and not isinstance(value, (list, dict)):
            return str(value)

    images = v_info.get("images") or v_info.get("image_data") or {}
    if isinstance(images, dict):
        for key in ("small", "thumb", "thumbnail", "icon"):
            value = images.get(key)
            if value and not isinstance(value, (list, dict)):
                return str(value)

    return None


@bot.command(name="test")
async def test_bot(ctx):
    """Kiểm tra chi tiết tình trạng bot"""
    db_status = "✅ Ready" if bot.db_ready else "⏳ Loading..." if bot.db_loading else "❌ Not loaded"
    
    embed = discord.Embed(
        title="🤖 BOT STATUS CHECK",
        color=discord.Color.blue()
    )
    embed.add_field(name="🟢 Bot Status", value="Online", inline=True)
    embed.add_field(name="📊 Database Status", value=db_status, inline=True)
    embed.add_field(name="🚗 Total Vehicles", value=f"{len(bot.vehicles_db)}", inline=True)
    embed.add_field(name="🔍 Indexed Aliases", value=f"{len(bot.vehicle_index)}", inline=True)
    embed.add_field(name="💾 Database File", value="`wt_data.json`", inline=True)
    embed.add_field(name="📌 Session", value=f"Uptime: Active", inline=True)
    embed.set_footer(text="Use !wthelp for command guide")
    
    await ctx.send(embed=embed)


@bot.command(name="wthelp")
async def help_command(ctx):
    """Hướng dẫn sử dụng bot War Thunder"""
    embed_help = discord.Embed(
        title="📖 HƯỚNG DẪN SỬ DỤNG BOT WAR THUNDER",
        description="Bot tra cứu thông số & phân tích giao tranh War Thunder.",
        color=discord.Color.blue()
    )
    embed_help.add_field(
        name="🔍 Tra cứu 1 xe",
        value="`!wt jagdtiger`\n`!wt t72b3`\n`!wt m48`",
        inline=False
    )
    embed_help.add_field(
        name="⚔️ So sánh 2 xe",
        value="`!wt jagdtiger vs t72b3`\n`!wt leopard vs t34`",
        inline=False
    )
    embed_help.add_field(
        name="➕ Thêm xe mới (Admin only)",
        value="`!addvehicle \"T-90M\" 11.3`\n`!addvehicle \"M1A2\" 10.7`",
        inline=False
    )
    embed_help.add_field(
        name="🛠️ Lệnh tiện ích",
        value="`!test` - Kiểm tra tình trạng bot\n`!diag` - Chẩn đoán kết nối\n`!wthelp` - Xem hướng dẫn này",
        inline=False
    )
    embed_help.set_footer(text="Bot hoạt động 24/7 trên Render")
    await ctx.send(embed=embed_help)


@bot.command(name="diag")
async def diagnose(ctx):
    """Chẩn đoán tình trạng bot"""
    db_status = "✅ Ready" if bot.db_ready else "⏳ Loading..." if bot.db_loading else "❌ Not loaded"
    
    diag_msg = f"""
📋 **CHẨN ĐOÁN BOT**
🤖 Bot status: Online
📊 DB Status: {db_status}
🔹 Vehicles in DB: {len(bot.vehicles_db)}
🔹 Indexed aliases: {len(bot.vehicle_index)}
🔗 Data URL: {WT_DATA_URL[:50]}...

**Thử kết nối tới URL...**
"""
    msg = await ctx.send(diag_msg)
    
    try:
        session = await bot.ensure_session()
        timeout = aiohttp.ClientTimeout(total=10, connect=5)
        async with session.get(WT_DATA_URL, timeout=timeout) as res:
            result = f"✅ HTTP {res.status}\n📥 Response size: {res.content_length} bytes"
    except Exception as e:
        result = f"❌ {type(e).__name__}: {str(e)[:100]}"
    
    await msg.edit(content=diag_msg + result)


@bot.command(name="addvehicle")
async def add_vehicle_command(ctx, vehicle_name: str = None, br: str = None):
    """Thêm xe mới vào database (Admin only)
    
    Cách dùng: !addvehicle "T-90M" 11.3
    """
    # Admin-only check
    if not ctx.author.guild_permissions.administrator:
        await ctx.send("❌ Chỉ **Admin** mới có quyền thêm xe!")
        return
    
    # Validate parameters
    if not vehicle_name or not br:
        await ctx.send("❌ Cách dùng: `!addvehicle \"Tên xe\" BR`\nVí dụ: `!addvehicle \"T-90M\" 11.3`")
        return
    
    # Try to parse BR
    try:
        br_value = float(br)
    except ValueError:
        await ctx.send(f"❌ BR phải là số! Bạn nhập: `{br}`")
        return
    
    # Clean up vehicle name (remove quotes if present)
    vehicle_name = vehicle_name.strip('"\'')
    
    # Add vehicle to database
    success, message = await add_vehicle_to_database(vehicle_name, br_value)
    
    if success:
        embed = discord.Embed(
            title="✅ Xe mới được thêm",
            description=message,
            color=discord.Color.green()
        )
        embed.add_field(name="🚗 Tên xe", value=vehicle_name, inline=True)
        embed.add_field(name="🎯 BR", value=f"`{br_value}`", inline=True)
        embed.add_field(name="📊 Database", value=f"`{len(bot.vehicles_db)} vehicles`", inline=True)
        await ctx.send(embed=embed)
    else:
        embed = discord.Embed(
            title="❌ Lỗi thêm xe",
            description=message,
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)


@bot.command(name="wt")
async def compare_vehicles(ctx, *, query: str = "help"):
    query_text = query.strip()

    if query_text.lower() == "help" or not query_text:
        # Redirect to !wthelp
        await help_command(ctx)
        return

    # Nếu DB chưa sẵn sàng và cũng không trong quá trình nạp -> Gọi nạp lại ngay
    if not getattr(bot, "db_ready", False):
        if not getattr(bot, "db_loading", False):
            print("⚠️ Database chưa sẵn sàng. Kích hoạt load lại...")
            asyncio.create_task(bot.load_wt_database())

        # Gửi tin nhắn loading và cập nhật trạng thái
        msg = await ctx.send("⏳ Đang tải dữ liệu xe War Thunder...")
        
        # Cho bot chờ tối đa 20 giây (40 x 0.5s)
        for i in range(40):
            await asyncio.sleep(0.5)
            if getattr(bot, "db_ready", False):
                await msg.edit(content="✅ Dữ liệu đã sẵn sàng! Đang xử lý...")
                break
            # Cập nhật thông báo mỗi 3 giây
            if i % 6 == 0 and i > 0:
                elapsed = (i // 2)
                await msg.edit(content=f"⏳ Đang tải dữ liệu... ({elapsed}s)")

        if not getattr(bot, "db_ready", False):
            db_size = len(bot.vehicles_db)
            index_size = len(bot.vehicle_index)
            await msg.edit(content=f"❌ Database xe đang nạp hoặc dính lỗi mạng GitHub.\n📊 Dữ liệu hiện tại: {db_size} vehicles, {index_size} indexed.\nM thử lại sau vài giây nhé!")
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
