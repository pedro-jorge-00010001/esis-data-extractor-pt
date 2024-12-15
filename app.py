import PyPDF2
import re
import json
import pandas as pd
import streamlit as st
import io  

def load_patterns(pattern_file):
    """Load regex patterns from a JSON file."""
    with open(pattern_file, 'r', encoding='utf-8') as file:
        return json.load(file)

def save_patterns(pattern_file, patterns):
    """Save regex patterns to a JSON file."""
    with open(pattern_file, 'w', encoding='utf-8') as file:
        json.dump(patterns, file, indent=4, ensure_ascii=False)

def extract_info_from_pdf(uploaded_file, patterns):
    file = io.BytesIO(uploaded_file.read())
    reader = PyPDF2.PdfReader(file)
    text = ''

    for page in reader.pages:
        text += page.extract_text()
    print(text)
    extracted_info = {}
    for key, pattern in patterns.items():
        match = re.search(pattern, text)
        extracted_info[key] = match.group(1).strip() if match else None

    return extracted_info

# Streamlit UI
st.title("PDF Information Extractor")

# Upload pattern file and load it
pattern_file = 'patterns.json'
patterns = load_patterns(pattern_file)

st.header("Edit Patterns")
for key, pattern in patterns.items():
    patterns[key] = st.text_input(f"Pattern for {key}", value=pattern)

# Save updated patterns
if st.button("Save Patterns"):
    save_patterns(pattern_file, patterns)
    st.success("Patterns saved successfully.")

# Upload PDF file
uploaded_file = st.file_uploader("Upload a PDF file", type=["pdf"])
if uploaded_file is not None:
    # Extract file name without extension
    file_name = uploaded_file.name.rsplit('.', 1)[0]

    # Extract information from the PDF
    extracted_info = extract_info_from_pdf(uploaded_file, patterns)

    # Display extracted information
    st.header("Extracted Information")
    st.write(extracted_info)

    # Convert to Excel and download
    df = pd.DataFrame([extracted_info])
    excel_file = f"Documents/{file_name}.csv"
    df.to_csv(excel_file, index=False)

    with open(excel_file, 'rb') as f:
        st.download_button(
            label="Download data as CSV",
            data=f,
            file_name=excel_file,
            mime="text/csv",
        )
