import requests
from bs4 import BeautifulSoup

def scrape_url(url: str) -> str:
    """
    Scrapes a URL and returns clean markdown-like text.
    Optimized for CMO analysis (Content, Headers, Links).
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Referer': 'https://www.google.com/',
            'Upgrade-Insecure-Requests': '1',
            'Cache-Control': 'max-age=0'
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Remove junk
        for script in soup(["script", "style", "nav", "footer"]):
            script.decompose()
            
        # Extract title
        title = soup.title.string if soup.title else "No Title"
        
        # Extract body text
        text = soup.get_text(separator='\n')
        
        # Clean up whitespace
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        clean_text = '\n'.join(chunk for chunk in chunks if chunk)
        
        return f"### [SCRAPE RESULT] {title}\nURL: {url}\n\n{clean_text[:4000]}..." # Truncate to avoid context overflow

    except Exception as e:
        return f"### [SCRAPE ERROR]\nFailed to scrape {url}. Error: {str(e)}"
