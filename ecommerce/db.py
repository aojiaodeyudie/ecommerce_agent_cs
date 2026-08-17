# -*- coding: utf-8 -*-
"""
电商客服 SQLite 数据层
======================
建表 + 种子数据，提供统一的数据访问接口。
所有表结构见 _SCHEMA；种子数据集中在 _SEED_* 中，便于替换为真实业务数据。

表：
  products   商品表     （商品参数/价格/库存）
  orders     订单表     （订单状态/金额/收货地址）
  logistics  物流表     （物流轨迹）
  coupons    优惠券表   （满减券）
  tickets    工单表     （转人工记录）
  sessions   会话表     （对话历史 + 槽位状态，替代 session_state）
"""
import json
import os
import re
import sqlite3
import uuid
from datetime import datetime, timedelta

from utils.config_handler import ecommerce_config
from utils.path_tool import get_abs_path
from utils.logger_handler import logger


def _extract_terms(text: str) -> list[str]:
    """从文本中提取候选关键词（按标点/空白切分，保留长度>=2的片段）。"""
    parts = re.split(r"[\s，。？！、,.!?;；:：()（）「」\"'']+", text)
    return [p for p in parts if len(p) >= 2]

# ---------------------------------------------------------------- schema

_SCHEMA = """
CREATE TABLE IF NOT EXISTS products (
    product_id  TEXT PRIMARY KEY,
    shop_id     TEXT NOT NULL DEFAULT 'shop_b',  -- 所属商家（ai=全店/智能客服兜底）
    name        TEXT NOT NULL,
    category    TEXT NOT NULL,
    price       REAL NOT NULL,
    specs       TEXT NOT NULL,          -- JSON 字符串：{续航, 吸力, 水箱...}
    stock       INTEGER NOT NULL,
    description TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS orders (
    order_id   TEXT PRIMARY KEY,
    user_id    TEXT NOT NULL,
    product_id TEXT NOT NULL,
    quantity   INTEGER NOT NULL,
    amount     REAL NOT NULL,
    status     TEXT NOT NULL,           -- pending_payment/paid/shipped/delivered/refunding/refunded/cancelled
    address    TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS logistics (
    tracking_no TEXT PRIMARY KEY,
    order_id    TEXT NOT NULL,
    carrier     TEXT NOT NULL,
    status      TEXT NOT NULL,          -- in_transit/delivered/exception
    trace_json  TEXT NOT NULL           -- JSON 数组：[{time, location, desc}]
);

CREATE TABLE IF NOT EXISTS coupons (
    coupon_id TEXT PRIMARY KEY,
    user_id   TEXT NOT NULL,
    title     TEXT NOT NULL,
    threshold REAL NOT NULL,            -- 满 X 元可用
    discount  REAL NOT NULL,            -- 减 Y 元
    expire_at TEXT NOT NULL,
    used      INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS tickets (
    ticket_id      TEXT PRIMARY KEY,
    session_id     TEXT,
    user_id        TEXT,
    reason         TEXT NOT NULL,
    status         TEXT DEFAULT 'open', -- open/processing/resolved
    transcript_json TEXT DEFAULT '[]',
    created_at     TEXT NOT NULL,
    deleted        INTEGER DEFAULT 0     -- 软删除标记（1=已删除）
);

CREATE TABLE IF NOT EXISTS sessions (
    session_id    TEXT PRIMARY KEY,
    user_id       TEXT,
    messages_json TEXT DEFAULT '[]',
    slots_json    TEXT DEFAULT '{}',
    updated_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS faq (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    question TEXT NOT NULL,             -- 标准问题
    answer   TEXT NOT NULL,             -- 标准答案
    keywords TEXT DEFAULT '',           -- 命中关键词（逗号分隔，用于模糊匹配）
    category TEXT DEFAULT 'general'     -- 分类：shipping/order/refund/invoice/coupon/payment/service/warranty/account
);
"""

# ---------------------------------------------------------------- seed data

# 商品种子（#F9 按商家拆分：shop_a~shop_f；ai=智能客服可查全部）
# (product_id, shop_id, name, category, price, specs, stock, description)
_SEED_PRODUCTS = [
    # ---- 星辉数码旗舰店（shop_a）----
    ("PA01", "shop_a", "星辉 S10 智能手机", "手机", 2999,
     {"屏幕": "6.7英寸OLED", "存储": "12+256G", "电池": "5000mAh", "快充": "80W"},
     120, "骁龙8系旗舰芯，1亿像素主摄"),
    ("PA02", "shop_a", "星辉 Note 千元机", "手机", 1299,
     {"屏幕": "6.5英寸LCD", "存储": "8+128G", "电池": "5000mAh"},
     200, "长续航千元机，长辈模式"),
    ("PA03", "shop_a", "轻羽 Air 轻薄本", "笔记本电脑", 4999,
     {"屏幕": "14英寸2.8K", "重量": "1.3kg", "存储": "16+512G", "续航": "12小时"},
     60, "金属机身，办公学习首选"),
    ("PA04", "shop_a", "疾风 T9 游戏本", "笔记本电脑", 7999,
     {"屏幕": "16英寸165Hz", "显卡": "RTX4060", "存储": "16+1T", "散热": "双风扇"},
     40, "电竞级性能，高刷屏"),
    ("PA05", "shop_a", "声浪 Pro 降噪耳机", "蓝牙耳机", 599,
     {"降噪": "主动降噪-45dB", "续航": "32小时", "连接": "蓝牙5.3"},
     300, "旗舰降噪，通勤利器"),
    ("PA06", "shop_a", "声浪 Lite 无线耳机", "蓝牙耳机", 199,
     {"续航": "24小时", "连接": "蓝牙5.2", "防水": "IPX4"},
     500, "百元性价比之选"),
    ("PA07", "shop_a", "慧眼 4K 运动相机", "数码配件", 1599,
     {"画质": "4K60fps", "防抖": "电子防抖", "防水": "10米"},
     80, "户外记录，Vlog 神器"),
    ("PA08", "shop_a", "闪充 65W 充电器", "数码配件", 129,
     {"功率": "65W", "接口": "双Type-C", "协议": "PD/QC"},
     1000, "氮化镓小体积，多设备通用"),
    ("PA09", "shop_a", "星辉 Pad 平板", "平板电脑", 2199,
     {"屏幕": "11英寸2K", "存储": "8+256G", "电池": "8000mAh"},
     90, "影音学习，手写笔支持"),
    ("PA10", "shop_a", "星辉 Watch 智能手表", "智能穿戴", 899,
     {"屏幕": "1.43英寸AMOLED", "续航": "14天", "防水": "5ATM"},
     150, "健康监测，运动模式丰富"),

    # ---- 蓝鲸家电专卖店（shop_b）----
    ("P001", "shop_b", "X30 扫地机器人", "扫地机器人", 3299,
     {"续航": "180分钟", "吸力": "5000Pa", "水箱": "电控水箱300ml", "导航": "激光雷达", "拖地": "支持"},
     50, "旗舰款扫拖一体，自动集尘+自清洁基站"),
    ("P002", "shop_b", "X20 Pro 扫拖一体机", "扫地机器人", 2599,
     {"续航": "150分钟", "吸力": "4000Pa", "水箱": "电控水箱250ml", "导航": "LDS激光", "拖地": "支持"},
     80, "高性价比扫拖一体，支持自动回充续扫"),
    ("P003", "shop_b", "V11 手持无线吸尘器", "吸尘器", 1499,
     {"续航": "60分钟", "吸力": "23000Pa", "尘杯": "0.6L", "重量": "1.5kg"},
     120, "轻量手持，吸拖一体，宠物毛发克星"),
    ("P004", "shop_b", "A5 空气净化器", "空气净化器", 1899,
     {"适用面积": "60㎡", "CADR": "500m³/h", "滤网": "HEPA13", "噪音": "≤35dB"},
     60, "除甲醛除PM2.5，卧室级静音"),
    ("P007", "shop_b", "智能指纹门锁", "智能家居", 1099,
     {"开锁方式": "指纹/密码/钥匙/APP", "锁体": "C级锁芯", "供电": "8节5号电池"},
     90, "半导体指纹，虚位密码防偷窥"),
    ("PB01", "shop_b", "蓝鲸 1.5匹 变频空调", "空调", 3299,
     {"匹数": "1.5匹", "能效": "新一级", "噪音": "18dB", "功能": "自清洁/除菌"},
     45, "全直流变频，冷暖两用"),
    ("PB02", "shop_b", "蓝鲸 风冷无霜冰箱", "冰箱", 3999,
     {"容量": "520L", "能效": "一级", "制冷": "风冷无霜", "分区": "干湿分储"},
     35, "大容量对开门，智能控温"),
    ("PB03", "shop_b", "蓝鲸 10kg 滚筒洗衣机", "洗衣机", 2599,
     {"容量": "10kg", "转速": "1400转", "功能": "除菌洗/空气洗", "能效": "一级"},
     55, "变频静音，除菌洗护"),
    ("PB04", "shop_b", "蓝鲸 侧吸油烟机", "烟机灶具", 1799,
     {"风量": "22m³/min", "风压": "450Pa", "噪音": "52dB", "自清洁": "热除油"},
     40, "大吸力侧吸，免拆洗"),
    ("PB05", "shop_b", "蓝鲸 60L 电热水器", "热水器", 1299,
     {"容量": "60L", "功率": "3000W", "能效": "一级", "安全": "防电墙"},
     70, "速热大水量，一级能效"),

    # ---- 云端生活馆（shop_c）----
    ("P005", "shop_c", "4L 智能电饭煲", "厨房电器", 399,
     {"容量": "4L", "功率": "860W", "功能": "柴火饭/粥/蛋糕", "内胆": "不粘涂层"},
     200, "3-6人适用，24小时预约"),
    ("P006", "shop_c", "破壁机 1.75L", "厨房电器", 599,
     {"容量": "1.75L", "功率": "1200W", "转速": "35000转/分", "杯体": "高硼硅玻璃"},
     150, "豆浆/米糊/冰沙/辅食，静音罩设计"),
    ("P008", "shop_c", "即热式饮水机", "厨房电器", 799,
     {"水温": "常温/45/65/85/100℃", "水箱": "3L", "出水量": "200ml/500ml"},
     70, "3秒即热，童锁保护，台式免安装"),
    ("PC01", "shop_c", "云朵 5L 空气炸锅", "厨房电器", 499,
     {"容量": "5L", "功率": "1500W", "控温": "80-200℃", "内胆": "不粘涂层"},
     180, "无油低脂，可视大窗"),
    ("PC02", "shop_c", "云端 多功能料理锅", "厨房电器", 699,
     {"容量": "4L", "功率": "1600W", "烤盘": "深锅+煎盘", "控温": "无级调温"},
     100, "一锅多用，火锅烤肉两不误"),
    ("PC03", "shop_c", "轻饮 胶囊咖啡机", "咖啡器具", 899,
     {"水箱": "1.2L", "压力": "19Bar", "功率": "1350W", "功能": "7档杯量"},
     90, "一键萃取，办公室优选"),
    ("PC04", "shop_c", "暖阳 电热烧水壶", "厨房电器", 129,
     {"容量": "1.7L", "功率": "1800W", "材质": "316不锈钢", "防烫": "双层"},
     400, "食品级不锈钢，烧水快"),
    ("PC05", "shop_c", "云磨 豆浆机", "厨房电器", 329,
     {"容量": "1.2L", "功率": "800W", "功能": "豆浆/米糊/果蔬", "免滤": "免过滤"},
     160, "破壁免滤，静音低噪"),
    ("PC06", "shop_c", "小鲜 电蒸锅", "厨房电器", 269,
     {"容量": "10L双层", "功率": "900W", "功能": "蒸煮/保温", "材质": "食品级PP"},
     130, "大容量双层，早餐神器"),

    # ---- 绿野家居旗舰店（shop_d）----
    ("PD01", "shop_d", "云柔 60支长绒棉四件套", "床品", 399,
     {"支数": "60支", "材质": "长绒棉", "尺寸": "1.8m床", "工艺": "贡缎"},
     300, "亲肤透气，裸睡级触感"),
    ("PD02", "shop_d", "轻眠 乳胶枕", "床品", 199,
     {"材质": "天然乳胶", "高度": "10cm", "枕型": "波浪形"},
     500, "护颈贴合，透气防螨"),
    ("PD03", "shop_d", "小象 折叠收纳箱", "收纳", 49,
     {"容量": "60L", "材质": "加厚PP", "承重": "30kg", "带轮": "底部滑轮"},
     800, "透明可视，叠加稳固"),
    ("PD04", "shop_d", "清尘 静电除尘掸", "清洁用品", 29,
     {"材质": "静电纤维", "杆长": "可伸缩", "可换头": "10片装"},
     1000, "吸附灰尘不扬尘，缝隙死角轻松清理"),
    ("PD05", "shop_d", "暖窝 珊瑚绒毯", "床品", 159,
     {"尺寸": "200×230cm", "材质": "珊瑚绒", "克重": "380g/㎡"},
     400, "加厚保暖，机洗不掉色"),
    ("PD06", "shop_d", "绿意 桌面绿植套装", "家居装饰", 89,
     {"植物": "绿萝+多肉", "花盆": "陶瓷×3", "土肥": "含营养土"},
     260, "净化空气，办公桌点缀"),
    ("PD07", "shop_d", "静语 遮光窗帘", "家居布艺", 299,
     {"遮光率": "90%", "尺寸": "定制", "材质": "高精密面料", "工艺": "韩褶"},
     180, "隔热隔音，遮光不遮风"),
    ("PD08", "shop_d", "小筑 置物架 5层", "收纳", 129,
     {"层数": "5层", "承重": "每层15kg", "材质": "碳钢", "尺寸": "60×30×160cm"},
     220, "免打孔安装，客厅浴室通用"),

    # ---- 鲜橙生鲜超市（shop_e）----
    ("PE01", "shop_e", "海南贵妃芒果 5斤", "水果", 39.9,
     {"产地": "海南", "规格": "5斤装", "甜度": "高", "配送": "冷链"},
     600, "树上熟现摘，香甜多汁"),
    ("PE02", "shop_e", "智利车厘子 2斤", "水果", 89.9,
     {"产地": "智利", "规格": "2斤装", "果径": "JJ级", "配送": "空运冷链"},
     300, "脆甜爆汁，礼盒装"),
    ("PE03", "shop_e", "丹东草莓 2斤", "水果", 59.9,
     {"产地": "辽宁丹东", "规格": "2斤装", "果径": "大果", "配送": "冷链"},
     400, "红颜99品种，果香浓郁"),
    ("PE04", "shop_e", "宁夏菜心 500g", "蔬菜", 9.9,
     {"产地": "宁夏", "规格": "500g", "新鲜度": "当日采摘", "配送": "冷链"},
     1000, "脆嫩清甜，无农残检测"),
    ("PE05", "shop_e", "冷鲜鸡胸肉 1kg", "肉禽", 29.9,
     {"部位": "鸡胸肉", "规格": "1kg", "冷链": "-18℃冷冻"},
     800, "高蛋白低脂，健身首选"),
    ("PE06", "shop_e", "挪威三文鱼刺身 300g", "水产", 79.9,
     {"产地": "挪威", "规格": "300g", "冷链": "冰鲜", "标准": "刺身级"},
     200, "肥美鲜嫩，开袋即食"),
    ("PE07", "shop_e", "农家土鸡蛋 30枚", "蛋奶", 39.9,
     {"规格": "30枚", "产地": "散养农家", "保质期": "30天"},
     900, "蛋黄饱满，营养丰富"),
    ("PE08", "shop_e", "新疆阿克苏苹果 5斤", "水果", 49.9,
     {"产地": "新疆阿克苏", "规格": "5斤装", "糖心": "冰糖心"},
     500, "脆甜多汁，糖心明显"),
    ("PE09", "shop_e", "鲜活基围虾 500g", "水产", 69.9,
     {"规格": "500g", "鲜活度": "全程充氧", "配送": "当日达"},
     350, "活虾现发，白灼清蒸皆宜"),

    # ---- 悦读书香书店（shop_f）----
    ("PF01", "shop_f", "《三体》全集（3册）", "文学小说", 88,
     {"作者": "刘慈欣", "出版社": "重庆出版社", "装帧": "平装"},
     800, "雨果奖获奖科幻巨著"),
    ("PF02", "shop_f", "《活着》", "文学小说", 35,
     {"作者": "余华", "出版社": "作家出版社", "页数": "191页"},
     1200, "中国当代文学经典"),
    ("PF03", "shop_f", "《人类简史》", "人文社科", 68,
     {"作者": "尤瓦尔·赫拉利", "出版社": "中信出版社", "装帧": "精装"},
     600, "从动物到上帝，全球现象级畅销书"),
    ("PF04", "shop_f", "《小王子》中英双语", "少儿读物", 29.9,
     {"作者": "圣埃克苏佩里", "双语": "中英对照", "插图": "原版插画"},
     900, "写给大人的童话"),
    ("PF05", "shop_f", "晨光 0.5mm 中性笔 12支", "文具", 19.9,
     {"规格": "0.5mm", "数量": "12支", "墨色": "黑色", "握感": "防滑软胶"},
     2000, "书写顺滑，考试办公通用"),
    ("PF06", "shop_f", "手账本 周计划笔记本", "文创", 39.9,
     {"规格": "A5", "页数": "192页", "内页": "周计划+空白", "装订": "锁线精装"},
     700, "高颜值手账，纸质厚实不透"),
    ("PF07", "shop_f", "《百年孤独》", "文学小说", 55,
     {"作者": "加西亚·马尔克斯", "出版社": "南海出版公司"},
     500, "魔幻现实主义文学巅峰"),
    ("PF08", "shop_f", "《刻意练习》", "成长励志", 49.9,
     {"作者": "安德斯·艾利克森", "出版社": "机械工业出版社"},
     650, "如何从新手到大师"),
    ("PF09", "shop_f", "故宫文创 书签礼盒", "文创", 59.9,
     {"材质": "金属", "数量": "6枚", "主题": "故宫藏品"},
     400, "国潮书签，送礼佳品"),
    ("PF10", "shop_f", "《明朝那些事儿》全集", "历史传记", 168,
     {"作者": "当年明月", "册数": "9册", "出版社": "北京联合出版公司"},
     350, "通俗历史经典，口碑之作"),
    ("PF11", "shop_f", "Kaco 按动中性笔 5支", "文具", 15.9,
     {"规格": "0.5mm", "数量": "5支", "墨色": "黑色", "按动": "按压式"},
     1500, "顺滑按动，办公常备"),
    ("PF12", "shop_f", "《蛤蟆先生去看心理医生》", "心理自助", 38,
     {"作者": "罗伯特·戴博德", "出版社": "天津人民出版社"},
     800, "国民级心理入门书"),
    ("PF13", "shop_f", "莫奈《睡莲》艺术拼图 1000片", "文创", 79.9,
     {"片数": "1000片", "尺寸": "70×50cm", "题材": "莫奈名画"},
     300, "艺术拼图，减压收藏"),
    ("PF14", "shop_f", "《平凡的世界》全三册", "文学小说", 108,
     {"作者": "路遥", "册数": "3册", "出版社": "北京十月文艺出版社"},
     280, "茅盾文学奖经典"),
    ("PF15", "shop_f", "喵喵 便签纸 4色装", "文具", 12.9,
     {"规格": "76×76mm", "数量": "4色×100张", "粘性": "可反复粘贴"},
     2000, "高颜值便签，记录灵感"),
]

_SEED_ORDERS = [
    # (order_id, user_id, product_id, quantity, amount, status, address, created_at)
    ("202608160001", "1001", "P001", 1, 3299, "shipped", "北京市朝阳区望京SOHO T1-1201", "2026-08-15 10:22:00"),
    ("202608050002", "1001", "P003", 1, 1499, "delivered", "北京市朝阳区望京SOHO T1-1201", "2026-08-05 14:10:00"),
    ("202607280003", "1001", "P004", 1, 1899, "delivered", "北京市朝阳区望京SOHO T1-1201", "2026-07-28 09:05:00"),
    ("202608150001", "1002", "P002", 1, 2599, "paid", "上海市浦东新区张江高科技园区2号楼", "2026-08-15 20:30:00"),
    ("202608100002", "1002", "P005", 1, 399, "delivered", "上海市浦东新区张江高科技园区2号楼", "2026-08-10 11:00:00"),
    ("202608120001", "1003", "P001", 1, 3299, "refunding", "广州市天河区体育西路191号", "2026-08-12 16:45:00"),
    ("202608010002", "1003", "P006", 1, 599, "delivered", "广州市天河区体育西路191号", "2026-08-01 13:20:00"),
    ("202608140001", "1004", "P007", 1, 1099, "pending_payment", "深圳市南山区科技园南区A8栋", "2026-08-14 19:55:00"),
    ("202608080002", "1004", "P008", 1, 799, "delivered", "深圳市南山区科技园南区A8栋", "2026-08-08 10:15:00"),
    ("202608130001", "1005", "P002", 1, 2599, "shipped", "成都市高新区天府三街199号", "2026-08-13 21:00:00"),
    ("202608060002", "1005", "P003", 1, 1499, "delivered", "成都市高新区天府三街199号", "2026-08-06 15:30:00"),
]

_SEED_LOGISTICS = [
    # (tracking_no, order_id, carrier, status, trace)
    ("SF1234567890", "202608160001", "顺丰速运", "in_transit", [
        {"time": "2026-08-16 09:00", "location": "杭州萧山转运中心", "desc": "快件已到达【杭州萧山转运中心】"},
        {"time": "2026-08-16 12:30", "location": "杭州萧山转运中心", "desc": "快件已从【杭州萧山转运中心】发出，下一站【北京顺义转运中心】"},
    ]),
    ("SF9876543210", "202608130001", "顺丰速运", "in_transit", [
        {"time": "2026-08-13 22:00", "location": "深圳宝安转运中心", "desc": "快件已到达【深圳宝安转运中心】"},
        {"time": "2026-08-14 08:10", "location": "深圳宝安转运中心", "desc": "快件已从【深圳宝安转运中心】发出，下一站【成都双流转运中心】"},
    ]),
    ("YT5566778899", "202608050002", "圆通速递", "delivered", [
        {"time": "2026-08-06 10:00", "location": "北京朝阳望京营业部", "desc": "快件已签收，签收人：本人"},
    ]),
    ("JD1122334455", "202608100002", "京东物流", "delivered", [
        {"time": "2026-08-11 09:20", "location": "上海浦东金桥站", "desc": "快件已签收，签收人：驿站代收"},
    ]),
]

_SEED_COUPONS = [
    # (coupon_id, user_id, title, threshold, discount, expire_at, used)
    ("CPN1001-1", "1001", "满3000减300", 3000, 300, "2026-08-31", 0),
    ("CPN1001-2", "1001", "满1500减100", 1500, 100, "2026-09-30", 1),
    ("CPN1002-1", "1002", "满2000减200", 2000, 200, "2026-08-31", 0),
    ("CPN1003-1", "1003", "满3000减300", 3000, 300, "2026-08-31", 0),
    ("CPN1004-1", "1004", "满1000减80", 1000, 80, "2026-09-15", 0),
    ("CPN1005-1", "1005", "满2500减250", 2500, 250, "2026-08-31", 0),
]

# 电商通用 FAQ 种子（40 条，与商品品类解耦）
_SEED_FAQ = [
    # (question, answer, keywords, category)
    ("运费怎么算？", "全场满99元包邮，不满99元运费8元；偏远地区（新疆、西藏、内蒙古、宁夏、青海、甘肃）加收15元运费。", "运费,邮费,包邮", "shipping"),
    ("包邮吗？", "全场满99元包邮，不满99元运费8元，偏远地区运费另计。", "包邮,免运费,运费", "shipping"),
    ("多久发货？", "现货商品付款后24小时内发货，预售商品按页面标注时间发货。", "发货,多久发,几天发,什么时候发", "order"),
    ("下单后多久能到？", "一般发货后3-5天送达，偏远地区5-7天；具体以物流信息为准。", "多久到,几天到,什么时候到,配送时间", "logistics"),
    ("怎么查我的订单？", "请提供您的订单号，我可以帮您查询订单状态和物流信息。", "查订单,我的订单,订单在哪", "order"),
    ("怎么查物流？", "请提供物流单号，我为您查询最新物流轨迹。", "查物流,物流到哪,快递到哪", "logistics"),
    ("可以改收货地址吗？", "未发货订单可以修改地址；已发货订单无法修改，请联系人工客服协助。", "改地址,换地址,修改地址", "account"),
    ("怎么退货？", "支持7天无理由退货（未拆封不影响二次销售）。在订单详情页申请售后，或告诉我订单号帮您操作。", "退货,怎么退,退掉", "refund"),
    ("退款多久到账？", "退款审核通过后1-3个工作日原路退回，具体到账时间以支付渠道为准。", "退款多久,什么时候到账,退钱", "refund"),
    ("7天无理由退货是什么意思？", "签收后7天内，商品未拆封、不影响二次销售，可无理由退货；非质量问题退货需用户承担寄回运费。", "无理由,七天无理由,7天无理由", "refund"),
    ("质量问题怎么办？", "签收后15天内出现质量问题可免费换货，1年内免费维修；质量问题商家承担往返运费。", "质量问题,坏了,破损,瑕疵", "refund"),
    ("退货运费谁出？", "非质量问题退货由用户承担寄回运费；质量问题由商家承担往返运费。", "运费谁出,退货运费,谁承担运费", "refund"),
    ("可以开发票吗？", "可以，下单时可选择开具电子普通发票，或联系客服补开；发票金额为实际支付金额。", "发票,开票,要发票", "invoice"),
    ("发票什么时候开？", "电子发票在订单完成后7个工作日内发送到您的邮箱/手机。", "发票多久,发票什么时候", "invoice"),
    ("有优惠券吗？", "请告诉我您的用户ID，我为您查询可用优惠券。", "优惠券,有券吗,优惠,领券", "coupon"),
    ("怎么领优惠券？", "您可以在店铺首页领取优惠券，或告诉我您的用户ID，我帮您查询可用的券。", "领券,怎么领,优惠", "coupon"),
    ("优惠券怎么用？", "结算时选择可用优惠券即可自动抵扣，注意查看使用门槛（满减金额）和有效期。", "券怎么用,优惠券怎么用,怎么使用优惠券", "coupon"),
    ("支持哪些支付方式？", "支持支付宝、微信支付、银行卡、花呗分期（部分商品支持）。", "支付,付款,怎么付", "payment"),
    ("可以分期付款吗？", "部分商品支持花呗分期，下单时选择花呗分期即可查看期数和费率。", "分期,花呗,白条,分几期", "payment"),
    ("客服几点上班？", "在线客服服务时间为每天9:00-22:00，人工坐席7×12小时在线。", "客服几点,上班时间,几点上班,在线时间", "service"),
    ("人工客服多久回复？", "人工客服一般5分钟内接入，高峰期可能稍等，请耐心等待。", "多久回复,回复时间,人工多久", "service"),
    ("怎么联系人工客服？", "直接回复\"转人工\"即可为您转接人工坐席。", "联系人工,找人工,人工客服", "service"),
    ("保修多久？", "整机保修1年，核心部件保修3年（详见商品详情页保修说明）。", "保修,质保,保修多久", "warranty"),
    ("保修范围包括什么？", "非人为损坏的质量问题在保修期内免费维修；人为损坏、进液、私自拆机不在保修范围。", "保修范围,什么能保修", "warranty"),
    ("坏了怎么维修？", "请联系人工客服提交维修工单，或前往品牌授权维修点；保修期内质量问题免费维修。", "维修,修理,坏了怎么办", "warranty"),
    ("可以退差价吗？", "若商品在您签收后7天内降价，可申请价保退差价，具体以订单页面价保规则为准。", "退差价,降价,价保,补差价", "refund"),
    ("怎么取消订单？", "未发货订单可直接取消，已发货订单需拒收或申请退货；告诉我订单号帮您处理。", "取消订单,不想要了,取消", "order"),
    ("订单一直显示待发货？", "可能是商品备货中，一般24小时内发出；超过48小时未发货请联系人工客服催单。", "待发货,没发货,一直不发货", "order"),
    ("物流信息不动了怎么办？", "物流超过48小时无更新可联系人工客服为您催件，或联系快递公司核实。", "物流不动,物流没更新,快递不动", "logistics"),
    ("可以指定快递吗？", "默认根据地址自动匹配快递（顺丰/京东/圆通等），暂不支持指定快递公司。", "指定快递,选快递,换快递", "logistics"),
    ("发货地址在哪？", "我们的仓库位于浙江杭州和广东深圳，就近发货。", "发货地,从哪里发货,仓库在哪", "order"),
    ("收到的货不对/发错了怎么办？", "请保留商品和包装，联系人工客服核实后为您安排退换，商家承担运费。", "发错,货不对,错发,少发", "refund"),
    ("少件/缺件怎么办？", "请提供订单号并拍照联系人工客服，核实后为您补发或退款。", "少件,缺件,少发,漏发", "refund"),
    ("商品支持7天无理由，拆了还能退吗？", "耗材类（滤网、刷头等）拆封后不支持无理由退货；整机激活使用后无质量问题不支持无理由退货。", "拆了能退吗,用过了能退吗,激活能退吗", "refund"),
    ("你们是正品吗？", "我们为品牌官方直营店，所有商品均为正品，支持官方验货。", "正品,是不是真的,假货", "service"),
    ("有线下门店吗？", "我们为线上官方旗舰店，暂无线下门店，支持全国联保。", "线下,实体店,门店", "service"),
    ("优惠券和活动能叠加吗？", "优惠券一般不与满减活动叠加，以结算页实际抵扣为准。", "叠加,一起用,同时用", "coupon"),
    ("为什么我的优惠券用不了？", "请检查优惠券的满减门槛、适用商品和有效期，或告诉我券的名称帮您核实。", "券用不了,优惠券不能用", "coupon"),
    ("买贵了能补差价吗？", "签收后7天内商品降价可申请价保退差价，具体以订单页面价保规则为准。", "买贵,降价,补差价", "refund"),
    ("怎么评价商品？", "确认收货后可在订单详情页评价，评价后还可获得积分。", "评价,评论,晒单", "service"),
]

# 退换政策：读 ecommerce.yml，工具层直接取用
_REFUND_POLICY = ecommerce_config.get("refund_policy", {})


# ---------------------------------------------------------------- db access

import functools
import threading


def _synchronized(method):
    """
    DB 方法互斥装饰器：
      - 串行化所有数据库操作（单 sqlite 连接必须串行访问）；
      - 连接异常（损坏/被外部替换）时自动重连并重试一次。
    """
    @functools.wraps(method)
    def wrapper(self, *args, **kwargs):
        with EcommerceDB._thread_lock:
            try:
                # close() 后连接置空：访问前自动重建（首次初始化由 _init_db 处理）
                if getattr(self, "_conn", None) is None and hasattr(self, "db_path"):
                    self._reconnect()
                return method(self, *args, **kwargs)
            except sqlite3.OperationalError as e:
                # 只读/被占用类错误：附加诊断信息后重连重试一次
                if "readonly" in str(e).lower() or "unable to open" in str(e).lower():
                    import os as _os
                    diag = (f"[诊断] {self.db_path} 可写={_os.access(self.db_path, _os.W_OK)} "
                            f"存在={_os.path.exists(self.db_path)}")
                    logger.error(f"[ecommerce.db]{method.__name__} 失败：{e}；{diag}")
                else:
                    logger.warning(f"[ecommerce.db]{method.__name__} 失败，重连后重试一次：{e}")
                self._reconnect()
                return method(self, *args, **kwargs)
            except sqlite3.Error:
                logger.warning(f"[ecommerce.db]{method.__name__} 失败，重连后重试一次")
                self._reconnect()
                return method(self, *args, **kwargs)
    return wrapper


class EcommerceDB:
    """电商库访问器：单例模式，惰性初始化，线程安全（RLock 串行化）。"""

    _instance = None
    # 类级可重入锁：单例场景等效实例锁，且支持 _init_db -> _seed_if_empty 嵌套
    _thread_lock = threading.RLock()

    def __new__(cls):
        with cls._thread_lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._init_db()
        return cls._instance

    @_synchronized
    def _init_db(self):
        db_rel = ecommerce_config.get("db_path", "data/ecommerce.db")
        self.db_path = get_abs_path(db_rel)
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._conn = None
        self._reconnect()
        self._conn.executescript(_SCHEMA)
        self._conn.commit()
        self._migrate()
        self._seed_if_empty()
        logger.info(f"[ecommerce.db] 初始化完成：{self.db_path}")

    def _migrate(self):
        """兼容旧库的增量迁移（新列等）。"""
        # tickets 表软删除列（旧库无 deleted 列）
        cols = {r[1] for r in self._conn.execute("PRAGMA table_info(tickets)").fetchall()}
        if "deleted" not in cols:
            self._conn.execute("ALTER TABLE tickets ADD COLUMN deleted INTEGER DEFAULT 0")
            self._conn.commit()
            logger.info("[ecommerce.db] 迁移：tickets 表新增 deleted 列")

        # #F9 商品表按商家拆分：旧库无 shop_id 列时补列（默认 shop_b 蓝鲸家电）
        pcols = {r[1] for r in self._conn.execute("PRAGMA table_info(products)").fetchall()}
        if "shop_id" not in pcols:
            self._conn.execute("ALTER TABLE products ADD COLUMN shop_id TEXT DEFAULT 'shop_b'")
            self._conn.commit()
            logger.info("[ecommerce.db] 迁移：products 表新增 shop_id 列（默认蓝鲸家电）")

    def _reconnect(self):
        """（重）建连接：供初始化与异常自愈使用。调用方需已持有锁。
        显式以读写模式（mode=rw）打开：若文件只读/被占用，连接阶段即报错，
        便于快速定位，而不是等到写操作才抛 'readonly database'。"""
        try:
            if getattr(self, "_conn", None) is not None:
                self._conn.close()
        except Exception:
            pass
        if os.path.exists(self.db_path):
            # 文件已存在：显式读写模式，只读/占用问题在连接阶段即暴露
            self._conn = sqlite3.connect(f"file:{self.db_path}?mode=rw", uri=True)
        else:
            # 首次运行：数据库文件尚不存在，允许创建
            self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row

    def _load_faq_seed(self) -> list[tuple]:
        """FAQ 种子：优先读外部配置 data/faq_seed.json（可编辑），
        不存在或解析失败时回退内置 _SEED_FAQ（D3 行业模板化）。"""
        seed_path = get_abs_path("data/faq_seed.json")
        if os.path.exists(seed_path):
            try:
                with open(seed_path, "r", encoding="utf-8") as f:
                    rows = json.load(f)
                if isinstance(rows, list) and rows:
                    return [
                        (r["question"], r["answer"],
                         r.get("keywords", ""), r.get("category", "general"))
                        for r in rows
                    ]
            except Exception as e:
                logger.warning(f"[ecommerce.db] faq_seed.json 读取失败，使用内置种子：{e}")
        return _SEED_FAQ

    # ---- 种子数据：各表独立判断，仅当对应表为空时灌入 ----
    @_synchronized
    def _seed_if_empty(self):
        with self._conn:
            # 商品/订单/物流/优惠券：仅当商品表为空时灌入
            pcount = self._conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
            # #F9 旧库升级：商品表已有旧数据但缺少新商家商品（PA01 等）→ 清空重灌新种子
            if pcount > 0:
                has_new = self._conn.execute(
                    "SELECT COUNT(*) FROM products WHERE product_id IN ('PA01','PB01','PC01','PD01','PE01','PF01')"
                ).fetchone()[0]
                if has_new == 0:
                    self._conn.execute("DELETE FROM products")
                    logger.info("[ecommerce.db] 检测到旧版商品数据，清空后重灌按商家拆分的新种子")
                    pcount = 0
            if pcount == 0:
                self._conn.executemany(
                    "INSERT INTO products (product_id, shop_id, name, category, price, specs, stock, description) "
                    "VALUES (?,?,?,?,?,?,?,?)",
                    # 元组结构：(id, shop, name, category, price, specs_dict, stock, desc)
                    [(p[0], p[1], p[2], p[3], p[4], json.dumps(p[5], ensure_ascii=False), p[6], p[7])
                     for p in _SEED_PRODUCTS],
                )
                logger.info("[ecommerce.db] 商品种子数据已灌入（按商家拆分）")

            # 订单/物流/优惠券：仅在对应表为空时灌入（避免升级重灌商品时重复）
            if self._conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0] == 0:
                self._conn.executemany(
                    "INSERT INTO orders (order_id, user_id, product_id, quantity, amount, status, address, created_at) "
                    "VALUES (?,?,?,?,?,?,?,?)",
                    _SEED_ORDERS,
                )
                self._conn.executemany(
                    "INSERT INTO logistics (tracking_no, order_id, carrier, status, trace_json) VALUES (?,?,?,?,?)",
                    [(t[0], t[1], t[2], t[3], json.dumps(t[4], ensure_ascii=False)) for t in _SEED_LOGISTICS],
                )
                self._conn.executemany(
                    "INSERT INTO coupons (coupon_id, user_id, title, threshold, discount, expire_at, used) "
                    "VALUES (?,?,?,?,?,?,?)",
                    _SEED_COUPONS,
                )
                logger.info("[ecommerce.db] 订单/物流/优惠券种子数据已灌入")

            # FAQ：仅当 faq 表为空时灌入（新增表，兼容已存在的库）
            if self._conn.execute("SELECT COUNT(*) FROM faq").fetchone()[0] == 0:
                faq_seed = self._load_faq_seed()
                self._conn.executemany(
                    "INSERT INTO faq (question, answer, keywords, category) VALUES (?,?,?,?)",
                    faq_seed,
                )
                logger.info(f"[ecommerce.db] FAQ 种子数据已灌入（{len(faq_seed)} 条）")

    # ---- 商品 ----
    # 常见疑问/冗余词（#G1：匹配前剔除，如"车厘子多少钱" → "车厘子"）
    _PRODUCT_NOISE_WORDS = (
        "多少钱一台", "多少钱一套", "多少钱一部", "多少钱一斤", "多少钱一瓶",
        "多少钱一盒", "多少钱一只", "多少钱一副", "多少钱一个", "多少钱呀",
        "多少钱啊", "多少钱", "价格多少", "价格是多少", "多少钱", "卖多少钱",
        "怎么卖", "怎么买", "怎么卖呀", "有货吗", "有卖吗", "有吗",
        "怎么样", "如何", "请问", "推荐", "哪个好", "多少", "价格",
    )

    @_synchronized
    def get_product_by_name(self, name: str, shop_id: str | None = None):
        """
        按名称查询商品（#F9 支持按商家过滤；#G1 增强匹配：整串 → 型号 → 关键词+去噪）。
        :param shop_id: 商家 ID（shop_a~shop_f）；None 或 'ai' 表示全店查询（智能客服兜底）
        """
        cleaned = name.replace(" ", "").replace("\u3000", "").lower()
        if not cleaned:
            return None
        candidates = self.list_products(shop_id=shop_id, limit=200)
        if not candidates:
            return None

        # 生成匹配变体：原串 + 剔除疑问/冗余词后的精简串（"车厘子多少钱"→"车厘子"）
        variants = [cleaned]
        stripped = cleaned
        for w in self._PRODUCT_NOISE_WORDS:
            stripped = stripped.replace(w, "")
        if stripped and stripped != cleaned:
            variants.append(stripped)

        for v in variants:
            # 0) 精确/包含整串匹配（去掉空格）
            for row in candidates:
                pname = row["name"].replace(" ", "").replace("\u3000", "").lower()
                if v == pname or v in pname or pname in v:
                    return row

            # 1) 型号强特征匹配：商品名中的字母+数字组合（如 S10/T9/X30）
            for row in candidates:
                models = re.findall(r"[A-Za-z]{1,4}\d{1,4}", row["name"])
                if any(m.lower() in v for m in models):
                    return row

            # 2) 关键词命中：商品名切词后与精简输入双向包含
            best_row, best_count = None, 0
            for row in candidates:
                terms = [t for t in re.split(r"[\s，。？！、,.!?;；:：()（）「」《》\"'']+", row["name"])
                         if len(t) >= 2 and not re.fullmatch(r"[A-Za-z]{1,4}\d{1,4}", t)]
                hits = sum(1 for t in terms if t.lower() in v or v in t.lower())
                if hits > best_count:
                    best_row, best_count = row, hits
            if best_row is not None:
                return best_row
        return None

    @_synchronized
    def get_product_by_id(self, product_id: str):
        return self._conn.execute(
            "SELECT * FROM products WHERE product_id = ?", (product_id,)
        ).fetchone()

    @_synchronized
    def list_products(self, shop_id: str | None = None, limit: int = 50):
        """商品列表（#F9 可按商家过滤；None/'ai' 返回全部）。"""
        if shop_id and shop_id != "ai":
            return self._conn.execute(
                "SELECT * FROM products WHERE shop_id = ? LIMIT ?", (shop_id, limit)
            ).fetchall()
        return self._conn.execute("SELECT * FROM products LIMIT ?", (limit,)).fetchall()

    # ---- 订单 ----
    @_synchronized
    def get_order(self, order_id: str):
        return self._conn.execute("SELECT * FROM orders WHERE order_id = ?", (order_id,)).fetchone()

    @_synchronized
    def list_orders_by_user(self, user_id: str, limit: int = 10):
        return self._conn.execute(
            "SELECT * FROM orders WHERE user_id = ? ORDER BY created_at DESC LIMIT ?", (user_id, limit)
        ).fetchall()

    @_synchronized
    def update_order_status(self, order_id: str, status: str):
        with self._conn:
            self._conn.execute("UPDATE orders SET status = ? WHERE order_id = ?", (status, order_id))

    @_synchronized
    def update_order_address(self, order_id: str, new_address: str):
        with self._conn:
            self._conn.execute("UPDATE orders SET address = ? WHERE order_id = ?", (new_address, order_id))

    # ---- 物流 ----
    @_synchronized
    def get_logistics(self, tracking_no: str):
        return self._conn.execute("SELECT * FROM logistics WHERE tracking_no = ?", (tracking_no,)).fetchone()

    @_synchronized
    def get_logistics_by_order(self, order_id: str):
        return self._conn.execute("SELECT * FROM logistics WHERE order_id = ?", (order_id,)).fetchone()

    # ---- 优惠券 ----
    @_synchronized
    def list_coupons_by_user(self, user_id: str):
        return self._conn.execute(
            "SELECT * FROM coupons WHERE user_id = ? AND used = 0", (user_id,)
        ).fetchall()

    @_synchronized
    def mark_coupon_used(self, coupon_id: str):
        with self._conn:
            self._conn.execute("UPDATE coupons SET used = 1 WHERE coupon_id = ?", (coupon_id,))

    # ---- 工单 ----
    @_synchronized
    def create_ticket(self, session_id, user_id, reason, transcript=None):
        ticket_id = f"TK{datetime.now().strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:4].upper()}"
        with self._conn:
            self._conn.execute(
                "INSERT INTO tickets (ticket_id, session_id, user_id, reason, status, transcript_json, created_at) "
                "VALUES (?,?,?,?,?,?,?)",
                (ticket_id, session_id, user_id, reason, "open",
                 json.dumps(transcript or [], ensure_ascii=False), datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            )
        return ticket_id

    @_synchronized
    def list_open_tickets(self, limit: int = 50):
        return self._conn.execute(
            "SELECT * FROM tickets WHERE status != 'resolved' ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()

    @_synchronized
    def list_tickets(self, *, status: str | None = None, keyword: str | None = None,
                     limit: int = 20, offset: int = 0) -> tuple[list, int]:
        """
        分页查询工单（第三波）：支持状态筛选与关键词搜索（工单号/用户ID/原因）。
        软删除的工单（deleted=1）不返回。
        :return: (rows, total)
        """
        where, params = ["deleted = 0"], []
        if status and status != "all":
            if status == "open":
                where.append("status != 'resolved'")
            else:
                where.append("status = ?")
                params.append(status)
        if keyword:
            where.append("(ticket_id LIKE ? OR user_id LIKE ? OR reason LIKE ?)")
            kw = f"%{keyword}%"
            params.extend([kw, kw, kw])
        where_sql = f"WHERE {' AND '.join(where)}"
        total = self._conn.execute(
            f"SELECT COUNT(*) FROM tickets {where_sql}", params
        ).fetchone()[0]
        rows = self._conn.execute(
            f"SELECT * FROM tickets {where_sql} ORDER BY created_at DESC LIMIT ? OFFSET ?",
            params + [limit, offset],
        ).fetchall()
        return rows, total

    @_synchronized
    def soft_delete_ticket(self, ticket_id: str) -> bool:
        """软删除单条工单，返回是否生效。"""
        with self._conn:
            cur = self._conn.execute(
                "UPDATE tickets SET deleted = 1 WHERE ticket_id = ? AND deleted = 0",
                (ticket_id,),
            )
        return cur.rowcount > 0

    @_synchronized
    def soft_delete_all_open(self) -> int:
        """软删除全部待处理工单（status != resolved），返回删除条数。"""
        with self._conn:
            cur = self._conn.execute(
                "UPDATE tickets SET deleted = 1 WHERE deleted = 0 AND status != 'resolved'"
            )
        return cur.rowcount

    @_synchronized
    def get_ticket(self, ticket_id: str):
        return self._conn.execute(
            "SELECT * FROM tickets WHERE ticket_id = ?", (ticket_id,)
        ).fetchone()

    @_synchronized
    def update_ticket_status(self, ticket_id: str, status: str):
        with self._conn:
            self._conn.execute(
                "UPDATE tickets SET status = ? WHERE ticket_id = ?", (status, ticket_id)
            )

    @_synchronized
    def resolve_ticket(self, ticket_id: str):
        with self._conn:
            self._conn.execute("UPDATE tickets SET status = 'resolved' WHERE ticket_id = ?", (ticket_id,))

    # ---- 会话 ----
    @_synchronized
    def get_session(self, session_id: str):
        return self._conn.execute("SELECT * FROM sessions WHERE session_id = ?", (session_id,)).fetchone()

    @_synchronized
    def list_sessions(self, user_id: str | None = None, limit: int = 50):
        """会话列表（第四波）：按更新时间倒序，可选按用户过滤。"""
        if user_id:
            return self._conn.execute(
                "SELECT * FROM sessions WHERE user_id = ? ORDER BY updated_at DESC LIMIT ?",
                (user_id, limit),
            ).fetchall()
        return self._conn.execute(
            "SELECT * FROM sessions ORDER BY updated_at DESC LIMIT ?", (limit,)
        ).fetchall()

    @_synchronized
    def save_session(self, session_id: str, user_id: str, messages: list, slots: dict):
        with self._conn:
            self._conn.execute(
                "INSERT INTO sessions (session_id, user_id, messages_json, slots_json, updated_at) "
                "VALUES (?,?,?,?,?) "
                "ON CONFLICT(session_id) DO UPDATE SET "
                "user_id=excluded.user_id, messages_json=excluded.messages_json, "
                "slots_json=excluded.slots_json, updated_at=excluded.updated_at",
                (session_id, user_id,
                 json.dumps(messages, ensure_ascii=False),
                 json.dumps(slots, ensure_ascii=False),
                 datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            )

    # ---- FAQ ----
    @_synchronized
    def get_faq(self, faq_id: int):
        return self._conn.execute("SELECT * FROM faq WHERE id = ?", (faq_id,)).fetchone()

    @_synchronized
    def list_faq(self, category: str | None = None, limit: int = 200):
        if category:
            return self._conn.execute(
                "SELECT * FROM faq WHERE category = ? ORDER BY id LIMIT ?", (category, limit)
            ).fetchall()
        return self._conn.execute("SELECT * FROM faq ORDER BY id LIMIT ?", (limit,)).fetchall()

    @_synchronized
    def search_faq(self, text: str, limit: int = 3):
        """关键词匹配 FAQ：答案文本/关键词字段包含输入中的任意命中词即返回候选。"""
        rows = self._conn.execute("SELECT * FROM faq ORDER BY id").fetchall()
        hits = []
        for row in rows:
            # 关键词字段精确命中优先
            kw_hit = [k for k in (row["keywords"] or "").split(",") if k and k in text]
            # 问题文本包含输入，或输入包含问题关键词
            q_hit = row["question"] in text or any(
                len(k) >= 2 and k in text for k in _extract_terms(row["question"])
            )
            if kw_hit or q_hit:
                hits.append((row, kw_hit))
        # 按命中关键词数量排序
        hits.sort(key=lambda x: len(x[1]), reverse=True)
        return [row for row, _ in hits[:limit]]

    @_synchronized
    def add_faq(self, question: str, answer: str, keywords: str = "",
                category: str = "general") -> int:
        """新增 FAQ，返回自增 id。"""
        with self._conn:
            cur = self._conn.execute(
                "INSERT INTO faq (question, answer, keywords, category) VALUES (?,?,?,?)",
                (question.strip(), answer.strip(), keywords, category),
            )
        return cur.lastrowid

    @_synchronized
    def delete_faq(self, faq_id: int) -> bool:
        """删除 FAQ，返回是否删除成功。"""
        with self._conn:
            cur = self._conn.execute("DELETE FROM faq WHERE id = ?", (faq_id,))
        return cur.rowcount > 0

    @_synchronized
    def close(self):
        """关闭连接并置空，后续访问会自动重建。"""
        try:
            if self._conn is not None:
                self._conn.close()
        finally:
            self._conn = None


# 模块级单例（惰性：首次访问才建库）
_db = None


def get_db() -> EcommerceDB:
    global _db
    if _db is None:
        _db = EcommerceDB()
    return _db


if __name__ == "__main__":
    db = get_db()
    print("=== 商品 ===")
    for p in db.list_products():
        print(f"  {p['product_id']} {p['name']} ¥{p['price']} 库存{p['stock']}")
    print("=== 用户1001订单 ===")
    for o in db.list_orders_by_user("1001"):
        print(f"  {o['order_id']} {o['status']} ¥{o['amount']}")
    print("=== 物流 ===")
    lg = db.get_logistics("SF1234567890")
    if lg:
        print(f"  {lg['tracking_no']} {lg['carrier']} {lg['status']}")
    print("=== 用户1002优惠券 ===")
    for c in db.list_coupons_by_user("1002"):
        print(f"  {c['title']} 满{c['threshold']}减{c['discount']}")
