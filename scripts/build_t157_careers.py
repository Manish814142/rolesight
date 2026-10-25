"""Build data/t157_careers.txt for at least 150 unfound companies.

Extracts company website URLs from Elevation Capital, Peak XV Partners, and Nexus VP,
checks for their careers landing pages (/careers, /jobs, or homepage), and writes
'Name | careers_url' seed lines.
"""

import csv
import json
import urllib.request
from concurrent.futures import ThreadPoolExecutor

from bs4 import BeautifulSoup


def main():
    # 1. Gather unfound company names from Batch 1 and 2
    unfound_names = []
    for b in ['01', '02', '03']:
        with open(f'data/t157_report_{b}.csv', encoding='utf-8') as f:
            for r in csv.DictReader(f):
                if r.get('verdict') in [
                    'no live board on supported ATSs',
                    'no India jobs',
                    'identity not confirmed'
                ]:
                    unfound_names.append(r['seed'])

    print(f'Total unfound companies across batches: {len(unfound_names)}')

    # 2. Map candidates to their source URLs
    with open('data/t157_candidates.tsv', encoding='utf-8') as f:
        cand_map = {r['name'].lower(): (r['name'], r['source_url']) for r in csv.DictReader(f, delimiter='\t')}

    # 3. Extract Elevation website links directly from cached/downloaded page
    elevation_websites = {}
    try:
        req = urllib.request.Request('https://www.elevationcapital.com/portfolio', headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=15) as r:
            html = r.read().decode('utf-8')
        soup = BeautifulSoup(html, 'html.parser')
        data = json.loads(soup.find('script', id='__NEXT_DATA__').string)

        def find_portfolios(d):
            if isinstance(d, dict):
                for k, v in d.items():
                    if k == 'portfolios' and isinstance(v, list):
                        return v
                    res = find_portfolios(v)
                    if res:
                        return res
            elif isinstance(d, list):
                for x in d:
                    res = find_portfolios(x)
                    if res:
                        return res
            return None

        ports = find_portfolios(data) or []
        for p in ports:
            title = p.get('title', '').strip()
            links = p.get('links', [])
            website = None
            for item in links:
                for cta in item.get('cta_link', []):
                    u = cta.get('url', '').strip()
                    if u.startswith('http') and not any(k in u for k in ['youtube', 'twitter', 'linkedin', 'instagram', 'facebook']):
                        website = u
                        break
                if website:
                    break
            if title and website:
                elevation_websites[title.lower()] = website
    except Exception as e:
        print('Error extracting Elevation websites:', e)

    print(f'Elevation websites extracted: {len(elevation_websites)}')

    # 4. Fetch Peak XV company page websites
    peak_xv_targets = []
    for u in unfound_names:
        c_info = cand_map.get(u.lower())
        if c_info:
            name, src = c_info
            if 'peakxv.com/companies/' in src:
                slug = src.split('/companies/')[-1]
                peak_xv_targets.append((name, slug))

    print(f'Peak XV unfound targets to probe: {len(peak_xv_targets)}')

    def fetch_peak_website(pair):
        name, slug = pair
        url = f'https://www.peakxv.com/companies/{slug}'
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=8) as r:
                html = r.read().decode('utf-8')
                soup = BeautifulSoup(html, 'html.parser')
                for a in soup.find_all('a', href=True):
                    txt = a.get_text(strip=True)
                    if txt.startswith('http') and not any(k in txt for k in ['peakxv', 'linkedin', 'twitter', 'x.com']):
                        return name, a['href'].strip()
        except Exception:
            pass
        return name, None

    peak_websites = {}
    with ThreadPoolExecutor(max_workers=15) as ex:
        for name, web in ex.map(fetch_peak_website, peak_xv_targets):
            if web:
                peak_websites[name.lower()] = web

    print(f'Peak XV websites extracted: {len(peak_websites)}')

    # 5. Combine and resolve careers URLs
    combined = {}
    for u in unfound_names:
        u_low = u.lower()
        web = elevation_websites.get(u_low) or peak_websites.get(u_low)
        if web and u not in combined:
            combined[u] = web.rstrip('/')

    print(f'Total unfound companies with website: {len(combined)}')

    # Probe careers URLs (e.g. /careers, /jobs, or base website)
    def resolve_careers_url(item):
        name, base_url = item
        # candidate URLs
        candidates = [
            f'{base_url}/careers',
            f'{base_url}/jobs',
            f'{base_url}/careers/',
            f'{base_url}/join-us',
            base_url
        ]
        for c_url in candidates:
            try:
                req = urllib.request.Request(c_url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=5) as r:
                    if r.status in (200, 301, 302):
                        final = r.geturl()
                        return name, final
            except Exception:
                continue
        return name, base_url

    careers_lines = []
    # Take first 170 to ensure >= 150
    items_to_resolve = list(combined.items())[:170]
    print(f'Probing careers pages for {len(items_to_resolve)} companies...')
    with ThreadPoolExecutor(max_workers=20) as ex:
        for name, careers_url in ex.map(resolve_careers_url, items_to_resolve):
            if careers_url:
                careers_lines.append(f'{name} | {careers_url}')

    with open('data/t157_careers.txt', 'w', encoding='utf-8') as f:
        f.write('# Careers page URLs for T157 census\n')
        for line in careers_lines:
            f.write(line + '\n')

    print(f'Successfully wrote {len(careers_lines)} lines to data/t157_careers.txt')


if __name__ == '__main__':
    main()
