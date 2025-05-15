# -*- coding: utf-8 -*-

import re
import sys
import random
import os
from typing import List, Tuple

import requests
from requests.models import Response


def find_links_in_text(text: str) -> List[str]:
    link_pattern = re.compile(
        r'((?:https?://|www\d{0,3}[.]|[a-z0-9.\-]+[.][a-z]{2,4}/)'
        r'(?:[^\s()<>]+|\(([^\s()<>]+|(\([^\s()<>]+\)))*\))+'
        r'(?:\(([^\s()<>]+|(\([^\s()<>]+\)))*\)|[^\s`!()\[\]{};:\'\".,<>?«»“”‘’]))'
    )
    raw_links = re.findall(link_pattern, text)
    return [str(raw_link[0]) for raw_link in raw_links]


def find_links_in_file(filename: str) -> List[str]:
    with open(filename, mode='r', encoding='utf-8') as file:
        readme = file.read()
        index_section = readme.find('## Index')
        content = readme[index_section:] if index_section != -1 else readme
    return find_links_in_text(content)


def check_duplicate_links(links: List[str]) -> Tuple[bool, List[str]]:
    seen = {}
    duplicates = []

    for link in links:
        link = link.rstrip('/')
        if link not in seen:
            seen[link] = 1
        elif seen[link] == 1:
            duplicates.append(link)

    return bool(duplicates), duplicates


def fake_user_agent() -> str:
    user_agents = [
        'Mozilla/5.0 (Windows NT 6.2) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/28.0.1467.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_6) AppleWebKit/605.1.15 (KHTML, like Gecko)',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.132 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/97.0.4692.71 Safari/537.36',
    ]
    return random.choice(user_agents)


def get_host_from_link(link: str) -> str:
    host = link.split('://', 1)[1] if '://' in link else link
    host = host.split('/', 1)[0].split('?', 1)[0].split('#', 1)[0]
    return host


def has_cloudflare_protection(resp: Response) -> bool:
    code = resp.status_code
    server = resp.headers.get('Server') or resp.headers.get('server')

    cloudflare_flags = [
        '403 Forbidden', 'cloudflare', 'Cloudflare', 'Security check',
        'Please Wait... | Cloudflare', 'We are checking your browser...',
        'Checking your browser before accessing', 'Ray ID:',
        '_cf_chl', '_cf_chl_opt', '__cf_chl_rt_tk',
        'cf-spinner-please-wait', 'cf-spinner-redirecting'
    ]

    if code in [403, 503] and server and 'cloudflare' in server.lower():
        html = resp.text
        return any(flag in html for flag in cloudflare_flags)
    return False


def check_if_link_is_working(link: str) -> Tuple[bool, str]:
    try:
        resp = requests.get(link, timeout=25, headers={
            'User-Agent': fake_user_agent(),
            'host': get_host_from_link(link)
        })
        if resp.status_code >= 400 and not has_cloudflare_protection(resp):
            return True, f'ERR:CLT: {resp.status_code} : {link}'
    except requests.exceptions.SSLError as error:
        return True, f'ERR:SSL: {error} : {link}'
    except requests.exceptions.ConnectionError as error:
        return True, f'ERR:CNT: {error} : {link}'
    except (TimeoutError, requests.exceptions.ConnectTimeout):
        return True, f'ERR:TMO: {link}'
    except requests.exceptions.TooManyRedirects as error:
        return True, f'ERR:TMR: {error} : {link}'
    except (Exception, requests.exceptions.RequestException) as error:
        return True, f'ERR:UKN: {error} : {link}'

    return False, ''


def check_if_list_of_links_are_working(list_of_links: List[str]) -> List[str]:
    errors = []
    for link in list_of_links:
        has_error, error_message = check_if_link_is_working(link)
        if has_error:
            errors.append(error_message)
    return errors


def start_duplicate_links_checker(links: List[str]) -> None:
    print('Checking for duplicate links...')
    has_duplicates, duplicates = check_duplicate_links(links)

    if has_duplicates:
        print(f'Found duplicate links:')
        for d in duplicates:
            print(d)
        sys.exit(1)
    else:
        print('No duplicate links.')


def start_links_working_checker(links: List[str]) -> None:
    print(f'Checking if {len(links)} links are working...')
    errors = check_if_list_of_links_are_working(links)
    if errors:
        print(f'Apparently {len(errors)} links are not working properly. See below:\n')
        for msg in errors:
            print(msg)
        sys.exit(1)


def main(filename: str, only_duplicate_links_checker: bool) -> None:
    links = find_links_in_file(filename)
    start_duplicate_links_checker(links)

    if not only_duplicate_links_checker:
        start_links_working_checker(links)


if __name__ == '__main__':
    default_file = r"D:\Project\apis-publicas-master\scripts\sample.md"
    filename = sys.argv[1] if len(sys.argv) > 1 else default_file
    only_duplicate_links_checker = False

    if not os.path.exists(filename):
        print(f"File not found: {filename}")
        sys.exit(1)

    if len(sys.argv) == 3:
        third_arg = sys.argv[2].lower()
        if third_arg in ['-odlc', '--only_duplicate_links_checker']:
            only_duplicate_links_checker = True
        else:
            print(f'Invalid argument: {third_arg}\nUsage: python script.py [file.md] [-odlc | --only_duplicate_links_checker]')
            sys.exit(1)

    main(filename, only_duplicate_links_checker)

