"""
华目眼镜管理系统 - Kivy Android版
从tkinter版本完整迁移，保持所有功能不变
"""
from __future__ import annotations

import csv
import json
import os
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.metrics import dp, sp
from kivy.properties import StringProperty, ListProperty, ObjectProperty, NumericProperty, BooleanProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.screenmanager import ScreenManager, Screen, SlideTransition
from kivy.uix.textinput import TextInput
from kivy.uix.spinner import Spinner
from kivy.uix.gridlayout import GridLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.recycleview import RecycleView
from kivy.uix.recycleboxlayout import RecycleBoxLayout
from kivy.uix.recycleview.views import RecycleDataViewBehavior
from kivy.uix.behaviors import FocusBehavior
from kivy.graphics import Color, Rectangle, RoundedRectangle
from kivy.utils import get_color_from_hex as gc

# ── 配置 ──────────────────────────────────────────────
APP_NAME = "华目眼镜管理系统"
DB_PATH = Path(os.environ.get("APPDATA", str(Path.home() / ".huamu"))) / "眼镜店管理系统" / "glasses_shop.db"

FRAME_BRANDS = ["暴龙", "帕莎", "雷朋", "陌森", "海伦凯勒", "川久保玲", "其他"]
LENS_TYPES = ["单光", "渐进多焦点", "防蓝光", "变色", "偏光", "抗疲劳", "驾驶型", "其他"]
CHANNELS = ["抖音", "美团", "大众点评", "小红书", "微信", "线下", "老客介绍", "其他"]
TAGS = ["高客单", "性价比", "镜片敏感", "时尚潮流", "功能需求", "儿童防控", "老年渐进"]
STATUSES = ["待取镜", "已取镜", "已结清", "欠款", "已取消"]
REMINDER_STATUSES = ["待处理", "已完成", "已取消"]

COLORS = {
    "bg": gc("#f5f7fb"),
    "panel": gc("#ffffff"),
    "glass": gc("#f8fbff"),
    "glass_active": gc("#eaf2ff"),
    "line": gc("#dbe4f0"),
    "text": gc("#172033"),
    "muted": gc("#667085"),
    "blue": gc("#007aff"),
    "blue_dark": gc("#0062cc"),
    "sidebar": gc("#edf4ff"),
    "sidebar_text": gc("#334155"),
    "accent_bg": gc("#007aff"),
    "accent_text": gc("#ffffff"),
    "header_bg": gc("#f1f6ff"),
    "row_even": gc("#f9fbfe"),
    "row_odd": gc("#ffffff"),
    "selected_row": gc("#d9ebff"),
}


def today() -> str:
    return date.today().isoformat()


def money(value) -> str:
    try:
        return f"{float(value or 0):.2f}"
    except (TypeError, ValueError):
        return "0.00"


def to_float(value, default=0.0) -> float:
    text = str(value or "").strip()
    if not text:
        return default
    return float(text)


def to_int_or_none(value):
    text = str(value or "").strip()
    if not text:
        return None
    return int(float(text))


# ── 数据库 ────────────────────────────────────────────
class Database:
    def __init__(self, path: Path = DB_PATH):
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.conn = sqlite3.connect(str(path))
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.row_factory = sqlite3.Row
        self._create_tables()
        self._migrate()

    def _create_tables(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS customers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                gender TEXT, age INTEGER, phone TEXT,
                source_channel TEXT, consumption_tag TEXT,
                last_visit_date TEXT, notes TEXT,
                created_at TEXT DEFAULT (datetime('now','localtime'))
            );
            CREATE TABLE IF NOT EXISTS prescriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id INTEGER NOT NULL,
                exam_date TEXT NOT NULL,
                od_sphere REAL, od_cylinder REAL, od_axis INTEGER, od_va REAL,
                os_sphere REAL, os_cylinder REAL, os_axis INTEGER, os_va REAL,
                pd REAL, ph REAL, add_power REAL, notes TEXT,
                created_at TEXT DEFAULT (datetime('now','localtime')),
                FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS purchases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id INTEGER NOT NULL,
                prescription_id INTEGER,
                frame_brand TEXT, frame_model TEXT, frame_name TEXT, frame_price REAL,
                lens_type TEXT, lens_brand TEXT, lens_model TEXT,
                lens_refractive_index TEXT, lens_price REAL,
                total_price REAL, paid REAL, balance REAL,
                purchase_date TEXT NOT NULL, pickup_date TEXT,
                status TEXT DEFAULT '待取镜', notes TEXT,
                created_at TEXT DEFAULT (datetime('now','localtime')),
                FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE,
                FOREIGN KEY (prescription_id) REFERENCES prescriptions(id) ON DELETE SET NULL
            );
            CREATE TABLE IF NOT EXISTS followup_reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id INTEGER NOT NULL,
                reminder_type TEXT NOT NULL,
                remind_date TEXT NOT NULL,
                status TEXT DEFAULT '待处理', notes TEXT,
                created_at TEXT DEFAULT (datetime('now','localtime')),
                FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE
            );
        """)
        self.conn.commit()

    def _migrate(self):
        expected = {
            "customers": ["source_channel", "consumption_tag", "last_visit_date", "notes"],
            "purchases": ["frame_brand", "frame_model", "lens_model", "lens_refractive_index"],
        }
        for table, cols in expected.items():
            existing = {row["name"] for row in self.conn.execute(f"PRAGMA table_info({table})")}
            for c in cols:
                if c not in existing:
                    self.conn.execute(f"ALTER TABLE {table} ADD COLUMN {c} TEXT")
        fixes = {"寰呭彇闀?": "待取镜", "寰呭鐞?": "待处理", "宸插彇娑?": "已取消"}
        for bad, good in fixes.items():
            self.conn.execute("UPDATE purchases SET status=? WHERE status=?", (good, bad))
            self.conn.execute("UPDATE followup_reminders SET status=? WHERE status=?", (good, bad))
        self.conn.commit()

    def rows(self, query, params=()):
        return self.conn.execute(query, params).fetchall()

    def row(self, query, params=()):
        return self.conn.execute(query, params).fetchone()

    def execute(self, query, params=()):
        cur = self.conn.execute(query, params)
        self.conn.commit()
        return cur

    def customers(self, keyword=""):
        kw = f"%{keyword.strip()}%"
        if keyword.strip():
            return self.rows(
                "SELECT * FROM customers WHERE name LIKE ? OR phone LIKE ? OR source_channel LIKE ? OR consumption_tag LIKE ? ORDER BY id DESC",
                (kw, kw, kw, kw),
            )
        return self.rows("SELECT * FROM customers ORDER BY id DESC")

    def save_customer(self, data, cid=None):
        vals = (data["name"], data["gender"], data["age"], data["phone"],
                data["source_channel"], data["consumption_tag"], data["last_visit_date"], data["notes"])
        if cid:
            self.execute("UPDATE customers SET name=?,gender=?,age=?,phone=?,source_channel=?,consumption_tag=?,last_visit_date=?,notes=? WHERE id=?",
                         vals + (cid,))
            return cid
        return self.execute("INSERT INTO customers(name,gender,age,phone,source_channel,consumption_tag,last_visit_date,notes) VALUES(?,?,?,?,?,?,?,?)", vals).lastrowid

    def delete_customer(self, cid):
        self.execute("DELETE FROM customers WHERE id=?", (cid,))

    def prescriptions(self, cid=None):
        base = "SELECT p.*,c.name customer_name FROM prescriptions p JOIN customers c ON c.id=p.customer_id"
        if cid:
            return self.rows(base + " WHERE p.customer_id=? ORDER BY exam_date DESC,id DESC", (cid,))
        return self.rows(base + " ORDER BY exam_date DESC,id DESC")

    def save_prescription(self, data):
        self.execute(
            "INSERT INTO prescriptions(customer_id,exam_date,od_sphere,od_cylinder,od_axis,od_va,os_sphere,os_cylinder,os_axis,os_va,pd,ph,add_power,notes) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (data["customer_id"], data["exam_date"], data["od_sphere"], data["od_cylinder"],
             data["od_axis"], data["od_va"], data["os_sphere"], data["os_cylinder"],
             data["os_axis"], data["os_va"], data["pd"], data["ph"], data["add_power"], data["notes"]))

    def purchases(self, cid=None):
        base = "SELECT p.*,c.name customer_name,c.phone FROM purchases p JOIN customers c ON c.id=p.customer_id"
        if cid:
            return self.rows(base + " WHERE p.customer_id=? ORDER BY p.purchase_date DESC,p.id DESC", (cid,))
        return self.rows(base + " ORDER BY p.purchase_date DESC,p.id DESC")

    def save_purchase(self, data):
        total = round(data["frame_price"] + data["lens_price"], 2)
        paid = data["paid"]
        balance = round(total - paid, 2)
        status = data["status"] or ("欠款" if balance > 0 else "待取镜")
        self.execute(
            "INSERT INTO purchases(customer_id,frame_brand,frame_model,frame_name,frame_price,lens_type,lens_brand,lens_model,lens_refractive_index,lens_price,total_price,paid,balance,purchase_date,pickup_date,status,notes) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (data["customer_id"], data["frame_brand"], data["frame_model"], data["frame_name"], data["frame_price"],
             data["lens_type"], data["lens_brand"], data["lens_model"], data["lens_refractive_index"],
             data["lens_price"], total, paid, balance, data["purchase_date"], data["pickup_date"], status, data["notes"]))
        self.execute("UPDATE customers SET last_visit_date=? WHERE id=?", (data["purchase_date"], data["customer_id"]))

    def reminders(self):
        return self.rows(
            "SELECT r.*,c.name customer_name FROM followup_reminders r JOIN customers c ON c.id=r.customer_id ORDER BY r.status='待处理' DESC,r.remind_date ASC")

    def add_reminder(self, cid, rtype, rdate, notes=""):
        self.execute("INSERT INTO followup_reminders(customer_id,reminder_type,remind_date,status,notes) VALUES(?,?,?,'待处理',?)", (cid, rtype, rdate, notes))

    def set_reminder_done(self, rid):
        self.execute("UPDATE followup_reminders SET status='已完成' WHERE id=?", (rid,))

    def stats(self):
        month = date.today().strftime("%Y-%m")
        revenue = self.row("SELECT COALESCE(SUM(total_price),0) v FROM purchases WHERE substr(purchase_date,1,7)=?", (month,))["v"]
        paid = self.row("SELECT COALESCE(SUM(paid),0) v FROM purchases WHERE substr(purchase_date,1,7)=?", (month,))["v"]
        customers = self.row("SELECT COUNT(*) v FROM customers")["v"]
        pending = self.row("SELECT COUNT(*) v FROM followup_reminders WHERE status='待处理'")["v"]
        unpaid = self.row("SELECT COALESCE(SUM(balance),0) v FROM purchases WHERE balance>0")["v"]
        return revenue, paid, customers, pending, unpaid

    def export_json(self):
        data = {}
        for table in ["customers", "prescriptions", "purchases", "followup_reminders"]:
            data[table] = [dict(row) for row in self.rows(f"SELECT * FROM {table} ORDER BY id")]
        data["exported_at"] = datetime.now().isoformat(timespec="seconds")
        return json.dumps(data, ensure_ascii=False, indent=2)

    def close(self):
        self.conn.close()


# ── Kivy 组件 ─────────────────────────────────────────
class RoundedButton(Button):
    """圆角按钮"""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.background_normal = ""
        self.background_color = (0, 0, 0, 0)
        self.bind(pos=self._update, size=self._update)

    def _update(self, *args):
        self.canvas.before.clear()
        with self.canvas.before:
            Color(rgba=COLORS["blue"])
            RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(8)])


class DataTableHeader(BoxLayout):
    def __init__(self, columns, widths, **kwargs):
        super().__init__(orientation="horizontal", size_hint_y=None, height=dp(40), **kwargs)
        with self.canvas.before:
            Color(rgba=COLORS["header_bg"])
            self.rect = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._upd, size=self._upd)
        for col, w in zip(columns, widths):
            lbl = Label(text=col, color=COLORS["muted"], bold=True, size_hint_x=w,
                        halign="center", valign="middle", font_size=sp(13))
            lbl.bind(size=lambda s, v: setattr(s, 'text_size', (v[0], None)))
            self.add_widget(lbl)

    def _upd(self, *a):
        self.rect.pos = self.pos
        self.rect.size = self.size


class DataTableRow(BoxLayout):
    def __init__(self, values, widths, is_header=False, **kwargs):
        super().__init__(orientation="horizontal", size_hint_y=None, height=dp(36), **kwargs)
        color = COLORS["panel"] if is_header else COLORS["row_even"]
        with self.canvas.before:
            Color(rgba=color)
            self.rect = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._upd, size=self._upd)
        for v, w in zip(values, widths):
            lbl = Label(text=str(v or ""), color=COLORS["text"], size_hint_x=w,
                        halign="center", valign="middle", font_size=sp(12),
                        shorten=True, text_size=(None, dp(34)))
            self.add_widget(lbl)

    def _upd(self, *a):
        self.rect.pos = self.pos
        self.rect.size = self.size


class DataTable(BoxLayout):
    """通用数据表格"""
    def __init__(self, columns, col_widths=None, **kwargs):
        super().__init__(orientation="vertical", **kwargs)
        self.columns = columns
        n = len(columns)
        self.col_widths = col_widths or [1.0 / n] * n
        with self.canvas.before:
            Color(rgba=COLORS["panel"])
            self.bg = Rectangle(pos=self.pos, size=self.size)
            Color(rgba=COLORS["line"])
            self.border = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(6)])
        self.bind(pos=self._upd, size=self._upd)

        self.header = DataTableHeader(columns, self.col_widths)
        self.add_widget(self.header)

        self.scroll = ScrollView(size_hint=(1, 1))
        self.body = BoxLayout(orientation="vertical", size_hint_y=None)
        self.body.bind(minimum_height=self.body.setter('height'))
        self.scroll.add_widget(self.body)
        self.add_widget(self.scroll)

    def _upd(self, *a):
        self.bg.pos = self.bg.size = self.border.pos = self.border.size = (0, 0, 0, 0)
        self.bg.pos = (self.pos[0] + dp(1), self.pos[1] + dp(1))
        self.bg.size = (self.size[0] - dp(2), self.size[1] - dp(2))
        self.border.pos = self.pos
        self.border.size = self.size

    def set_data(self, rows):
        self.body.clear_widgets()
        for i, row in enumerate(rows):
            self.body.add_widget(DataTableRow(row, self.col_widths))


class StatsCard(BoxLayout):
    def __init__(self, title, **kwargs):
        super().__init__(orientation="vertical", size_hint=(1, None), height=dp(90), padding=[dp(12), dp(10)], **kwargs)
        with self.canvas.before:
            Color(rgba=COLORS["panel"])
            self.bg = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(8)])
        self.bind(pos=self._upd, size=self._upd)
        self._title = Label(text=title, color=COLORS["muted"], size_hint_y=None, height=dp(22),
                            halign="left", valign="middle", font_size=sp(12))
        self._title.bind(size=lambda s, v: setattr(s, 'text_size', (v[0], None)))
        self.add_widget(self._title)
        self._value = Label(text="0", color=COLORS["text"], size_hint_y=None, height=dp(36),
                            bold=True, font_size=sp(22), halign="left", valign="middle")
        self._value.bind(size=lambda s, v: setattr(s, 'text_size', (v[0], None)))
        self.add_widget(self._value)

    def set_value(self, v):
        self._value.text = str(v)

    def _upd(self, *a):
        self.bg.pos = self.pos
        self.bg.size = self.size


# ── 屏幕 ──────────────────────────────────────────────
class DashboardScreen(Screen):
    def __init__(self, db, **kw):
        super().__init__(name="dashboard", **kw)
        self.db = db
        self.build()

    def build(self):
        root = BoxLayout(orientation="vertical", padding=[dp(14), dp(10)], spacing=dp(10))
        with root.canvas.before:
            Color(rgba=COLORS["bg"])
            Rectangle(pos=root.pos, size=root.size)
        root.bind(pos=lambda s, v: setattr(root.canvas.before.children[-1], 'pos', v))
        root.bind(size=lambda s, v: setattr(root.canvas.before.children[-1], 'size', v))

        # 标题
        hdr = BoxLayout(size_hint_y=None, height=dp(44))
        hdr.add_widget(Label(text="工作台", color=COLORS["text"], bold=True, font_size=sp(18),
                             halign="left", valign="middle", size_hint_x=0.7))
        hdr.add_widget(Label(text="", size_hint_x=0.3))
        root.add_widget(hdr)

        # 统计卡片
        self.stats_row = BoxLayout(size_hint_y=None, height=dp(100), spacing=dp(8))
        self.stat_cards = []
        for t in ["本月应收", "本月实收", "客户总数", "待处理提醒", "未收余额"]:
            card = StatsCard(t)
            self.stat_cards.append(card)
            self.stats_row.add_widget(card)
        root.add_widget(self.stats_row)

        # 最近销售
        root.add_widget(Label(text="最近销售", color=COLORS["text"], bold=True, font_size=sp(14),
                              halign="left", valign="middle", size_hint_y=None, height=dp(30)))
        self.sales_table = DataTable(["日期", "客户", "项目", "金额", "状态"],
                                     [0.22, 0.20, 0.26, 0.16, 0.16])
        root.add_widget(self.sales_table)

        # 回访提醒
        root.add_widget(Label(text="回访提醒", color=COLORS["text"], bold=True, font_size=sp(14),
                              halign="left", valign="middle", size_hint_y=None, height=dp(30)))
        self.reminder_table = DataTable(["日期", "客户", "类型", "状态"],
                                        [0.25, 0.25, 0.25, 0.25])
        root.add_widget(self.reminder_table)

        self.add_widget(root)

    def on_enter(self):
        self.refresh()

    def refresh(self):
        revenue, paid, customers, pending, unpaid = self.db.stats()
        vals = [money(revenue), money(paid), customers, pending, money(unpaid)]
        for card, v in zip(self.stat_cards, vals):
            card.set_value(v)

        sales_data = []
        for row in self.db.purchases()[:12]:
            item = f"{row['frame_brand'] or row['frame_name'] or ''} / {row['lens_type'] or ''}"
            sales_data.append((row["purchase_date"], row["customer_name"], item, money(row["total_price"]), row["status"]))
        self.sales_table.set_data(sales_data)

        rem_data = []
        for row in self.db.reminders()[:12]:
            rem_data.append((row["remind_date"], row["customer_name"], row["reminder_type"], row["status"]))
        self.reminder_table.set_data(rem_data)


class CustomersScreen(Screen):
    def __init__(self, db, **kw):
        super().__init__(name="customers", **kw)
        self.db = db
        self.build()

    def build(self):
        root = BoxLayout(orientation="vertical", padding=[dp(14), dp(10)], spacing=dp(10))
        with root.canvas.before:
            Color(rgba=COLORS["bg"])
            Rectangle(pos=root.pos, size=root.size)

        hdr = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(8))
        hdr.add_widget(Label(text="客户管理", color=COLORS["text"], bold=True, font_size=sp(18),
                             halign="left", valign="middle", size_hint_x=0.5))
        self.search_input = TextInput(hint_text="搜索姓名/电话/来源...", multiline=False,
                                       size_hint_x=0.3, size_hint_y=None, height=dp(36),
                                       background_color=COLORS["panel"],
                                       foreground_color=COLORS["text"],
                                       cursor_color=COLORS["blue"],
                                       font_size=sp(13))
        self.search_input.bind(text=lambda s, v: self.refresh())
        hdr.add_widget(self.search_input)
        btn_add = Button(text="+ 新增客户", size_hint_x=0.2, size_hint_y=None, height=dp(36),
                         background_normal="", background_color=COLORS["blue"],
                         color=COLORS["accent_text"], font_size=sp(13))
        btn_add.bind(on_release=lambda x: self._open_dialog(None))
        hdr.add_widget(btn_add)
        root.add_widget(hdr)

        self.table = DataTable(["ID", "姓名", "性别", "年龄", "电话", "来源", "标签", "最近到店"],
                               [0.06, 0.14, 0.08, 0.07, 0.18, 0.12, 0.15, 0.20])
        root.add_widget(self.table)

        self.add_widget(root)

    def on_enter(self):
        self.refresh()

    def refresh(self):
        kw = self.search_input.text if hasattr(self, 'search_input') else ""
        data = []
        for row in self.db.customers(kw):
            data.append((row["id"], row["name"], row["gender"] or "", row["age"] or "",
                         row["phone"] or "", row["source_channel"] or "",
                         row["consumption_tag"] or "", row["last_visit_date"] or ""))
        self.table.set_data(data)

    def _open_dialog(self, row):
        content = CustomerForm(self.db, row)
        popup = Popup(title="编辑客户" if row else "新增客户", content=content,
                      size_hint=(0.9, 0.9), background_color=COLORS["panel"],
                      title_color=COLORS["text"], title_size=sp(16))
        content.popup = popup
        content.callback = self.refresh
        popup.open()


class PrescriptionsScreen(Screen):
    def __init__(self, db, **kw):
        super().__init__(name="prescriptions", **kw)
        self.db = db
        self.build()

    def build(self):
        root = BoxLayout(orientation="vertical", padding=[dp(14), dp(10)], spacing=dp(10))
        with root.canvas.before:
            Color(rgba=COLORS["bg"])
            Rectangle(pos=root.pos, size=root.size)

        hdr = BoxLayout(size_hint_y=None, height=dp(44))
        hdr.add_widget(Label(text="验光记录", color=COLORS["text"], bold=True, font_size=sp(18),
                             halign="left", valign="middle", size_hint_x=0.7))
        btn = Button(text="+ 新增验光", size_hint_x=0.3, size_hint_y=None, height=dp(36),
                     background_color=COLORS["blue"], background_normal="",
                     color=COLORS["accent_text"], font_size=sp(13))
        btn.bind(on_release=lambda x: self._open_dialog())
        hdr.add_widget(btn)
        root.add_widget(hdr)

        self.table = DataTable(["日期", "客户", "右眼S", "右眼C", "右眼轴", "左眼S", "左眼C", "左眼轴", "瞳距", "备注"],
                               [0.12, 0.12, 0.10, 0.10, 0.08, 0.10, 0.10, 0.08, 0.08, 0.12])
        root.add_widget(self.table)
        self.add_widget(root)

    def on_enter(self):
        self.refresh()

    def refresh(self):
        data = []
        for r in self.db.prescriptions():
            data.append((r["exam_date"], r["customer_name"],
                         money(r["od_sphere"]) if r["od_sphere"] is not None else "",
                         money(r["od_cylinder"]) if r["od_cylinder"] is not None else "",
                         r["od_axis"] or "", money(r["os_sphere"]) if r["os_sphere"] is not None else "",
                         money(r["os_cylinder"]) if r["os_cylinder"] is not None else "",
                         r["os_axis"] or "", r["pd"] or "", (r["notes"] or "")[:16]))
        self.table.set_data(data)

    def _open_dialog(self):
        content = PrescriptionForm(self.db)
        popup = Popup(title="新增验光", content=content, size_hint=(0.9, 0.9),
                      background_color=COLORS["panel"], title_color=COLORS["text"], title_size=sp(16))
        content.popup = popup
        content.callback = self.refresh
        popup.open()


class SalesScreen(Screen):
    def __init__(self, db, **kw):
        super().__init__(name="sales", **kw)
        self.db = db
        self.build()

    def build(self):
        root = BoxLayout(orientation="vertical", padding=[dp(14), dp(10)], spacing=dp(10))
        with root.canvas.before:
            Color(rgba=COLORS["bg"])
            Rectangle(pos=root.pos, size=root.size)

        hdr = BoxLayout(size_hint_y=None, height=dp(44))
        hdr.add_widget(Label(text="销售记录", color=COLORS["text"], bold=True, font_size=sp(18),
                             halign="left", valign="middle", size_hint_x=0.7))
        btn = Button(text="+ 新增销售", size_hint_x=0.3, size_hint_y=None, height=dp(36),
                     background_color=COLORS["blue"], background_normal="",
                     color=COLORS["accent_text"], font_size=sp(13))
        btn.bind(on_release=lambda x: self._open_dialog())
        hdr.add_widget(btn)
        root.add_widget(hdr)

        self.table = DataTable(["日期", "客户", "电话", "镜架", "镜片", "总价", "已付", "余额", "状态"],
                               [0.11, 0.12, 0.13, 0.11, 0.11, 0.09, 0.09, 0.09, 0.10])
        root.add_widget(self.table)
        self.add_widget(root)

    def on_enter(self):
        self.refresh()

    def refresh(self):
        data = []
        for r in self.db.purchases():
            data.append((r["purchase_date"], r["customer_name"], r["phone"] or "",
                         r["frame_brand"] or r["frame_name"] or "", r["lens_type"] or "",
                         money(r["total_price"]), money(r["paid"]), money(r["balance"]), r["status"]))
        self.table.set_data(data)

    def _open_dialog(self):
        content = SaleForm(self.db)
        popup = Popup(title="快速开单", content=content, size_hint=(0.92, 0.92),
                      background_color=COLORS["panel"], title_color=COLORS["text"], title_size=sp(16))
        content.popup = popup
        content.callback = self.refresh
        popup.open()


class SettingsScreen(Screen):
    def __init__(self, db, **kw):
        super().__init__(name="settings", **kw)
        self.db = db
        self.build()

    def build(self):
        root = BoxLayout(orientation="vertical", padding=[dp(14), dp(10)], spacing=dp(12))
        with root.canvas.before:
            Color(rgba=COLORS["bg"])
            Rectangle(pos=root.pos, size=root.size)

        root.add_widget(Label(text="设置", color=COLORS["text"], bold=True, font_size=sp(18),
                              halign="left", valign="middle", size_hint_y=None, height=dp(40)))

        card = BoxLayout(orientation="vertical", size_hint_y=None, height=dp(180),
                         padding=[dp(16), dp(14)], spacing=dp(10))
        with card.canvas.before:
            Color(rgba=COLORS["panel"])
            RoundedRectangle(pos=card.pos, size=card.size, radius=[dp(8)])
        card.bind(pos=lambda s, v: setattr(card.canvas.before.children[-1], 'pos', v))
        card.bind(size=lambda s, v: setattr(card.canvas.before.children[-1], 'size', v))

        card.add_widget(Label(text="数据维护", color=COLORS["text"], bold=True, font_size=sp(14),
                              halign="left", valign="middle", size_hint_y=None, height=dp(30)))

        btn_row = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(8))
        btn1 = Button(text="导出 JSON", background_color=COLORS["blue"], background_normal="",
                      color=COLORS["accent_text"], font_size=sp(13))
        btn1.bind(on_release=lambda x: self._export_json())
        btn2 = Button(text="导出客户 CSV", background_color=COLORS["blue"], background_normal="",
                      color=COLORS["accent_text"], font_size=sp(13))
        btn2.bind(on_release=lambda x: self._export_csv())
        btn_row.add_widget(btn1)
        btn_row.add_widget(btn2)
        card.add_widget(btn_row)

        card.add_widget(Label(text=f"数据库位置：{DB_PATH}", color=COLORS["muted"],
                              font_size=sp(11), halign="left", valign="middle",
                              size_hint_y=None, height=dp(30)))
        root.add_widget(card)
        self.add_widget(root)

    def _get_export_dir(self):
        """跨平台获取下载目录"""
        try:
            from android.storage import primary_external_storage_path
            return Path(primary_external_storage_path()) / "Download"
        except ImportError:
            return Path.home() / "Downloads"

    def _export_json(self):
        path = self._get_export_dir() / f"华目眼镜备份_{today()}.json"
        path.write_text(self.db.export_json(), encoding="utf-8")
        self._toast(f"已导出到 {path}")

    def _export_csv(self):
        path = self._get_export_dir() / f"客户列表_{today()}.csv"
        with open(str(path), "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(["ID", "姓名", "性别", "年龄", "电话", "来源", "标签", "最近到店", "备注"])
            for r in self.db.customers():
                writer.writerow([r["id"], r["name"], r["gender"], r["age"], r["phone"],
                                 r["source_channel"], r["consumption_tag"], r["last_visit_date"], r["notes"]])
        self._toast(f"已导出到 {path}")

    def _toast(self, msg):
        try:
            from kivy.uix.toast import Toast
            Toast().show(msg)
        except:
            pass


# ── 表单 ──────────────────────────────────────────────
class FormField(BoxLayout):
    def __init__(self, label, values=None, default="", is_spinner=False, **kw):
        super().__init__(orientation="vertical", size_hint_y=None, height=dp(68), spacing=dp(3), **kw)
        self.add_widget(Label(text=label, color=COLORS["muted"], font_size=sp(12),
                              halign="left", valign="middle", size_hint_y=None, height=dp(20)))
        if values:
            self.input = Spinner(text=str(default) if default else values[0], values=values,
                                 background_color=COLORS["panel"], color=COLORS["text"],
                                 size_hint_y=None, height=dp(36), font_size=sp(13))
        else:
            self.input = TextInput(text=str(default) if default else "", multiline=False,
                                   background_color=COLORS["panel"], foreground_color=COLORS["text"],
                                   cursor_color=COLORS["blue"], size_hint_y=None, height=dp(36),
                                   font_size=sp(13))
        self.add_widget(self.input)


class CustomerForm(ScrollView):
    def __init__(self, db, row=None, **kw):
        super().__init__(**kw)
        self.db = db
        self.row = row
        self.popup = None
        self.callback = None

        body = BoxLayout(orientation="vertical", size_hint_y=None, padding=[dp(8), dp(4)], spacing=dp(4))
        body.bind(minimum_height=body.setter('height'))

        self.fields = {}
        for label, key, vals in [("姓名", "name", None), ("性别", "gender", ["男", "女", ""]),
                                  ("年龄", "age", None), ("电话", "phone", None),
                                  ("来源", "source_channel", CHANNELS), ("标签", "consumption_tag", TAGS),
                                  ("最近到店", "last_visit_date", None)]:
            default = row[key] if row else ""
            f = FormField(label, vals, str(default) if default is not None else "")
            self.fields[key] = f
            body.add_widget(f)

        body.add_widget(Label(text="备注", color=COLORS["muted"], font_size=sp(12),
                              halign="left", valign="middle", size_hint_y=None, height=dp(20)))
        self.notes = TextInput(text=row["notes"] if row else "", multiline=True,
                               background_color=COLORS["panel"], foreground_color=COLORS["text"],
                               cursor_color=COLORS["blue"], size_hint_y=None, height=dp(80), font_size=sp(13))
        body.add_widget(self.notes)

        # 按钮
        btn_row = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(8))
        btn_cancel = Button(text="取消", background_color=gc("#ccc"), background_normal="",
                            color=COLORS["text"], font_size=sp(13))
        btn_cancel.bind(on_release=lambda x: self.popup.dismiss() if self.popup else None)
        btn_save = Button(text="保存", background_color=COLORS["blue"], background_normal="",
                          color=COLORS["accent_text"], font_size=sp(13))
        btn_save.bind(on_release=lambda x: self._save())
        btn_row.add_widget(btn_cancel)
        btn_row.add_widget(btn_save)
        body.add_widget(btn_row)

        self.add_widget(body)

    def _save(self):
        try:
            name = self.fields["name"].input.text.strip()
            if not name:
                return
            data = {k: v.input.text.strip() for k, v in self.fields.items()}
            data["age"] = to_int_or_none(data["age"])
            data["notes"] = self.notes.text.strip()
            self.db.save_customer(data, self.row["id"] if self.row else None)
            self.popup.dismiss()
            if self.callback:
                self.callback()
        except Exception as e:
            pass


class PrescriptionForm(ScrollView):
    def __init__(self, db, **kw):
        super().__init__(**kw)
        self.db = db
        self.popup = None
        self.callback = None

        body = BoxLayout(orientation="vertical", size_hint_y=None, padding=[dp(8), dp(4)], spacing=dp(4))
        body.bind(minimum_height=body.setter('height'))

        # 选择客户
        body.add_widget(Label(text="选择客户", color=COLORS["muted"], font_size=sp(12), halign="left", valign="middle", size_hint_y=None, height=dp(20)))
        self.customer_spinner = Spinner(text="请选择客户", values=[], background_color=COLORS["panel"], color=COLORS["text"], size_hint_y=None, height=dp(36), font_size=sp(13))
        customers = self.db.customers()
        self.customer_map = {}
        for c in customers:
            label = f"{c['id']} - {c['name']}"
            self.customer_map[label] = c["id"]
            self.customer_spinner.values.append(label)
        body.add_widget(self.customer_spinner)

        self.fields = {}
        for label, key in [("验光日期", "exam_date"), ("右眼球镜", "od_sphere"), ("右眼柱镜", "od_cylinder"),
                            ("右眼轴位", "od_axis"), ("右眼视力", "od_va"), ("左眼球镜", "os_sphere"),
                            ("左眼柱镜", "os_cylinder"), ("左眼轴位", "os_axis"), ("左眼视力", "os_va"),
                            ("瞳距", "pd"), ("瞳高", "ph"), ("ADD", "add_power")]:
            default = today() if key == "exam_date" else ""
            f = FormField(label, None, default)
            self.fields[key] = f
            body.add_widget(f)

        body.add_widget(Label(text="备注", color=COLORS["muted"], font_size=sp(12), halign="left", valign="middle", size_hint_y=None, height=dp(20)))
        self.notes = TextInput(text="", multiline=True, background_color=COLORS["panel"], foreground_color=COLORS["text"], cursor_color=COLORS["blue"], size_hint_y=None, height=dp(60), font_size=sp(13))
        body.add_widget(self.notes)

        btn_row = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(8))
        btn_cancel = Button(text="取消", background_color=gc("#ccc"), background_normal="", color=COLORS["text"], font_size=sp(13))
        btn_cancel.bind(on_release=lambda x: self.popup.dismiss() if self.popup else None)
        btn_save = Button(text="保存", background_color=COLORS["blue"], background_normal="", color=COLORS["accent_text"], font_size=sp(13))
        btn_save.bind(on_release=lambda x: self._save())
        btn_row.add_widget(btn_cancel)
        btn_row.add_widget(btn_save)
        body.add_widget(btn_row)

        self.add_widget(body)

    def _save(self):
        try:
            sel = self.customer_spinner.text
            if sel not in self.customer_map:
                return
            data = {"customer_id": self.customer_map[sel], "notes": self.notes.text.strip()}
            for key, f in self.fields.items():
                val = f.input.text.strip()
                if key == "exam_date":
                    data[key] = val or today()
                elif key.endswith("axis"):
                    data[key] = to_int_or_none(val)
                elif key.endswith("ph"):
                    data[key] = to_float(val, None) if val else None
                else:
                    data[key] = to_float(val, None) if val else None
            self.db.save_prescription(data)
            self.popup.dismiss()
            if self.callback:
                self.callback()
        except Exception as e:
            pass


class SaleForm(ScrollView):
    def __init__(self, db, **kw):
        super().__init__(**kw)
        self.db = db
        self.popup = None
        self.callback = None

        body = BoxLayout(orientation="vertical", size_hint_y=None, padding=[dp(8), dp(4)], spacing=dp(4))
        body.bind(minimum_height=body.setter('height'))

        body.add_widget(Label(text="选择客户", color=COLORS["muted"], font_size=sp(12), halign="left", valign="middle", size_hint_y=None, height=dp(20)))
        self.customer_spinner = Spinner(text="请选择客户", values=[], background_color=COLORS["panel"], color=COLORS["text"], size_hint_y=None, height=dp(36), font_size=sp(13))
        self.customer_map = {}
        for c in self.db.customers():
            label = f"{c['id']} - {c['name']}"
            self.customer_map[label] = c["id"]
            self.customer_spinner.values.append(label)
        body.add_widget(self.customer_spinner)

        self.fields = {}
        pick_date = (date.today() + timedelta(days=7)).isoformat()
        for label, key, vals, default in [
            ("销售日期", "purchase_date", None, today()),
            ("取镜日期", "pickup_date", None, pick_date),
            ("镜架品牌", "frame_brand", FRAME_BRANDS, ""),
            ("镜架型号", "frame_model", None, ""),
            ("镜架名称", "frame_name", None, ""),
            ("镜架价格", "frame_price", None, "0"),
            ("镜片类型", "lens_type", LENS_TYPES, ""),
            ("镜片品牌", "lens_brand", None, ""),
            ("镜片型号", "lens_model", None, ""),
            ("折射率", "lens_refractive_index", ["1.56", "1.60", "1.67", "1.74"], ""),
            ("镜片价格", "lens_price", None, "0"),
            ("已收金额", "paid", None, "0"),
            ("状态", "status", STATUSES, "待取镜"),
        ]:
            f = FormField(label, vals, default)
            self.fields[key] = f
            body.add_widget(f)

        body.add_widget(Label(text="备注", color=COLORS["muted"], font_size=sp(12), halign="left", valign="middle", size_hint_y=None, height=dp(20)))
        self.notes = TextInput(text="", multiline=True, background_color=COLORS["panel"], foreground_color=COLORS["text"], cursor_color=COLORS["blue"], size_hint_y=None, height=dp(60), font_size=sp(13))
        body.add_widget(self.notes)

        btn_row = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(8))
        btn_cancel = Button(text="取消", background_color=gc("#ccc"), background_normal="", color=COLORS["text"], font_size=sp(13))
        btn_cancel.bind(on_release=lambda x: self.popup.dismiss() if self.popup else None)
        btn_save = Button(text="保存", background_color=COLORS["blue"], background_normal="", color=COLORS["accent_text"], font_size=sp(13))
        btn_save.bind(on_release=lambda x: self._save())
        btn_row.add_widget(btn_cancel)
        btn_row.add_widget(btn_save)
        body.add_widget(btn_row)

        self.add_widget(body)

    def _save(self):
        try:
            sel = self.customer_spinner.text
            if sel not in self.customer_map:
                return
            data = {"customer_id": self.customer_map[sel], "notes": self.notes.text.strip()}
            for key, f in self.fields.items():
                data[key] = f.input.text.strip()
            for k in ["frame_price", "lens_price", "paid"]:
                data[k] = to_float(data[k])
            self.db.save_purchase(data)
            self.popup.dismiss()
            if self.callback:
                self.callback()
        except Exception:
            pass


# ── 侧边栏导航 ────────────────────────────────────────
class Sidebar(BoxLayout):
    def __init__(self, screen_manager, **kw):
        super().__init__(orientation="vertical", size_hint=(None, 1), width=dp(180), **kw)
        self.sm = screen_manager
        with self.canvas.before:
            Color(rgba=COLORS["sidebar"])
            Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._upd, size=self._upd)
        self.buttons = {}

        self.add_widget(Label(text="华目眼镜", color=COLORS["text"], bold=True,
                              font_size=sp(16), halign="left", valign="middle",
                              size_hint_y=None, height=dp(50), padding=[dp(14), 0]))
        self.add_widget(Label(text="门店管理", color=COLORS["muted"], font_size=sp(11),
                              halign="left", valign="middle", size_hint_y=None,
                              height=dp(24), padding=[dp(16), 0]))

        for name in ["工作台", "客户", "验光", "销售", "设置"]:
            btn = Button(text=name, background_normal="", background_color=COLORS["sidebar"],
                         color=COLORS["sidebar_text"], font_size=sp(13),
                         halign="left", valign="middle", size_hint_y=None, height=dp(44))
            btn.bind(on_release=lambda x, n=name: self._switch(n))
            self.buttons[name] = btn
            self.add_widget(btn)

        self._highlight("工作台")

    def _upd(self, *a):
        self.canvas.before.children[-1].pos = self.pos
        self.canvas.before.children[-1].size = self.size

    def _switch(self, name):
        self._highlight(name)
        scr_map = {"工作台": "dashboard", "客户": "customers", "验光": "prescriptions", "销售": "sales", "设置": "settings"}
        self.sm.current = scr_map[name]

    def _highlight(self, active):
        for name, btn in self.buttons.items():
            if name == active:
                btn.background_color = COLORS["glass_active"]
                btn.color = COLORS["blue"]
                btn.bold = True
            else:
                btn.background_color = COLORS["sidebar"]
                btn.color = COLORS["sidebar_text"]
                btn.bold = False


# ── 主应用 ────────────────────────────────────────────
class HuamuApp(App):
    def build(self):
        self.title = APP_NAME
        self.db = Database()

        root = BoxLayout(orientation="horizontal")
        self.sm = ScreenManager(transition=SlideTransition())

        self.sm.add_widget(DashboardScreen(self.db))
        self.sm.add_widget(CustomersScreen(self.db))
        self.sm.add_widget(PrescriptionsScreen(self.db))
        self.sm.add_widget(SalesScreen(self.db))
        self.sm.add_widget(SettingsScreen(self.db))

        sidebar = Sidebar(self.sm)
        root.add_widget(sidebar)
        root.add_widget(self.sm)
        return root

    def on_stop(self):
        self.db.close()


if __name__ == "__main__":
    HuamuApp().run()
