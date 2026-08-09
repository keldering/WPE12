import requests
from bs4 import BeautifulSoup, NavigableString
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import textwrap
import re
import webbrowser
from datetime import datetime
from urllib.parse import urljoin

# Store extracted data in memory so it can be formatted on the fly without re-fetching
last_extracted_data = []
last_extracted_url = ""

def clean_text(text):
    if not text:
        return ""
    return re.sub(r'\s+', ' ', text).strip()

def node_to_markdown_inline(node, base_url=""):
    """Converteert inline HTML elementen (a, code, strong, em) naar Markdown met behoud van links."""
    if not node:
        return ""
    
    parts = []
    children = getattr(node, 'children', [node])
    for child in children:
        if isinstance(child, NavigableString):
            parts.append(str(child))
        elif child.name == 'a':
            href = child.get('href', '').strip()
            link_text = clean_text(child.get_text())
            if href:
                full_url = urljoin(base_url, href) if base_url else href
                if link_text:
                    parts.append(f" [{link_text}]({full_url}) ")
                else:
                    parts.append(f" [{full_url}]({full_url}) ")
            else:
                parts.append(link_text)
        elif child.name in ['strong', 'b']:
            text = clean_text(child.get_text())
            parts.append(f"**{text}**" if text else "")
        elif child.name in ['em', 'i']:
            text = clean_text(child.get_text())
            parts.append(f"*{text}*" if text else "")
        elif child.name == 'code':
            text = child.get_text().strip()
            parts.append(f"`{text}`" if text else "")
        else:
            parts.append(node_to_markdown_inline(child, base_url))
            
    res = "".join(parts)
    return re.sub(r'[ \t]+', ' ', res).strip()

def fetch_and_extract(url, extract_type, keyword=""):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        if extract_type == "Links":
            extracted_data = []
            for link in soup.find_all('a', href=True):
                href = urljoin(url, link.get('href'))
                text = clean_text(link.get_text())
                item = f"[{text}]({href})" if text else href
                extracted_data.append(item)
                
        elif extract_type == "Headings (H1-H6)":
            headings = ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']
            extracted_data = []
            for tag in soup.find_all(headings):
                level = tag.name.upper()
                text = node_to_markdown_inline(tag, url)
                if text:
                    extracted_data.append(f"{level}: {text}")
        
        elif extract_type == "Paragraphs":
            extracted_data = []
            for p in soup.find_all('p'):
                text = node_to_markdown_inline(p, url)
                if text:
                    extracted_data.append(text)
        
        elif extract_type == "Images":
            extracted_data = []
            for img in soup.find_all('img', src=True):
                src = urljoin(url, img['src'])
                alt = clean_text(img.get('alt', ''))
                item = f"![{alt}]({src})" if alt else src
                extracted_data.append(item)
        else:
            extracted_data = []
        
        # Apply keyword filtering if specified
        if keyword:
            keyword_lower = keyword.lower()
            extracted_data = [item for item in extracted_data if keyword_lower in item.lower()]
            
        return extracted_data
    
    except requests.exceptions.RequestException as e:
        messagebox.showerror("Netwerk Fout", f"Kan URL niet ophalen:\n{str(e)}")
        return None

def get_char_width():
    try:
        width = int(width_entry.get())
        return width if width > 0 else 75
    except ValueError:
        return 75

def format_extracted_data(data, char_width=75, mode="Markdown"):
    if not data:
        return ""

    if mode == "Markdown Snippet (Journal Ready)":
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M')
        header_block = f"### Extracted Snippets\n* **Source URL**: [{last_extracted_url}]({last_extracted_url})\n* **Date**: {now_str}\n\n---\n"
        snippets = []
        for item in data:
            lines = str(item).splitlines()
            quoted = "\n".join(f"> {line}" for line in lines if line)
            snippets.append(quoted)
        return header_block + "\n\n".join(snippets)
    else:
        formatted_items = []
        for item in data:
            lines = str(item).splitlines()
            wrapped_item = "\n".join(
                textwrap.fill(line, width=char_width, break_long_words=True)
                for line in lines if line
            )
            formatted_items.append(wrapped_item)
        return "\n\n".join(formatted_items)

def extract_button_click():
    global last_extracted_data, last_extracted_url
    url = url_entry.get().strip()
    extract_type = extract_var.get()
    keyword = filter_entry.get().strip()
    char_width = get_char_width()
    mode = format_mode_var.get()
    
    if url and extract_type:
        last_extracted_url = url
        extracted_data = fetch_and_extract(url, extract_type, keyword=keyword)
        
        result_text.delete(1.0, tk.END)
        if extracted_data is not None and len(extracted_data) > 0:
            last_extracted_data = extracted_data
            formatted_text = format_extracted_data(last_extracted_data, char_width=char_width, mode=mode)
            result_text.insert(tk.END, formatted_text)
            make_links_clickable_click()
        elif extracted_data is not None and len(extracted_data) == 0:
            last_extracted_data = []
            result_text.insert(tk.END, "Geen gegevens gevonden voor de geselecteerde zoekopdracht/filter.")
        else:
            last_extracted_data = []
            result_text.insert(tk.END, "Fout bij het ophalen van gegevens.")
    else:
        messagebox.showwarning("Invoer ontbreekt", "Vul een geldige URL in en kies een extractietype.")

def format_button_click():
    global last_extracted_data
    char_width = get_char_width()
    mode = format_mode_var.get()
    
    if last_extracted_data:
        formatted_text = format_extracted_data(last_extracted_data, char_width=char_width, mode=mode)
        result_text.delete(1.0, tk.END)
        result_text.insert(tk.END, formatted_text)
        make_links_clickable_click()
    else:
        current_content = result_text.get("1.0", "end-1c").strip()
        if current_content:
            lines = current_content.splitlines()
            formatted_text = format_extracted_data(lines, char_width=char_width, mode=mode)
            result_text.delete(1.0, tk.END)
            result_text.insert(tk.END, formatted_text)
            make_links_clickable_click()

def copy_to_clipboard():
    content = result_text.get("1.0", "end-1c").strip()
    if content:
        root.clipboard_clear()
        root.clipboard_append(content)
        messagebox.showinfo("Gekopieerd", "Geselecteerde snippets gekopieerd naar klembord!")

def append_to_journal():
    content = result_text.get("1.0", "end-1c").strip()
    if not content:
        messagebox.showwarning("Geen inhoud", "Er is geen tekst om aan het journaal toe te voegen.")
        return
        
    file_path = filedialog.asksaveasfilename(
        title="Selecteer of maak een Journaalbestand (.md)",
        defaultextension=".md",
        filetypes=[("Markdown files", "*.md"), ("Text files", "*.txt"), ("All files", "*.*")]
    )
    if not file_path:
        return
        
    try:
        with open(file_path, "a", encoding="utf-8") as f:
            f.write("\n\n" + content + "\n")
        messagebox.showinfo("Succes", f"Snippet succesvol toegevoegd aan:\n{file_path}")
    except Exception as e:
        messagebox.showerror("Opslag Fout", f"Kan bestand niet bijwerken:\n{str(e)}")

def save_button_click():
    try:
        file_path = filedialog.asksaveasfilename(
            defaultextension=".md",
            filetypes=[("Markdown files", "*.md"), ("Text files", "*.txt"), ("All files", "*.*")]
        )
        if not file_path:
            return
        with open(file_path, "w", encoding="utf-8") as file:
            file.write(result_text.get("1.0", "end-1c"))
        messagebox.showinfo("Succes", f"Opslaan voltooid: {file_path}")
    except Exception as e:
        messagebox.showerror("Fout", f"Opslaan mislukt: {e}")

def open_url(event):
    click_index = result_text.index(f"@{event.x},{event.y}")
    if "link" in result_text.tag_names(click_index):
        ranges = result_text.tag_ranges("link")
        for i in range(0, len(ranges), 2):
            start, end = ranges[i], ranges[i + 1]
            if result_text.compare(start, "<=", click_index) and result_text.compare(click_index, "<", end):
                url = result_text.get(start, end).strip()
                if url:
                    if not url.startswith(("http://", "https://")):
                        url = "https://" + url
                    webbrowser.open(url)
                break

def make_links_clickable_click():
    result_text.tag_config("link", foreground="blue", underline=True)
    result_text.tag_bind("link", "<Enter>", lambda e: result_text.config(cursor="hand2"))
    result_text.tag_bind("link", "<Leave>", lambda e: result_text.config(cursor=""))
    result_text.tag_bind("link", "<Button-1>", open_url)

    result_text.tag_remove("link", "1.0", tk.END)

    content = result_text.get("1.0", tk.END)
    url_pattern = re.compile(r'https?://[^\s\)]+|www\.[^\s\)]+')

    for match in url_pattern.finditer(content):
        start_idx = f"1.0 + {match.start()} chars"
        end_idx = f"1.0 + {match.end()} chars"
        result_text.tag_add("link", start_idx, end_idx)

# --- GUI SETUP ---
if __name__ == "__main__":
    root = tk.Tk()
    root.title("WPE11 - Webpage Snippet Extractor & Journal Builder")
    root.geometry("800x800")
    root.configure(bg="#f8f9fa")

    # URL Input Frame
    url_frame = ttk.Frame(root, padding=5)
    url_frame.pack(fill=tk.X, padx=10, pady=5)
    ttk.Label(url_frame, text="URL:", font=("Arial", 9, "bold")).pack(side=tk.LEFT, padx=(0, 5))
    url_entry = ttk.Entry(url_frame, width=80)
    url_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

    # Options Frame (Type, Filter, Width, Mode)
    opts_frame = ttk.Frame(root, padding=5)
    opts_frame.pack(fill=tk.X, padx=10, pady=5)

    ttk.Label(opts_frame, text="Type:").grid(row=0, column=0, sticky=tk.W, padx=5)
    extract_var = tk.StringVar(value="Paragraphs")
    extract_combobox = ttk.Combobox(opts_frame, textvariable=extract_var, values=["Paragraphs", "Headings (H1-H6)", "Links", "Images"], width=18)
    extract_combobox.grid(row=0, column=1, sticky=tk.W, padx=5)

    ttk.Label(opts_frame, text="Filter Trefwoord:").grid(row=0, column=2, sticky=tk.W, padx=5)
    filter_entry = ttk.Entry(opts_frame, width=20)
    filter_entry.grid(row=0, column=3, sticky=tk.W, padx=5)

    ttk.Label(opts_frame, text="Breedte:").grid(row=0, column=4, sticky=tk.W, padx=5)
    width_entry = ttk.Entry(opts_frame, width=8)
    width_entry.insert(0, "75")
    width_entry.grid(row=0, column=5, sticky=tk.W, padx=5)

    # Format Mode Selection
    ttk.Label(opts_frame, text="Formaat:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
    format_mode_var = tk.StringVar(value="Markdown Snippet (Journal Ready)")
    format_combobox = ttk.Combobox(opts_frame, textvariable=format_mode_var, values=["Markdown Snippet (Journal Ready)", "Plain Text (Wrapped)"], width=30)
    format_combobox.grid(row=1, column=1, columnspan=2, sticky=tk.W, padx=5, pady=5)

    # Action Buttons Frame
    button_frame = ttk.Frame(root, padding=5)
    button_frame.pack(fill=tk.X, padx=10, pady=5)

    ttk.Button(button_frame, text="Extract Snippets", command=extract_button_click).pack(side=tk.LEFT, padx=3)
    ttk.Button(button_frame, text="Re-Format On-the-Fly", command=format_button_click).pack(side=tk.LEFT, padx=3)
    ttk.Button(button_frame, text="Copy Snippet", command=copy_to_clipboard).pack(side=tk.LEFT, padx=3)
    ttk.Button(button_frame, text="Append to Journal", command=append_to_journal).pack(side=tk.LEFT, padx=3)
    ttk.Button(button_frame, text="Save File", command=save_button_click).pack(side=tk.LEFT, padx=3)

    # Result Text Box
    result_frame = ttk.Frame(root, padding=5)
    result_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

    result_text = tk.Text(result_frame, wrap=tk.WORD, font=("Consolas", 10))
    result_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    scrollbar = ttk.Scrollbar(result_frame, command=result_text.yview)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    result_text.config(yscrollcommand=scrollbar.set)

    root.mainloop()







