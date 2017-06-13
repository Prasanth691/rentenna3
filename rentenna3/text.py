def indefiniteArticle(noun):
    if noun[0].upper() in ['A', 'E', 'I', 'O', 'U']:
        return "an %s" % noun
    else:
        return "a %s" % noun

def capitalize(str):
    if str:
        str = str.strip()
        return str[0].upper() + str[1:]

def commas(items):
    items = list(items) # so as not to be destructive
    items = [item.strip() for item in items]
    if len(items) > 1:
        items[-1] = "and %s" % items[-1]
    if len(items) > 2:
        return ", ".join(items)
    else:
        return " ".join(items)

def commaNumber(number):
    return "{:,}".format(int(number))

def percent(value, alreadyBase100=False):
    if not alreadyBase100:
        value = 100 * value
    return "%s%%" % int(value)

def plural(number, singularVersion, pluralVersion=None):
    return "%s %s" % (number, 
        pluralName(number, singularVersion, pluralVersion))

def pluralName(number, singularVersion, pluralVersion=None):
    if number == 1:
        return singularVersion
    else:
        return pluralVersion or (singularVersion + "s")

def rank(rank, threshold=0.5, above="highest", below="lowest"):
    if rank[0] > threshold * rank[1]:
        comparative = above
        rank = rank[1] - rank[0]
    else:
        comparative = below
        rank = rank[0] + 1
    return "#%s %s" % (rank, comparative)

def capitalizeEveryWord(text):
    return " ".join([word.capitalize() for word in text.split(' ')])
