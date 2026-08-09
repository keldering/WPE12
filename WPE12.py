import os
import re
from datetime import datetime
import urllib.request
import tkinter as tk
from tkinter import messagebox, filedialog, scrolledtext
from bs4 import BeautifulSoup

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
    # Sla alleen letters, cijfers en spaties op, vervang de rest door niks
    clean = re.sub(r'[\\/*?:"<>|]', "", text)
    # Vervang spaties door underscores en kap af op 40 karakters voor de leesbaarheid
    return re.sub(r'\s+', '_', clean.strip())[:40]

def parse_html_table(table_node):
    rows = table_node.find_all('tr')
    if not rows:
        return ""
        
    md_table = []
    header_cells = rows.find_all(['th', 'td'])
    headers = [clean_fragment(c.get_text()) for c in header_cells]
    
    if not any(headers):
        return ""
        
    md_table.append("| " + " | ".join(headers) + " |")
    md_table.append("| " + " | ".join(["---"] * len(headers)) + " |")
    
    for row in rows[1:]:
        cells = row.find_all(['td', 'th'])
        row_data = [clean_fragment(c.get_text()) for c in cells]
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
    
    # Sla de schone titel op voor de bestandsnaam-generatie
    current_page_title = slugify_title(title_text)
    
    md_document.append("# METADATA")
    md_document.append(f"* **Documenttitel**: {title_text}")
    md_document.append(f"* **Bron-URL**: {url}")
    md_document.append(f"* **Project**: {project_name}")
    md_document.append(f"* **Scrapedatum**: {datetime.now().strftime('%d-%m-%Y %H:%M')}")
    md_document.append(f"* **Status**: Gestructureerd voor Gemini\n")
    md_document.append("---\n")
    
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
        for element in main_container.find_all(['h1', 'h2', 'h3', 'p', 'table', 'ul', 'ol'], recursive=True):
            if element.find_parent(['table', 'ul', 'ol']) and element.name not in ['table', 'ul', 'ol']:
                continue
                
            if element.name in ['h1', 'h2', 'h3']:
                level = int(element.name[1])
                md_document.append(f"\n{'#' * level} {clean_fragment(element.get_text())}")
            elif element.name == 'p':
                text = clean_fragment(element.get_text())
                if text:
                    md_document.append(f"\n{text}\n")
            elif element.name == 'table':
                md_document.append(parse_html_table(element))
            elif element.name in ['ul', 'ol']:
                items = element.find_all('li', recursive=False)
                for item in items:
                    marker = "1." if element.name == 'ol' else "*"
                    md_document.append(f"{marker} {clean_fragment(item.get_text())}")
                md_document.append("")

    final_output = "\n".join(md_document)
    return re.sub(r'\n{3,}', '\n\n', final_output)

# --- GUI LOGICA ---
def execute_scrape():
    url = url_input.get().strip()
    if not url:
        messagebox.showwarning("Invoer ontbreekt", "Vul eerst een geldige URL in.")
        return
        
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
        with urllib.request.urlopen(req) as response:
            html = response.read().decode('utf-8', errors='ignore')
            
        markdown_result = scrape_to_structured_markdown(html, url)
        
        preview_box.delete(1.0, tk.END)
        preview_box.insert(tk.END, markdown_result)
        
        btn_save.config(state=tk.NORMAL)
        
    except Exception as error:
        messagebox.showerror("Scrape Fout", f"Kan de pagina niet verwerken:\n{str(error)}")

def save_markdown():
    global current_page_title
    markdown_content = preview_box.get(1.0, tk.END).strip()
    if not markdown_content:
        return
        
    # Genereer de automatische chronologische bestandsnaam (YYYY-MM-DD_Titel)
    date_str = datetime.now().strftime('%Y-%m-%d')
    suggested_filename = f"{date_str}_Keldering_{current_page_title}.md"
        
    save_path = filedialog.asksaveasfilename(
        initialfile=suggested_filename,  # Dit injecteert de automatische naam in de dialoog
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

tk.Label(app, text="Markdown Voorbeeld (Bewerkbaar):", bg="#f5f5f5", font=("Arial", 9, "italic")).pack(pady=2)
preview_box = scrolledtext.ScrolledText(app, width=85, height=36, font=("Consolas", 10), bg="white", fg="black")
preview_box.pack(pady=5, padx=10)

btn_save = tk.Button(
    app, text="Sla Markdown op (.md)", command=save_markdown, 
    bg="#4CAF50", fg="white", font=("Arial", 11, "bold"), padx=15, pady=5,
    state=tk.DISABLED  
)
btn_save.pack(pady=10)

app.mainloop()
