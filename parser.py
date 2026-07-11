import re


def calculate_water(text):
    prices = {
        1000: 0,
        1100: 0,
        1300: 0
    }

    total_bottles = 0
    total_money = 0
    customers = 0

    lines = text.split("\n")

    for line in lines:
        match = re.search(r"(\d+)\((\d+)\)", line)

        if match:
            bottles = int(match.group(1))
            price = int(match.group(2))

            if price in prices:
                prices[price] += bottles

            total_bottles += bottles
            total_money += bottles * price
            customers += 1

    return {
        "prices": prices,
        "total_bottles": total_bottles,
        "total_money": total_money,
        "customers": customers
    }
