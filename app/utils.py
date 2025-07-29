import os


def check_amount(args):
    price = os.environ["PRICE"]
    if not args:
        return price
    try:
        number = int(args)
        return number
    except ValueError:
        if args.lstrip('-').isdigit() and (args.startswith('-') or args.isdigit()):
            return price
        else:
            return price
