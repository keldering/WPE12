import os
import re
from datetime import datetime
import requests
from urllib.parse import urljoin
import tkinter as tk
from tkinter import messagebox, filedialog, scrolledtext
from bs4 import BeautifulSoup, NavigableString

# --- CONFIGURATIE VOOR DOELGERICHTE SCRAPING ---
SITE_CONFIGS = {
    "standaard": {
        "content_container": ["main", "article", "div.content", "div.body"],
        "ignore_elements": ["script", "style", "nav", "footer", "header", "aside", ".sidebar", ".ads"],
        "title_selector": "h1"
    }
}

# Globale variabele om de schone titel te onthouden voor de bestandsnaam
current_page_title = "Journaalpost"

def extract_domain(url):
    match = re.search(r"https?://(?:www\.)?([^/]+)", url)
    return match.group(1) if match else "standaard"

def clean_fragment(text):
    if not text:
        return ""
    return re.sub(r'\n\s*\n', '\n\n', text.strip())

def slugify_title(text):
    """Maakt een titel veilig voor Windows bestandsnamen."""
    if not text:
        return "Journaalpost"
    clean = re.sub(r'[\\/*?:"<>|]', "", text)
    return re.sub(r'\s+', '_', clean.strip())[:40]

def clean_url(href, base_url=""):
    """Sanitizes raw href strings, handling list representations, trailing brackets, and relative paths."""
    if not href:
        return ""
    if isinstance(href, (list, tuple)):
        href = href[0] if href else ""
    href_str = str(href).strip("[]'\" \t\r\n")
    if href_str.startswith(('javascript:', 'mailto:', 'tel:', '#')):
        return ""
    full_url = urljoin(base_url, href_str) if base_url else href_str
    full_url = re.sub(r"[\]\)'\",\.]+$", "", full_url.strip())
    return full_url

def node_to_markdown_inline(node, base_url=""):
    """Converteert inline HTML elementen (a, code, strong, em) naar Markdown met behoud van schone links."""
    if not node:
        return ""
    
    parts = []
    children = getattr(node, 'children', [node])
    for child in children:
        if isinstance(child, NavigableString):
            parts.append(str(child))
        elif child.name == 'a':
            raw_href = child.get('href', '')
            full_url = clean_url(raw_href, base_url)
            link_text = clean_fragment(child.get_text())
            if full_url:
                if link_text:
                    parts.append(f" [{link_text}]({full_url}) ")
                else:
                    parts.append(f" [{full_url}]({full_url}) ")
            else:
                parts.append(link_text)
        elif child.name in ['strong', 'b']:
            text = clean_fragment(child.get_text())
            parts.append(f"**{text}**" if text else "")
        elif child.name in ['em', 'i']:
            text = clean_fragment(child.get_text())
            parts.append(f"*{text}*" if text else "")
        elif child.name == 'code' and getattr(node, 'name', '') != 'pre':
            text = child.get_text().strip()
            parts.append(f"`{text}`" if text else "")
        else:
            parts.append(node_to_markdown_inline(child, base_url))
            
    res = "".join(parts)
    return re.sub(r'[ \t]+', ' ', res).strip()

def parse_html_table(table_node, base_url=""):
    rows = table_node.find_all('tr')
    if not rows:
        return ""
        
    md_table = []
    header_cells = rows[0].find_all(['th', 'td'])
    headers = [node_to_markdown_inline(c, base_url) for c in header_cells]
    
    if not any(headers):
        return ""
        
    md_table.append("| " + " | ".join(headers) + " |")
    md_table.append("| " + " | ".join(["---"] * len(headers)) + " |")
    
    for row in rows[1:]:
        cells = row.find_all(['td', 'th'])
        row_data = [node_to_markdown_inline(c, base_url) for c in cells]
        if len(row_data) < len(headers):
            row_data += [""] * (len(headers) - len(row_data))
        md_table.append("| " + " | ".join(row_data[:len(headers)]) + " |")
        
    return "\n" + "\n".join(md_table) + "\n\n"

def scrape_to_structured_markdown(html_source, url, project_name="Project Keldering"):
    global current_page_title
    domain = extract_domain(url)
    config = SITE_CONFIGS.get(domain, SITE_CONFIGS["standaard"])
    
    soup = BeautifulSoup(html_source, 'html.parser')
    md_document = []
    
    page_title = soup.find(config["title_selector"])
    title_text = clean_fragment(page_title.get_text()) if page_title else "Geen titel gevonden"
    current_page_title = slugify_title(title_text)
    
    # --- GEMINI-OPTIMIZED YAML FRONTMATTER ---
    md_document.append("---")
    md_document.append(f'title: "{title_text}"')
    md_document.append(f'source_url: "{url}"')
    md_document.append(f'domain: "{domain}"')
    md_document.append(f'scraped_date: "{datetime.now().strftime("%Y-%m-%d %H:%M")}"')
    md_document.append(f'project: "{project_name}"')
    md_document.append('status: "Gemini-Ready"')
    md_document.append("---\n")
    
    md_document.append(f"# {title_text}\n")
    
    for selector in config["ignore_elements"]:
        for garbage in soup.select(selector):
            garbage.decompose()
            
    main_container = None
    for selector in config["content_container"]:
        main_container = soup.select_one(selector)
        if main_container:
            break
            
    if not main_container:
        main_container = soup.body
        
    if main_container:
        for element in main_container.find_all(['h1', 'h2', 'h3', 'h4', 'p', 'blockquote', 'pre', 'table', 'ul', 'ol'], recursive=True):
            if element.find_parent(['table', 'ul', 'ol', 'blockquote', 'pre']) and element.name not in ['table', 'ul', 'ol', 'blockquote', 'pre']:
                continue
                
            if element.name in ['h1', 'h2', 'h3', 'h4']:
                header_text = node_to_markdown_inline(element, url)
                if element.name == 'h1' and header_text.strip().lower() == title_text.strip().lower():
                    continue
                level = int(element.name[1])
                md_document.append(f"\n{'#' * level} {header_text}\n")
            elif element.name == 'p':
                text = node_to_markdown_inline(element, url)
                if text:
                    md_document.append(f"\n{text}\n")
            elif element.name == 'blockquote':
                text = node_to_markdown_inline(element, url)
                if text:
                    quoted = "\n".join(f"> {line}" for line in text.splitlines() if line)
                    md_document.append(f"\n{quoted}\n")
            elif element.name == 'pre':
                code_text = element.get_text().strip()
                if code_text:
                    md_document.append(f"\n```\n{code_text}\n```\n")
            elif element.name == 'table':
                md_document.append(parse_html_table(element, url))
            elif element.name in ['ul', 'ol']:
                items = element.find_all('li', recursive=False)
                for idx, item in enumerate(items, 1):
                    marker = f"{idx}." if element.name == 'ol' else "*"
                    text = node_to_markdown_inline(item, url)
                    md_document.append(f"{marker} {text}")
                md_document.append("")

    final_output = "\n".join(md_document)
    return re.sub(r'\n{3,}', '\n\n', final_output)

# --- GUI LOGICA ---
def on_preview_link_click(event):
    click_index = preview_box.index(f"@{event.x},{event.y}")
    if "preview_link" in preview_box.tag_names(click_index):
        ranges = preview_box.tag_ranges("preview_link")
        for i in range(0, len(ranges), 2):
            start, end = ranges[i], ranges[i + 1]
            if preview_box.compare(start, "<=", click_index) and preview_box.compare(click_index, "<", end):
                clicked_text = preview_box.get(start, end).strip()
                
                match = re.search(r'\((https?://[^\s\)]+)\)', clicked_text)
                if match:
                    raw_url = match.group(1)
                elif clicked_text.startswith(('http://', 'https://')):
                    raw_url = clicked_text
                else:
                    raw_url = ""
                    
                target_url = clean_url(raw_url)
                if target_url:
                    url_input.delete(0, tk.END)
                    url_input.insert(0, target_url)
                    messagebox.showinfo(
                        "URL Overgezet", 
                        f"Geselecteerde URL is geladen in het invoerveld:\n{target_url}\n\nKlik op 'Scrape and format MD' om deze pagina te verwerken!"
                    )
                break

def make_preview_links_clickable():
    preview_box.tag_config("preview_link", foreground="#1E88E5", underline=True)
    preview_box.tag_bind("preview_link", "<Enter>", lambda e: preview_box.config(cursor="hand2"))
    preview_box.tag_bind("preview_link", "<Leave>", lambda e: preview_box.config(cursor=""))
    preview_box.tag_bind("preview_link", "<Button-1>", on_preview_link_click)

    preview_box.tag_remove("preview_link", "1.0", tk.END)

    content = preview_box.get("1.0", tk.END)
    md_link_pattern = re.compile(r'\[([^\]]+)\]\((https?://[^\s\)]+)\)|https?://[^\s\)]+')

    for match in md_link_pattern.finditer(content):
        start_idx = f"1.0 + {match.start()} chars"
        end_idx = f"1.0 + {match.end()} chars"
        preview_box.tag_add("preview_link", start_idx, end_idx)


def execute_scrape():
    url = url_input.get().strip()
    if not url:
        messagebox.showwarning("Invoer ontbreekt", "Vul eerst een geldige URL in.")
        return
        
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept-Language': 'nl,en-US;q=0.9,en;q=0.8'
        }
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        
        markdown_result = scrape_to_structured_markdown(response.text, url)
        
        preview_box.delete(1.0, tk.END)
        preview_box.insert(tk.END, markdown_result)
        make_preview_links_clickable()
        
        btn_save.config(state=tk.NORMAL)
        
    except requests.exceptions.RequestException as req_err:
        messagebox.showerror("Netwerk / Scrape Fout", f"Kan de pagina niet ophalen:\n{str(req_err)}")
    except Exception as error:
        messagebox.showerror("Verwerkings Fout", f"Fout bij verwerken van de pagina:\n{str(error)}")

def save_markdown():
    global current_page_title
    markdown_content = preview_box.get(1.0, tk.END).strip()
    if not markdown_content:
        return
        
    date_str = datetime.now().strftime('%Y-%m-%d')
    suggested_filename = f"{date_str}_Keldering_{current_page_title}.md"
        
    save_path = filedialog.asksaveasfilename(
        initialfile=suggested_filename,
        defaultextension=".md",
        filetypes=[("Markdown bestanden", "*.md")],
        title="Sla het Gemini-brondocument op"
    )
    
    if save_path:
        try:
            with open(save_path, "w", encoding="utf-8") as f:
                f.write(markdown_content)
            messagebox.showinfo("Succes", f"Bestand opgeslagen op:\n{save_path}")
            
            url_input.delete(0, tk.END)
            preview_box.delete(1.0, tk.END)
            btn_save.config(state=tk.DISABLED)
        except Exception as e:
            messagebox.showerror("Opslag Fout", f"Kon bestand niet opslaan:\n{str(e)}")

# --- USER INTERFACE (TKINTER) ---
if __name__ == "__main__":
    app = tk.Tk()
    app.title("WPE12 - Gemini Source Formatter + Auto-Naming")
    app.geometry("750x850")
    app.configure(bg="#f5f5f5")

    tk.Label(app, text="Voer de te scrapen URL in:", bg="#f5f5f5", font=("Arial", 10, "bold")).pack(pady=5)
    url_input = tk.Entry(app, width=85, font=("Arial", 10))
    url_input.pack(pady=5)
    url_input.focus()

    btn_scrape = tk.Button(
        app, text="Scrape and format MD", command=execute_scrape, 
        bg="#2196F3", fg="white", font=("Arial", 10, "bold"), padx=10
    )
    btn_scrape.pack(pady=5)

    tk.Label(app, text="Markdown Voorbeeld (Bewerkbaar - Klik op een link om URL over te nemen):", bg="#f5f5f5", font=("Arial", 9, "italic")).pack(pady=2)
    preview_box = scrolledtext.ScrolledText(app, width=85, height=36, font=("Consolas", 10), bg="white", fg="black")
    preview_box.pack(pady=5, padx=10)

    btn_save = tk.Button(
        app, text="Sla Markdown op (.md)", command=save_markdown, 
        bg="#4CAF50", fg="white", font=("Arial", 11, "bold"), padx=15, pady=5,
        state=tk.DISABLED  
    )
    btn_save.pack(pady=10)

    app.mainloop()



