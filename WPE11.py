import requests
from bs4 import BeautifulSoup
import tkinter as tk
from tkinter import ttk
from tkinter import filedialog
import textwrap
import re
import webbrowser
from urllib.parse import urljoin

# Store extracted data in memory so it can be formatted on the fly without re-fetching
last_extracted_data = []


def fetch_and_extract(url, extract_type):
    try:
        response = requests.get(url)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        if extract_type == "Links":
            extracted_data = [urljoin(url, link.get('href')) for link in soup.find_all('a', href=True)]
        elif extract_type == "Headings (H1-H6)":
            headings = ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']
            extracted_data = [f"{tag.name}: {tag.text.strip()}" for tag in soup.find_all(headings)]
        
        elif extract_type == "Paragraphs":
            paragraphs = [p.get_text(strip=True) for p in soup.find_all('p')]
            extracted_data = paragraphs
        
        elif extract_type == "Images":
            images = [urljoin(url, img['src']) for img in soup.find_all('img', src=True)]
            extracted_data = images
        else:
            extracted_data = []
        
        return extracted_data
    
    except requests.exceptions.RequestException as e:
        print(f"An error occurred: {e}")
        return None


def get_char_width():
    """Reads character width from entry field, defaulting to 50 if invalid."""
    try:
        width = int(width_entry.get())
        return width if width > 0 else 50
    except ValueError:
        return 50


def format_extracted_data(data, char_width=50, vharwidth=None):
    """
    Formats extracted data on the fly according to specified character width.
    Accepts `char_width` or `vharwidth` as parameter.
    """
    if vharwidth is not None:
        char_width = vharwidth

    if not data:
        return ""

    formatted_items = []
    for item in data:
        lines = str(item).splitlines()
        wrapped_item = "\n".join(
            textwrap.fill(line, width=char_width, break_long_words=True)
            for line in lines if line
        )
        formatted_items.append(wrapped_item)
    return "\n".join(formatted_items)


def extract_button_click():
    global last_extracted_data
    url = url_entry.get()
    extract_type = extract_var.get()
    char_width = get_char_width()
    
    if url and extract_type:
        extracted_data = fetch_and_extract(url, extract_type)
        
        result_text.delete(1.0, tk.END)  # Clear previous results
        if extracted_data is not None and len(extracted_data) > 0:
            last_extracted_data = extracted_data
            formatted_text = format_extracted_data(last_extracted_data, char_width=char_width)
            result_text.insert(tk.END, formatted_text)
        elif extracted_data is not None and len(extracted_data) == 0:
            last_extracted_data = []
            result_text.insert(tk.END, "No data found for the selected extraction type.")
        else:
            last_extracted_data = []
            result_text.insert(tk.END, "An error occurred while fetching data.")
    else:
        result_text.delete(1.0, tk.END)
        result_text.insert(tk.END, "Please enter a URL and select an extraction type.")


def format_button_click():
    """Formats already extracted data on the fly with the specified character width."""
    global last_extracted_data
    char_width = get_char_width()
    
    if last_extracted_data:
        formatted_text = format_extracted_data(last_extracted_data, char_width=char_width)
        result_text.delete(1.0, tk.END)
        result_text.insert(tk.END, formatted_text)
    else:
        # Fallback: if user manually edited or typed in result_text, re-wrap current text lines
        current_content = result_text.get("1.0", "end-1c").strip()
        if current_content:
            lines = current_content.splitlines()
            formatted_text = format_extracted_data(lines, char_width=char_width)
            result_text.delete(1.0, tk.END)
            result_text.insert(tk.END, formatted_text)
        else:
            result_text.delete(1.0, tk.END)
            result_text.insert(tk.END, "No extracted data available to format.")


def save_button_click():
    try:
        file_path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        if not file_path:
            return
        with open(file_path, "w", encoding="utf-8") as file:
            file.write(result_text.get("1.0", "end-1c"))
        print(f"Text saved to {file_path}")
    except Exception as e:
        print(f"An error occurred: {e}")


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
    """Finds links in result_text and converts them into clickable blue hyperlinks."""
    result_text.tag_config("link", foreground="blue", underline=True)
    result_text.tag_bind("link", "<Enter>", lambda e: result_text.config(cursor="hand2"))
    result_text.tag_bind("link", "<Leave>", lambda e: result_text.config(cursor=""))
    result_text.tag_bind("link", "<Button-1>", open_url)

    result_text.tag_remove("link", "1.0", tk.END)

    content = result_text.get("1.0", tk.END)
    url_pattern = re.compile(r'https?://[^\s]+|www\.[^\s]+')

    for match in url_pattern.finditer(content):
        start_idx = f"1.0 + {match.start()} chars"
        end_idx = f"1.0 + {match.end()} chars"
        result_text.tag_add("link", start_idx, end_idx)


# Create the main window
root = tk.Tk()
root.title("Webpage Extractor")

# Create and place widgets
url_frame = ttk.Frame(root)
url_frame.grid(column=0, row=0, columnspan=2, padx=5, pady=5, sticky=tk.W)
url_label = ttk.Label(url_frame, text="URL:")
url_label.pack(side=tk.LEFT, padx=(0, 5))
url_entry = ttk.Entry(url_frame, width=150)
url_entry.pack(side=tk.LEFT)

extract_var = tk.StringVar()
extract_var.set("Links")  # default value

extract_frame = ttk.Frame(root)
extract_frame.grid(column=0, row=1, columnspan=2, padx=5, pady=5, sticky=tk.W)
extract_label = ttk.Label(extract_frame, text="Type:")
extract_label.pack(side=tk.LEFT, padx=(0, 5))
extract_combobox = ttk.Combobox(extract_frame, textvariable=extract_var, values=["Links", "Headings (H1-H6)", "Paragraphs", "Images"])
extract_combobox.pack(side=tk.LEFT)

width_frame = ttk.Frame(root)
width_frame.grid(column=0, row=2, columnspan=2, padx=5, pady=5, sticky=tk.W)
width_label = ttk.Label(width_frame, text="Width:")
width_label.pack(side=tk.LEFT, padx=(0, 5))
width_entry = ttk.Entry(width_frame, width=20)
width_entry.insert(0, "50")
width_entry.pack(side=tk.LEFT)

# Frame for action buttons
button_frame = ttk.Frame(root)
button_frame.grid(column=0, row=3, columnspan=2, padx=5, pady=10, sticky=tk.W)

extract_button = ttk.Button(button_frame, text="Extract", command=extract_button_click)
extract_button.pack(side=tk.LEFT, padx=(0, 5))

format_button = ttk.Button(button_frame, text="Format On-the-Fly", command=format_button_click)
format_button.pack(side=tk.LEFT, padx=5)

clickable_button = ttk.Button(button_frame, text="Make Links Clickable", command=make_links_clickable_click)
clickable_button.pack(side=tk.LEFT, padx=5)

save_button = ttk.Button(button_frame, text="Save Text", command=save_button_click)
save_button.pack(side=tk.LEFT, padx=5)

result_text = tk.Text(root, height=50, width=200)
result_text.grid(column=0, row=5, columnspan=2, padx=5, pady=5)

# Run the application
root.mainloop()






