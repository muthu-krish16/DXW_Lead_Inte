import google.generativeai as genai
import json
import os
import requests
from bs4 import BeautifulSoup
from ddgs import DDGS
from urllib.parse import urljoin, urlparse


def configure_gemini(api_key):
    genai.configure(api_key=api_key)
    return genai.GenerativeModel("gemini-3.1-flash-lite") # gemini-3.1-flash-lite or gemini-3-flash-preview


# ── LOAD PROMPT ──────────────────────────────────────────────
def load_prompt():
    with open("prompt.txt", "r", encoding="utf-8") as file:
        return file.read()


# ── URL NORMALIZATION ────────────────────────────────────────
def normalize_url(url):
    """
    Normalize URL for comparison:
    - lowercase
    - remove trailing slash
    - remove www.
    - remove fragments (#)
    - remove common tracking params
    """
    url = url.strip().lower()

    parsed = urlparse(url)

    # Remove www.
    host = parsed.netloc.replace("www.", "")

    # Remove fragment
    path = parsed.path.rstrip("/")

    # Rebuild clean URL
    clean = f"{parsed.scheme}://{host}{path}"

    return clean


def is_duplicate(url, fetched_set):
    """Check if URL (or a variation) has already been fetched."""
    normalized = normalize_url(url)

    if normalized in fetched_set:
        return True

    # Also check without scheme
    no_scheme = normalized.split("://", 1)[-1]
    for existing in fetched_set:
        if existing.split("://", 1)[-1] == no_scheme:
            return True

    return False


# ── ROBUST URL FETCHER ───────────────────────────────────────
def fetch_url_content(url, max_chars=3000):
    """Fetch and clean text from a single URL."""
    try:
        session = requests.Session()
        session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        })

        resp = session.get(url.strip(), timeout=12, allow_redirects=True)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")

        for tag in soup(["script", "style", "nav", "footer",
                          "header", "meta", "noscript", "iframe"]):
            tag.decompose()

        text = soup.get_text(separator=" ", strip=True)
        text = " ".join(text.split())

        if len(text) > max_chars:
            text = text[:max_chars] + "..."

        print(f"  ✓ Fetched {url} — {len(text)} chars")
        return text

    except Exception as e:
        print(f"  ✗ Could not fetch {url}: {e}")
        return ""


# ── TECH STACK DETECTION ─────────────────────────────────────
def detect_tech_stack(url):
    """
    Scan a website's raw HTML, headers, and scripts to detect technologies.
    Returns a dict of detected technologies grouped by category.
    """
    detected = {
        "analytics"      : [],
        "crm_marketing"  : [],
        "cloud_infra"    : [],
        "frontend"       : [],
        "cms_platform"   : [],
        "data_tools"     : [],
        "ai_ml"          : [],
        "communication"  : [],
        "payments"       : [],
        "other"          : [],
    }

    try:
        session = requests.Session()
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
        })
        resp = session.get(url.strip(), timeout=12, allow_redirects=True)
        html = resp.text.lower()
        headers = {k.lower(): v.lower() for k, v in resp.headers.items()}

        # ── SIGNATURES: (search_string, technology_name, category) ──
        signatures = [
            # Analytics
            ("google-analytics.com", "Google Analytics", "analytics"),
            ("googletagmanager.com", "Google Tag Manager", "analytics"),
            ("gtag(", "Google Analytics (gtag)", "analytics"),
            ("analytics.js", "Google Analytics", "analytics"),
            ("ga('create'", "Google Analytics", "analytics"),
            ("mixpanel", "Mixpanel", "analytics"),
            ("amplitude", "Amplitude", "analytics"),
            ("segment.com", "Segment", "analytics"),
            ("segment.io", "Segment", "analytics"),
            ("hotjar", "Hotjar", "analytics"),
            ("heap-", "Heap Analytics", "analytics"),
            ("fullstory", "FullStory", "analytics"),
            ("posthog", "PostHog", "analytics"),
            ("plausible", "Plausible Analytics", "analytics"),
            ("matomo", "Matomo", "analytics"),
            ("pendo", "Pendo", "analytics"),

            # CRM & Marketing
            ("hubspot", "HubSpot", "crm_marketing"),
            ("hs-scripts.com", "HubSpot", "crm_marketing"),
            ("salesforce", "Salesforce", "crm_marketing"),
            ("pardot", "Salesforce Pardot", "crm_marketing"),
            ("marketo", "Marketo", "crm_marketing"),
            ("mailchimp", "Mailchimp", "crm_marketing"),
            ("intercom", "Intercom", "crm_marketing"),
            ("drift", "Drift", "crm_marketing"),
            ("crisp.chat", "Crisp Chat", "crm_marketing"),
            ("zendesk", "Zendesk", "crm_marketing"),
            ("freshdesk", "Freshdesk", "crm_marketing"),
            ("optimizely", "Optimizely", "crm_marketing"),
            ("meta pixel", "Meta Pixel", "crm_marketing"),
            ("fbq(", "Meta Pixel", "crm_marketing"),
            ("facebook.net/en_us/fbevents", "Meta Pixel", "crm_marketing"),
            ("linkedin.com/insight", "LinkedIn Insight Tag", "crm_marketing"),
            ("ads.google.com", "Google Ads", "crm_marketing"),
            ("doubleclick", "Google DoubleClick", "crm_marketing"),
            ("twitter.com/i/adsct", "Twitter Ads", "crm_marketing"),
            ("6sense", "6sense", "crm_marketing"),
            ("clearbit", "Clearbit", "crm_marketing"),
            ("zoominfo", "ZoomInfo", "crm_marketing"),

            # Cloud & Infrastructure
            ("amazonaws.com", "AWS", "cloud_infra"),
            ("aws-", "AWS", "cloud_infra"),
            ("cloudfront.net", "AWS CloudFront", "cloud_infra"),
            ("s3.amazonaws", "AWS S3", "cloud_infra"),
            ("googleapis.com", "Google Cloud", "cloud_infra"),
            ("gstatic.com", "Google Cloud", "cloud_infra"),
            ("azure", "Microsoft Azure", "cloud_infra"),
            ("cloudflare", "Cloudflare", "cloud_infra"),
            ("fastly", "Fastly CDN", "cloud_infra"),
            ("akamai", "Akamai CDN", "cloud_infra"),
            ("vercel", "Vercel", "cloud_infra"),
            ("netlify", "Netlify", "cloud_infra"),
            ("heroku", "Heroku", "cloud_infra"),
            ("digitalocean", "DigitalOcean", "cloud_infra"),
            ("docker", "Docker", "cloud_infra"),
            ("kubernetes", "Kubernetes", "cloud_infra"),
            ("nginx", "Nginx", "cloud_infra"),
            ("x-powered-by", "Server Header", "cloud_infra"),

            # Frontend
            ("react", "React", "frontend"),
            ("__next", "Next.js", "frontend"),
            ("_next/", "Next.js", "frontend"),
            ("vue.js", "Vue.js", "frontend"),
            ("nuxt", "Nuxt.js", "frontend"),
            ("angular", "Angular", "frontend"),
            ("svelte", "Svelte", "frontend"),
            ("jquery", "jQuery", "frontend"),
            ("bootstrap", "Bootstrap", "frontend"),
            ("tailwindcss", "Tailwind CSS", "frontend"),
            ("webpack", "Webpack", "frontend"),
            ("gatsby", "Gatsby", "frontend"),

            # CMS & Platforms
            ("wp-content", "WordPress", "cms_platform"),
            ("wordpress", "WordPress", "cms_platform"),
            ("shopify", "Shopify", "cms_platform"),
            ("myshopify", "Shopify", "cms_platform"),
            ("wix.com", "Wix", "cms_platform"),
            ("squarespace", "Squarespace", "cms_platform"),
            ("webflow", "Webflow", "cms_platform"),
            ("drupal", "Drupal", "cms_platform"),
            ("ghost", "Ghost CMS", "cms_platform"),
            ("contentful", "Contentful", "cms_platform"),
            ("prismic", "Prismic", "cms_platform"),
            ("sanity.io", "Sanity CMS", "cms_platform"),
            ("strapi", "Strapi", "cms_platform"),
            ("bigcommerce", "BigCommerce", "cms_platform"),
            ("magento", "Magento", "cms_platform"),

            # Data Tools
            ("snowflake", "Snowflake", "data_tools"),
            ("bigquery", "Google BigQuery", "data_tools"),
            ("databricks", "Databricks", "data_tools"),
            ("looker", "Looker", "data_tools"),
            ("tableau", "Tableau", "data_tools"),
            ("powerbi", "Power BI", "data_tools"),
            ("redshift", "AWS Redshift", "data_tools"),
            ("elastic", "Elasticsearch", "data_tools"),
            ("algolia", "Algolia Search", "data_tools"),
            ("mongo", "MongoDB", "data_tools"),
            ("firebase", "Firebase", "data_tools"),
            ("supabase", "Supabase", "data_tools"),

            # AI/ML
            ("openai", "OpenAI", "ai_ml"),
            ("chatgpt", "ChatGPT / OpenAI", "ai_ml"),
            ("anthropic", "Anthropic Claude", "ai_ml"),
            ("tensorflow", "TensorFlow", "ai_ml"),
            ("pytorch", "PyTorch", "ai_ml"),
            ("huggingface", "Hugging Face", "ai_ml"),
            ("langchain", "LangChain", "ai_ml"),
            ("pinecone", "Pinecone", "ai_ml"),
            ("weaviate", "Weaviate", "ai_ml"),
            ("cohere", "Cohere", "ai_ml"),

            # Communication
            ("slack", "Slack", "communication"),
            ("twilio", "Twilio", "communication"),
            ("sendgrid", "SendGrid", "communication"),
            ("postmark", "Postmark", "communication"),

            # Payments
            ("stripe", "Stripe", "payments"),
            ("braintree", "Braintree", "payments"),
            ("paypal", "PayPal", "payments"),
            ("adyen", "Adyen", "payments"),
            ("square", "Square", "payments"),
        ]

        # Check server header
        server = headers.get("server", "")
        if server:
            detected["cloud_infra"].append(f"Server: {server}")

        powered_by = headers.get("x-powered-by", "")
        if powered_by:
            detected["cloud_infra"].append(f"Powered by: {powered_by}")

        # Scan HTML for all signatures
        for sig, tech, category in signatures:
            if sig in html and tech not in detected[category]:
                detected[category].append(tech)

        # Count total
        total = sum(len(v) for v in detected.values())
        print(f"  🔍 Tech detection: {total} technologies found")

        return detected

    except Exception as e:
        print(f"  ✗ Tech detection failed for {url}: {e}")
        return detected


def format_tech_stack(detected):
    """Format detected tech stack into a readable block for the prompt."""
    lines = []
    labels = {
        "analytics":     "Analytics & Tracking",
        "crm_marketing": "CRM & Marketing",
        "cloud_infra":   "Cloud & Infrastructure",
        "frontend":      "Frontend Framework",
        "cms_platform":  "CMS / Platform",
        "data_tools":    "Data & Database Tools",
        "ai_ml":         "AI / ML Tools",
        "communication": "Communication",
        "payments":      "Payments",
        "other":         "Other",
    }
    for key, label in labels.items():
        tools = detected.get(key, [])
        if tools:
            lines.append(f"{label}: {', '.join(tools)}")

    return "\n".join(lines) if lines else "No technologies detected from HTML scan."


# ── CLEAN & SPLIT URLs ───────────────────────────────────────
def clean_urls(raw_urls):
    """Split multi-line URLs and deduplicate."""
    cleaned = []
    for raw in raw_urls:
        raw = str(raw).strip()
        if not raw or raw.lower() in ["nan", "none"]:
            continue

        for sep in ["\n", "\r", ",", " "]:
            if sep in raw:
                parts = raw.split(sep)
                for p in parts:
                    p = p.strip()
                    if p.startswith("http"):
                        cleaned.append(p)
                break
        else:
            if raw.startswith("http"):
                cleaned.append(raw)

    # Deduplicate using normalization
    seen = set()
    unique = []
    for u in cleaned:
        norm = normalize_url(u)
        if norm not in seen:
            seen.add(norm)
            unique.append(u)

    return unique


# ── DISCOVER INTERNAL LINKS FROM HOMEPAGE ────────────────────
def discover_internal_links(domain):
    """
    Fetch homepage HTML and extract all internal page links.
    Returns a deduplicated list of full URLs on the same domain.
    """
    try:
        session = requests.Session()
        session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        })

        resp = session.get(domain.strip(), timeout=12, allow_redirects=True)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")
        base_parsed = urlparse(domain.strip())
        base_domain = base_parsed.netloc.replace("www.", "").lower()

        links = set()

        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"].strip()

            # Skip empty, anchors, mailto, tel, javascript
            if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
                continue

            # Build full URL
            full_url = urljoin(domain, href)
            parsed = urlparse(full_url)

            # Only same domain
            link_domain = parsed.netloc.replace("www.", "").lower()
            if link_domain != base_domain:
                continue

            # Skip files (images, PDFs, etc.)
            skip_ext = (".pdf", ".png", ".jpg", ".jpeg", ".gif", ".svg",
                        ".zip", ".mp4", ".mp3", ".css", ".js", ".ico")
            if parsed.path.lower().endswith(skip_ext):
                continue

            # Remove fragments and trailing slash for dedup
            clean = f"{parsed.scheme}://{parsed.netloc}{parsed.path.rstrip('/')}"
            links.add(clean)

        print(f"  ✓ Discovered {len(links)} internal links from {domain}")
        return list(links)

    except Exception as e:
        print(f"  ✗ Could not discover links from {domain}: {e}")
        return []


# ── CLASSIFY PAGE BY URL PATTERN ─────────────────────────────
def classify_page(url):
    """Guess page type from URL path for labeling purposes."""
    path = urlparse(url).path.lower()

    patterns = {
        "About"        : ["about", "our-story", "who-we-are", "team", "leadership", "company"],
        "Services"     : ["service", "solution", "offering", "what-we-do", "capability", "platform", "product"],
        "Careers"      : ["career", "job", "hiring", "join", "open-position", "work-with"],
        "Blog"         : ["blog", "article", "insight", "resource", "thought", "post", "content"],
        "News"         : ["news", "press", "media", "announcement", "release"],
        "Case Study"   : ["case-stud", "customer-stor", "success-stor", "portfolio", "project"],
        "Contact"      : ["contact", "get-in-touch", "reach-us", "demo", "request"],
        "Partners"     : ["partner", "integration", "ecosystem", "alliance"],
        "Industries"   : ["industr", "vertical", "sector"],
        "Pricing"      : ["pricing", "plan", "package"],
        "Documentation": ["doc", "guide", "api", "developer", "support"],
    }

    for label, keywords in patterns.items():
        for kw in keywords:
            if kw in path:
                return label

    return "Other Page"


# ── AUTO-CRAWL ALL INTERNAL PAGES ────────────────────────────
def auto_crawl_subpages(domain, fetched_set, max_pages=15):
    """
    Discover all internal links from the homepage and crawl them.
    - Prioritizes high-value pages (about, services, careers, case studies)
    - Skips already-fetched URLs
    - Limits total pages to max_pages
    """
    print(f"  Discovering internal links from {domain}...")
    all_links = discover_internal_links(domain)

    if not all_links:
        print("  ✗ No internal links found — site may block crawling")
        return []

    # Classify and prioritize
    priority_order = [
        "About", "Services", "Careers", "Case Study", "Blog",
        "News", "Industries", "Partners", "Pricing", "Contact",
        "Documentation", "Other Page"
    ]

    classified = []
    for link in all_links:
        page_type = classify_page(link)
        classified.append((link, page_type))

    # Sort by priority
    def sort_key(item):
        try:
            return priority_order.index(item[1])
        except ValueError:
            return len(priority_order)

    classified.sort(key=sort_key)

    # Crawl with dedup and limit
    results = []
    crawled = 0

    for url, page_type in classified:
        if crawled >= max_pages:
            print(f"  ⏹ Reached max page limit ({max_pages})")
            break

        if is_duplicate(url, fetched_set):
            print(f"  ⏩ Skipped (already fetched): {url}")
            continue

        content = fetch_url_content(url, max_chars=2000)

        if content and len(content) > 100:
            results.append({
                "url": url,
                "content": content,
                "type": page_type
            })
            fetched_set.add(normalize_url(url))
            crawled += 1
        else:
            print(f"  ⏩ Skipped (no useful content): {url}")

    print(f"  ✓ Crawled {crawled} internal pages")
    return results


# ── DUCKDUCKGO SEARCH ────────────────────────────────────────
def search_company(company_name, max_results=3):
    """Search DuckDuckGo across 10 angles."""
    clean_name = company_name.strip()

    queries = [
        # Core intel
        f"{clean_name} latest news",
        f"{clean_name} technology stack platform tools",
        f"{clean_name} challenges problems issues",
        f"{clean_name} services solutions products",
        # Funding & financial
        f"{clean_name} funding raised investment",
        f"{clean_name} series round investors",
        f"{clean_name} revenue valuation acquisition",
        # Third-party sources
        f"site:crunchbase.com {clean_name}",
        f"site:tracxn.com {clean_name}",
        f"site:pitchbook.com {clean_name}",
        f"site:builtwith.com {clean_name}",
        f"site:glassdoor.com {clean_name} reviews",
        f"site:g2.com {clean_name}",
        f"site:linkedin.com/posts {clean_name}",
    ]

    all_results = []
    seen_urls = set()
    ddgs = DDGS()

    for query in queries:
        try:
            print(f"  🔍 Searching: {query}")
            results = ddgs.text(query, max_results=max_results)

            for r in results:
                url = r.get("href", "")
                norm = normalize_url(url) if url else ""
                if url and norm not in seen_urls:
                    seen_urls.add(norm)
                    all_results.append({
                        "url"     : url,
                        "title"   : r.get("title", ""),
                        "snippet" : r.get("body", ""),
                        "query"   : query
                    })

        except Exception as e:
            print(f"  ✗ Search failed for '{query}': {e}")

    print(f"  ✓ Found {len(all_results)} unique search results")
    return all_results


# ── ENRICH SEARCH RESULTS ────────────────────────────────────
def enrich_search_results(search_results, fetched_set, max_to_fetch=5):
    """Fetch full content from search results. Skip already-fetched URLs."""
    enriched = []
    fetched_count = 0

    for item in search_results:
        if fetched_count >= max_to_fetch:
            break

        url = item["url"]

        # ── DEDUP CHECK ──
        if is_duplicate(url, fetched_set):
            print(f"  ⏩ Skipped (already fetched): {url}")
            continue

        print(f"  Enriching: {url}")
        content = fetch_url_content(url, max_chars=2000)

        if content and len(content) > 100:
            enriched.append({
                "url"    : url,
                "title"  : item.get("title", ""),
                "content": content
            })
            fetched_set.add(normalize_url(url))
            fetched_count += 1

    return enriched


# ── BUILD FULL CONTENT WITH DEDUP ────────────────────────────
def build_full_content(raw_urls, company_name):
    """
    Master pipeline:
    1. Excel URLs
    2. Auto-crawl sub-pages (skip duplicates)
    3. DuckDuckGo search (skip duplicates)
    4. Enrich search results (skip duplicates)
    Returns (content_block, sources_list)
    """
    all_sources = []
    content_blocks = []
    fetched_set = set()  # ← master dedup tracker

    # Clean URLs first
    urls = clean_urls(raw_urls)
    print(f"\n📌 Cleaned URLs: {len(urls)} found")
    for u in urls:
        print(f"   → {u}")

    # ── STEP 1: Scrape Excel URLs ──
    print("\n📌 STEP 1: Scraping Excel URLs")
    for url in urls:
        content = fetch_url_content(url)
        if content:
            content_blocks.append(f"[SOURCE: {url}]\n[TYPE: Website]\n{content}")
            all_sources.append({"url": url, "type": "Website (Excel)"})
            fetched_set.add(normalize_url(url))

    # ── STEP 2: Auto-crawl (dedup-aware) ──
    main_domain = None
    for url in urls:
        if "linkedin" not in url.lower():
            main_domain = url
            break

    if main_domain:
        print(f"\n📌 STEP 2: Auto-crawling sub-pages of {main_domain}")
        subpages = auto_crawl_subpages(main_domain, fetched_set)
        for page in subpages:
            content_blocks.append(
                f"[SOURCE: {page['url']}]\n[TYPE: {page['type']}]\n{page['content']}"
            )
            all_sources.append({"url": page["url"], "type": page["type"]})

    # ── STEP 3: DuckDuckGo search ──
    print("\n📌 STEP 3: Searching DuckDuckGo (10 queries)")
    search_results = search_company(company_name)

    # ── STEP 4: Enrich search results (dedup-aware) ──
    print(f"\n📌 STEP 4: Enriching top search results (skipping duplicates)")
    enriched = enrich_search_results(search_results, fetched_set)

    for item in enriched:
        content_blocks.append(
            f"[SOURCE: {item['url']}]\n[TYPE: Web Search Result]\n[TITLE: {item['title']}]\n{item['content']}"
        )
        all_sources.append({"url": item["url"], "type": "Web Search"})

    # Add remaining search snippets (no full fetch needed)
    for item in search_results:
        if not is_duplicate(item["url"], fetched_set) and item["snippet"]:
            content_blocks.append(
                f"[SOURCE: {item['url']}]\n[TYPE: Search Snippet]\n[TITLE: {item['title']}]\n{item['snippet']}"
            )
            all_sources.append({"url": item["url"], "type": "Search Snippet"})
            fetched_set.add(normalize_url(item["url"]))

    full_content = "\n\n---\n\n".join(content_blocks) if content_blocks else "No content could be gathered. Use your general knowledge."

    # ── STEP 5: Tech stack detection from HTML ──
    detected_tech = {}
    if main_domain:
        print(f"\n📌 STEP 5: Scanning HTML for tech stack")
        detected_tech = detect_tech_stack(main_domain)

    print(f"\n✓ Total sources collected: {len(all_sources)}")
    print(f"✓ Total unique URLs fetched: {len(fetched_set)}")
    skipped = len(urls) + 12 + len(search_results) - len(fetched_set)
    if skipped > 0:
        print(f"✓ Duplicate fetches avoided: ~{skipped}")

    return full_content, all_sources, detected_tech


# ── FORMAT CONTACTS ──────────────────────────────────────────
def format_contacts(contacts):
    if not contacts:
        return "No contacts available."
    lines = [
        f"- {c.get('name', '').strip()} | {c.get('title', '').strip()} | {c.get('email', '').strip()}"
        for c in contacts
        if any([c.get('name'), c.get('title'), c.get('email')])
    ]
    return "\n".join(lines) if lines else "No contacts available."


# ── MAIN ANALYSIS ────────────────────────────────────────────
def _call_gemini(model, prompt, label="", max_retries=3):
    """Single Gemini call with retry/backoff and error handling."""
    import time

    # Cap prompt size to avoid 504s (~150k chars ≈ 37k tokens is safe)
    MAX_PROMPT_CHARS = 150_000
    if len(prompt) > MAX_PROMPT_CHARS:
        prompt = prompt[:MAX_PROMPT_CHARS] + "\n[CONTENT TRUNCATED FOR LENGTH]"
        print(f"  ⚠ {label} prompt truncated to {MAX_PROMPT_CHARS} chars")

    for attempt in range(1, max_retries + 1):
        try:
            resp = model.generate_content(
                prompt,
                generation_config=genai.GenerationConfig(
                    temperature=0.3,
                    max_output_tokens=8192
                ),
                request_options={"timeout": 120}
            )

            text = ""
            try:
                text = resp.text.strip()
            except Exception:
                for part in resp.candidates[0].content.parts:
                    if hasattr(part, "text") and part.text:
                        text += part.text
                text = text.strip()

            print(f"  {label} response: {len(text)} chars")
            return text

        except Exception as e:
            err = f"{type(e).__name__}: {e}"
            if attempt < max_retries:
                wait = 2 ** attempt  # 2s, 4s, 8s
                print(f"  {label} attempt {attempt} failed ({err}) — retrying in {wait}s...")
                time.sleep(wait)
            else:
                print(f"  {label} ERROR: {err}")
                return ""


def _parse_json(text):
    """Clean and parse JSON from Gemini response."""
    if not text:
        return None
    c = text
    if "```json" in c: c = c.split("```json")[1]
    if "```" in c: c = c.split("```")[0]
    return json.loads(c.strip())


def analyze_company(company_info, urls, contacts, api_key):

    global model
    model = configure_gemini(api_key)

    prompt_template = load_prompt()
    contacts_block  = format_contacts(contacts)
    scraped_content, sources, detected_tech = build_full_content(urls, company_info.get("company_name", ""))

    sources_list_text = "\n".join([f"- [{s['type']}] {s['url']}" for s in sources]) if sources else "No sources."
    tech_stack_text = format_tech_stack(detected_tech) if detected_tech else "No technologies detected."

    # Extract DXW profile and rules from prompt
    dxw_block = prompt_template.split("# RULES")[0] if "# RULES" in prompt_template else prompt_template
    rules_block = ""
    if "# RULES" in prompt_template and "# JSON OUTPUT" in prompt_template:
        rules_block = prompt_template.split("# RULES")[1].split("# JSON OUTPUT")[0]

    context = f"""
COMPANY: {company_info.get('company_name','Unknown')} | Industry: {company_info.get('industry','Unknown')} | Size: {company_info.get('employee_size','Unknown')} | Revenue: {company_info.get('revenue','Unknown')} | Location: {company_info.get('city','')}, {company_info.get('state','')}, {company_info.get('country','')}

CONTACTS: {contacts_block}

DETECTED TECH (confirmed from HTML scan): {tech_stack_text}

SOURCES: {sources_list_text}

CONTENT:
{scraped_content}
"""

    base_instructions = f"""
{dxw_block}
# RULES
{rules_block}
Cite sources inline as [URL]. Every text field: 1-2 concise sentences max. Keep response under 5000 tokens.
Treat DETECTED TECH as confirmed. Map DXW to specific tools.
{context}
"""

    # ═══ CALL 1: Sections 1-4 ═══
    schema1 = '{"1_business_operations":{"one_line_summary":"","company_overview":"","who_they_serve":"","business_model":"","company_size_and_stage":"","geography_and_presence":"","key_partnerships":[],"competitive_positioning":"","operational_complexity_analysis":"","where_data_is_generated":"","real_time_data_environment":"","regulatory_environment":"","sources_referenced":[]},"2_technology_stack":{"confirmed_technologies":[],"likely_technologies":[],"cloud_infrastructure":"","databases_and_warehouses":"","data_pipelines_and_etl":"","ai_ml_tools_and_frameworks":"","analytics_and_bi":"","crm_and_marketing_tools":"","legacy_vs_modern_assessment":"","hybrid_complexity_analysis":"","integration_burden_analysis":"","where_dxw_fits":[{"their_system":"","the_problem":"","dxw_service":"","what_dxw_does":"","impact":"","urgency":""}],"new_suggestions":[{"recommendation":"","why":"","dxw_service":"","impact":""}],"sources_referenced":[]},"3_data_architecture":{"data_flow_analysis":"","known_data_systems":[],"silo_analysis":"","governance_break_points":"","structured_vs_unstructured":"","central_warehouse_assessment":"","data_duplication_risks":"","cross_system_dependencies":"","scalability_assessment":"","migration_signals":"","dxw_opportunities":[{"gap":"","dxw_service":"","what_dxw_does":"","impact":""}],"sources_referenced":[]},"4_governance_maturity":{"overall_rating":"","governance_analysis":"","governance_hiring_signals":"","outsourcing_signals":"","missing_standards":"","compliance_pressure":"","dxw_opportunities":[{"gap":"","dxw_service":"","what_dxw_does":"","impact":""}],"sources_referenced":[]}}'

    print("\n" + "=" * 60)
    print("CALL 1/3: Sections 1-4 (Business, Tech, Data, Governance)...")
    print("=" * 60)
    text1 = _call_gemini(model, f"{base_instructions}\nReturn ONLY this JSON:\n{schema1}", "Call 1")

    # ═══ CALL 2: Sections 5-8 ═══
    schema2 = '{"5_hiring_intelligence":{"overview":"","roles_detected":[],"hiring_inferences":[{"role_or_pattern":"","what_it_means":"","implied_pain":"","dxw_relevance":"","evidence_type":""}],"talent_gaps":"","budget_direction":"","sources_referenced":[]},"6_public_signals":{"overview":"","glassdoor_analysis":"","customer_feedback":"","news_and_media":"","regulatory_signals":"","transformation_friction":"","signal_inferences":[{"signal":"","what_it_means":"","confidence":"","dxw_relevance":""}],"sources_referenced":[]},"7_products_and_pain_areas":{"has_own_products":"","products":[{"name":"","description":"","target_customer":"","pain_analysis":"","dxw_fit":"","dxw_service":"","evidence":"","evidence_type":""}],"services":[{"name":"","description":"","pain_analysis":"","dxw_fit":"","dxw_service":""}],"sources_referenced":[]},"8_maturity_assessment":{"ai_ml_maturity":{"rating":"","analysis":""},"data_governance_maturity":{"rating":"","analysis":""},"data_operations_maturity":{"rating":"","analysis":""},"integration_maturity":{"rating":"","analysis":""},"reporting_bi_maturity":{"rating":"","analysis":""},"automation_maturity":{"rating":"","analysis":""},"overall_assessment":"","sources_referenced":[]}}'

    print(f"\nCALL 2/3: Sections 5-8 (Hiring, Signals, Products, Maturity)...")
    print("=" * 60)
    text2 = _call_gemini(model, f"{base_instructions}\nReturn ONLY this JSON:\n{schema2}", "Call 2")

    # ═══ CALL 3: Sections 9-15 ═══
    schema3 = '{"9_pain_hypothesis_chain":[{"observation":"","inference":"","likely_pain":"","business_impact":"","confidence":"","urgency":"","dxw_service":"","dxw_solution":"","stakeholder":"","evidence_type":""}],"10_dxw_opportunity_mapping":[{"dxw_service":"","target_need":"","why_relevant":"","impact":"","stakeholder":"","urgency":""}],"11_funding_and_investment":{"company_type":"","publicly_traded":"","ticker":"","funding_rounds":[{"round":"","amount":"","date":"","lead_investor":"","source":""}],"total_funding":"","valuation":"","key_investors":[],"revenue_analysis":"","investment_focus":"","recent_milestones":[],"financial_health":"","dxw_implication":"","sources_referenced":[]},"12_leadership_signals":{"key_leaders":[],"leadership_messaging_analysis":"","strategic_priorities":[],"implied_pain":"","sources_referenced":[]},"13_confidence_and_risk":{"overall_confidence":"","high_confidence_findings":[],"medium_confidence_findings":[],"low_confidence_findings":[],"key_uncertainties":[],"what_we_dont_know":[],"recommended_next_steps_to_validate":[]},"14_scores":{"operational_complexity":{"score":0,"why":""},"data_architecture_risk":{"score":0,"why":""},"governance_gap":{"score":0,"why":""},"tech_modernization_need":{"score":0,"why":""},"ai_maturity":{"score":0,"why":""},"dxw_fitment":{"score":0,"why":""},"timing_urgency":{"score":0,"why":""},"account_potential":{"score":0,"why":""}},"15_summary":{"company":"","what_they_do":"","why_dxw_should_care":"","top_3_opportunities":[],"who_to_call":"","deal_size":"","tier":"","next_step":""}}'

    print(f"\nCALL 3/3: Sections 9-15 (Pain, DXW Map, Funding, Leadership, Scores, Summary)...")
    print("=" * 60)
    text3 = _call_gemini(model, f"{base_instructions}\nReturn ONLY this JSON:\n{schema3}", "Call 3")

    # ═══ MERGE ═══
    try:
        data1 = _parse_json(text1) if text1 else {}
        data2 = _parse_json(text2) if text2 else {}
        data3 = _parse_json(text3) if text3 else {}

        if not data1 and not data2 and not data3:
            print("ERROR: All calls failed")
            return _fallback(company_info), sources

        merged = {}
        for i, d in enumerate([data1, data2, data3], 1):
            if d:
                merged.update(d)
                print(f"✓ Call {i} parsed")
            else:
                print(f"✗ Call {i} failed")

        print(f"✓ Merged: {len(merged)} sections\n")
        return merged, sources

    except json.JSONDecodeError as e:
        print(f"JSON PARSE ERROR: {e}")
        return _fallback(company_info), sources
    except Exception as e:
        print(f"MERGE ERROR: {type(e).__name__}: {e}")
        return _fallback(company_info), sources


# ── FALLBACK ─────────────────────────────────────────────────
def _fallback(company_info):
    name = company_info.get("company_name", "Unknown")
    fb = {"score": 5, "why": "Analysis failed"}
    mat = {"rating": "Unknown", "analysis": "Analysis failed"}
    return {
        "1_business_operations": {"one_line_summary":f"{name} — analysis failed","company_overview":"","who_they_serve":"","business_model":"","company_size_and_stage":"","geography_and_presence":"","key_partnerships":[],"competitive_positioning":"","operational_complexity_analysis":"","where_data_is_generated":"","real_time_data_environment":"","regulatory_environment":"","sources_referenced":[]},
        "2_technology_stack": {"confirmed_technologies":[],"likely_technologies":[],"cloud_infrastructure":"","databases_and_warehouses":"","data_pipelines_and_etl":"","ai_ml_tools_and_frameworks":"","analytics_and_bi":"","crm_and_marketing_tools":"","legacy_vs_modern_assessment":"","hybrid_complexity_analysis":"","integration_burden_analysis":"","where_dxw_fits":[],"new_suggestions":[],"sources_referenced":[]},
        "3_data_architecture": {"data_flow_analysis":"","known_data_systems":[],"silo_analysis":"","governance_break_points":"","structured_vs_unstructured":"","central_warehouse_assessment":"","data_duplication_risks":"","cross_system_dependencies":"","scalability_assessment":"","migration_signals":"","dxw_opportunities":[],"sources_referenced":[]},
        "4_governance_maturity": {"overall_rating":"","governance_analysis":"","dxw_opportunities":[],"sources_referenced":[]},
        "5_hiring_intelligence": {"overview":"","roles_detected":[],"hiring_inferences":[],"talent_gaps":"","budget_direction":"","sources_referenced":[]},
        "6_public_signals": {"overview":"","signal_inferences":[],"sources_referenced":[]},
        "7_products_and_pain_areas": {"has_own_products":"","products":[],"services":[],"sources_referenced":[]},
        "8_maturity_assessment": {"ai_ml_maturity":mat,"data_governance_maturity":mat,"data_operations_maturity":mat,"integration_maturity":mat,"reporting_bi_maturity":mat,"automation_maturity":mat,"overall_assessment":"Analysis failed","sources_referenced":[]},
        "9_pain_hypothesis_chain": [],
        "10_dxw_opportunity_mapping": [],
        "11_funding_and_investment": {"company_type":"","funding_rounds":[],"total_funding":"INSUFFICIENT DATA","valuation":"","key_investors":[],"revenue_analysis":"","investment_focus":"","recent_milestones":[],"financial_health":"","dxw_implication":"","sources_referenced":[]},
        "12_leadership_signals": {"key_leaders":[],"leadership_messaging_analysis":"","strategic_priorities":[],"implied_pain":"","sources_referenced":[]},
        "13_confidence_and_risk": {"overall_confidence":"None","high_confidence_findings":[],"medium_confidence_findings":[],"low_confidence_findings":[],"key_uncertainties":[],"what_we_dont_know":["Analysis failed"],"recommended_next_steps_to_validate":[]},
        "14_scores": {"operational_complexity":fb,"data_architecture_risk":fb,"governance_gap":fb,"tech_modernization_need":fb,"ai_maturity":fb,"dxw_fitment":fb,"timing_urgency":fb,"account_potential":fb},
        "15_summary": {"company":name,"what_they_do":"Analysis failed","why_dxw_should_care":"Retry","top_3_opportunities":[],"who_to_call":"—","deal_size":"—","tier":"Unknown","next_step":"Retry"}
    }