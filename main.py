import json
import logging
import markdownify
import re
import requests
import time

from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_fixed
from urllib.parse import urlparse

# Setup logger
logger = logging.getLogger("main")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

def retry_log_warning(retry_state):
    logger.warning(f"Retrying attempt {retry_state.attempt_number} due to: {retry_state.outcome.exception()}")

@retry(stop=stop_after_attempt(3), wait=wait_fixed(3), before_sleep=retry_log_warning, reraise=True)
def fetch_url(url: str):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
    }
    rep = requests.get(url, headers=headers)
    rep.raise_for_status
    
    return rep.text

def processing_html(html: str):
    """Extract main content from html and convert to markdown"""
    
    # Add a newline after each HTML tag, to lower the chance markdownify missing line breaks 
    html = re.sub(r'(>)(<)', r'\1\n\2', html)
    soup = BeautifulSoup(html, "html.parser")

    # Get the main article
    article = soup.find('article')

    # Convert to markdown
    options = {
        "heading_style": "ATX",
        "strip": ["img", "a"],
    }
    content = markdownify.MarkdownConverter(**options).convert_soup(article)
    
    # Remove whitespaces at the beginning and end of each line
    content = "\n".join([line.strip() for line in content.splitlines()])

    # Remove duplicated empty lines
    content = re.sub(r'\n{2,}', '\n\n', content)

    return content

def read_url(url: str):
    """Fetch and get content from URL"""
    html = fetch_url(url)
    content = processing_html(html)
    return content

@retry(stop=stop_after_attempt(3), wait=wait_fixed(3), before_sleep=retry_log_warning, reraise=True)
def get_help_docs_urls():
    """Get list of docs URL from Notion 'Help - Reference docs'"""
    
    help_main = "https://www.notion.so/help/reference"

    parsed_url = urlparse(help_main)
    base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
    
    # Fetch the main help page
    html = fetch_url(help_main)
    soup = BeautifulSoup(html, 'html.parser')
    
    # Find the JSON data
    script_tag = soup.find('script', {'id': '__NEXT_DATA__'})
    json_data = json.loads(script_tag.string)

    urls = []

    # Get URLs of all sections
    _l1_list = json_data.get("props").get("pageProps").get("helpArticleTree")
    logger.info(f"Found {len(_l1_list)} sections")
    for l1 in _l1_list:
        _l2_list = l1.get("entries")
        count = 0
        for i in _l2_list:
            url = i.get("url")
            if url:
                count += 1
                urls.append(f"{base_url}{url}")
        logger.debug(f"Found {count} urls from this section")

    logger.info(f"Found {len(urls)} URLs in total")
    return urls

def split_markdown(markdown_text, max_chunk_size=750):
    """Splits given markdown document based on rules below in order:
        1. Each chunk contains one or multiple headline sections;
        2. Keep each chunk near but not exceeding 750 characters;
        3. If one headline section exceeds the 750 limit, ignore the limit.
    """
    headlines = re.split(r'(^#+\s.*?$)', markdown_text, flags=re.MULTILINE)
    
    # Reassemble sections based on the split headlines
    sections = []
    current_section = ""
    
    # Combine headlines and their corresponding content
    for i in range(1, len(headlines), 2):
        headline = headlines[i]
        content = headlines[i + 1] if i + 1 < len(headlines) else ""
        
        # Check if adding this section would exceed the max chunk size
        if len(current_section) and len(current_section) + len(headline) + len(content) > max_chunk_size:
            sections.append(current_section.strip())
            current_section = ""
        
        current_section += headline + content
        
    # Add any remaining content to sections
    if current_section:
        sections.append(current_section.strip())
    
    return sections

def save_list_to_file(data_list, filename="results.txt"):
    """Save a list of multi-line strings to a file. 
    Each string is saved in a readable way with Python compatibility.
    """
    with open(filename, "w") as file:
        file.write("[\n")
        for item in data_list:
            file.write(f"    {repr(item)},\n")
        file.write("]\n")
        
    logger.info(f"Chunks saved to {filename}.")

def scrapping_notion():
    """Read all Notion help docs, split to chunks, write to file"""
    chunks = []
    urls = get_help_docs_urls()
    for url in urls:
        try:  # Ignore failed URL
            content = read_url(url)
            _chunks = split_markdown(content)
            chunks.extend(_chunks)
            logger.info(f"Got {len(_chunks)} chunk(s) from URL '{url}'")
        except Exception as e:
            logger.error(f"Failed processing URL '{url}'")

        time.sleep(1)  # Sleep between each fetch to avoid overloading server

    logger.info(f"{len(chunks)} chunks in total")
    save_list_to_file(chunks)

if __name__ == "__main__":
    scrapping_notion()
