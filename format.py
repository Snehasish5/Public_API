# -*- coding: utf-8 -*-

import re
import sys
from string import punctuation as punct
from typing import List, Tuple, Dict

# Remove specific punctuation characters from validation set
punctuation = punct.replace('(', '').replace(')', '')

anchor = '###'
auth_keys = ['apiKey', 'OAuth', 'X-Mashape-Key', 'User-Agent', 'No']
https_keys = ['Yes', 'No']
cors_keys = ['Yes', 'No', 'Unknown']

index_title = 0
index_desc = 1
index_auth = 2
index_https = 3
index_cors = 4

num_segments = 5
min_entries_per_category = 3
max_description_length = 100

# ✅ Use raw strings to avoid escape sequence warnings
anchor_re = re.compile(rf"{anchor}\s(.+)")
category_title_in_index_re = re.compile(r"\*\s\[(.*)\]")
link_re = re.compile(r"\[(.+)\]\((http.*)\)")

# Type aliases
APIList = List[str]
Categories = Dict[str, APIList]
CategoriesLineNumber = Dict[str, int]


def error_message(line_number: int, message: str) -> str:
    line = line_number + 1
    return f'(L{line:03d}) {message}'


def get_categories_content(contents: List[str]) -> Tuple[Categories, CategoriesLineNumber]:
    categories = {}
    category_line_num = {}

    for line_num, line_content in enumerate(contents):
        if line_content.startswith(anchor):
            category = line_content.split(anchor)[1].strip()
            categories[category] = []
            category_line_num[category] = line_num
            continue

        if not line_content.startswith('|') or line_content.startswith('|---'):
            continue

        raw_title = [
            raw_content.strip() for raw_content in line_content.split('|')[1:-1]
        ][0]

        title_match = link_re.match(raw_title)
        if title_match:
            title = title_match.group(1).upper()
            categories[category].append(title)

    return (categories, category_line_num)


def check_alphabetical_order(lines: List[str]) -> List[str]:
    err_msgs = []
    categories, category_line_num = get_categories_content(contents=lines)

    for category, api_list in categories.items():
        if sorted(api_list) != api_list:
            err_msg = error_message(
                category_line_num[category],
                f'{category} category is not alphabetical order'
            )
            err_msgs.append(err_msg)

    return err_msgs


def check_title(line_num: int, raw_title: str) -> List[str]:
    err_msgs = []
    title_match = link_re.match(raw_title)

    if not title_match:
        err_msgs.append(error_message(line_num, 'Title syntax should be "[TITLE](LINK)"'))
    else:
        title = title_match.group(1)
        if title.upper().endswith(' API'):
            err_msgs.append(error_message(line_num, 'Title should not end with "... API". Every entry is an API here!'))

    return err_msgs


def check_description(line_num: int, description: str) -> List[str]:
    err_msgs = []

    if description[0].upper() != description[0]:
        err_msgs.append(error_message(line_num, 'first character of description is not capitalized'))

    if description[-1] in punctuation:
        err_msgs.append(error_message(line_num, f'description should not end with {description[-1]}'))

    if len(description) > max_description_length:
        err_msgs.append(error_message(
            line_num,
            f'description should not exceed {max_description_length} characters (currently {len(description)})'
        ))

    return err_msgs


def check_auth(line_num: int, auth: str) -> List[str]:
    err_msgs = []
    backtick = '`'

    if auth != 'No' and (not auth.startswith(backtick) or not auth.endswith(backtick)):
        err_msgs.append(error_message(line_num, 'auth value is not enclosed with `backticks`'))

    if auth.replace(backtick, '') not in auth_keys:
        err_msgs.append(error_message(line_num, f'{auth} is not a valid Auth option'))

    return err_msgs


def check_https(line_num: int, https: str) -> List[str]:
    return [error_message(line_num, f'{https} is not a valid HTTPS option')] if https not in https_keys else []


def check_cors(line_num: int, cors: str) -> List[str]:
    return [error_message(line_num, f'{cors} is not a valid CORS option')] if cors not in cors_keys else []


def check_entry(line_num: int, segments: List[str]) -> List[str]:
    raw_title = segments[index_title]
    description = segments[index_desc]
    auth = segments[index_auth]
    https = segments[index_https]
    cors = segments[index_cors]

    return (
        check_title(line_num, raw_title) +
        check_description(line_num, description) +
        check_auth(line_num, auth) +
        check_https(line_num, https) +
        check_cors(line_num, cors)
    )


def check_file_format(lines: List[str]) -> List[str]:
    err_msgs = []
    category_title_in_index = []

    err_msgs.extend(check_alphabetical_order(lines))

    num_in_category = min_entries_per_category + 1
    category = ''
    category_line = 0

    for line_num, line_content in enumerate(lines):
        category_title_match = category_title_in_index_re.match(line_content)
        if category_title_match:
            category_title_in_index.append(category_title_match.group(1))

        if line_content.startswith(anchor):
            category_match = anchor_re.match(line_content)
            if category_match:
                if category_match.group(1) not in category_title_in_index:
                    err_msgs.append(error_message(line_num, f'category header ({category_match.group(1)}) not added to Index section'))
            else:
                err_msgs.append(error_message(line_num, 'category header is not formatted correctly'))

            if num_in_category < min_entries_per_category:
                err_msgs.append(error_message(category_line, f'{category} category does not have the minimum {min_entries_per_category} entries (only has {num_in_category})'))

            category = line_content.split(' ')[1]
            category_line = line_num
            num_in_category = 0
            continue

        if not line_content.startswith('|') or line_content.startswith('|---'):
            continue

        num_in_category += 1
        segments = line_content.split('|')[1:-1]
        if len(segments) < num_segments:
            err_msgs.append(error_message(line_num, f'entry does not have all the required columns (have {len(segments)}, need {num_segments})'))
            continue

        for segment in segments:
            if len(segment) - len(segment.lstrip()) != 1 or len(segment) - len(segment.rstrip()) != 1:
                err_msgs.append(error_message(line_num, 'each segment must start and end with exactly 1 space'))

        segments = [segment.strip() for segment in segments]
        err_msgs.extend(check_entry(line_num, segments))

    return err_msgs


def main(filename: str) -> None:
    with open(filename, mode='r', encoding='utf-8') as file:
        lines = [line.rstrip() for line in file]

    file_format_err_msgs = check_file_format(lines)

    if file_format_err_msgs:
        for err_msg in file_format_err_msgs:
            print(err_msg)
        sys.exit(1)


if __name__ == '__main__':
    # Use "sample.md" as default if no file passed
    filename = sys.argv[1] if len(sys.argv) > 1 else (r"D:\Project\apis-publicas-master\scripts\Sample.md")

    try:
        main(filename)
    except FileNotFoundError:
        print(f"File not found: {filename}")
        sys.exit(1)
