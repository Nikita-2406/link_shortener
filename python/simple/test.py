from main import URLShortener
from time import time


start = time()

shortner = URLShortener(max_count_url=800)

filename = "urls.txt"

with open(filename, "r", encoding="utf-8") as f:
    for line in f:
        short = shortner.shorten(line)
        long = shortner.resolve(short)



print(time() - start)