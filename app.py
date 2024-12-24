import PyPDF2
import re
import json
import pandas as pd
import streamlit as st
import io
import sqlite3

def create_database():
    conn = sqlite3.connect('extracted_data.db')
    cursor = conn.cursor()

    # Create table for extracted data with compound unique constraint
    cursor.execute('''CREATE TABLE IF NOT EXISTS extracted_data (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        file_name TEXT,
                        key TEXT,
                        value TEXT,
                        UNIQUE(file_name, key)
                    )''')

    # Create table for raw text
    cursor.execute('''CREATE TABLE IF NOT EXISTS raw_text (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        file_name TEXT UNIQUE,
                        text TEXT
                    )''')

    conn.commit()
    conn.close()

def save_to_database(data, raw_text):
    conn = sqlite3.connect('extracted_data.db')
    cursor = conn.cursor()

    # Save raw text
    for file_name, text in raw_text.items():
        cursor.execute('INSERT OR REPLACE INTO raw_text (file_name, text) VALUES (?, ?)', 
                      (file_name, text))

    # Save extracted data using REPLACE to handle duplicates
    for file_name, extracted_info in data.items():
        for key, value in extracted_info.items():
            cursor.execute('''INSERT OR REPLACE INTO extracted_data 
                            (file_name, key, value) VALUES (?, ?, ?)''', 
                         (file_name, key, value))

    conn.commit()
    conn.close()

def get_raw_text(file_name):
    conn = sqlite3.connect('extracted_data.db')
    cursor = conn.cursor()

    cursor.execute('SELECT text FROM raw_text WHERE file_name = ?', (file_name,))
    row = cursor.fetchone()
    conn.close()

    return row[0] if row else None

def get_all_data():
    conn = sqlite3.connect('extracted_data.db')
    cursor = conn.cursor()

    cursor.execute('SELECT file_name, key, value FROM extracted_data')
    rows = cursor.fetchall()
    conn.close()

    # Convert to DataFrame
    df = pd.DataFrame(rows, columns=['File Name', 'Key', 'Value'])

    # Remove duplicate entries
    df = df.drop_duplicates(subset=['File Name', 'Key'])

    # Pivot the DataFrame
    pivot_df = df.pivot(index='File Name', columns='Key', values='Value').reset_index()

    return pivot_df

def refresh_extracted_info():
    conn = sqlite3.connect('extracted_data.db')
    cursor = conn.cursor()

    cursor.execute('SELECT file_name, text FROM raw_text')
    rows = cursor.fetchall()

    updated_data = {}
    for file_name, text in rows:
        extracted_info = extract_info_from_text(text, patterns)
        updated_data[file_name] = extracted_info
        cursor.execute('DELETE FROM extracted_data WHERE file_name = ?', (file_name,))
        for key, value in extracted_info.items():
            cursor.execute('INSERT INTO extracted_data (file_name, key, value) VALUES (?, ?, ?)', 
                           (file_name, key, value))

    conn.commit()
    conn.close()

    return updated_data

# Pattern management
def load_patterns(pattern_file):
    with open(pattern_file, 'r', encoding='utf-8') as file:
        return json.load(file)

def save_patterns(pattern_file, patterns):
    with open(pattern_file, 'w', encoding='utf-8') as file:
        json.dump(patterns, file, indent=4, ensure_ascii=False)

# PDF extraction
def extract_text_from_pdf(uploaded_file):
    file = io.BytesIO(uploaded_file.read())
    reader = PyPDF2.PdfReader(file)
    text = ''

    for page in reader.pages:
        text += page.extract_text()

    return text

def extract_info_from_text(text, patterns):
    extracted_info = {}
    for key, pattern in patterns.items():
        matches = re.finditer(pattern, text)
        if matches:
            all_matches = []
            for match in matches:
                # Get all matched groups that aren't None
                valid_groups = [g for g in match.groups() if g is not None]
                if valid_groups:
                    all_matches.extend(valid_groups)
                else:
                    all_matches.append(match.group(0))
            
            # Get the shortest non-empty match after stripping
            valid_matches = [m.strip() for m in all_matches if m.strip()]
            if valid_matches:
                shortest_match = min(valid_matches, key=len)
                extracted_info[key] = shortest_match
            else:
                extracted_info[key] = None
        else:
            extracted_info[key] = None

    return extracted_info

# Streamlit application
st.set_page_config(layout="wide")
st.title("PDF Information Extractor")

# Sidebar for navigation
page = st.sidebar.selectbox("Choose a page", ["Import Files", "View Extracted Data", "Reevaluate Patterns"])

# Pattern file setup
pattern_file = 'patterns.json'
patterns = load_patterns(pattern_file)

if page == "Import Files":
    st.header("Import PDF Files")

    # Edit patterns
    st.subheader("Edit Patterns")
    for key, pattern in patterns.items():
        patterns[key] = st.text_input(f"Pattern for {key}", value=pattern)

    if st.button("Save Patterns"):
        save_patterns(pattern_file, patterns)
        st.success("Patterns saved successfully.")

    # File uploader
    uploaded_files = st.file_uploader("Upload PDF files", type=["pdf"], accept_multiple_files=True)

    if uploaded_files:
        all_extracted_info = {}
        raw_text_data = {}

        for uploaded_file in uploaded_files:
            file_name = uploaded_file.name.rsplit('.', 1)[0]

            if file_name in get_all_data():
                st.warning(f"File '{file_name}' is already in the database and won't be re-imported.")
                continue

            text = extract_text_from_pdf(uploaded_file)
            raw_text_data[file_name] = text
            extracted_info = extract_info_from_text(text, patterns)
            all_extracted_info[file_name] = extracted_info

        # Save to database
        save_to_database(all_extracted_info, raw_text_data)
        st.success("Data saved to the database successfully.")

        # Display extracted information
        st.subheader("Extracted Information")
        st.json(all_extracted_info)

elif page == "View Extracted Data":
    st.header("Extracted Data")

    # Fetch data from database
    data = get_all_data()

    if not data.empty:
        st.dataframe(data, use_container_width=True)

        # Download as CSV
        csv = data.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="Download Data as CSV",
            data=csv,
            file_name="extracted_data.csv",
            mime="text/csv"
        )
    else:
        st.info("No data available.")


elif page == "Reevaluate Patterns":
    st.header("Reevaluate Patterns")

    # Edit patterns
    st.subheader("Edit Patterns")
    for key, pattern in patterns.items():
        patterns[key] = st.text_input(f"Pattern for {key}", value=pattern)

    if st.button("Save Patterns"):
        save_patterns(pattern_file, patterns)
        st.success("Patterns saved successfully.")

    file_name = st.selectbox("Select a file to reevaluate", [row[0] for row in get_all_data().values])
    if file_name:
        raw_text = get_raw_text(file_name)

        if raw_text:
            st.text_area("Raw Text", raw_text, height=300, disabled=True)

            reevaluated_info = extract_info_from_text(raw_text, patterns)

            st.subheader("Reevaluated Information")
            st.json(reevaluated_info)

        else:
            st.warning("No raw text found for the selected file.")
    if st.button("Refresh Extracted Info"):
        updated_data = refresh_extracted_info()
        st.success("Extracted info refreshed successfully.")
        st.json(updated_data)

# Initialize database
create_database()
