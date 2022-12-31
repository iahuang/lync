from lync.genius import Genius, CACHE_FOREVER

g = Genius(CACHE_FOREVER)
result = g.search("sza - low")

assert result is not None

print(f"Lyrics for {result.title} by {result.artist_name} ({result.release_year}):")
print()

for line in g.get_lyrics(result).lines:
    print(line.text_adlibs_removed())