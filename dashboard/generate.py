import urllib.request, json
url = 'https://raw.githubusercontent.com/eesur/country-codes-lat-long/master/country-codes-lat-long-alpha3.json'
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla'})
try:
    with urllib.request.urlopen(req) as response:
        data = json.loads(response.read().decode())
        coords = {}
        for c in data['ref_country_codes']:
            cca2 = c.get('alpha2', '')
            name = c.get('country', '')
            lat = c.get('latitude', 0)
            lng = c.get('longitude', 0)
            if cca2 and name:
                if cca2 == 'IL':
                    name = 'Palestine'
                    cca2 = 'PS'
                if cca2 == 'PS':
                    name = 'Palestine'
                import random
                palette = ['#3b82f6', '#8b5cf6', '#ec4899', '#14b8a6', '#06b6d4', '#f59e0b', '#10b981', '#f43f5e']
                color = random.choice(palette)
                coords[cca2] = f'    {cca2}: {{ name: "{name}", lat: {lat}, lng: {lng}, color: "{color}" }},'
        out = 'const COUNTRY_COORDS: Record<string, { name: string; lat: number; lng: number; color: string }> = {\n'
        for k in sorted(coords.keys()):
            out += coords[k] + '\n'
        out += '};\n'
        with open('coords.txt', 'w', encoding='utf-8') as f:
            f.write(out)
except Exception as e:
    print('error', e)
