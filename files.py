
import pdfplumber
import json
import re

PDF_FILE = r"C:\Users\hp\Downloads\Advance Analytics_Question.pdf"
OUTPUT_FILE = "data/Stats_med.json"


def normalize(t):
    return re.sub(r"\s+", " ", t).strip()


def extract_mcqs(pdf_path):
    full_text = ""

    # Extract text page by page
    with pdfplumber.open(pdf_path) as pdf:
        for p in pdf.pages:
            txt = p.extract_text()
            if txt:
                full_text += "\n" + txt

    # Normalize text
    full_text = full_text.replace("\r", "")
    lines = [line.strip() for line in full_text.split("\n") if line.strip()]

    mcqs = []
    current_question = ""
    options = {"A": "", "B": "", "C": "", "D": ""}
    in_question = False
    found_A = found_B = found_C = found_D = False
    correct = ""
    q_no = 1

    for line in lines:

        # Detect ANSWER
        ans = re.search(r"Answer[:\s]+([A-Da-d])", line)
        if ans:
            correct = ans.group(1).upper()

            # Save only if question + all 4 options are available
            if current_question and all(options.values()):
                mcqs.append({
                    "number": q_no,
                    "question_text": normalize(current_question),
                    "option_a": normalize(options["A"]),
                    "option_b": normalize(options["B"]),
                    "option_c": normalize(options["C"]),
                    "option_d": normalize(options["D"]),
                    "correct_option": correct,
                    "explanation": ""
                })
                q_no += 1

            # Reset for next MCQ
            current_question = ""
            options = {"A": "", "B": "", "C": "", "D": ""}
            found_A = found_B = found_C = found_D = False
            correct = ""
            continue

        # Detect OPTIONS
        if re.match(r"^[A][\).]", line, re.IGNORECASE):
            found_A = True
            options["A"] += " " + line[2:].strip()
            continue

        if re.match(r"^[B][\).]", line, re.IGNORECASE):
            found_B = True
            options["B"] += " " + line[2:].strip()
            continue

        if re.match(r"^[C][\).]", line, re.IGNORECASE):
            found_C = True
            options["C"] += " " + line[2:].strip()
            continue

        if re.match(r"^[D][\).]", line, re.IGNORECASE):
            found_D = True
            options["D"] += " " + line[2:].strip()
            continue

        # Lines **after D** but before Answer ALSO belong to options
        if found_A and not found_B:
            options["A"] += " " + line
        elif found_B and not found_C:
            options["B"] += " " + line
        elif found_C and not found_D:
            options["C"] += " " + line
        elif found_D and not correct:
            options["D"] += " " + line
        else:
            # Otherwise it's question text
            current_question += " " + line

    return mcqs


# Run extractor
mcqs = extract_mcqs(PDF_FILE)

with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(mcqs, f, indent=4)

print("Extracted:", len(mcqs), "MCQs →", OUTPUT_FILE)

