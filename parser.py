
import re
import logging
from datetime import datetime, date
from typing import Optional

logger = logging.getLogger("gift_hub.parser")


# ─────────────────────────────────────────────────────────────────────
#  Message Format Pattern
# ─────────────────────────────────────────────────────────────────────
#  Format: <နာမည်> <ရေဘူးအရေအတွက်>(<ငွေပမာဏ>)
#  Examples:
#    ရေပေါ်ဘုန်းကြီးကျောင်း 13(1000)
#    ကိုအသေး 30(1100)
#    ဒေါ်မြမြ 5(1300)
#    ဦးဇင်း 1(1000)
#
#  Rules:
#    - နာမည်: Myanmar characters + English + digits + spaces + dots
#    - ရေဘူးအရေအတွက်: ဂဏန်း (int)
#    - ငွေပမာဏ: () ကွင်းထဲက ဂဏန်း (int)
#    - ခွဲတွက် 1000, 1100, 1300 ကို အလိုအလျောက် ခွဲခြား
# ─────────────────────────────────────────────────────────────────────


# နာမည် pattern — Myanmar characters, English, digits, spaces, dots, commas
NAME_PATTERN = r'([\u1000-\u109F\uAA60-\uAA7FA-Za-z0-9\s\.\,\-\_]+?)'
BOTTLES_PATTERN = r'([1-9]\d*)'
MONEY_PATTERN = r'\((\d+)\)'

# Complete regex pattern
ENTRY_PATTERN = re.compile(
    rf'^{NAME_PATTERN}\s+{BOTTLES_PATTERN}{MONEY_PATTERN}$',
    re.UNICODE
)


def parse_entry(text: str) -> Optional[dict]:
    """
    စာရင်း entry တစ်ခုကို parse လုပ်ပြီး dictionary ပြန်ထုတ်ပေး

    Args:
        text: စာရင်း message text (e.g. "ရေပေါ်ဘုန်းကြီးကျောင်း 13(1000)")

    Returns:
        dictionary with keys: name, bottles, money, price_per_bottle, timestamp
        ပြန်ထုတ်ပေးပါမယ်။
        Parse မရရင် None ပြန်ပေး
    """
    text = text.strip()
    match = ENTRY_PATTERN.match(text)

    if not match:
        logger.warning("Parse မရသော message: %s", text)
        return None

    name = match.group(1).strip()
    bottles = int(match.group(2))
    money = int(match.group(3))

    # ရေဘူးတစ်ဘူးနှုန်း
    price_per_bottle = money / bottles if bottles > 0 else 0

    # ခွဲတွက် (1000, 1100, 1300) သတ်မှတ် — money value ကို တိုက်ရိုက် check
    tier = _determine_tier(money)

    result = {
        "name": name,
        "bottles": bottles,
        "money": money,
        "price_per_bottle": price_per_bottle,
        "tier": tier,
        "timestamp": datetime.now(),
        "date": date.today(),
    }

    logger.info(
        "Parse success — %s | %d ဘူး | %d Ks | %s/bottle",
        name, bottles, money, tier
    )
    return result


def parse_batch(text: str) -> list[dict]:
    """
    Group ထဲက batch message (လိုင်းအများကြီး) ကို parse လုပ်

    Args:
        text: batch text (လိုင်းတစ်လိုင်း = entry တစ်ခု)

    Returns:
        parse ရသော entry list
    """
    entries = []
    lines = text.strip().split("\n")

    for line in lines:
        line = line.strip()
        if not line:
            continue

        result = parse_entry(line)
        if result:
            entries.append(result)
        else:
            logger.warning("Batch line skip: %s", line)

    logger.info("Batch parse: %d/%d entries successful", len(entries), len(lines))
    return entries


def _determine_tier(money: int) -> str:
    """
    ငွေပမာဏအတိုင်း ခွဲတွက် tier သတ်မှတ်
    """
    if money == 1000:
        return "1000"
    elif money == 1100:
        return "1100"
    elif money == 1300:
        return "1300"
    else:
        return str(money)


def format_reply(entry: dict, user_name: str = "") -> str:
    """
    Parse ရပြီးသား entry ကို reply message အဖြစ် format လုပ်
    """
    name = entry["name"]
    bottles = entry["bottles"]
    money = entry["money"]
    tier = entry["tier"]
    sender = f" ({user_name})" if user_name else ""

    reply = (
        f"✅ <b>စာရင်းထည့်ပြီးပါပြီ {sender}</b>\n\n"
        f"👤 နာမည်: <b>{name}</b>\n"
        f"💧 ရေဘူး: <b>{bottles} ဘူး</b>\n"
        f"💰 ငွေ: <b>{money:,} Ks</b>\n"
        f"📊 ခွဲတွက်: <b>{tier}</b>\n"
        f"⏰ အချိန်: <b>{entry['timestamp'].strftime('%H:%M:%S')}</b>"
    )
    return reply


def format_reply_summary(entries: list[dict], user_name: str = "") -> str:
    """
    Batch parse ရပြီးသား entries တွေရဲ့ summary reply
    """
    if not entries:
        return "⚠️ စာရင်း parse မရပါ။ Format ကို ပြန်စစ်ပါ။\n\n" \
               "Format: နာမည် ဂဏန်း(ငွေ)\n" \
               "Example: ရေပေါ်ဘုန်းကြီးကျောင်း 13(1000)"

    total_bottles = sum(e["bottles"] for e in entries)
    total_money = sum(e["money"] for e in entries)
    customer_count = len(entries)

        # Tier-wise bottle summary
    tier_bottles = {"1000": 0, "1100": 0, "1300": 0}
    for e in entries:
        tier_bottles[e["tier"]] += e["bottles"]

    sender_info = f" ({user_name})" if user_name else ""

    reply = f"✅ <b>စာရင်း {customer_count} ယောက် ထည့်ပြီးပါပြီ {sender_info}</b>\n\n"

    reply += f"👥 Customer စုစုပေါင်း: <b>{customer_count} ယောက်</b>\n"
    reply += f"💰 ငွေ စုစုပေါင်း: <b>{total_money:,} Ks</b>\n\n"

    reply += "📊 <b>ဘူးအရေအတွက်</b>\n"

    if tier_bottles["1000"] > 0:
        reply += f"1000 Ks : <b>{tier_bottles['1000']} ဘူး</b>\n"

    if tier_bottles["1100"] > 0:
        reply += f"1100 Ks : <b>{tier_bottles['1100']} ဘူး</b>\n"

    if tier_bottles["1300"] > 0:
        reply += f"1300 Ks : <b>{tier_bottles['1300']} ဘူး</b>\n"

    reply += f"\n📦 <b>စုစုပေါင်း ဘူးအရေအတွက်: {total_bottles:,} ဘူး</b>\n\n"
    reply += "✅ <b>စာရင်းထဲ သိမ်းပြီးပါပြီ!</b>\n"
    reply += "🙏 <b>ကျေးဇူးတင်ပါတယ်။</b>"

    return reply


if __name__ == "__main__":
    # Test
    test_entries = [
        "ရေပေါ်ဘုန်းကြီးကျောင်း 13(1000)",
        "ကိုအသေး 30(1100)",
        "ဒေါ်မြမြ 5(1300)",
        "invalid entry",
    ]

    for entry in test_entries:
        result = parse_entry(entry)
        if result:
            print(f"✅ {result['name']} | {result['bottles']} ဘူး | {result['money']} Ks | {result['tier']}")
        else:
            print(f"❌ {entry}")
