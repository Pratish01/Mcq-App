import pdfplumber
import json
import re

PDF_FILE = r"C:\Users\hp\Downloads\Python Snippet Question Bank.pdf"
OUTPUT_JSON = "data/python_easy.json"


def extract_text(pdf_path):
    full_text = []

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text(x_tolerance=2, y_tolerance=2)
            if text:
                full_text.append(text)

    return "\n".join(full_text)


def parse_mcqs(text):
    questions = []

    # Split by "What will be" OR "What is" (works for this PDF)
    blocks = re.split(
        r"(?=What\s+(?:will|is|does))",
        text,
        flags=re.IGNORECASE
    )

    q_no = 1

    for block in blocks:
        if "Answer:" not in block:
            continue

        # Extract answer letter
        ans_match = re.search(r"Answer:\s*([a-dA-D])\)", block)
        if not ans_match:
            continue

        correct = ans_match.group(1).upper()

        # Extract options
        options = re.findall(
            r"[a-dA-D]\)\s*(.+)",
            block
        )

        if len(options) < 4:
            continue

        # Question text = everything before option a)
        q_text = block.split("a)")[0].strip()

        questions.append({
            "number": q_no,
            "question_text": q_text,   # 👈 snippet preserved EXACTLY
            "option_a": options[0].strip(),
            "option_b": options[1].strip(),
            "option_c": options[2].strip(),
            "option_d": options[3].strip(),
            "correct_option": correct,
            "explanation": ""
        })

        q_no += 1

    return questions


if __name__ == "__main__":
    raw_text = extract_text(PDF_FILE)
    mcqs = parse_mcqs(raw_text)

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(mcqs, f, indent=4, ensure_ascii=False)

    print(f"✅ Extracted {len(mcqs)} MCQs with snippets preserved")
