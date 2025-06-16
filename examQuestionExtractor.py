from pdf2image import convert_from_path
import pytesseract
import json
import re
import os

def extract_questions_from_text(text):
    # Pattern to match questions followed by options A) B) C) D)
    pattern = re.compile(
        r'(?P<qnum>\d+)\.\s+(?P<question>.+?)(?=\n[A-D]\))(?P<options>(?:\n[A-D]\).+?){2,4})(?=\n\d+\.|\Z)', re.DOTALL)

    questions = []
    for idx, match in enumerate(pattern.finditer(text)):
        question_text = match.group('question').strip().replace('\n', ' ')
        options_block = match.group('options').strip()

        options = []
        answer = ""
        for i, line in enumerate(options_block.split('\n')):
            match_option = re.match(r'([A-D])\)\s+(.*)', line.strip())
            if match_option:
                option_label = match_option.group(1)
                option_text = match_option.group(2).strip()
                if option_text.endswith('*'):
                    option_text = option_text.rstrip('*').strip()
                    answer = option_label
                options.append(option_text)

        questions.append({
            "id": idx + 1,
            "question": question_text,
            "options": options,
            "answer": answer,
            "explanation": ""
        })

    return questions

def extract_from_pdf(pdf_path, output_json):
    try:
        images = convert_from_path(pdf_path)
    except Exception as e:
        print(f"❌ Failed to convert PDF to images: {e}")
        return

    full_text = ""
    for i, img in enumerate(images):
        text = pytesseract.image_to_string(img)
        full_text += text + "\n"

    # Write full OCR text to a .txt file for debugging
    with open(output_json.replace(".json", ".txt"), "w", encoding="utf-8") as debug_txt:
        debug_txt.write(full_text)

    questions = extract_questions_from_text(full_text)

    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(questions, f, indent=4, ensure_ascii=False)

    print(f"✅ Extracted {len(questions)} questions to {output_json} using OCR")

def format_text_file(input_txt, formatted_txt):
    import re
    with open(input_txt, "r", encoding="utf-8") as f:
        lines = f.readlines()

    cleaned_lines = []
    question_number_pattern = re.compile(r'^\d{1,3}[\.\)]\s')
    option_pattern = re.compile(r'^[A-D][\.\)]\s')

    for line in lines:
        stripped = line.strip()
        if question_number_pattern.match(stripped) or option_pattern.match(stripped):
            cleaned_lines.append(stripped)
        else:
            # Join broken lines of question or option
            if cleaned_lines:
                cleaned_lines[-1] += ' ' + stripped

    with open(formatted_txt, "w", encoding="utf-8") as f:
        for line in cleaned_lines:
            f.write(line + "\n")

    print(f"✅ Formatted and cleaned OCR text written to '{formatted_txt}'")

def parse_formatted_text_to_json(formatted_txt, output_json):
    with open(formatted_txt, "r", encoding="utf-8") as f:
        lines = f.readlines()

    questions = []
    q_id = 1
    current_question = ""
    options = []
    answer = ""

    for line in lines:
        line = line.strip()
        if re.match(r'^\d{1,3}[\.\)]\s', line):
            if current_question and options:
                questions.append({
                    "id": q_id,
                    "question": current_question,
                    "options": options,
                    "answer": answer,
                    "explanation": ""
                })
                q_id += 1
            current_question = re.sub(r'^\d{1,3}[\.\)]\s+', '', line)
            options = []
            answer = ""
        elif re.match(r'^[A-D][\.\)]\s', line):
            opt_match = re.match(r'^([A-D])[\.\)]\s+(.*)', line)
            if opt_match:
                opt_label, opt_text = opt_match.groups()
                if opt_text.endswith('*'):
                    opt_text = opt_text.rstrip('*').strip()
                    answer = opt_label
                options.append(opt_text)

    if current_question and options:
        questions.append({
            "id": q_id,
            "question": current_question,
            "options": options,
            "answer": answer,
            "explanation": ""
        })

    # Fallback: Try inline parsing if no questions were found
    if not questions:
        print("🔍 Attempting inline parsing...")
        with open(formatted_txt, "r", encoding="utf-8") as f:
            text = f.read()

        question_blocks = re.split(r'(?<=\))\s*(?=\d{1,3}[\.\)])', text.strip())
        for block in question_blocks:
            match = re.match(r'^\d{1,3}[\.\)]\s*(.+)', block, re.DOTALL)
            if not match:
                continue

            body = match.group(1).strip()
            option_matches = re.findall(r'\(([a-d])\)\s*([^\(]+?)(?=\s*\([a-d]\)|$)', body)

            if not option_matches:
                continue

            question_text = re.split(r'\(a\)', body)[0].strip()
            options = [opt.strip() for _, opt in option_matches]
            answer = ""

            questions.append({
                "id": q_id,
                "question": question_text,
                "options": options,
                "answer": answer,
                "explanation": ""
            })
            q_id += 1

    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(questions, f, indent=4, ensure_ascii=False)

    print(f"✅ Parsed {len(questions)} questions from formatted text into '{output_json}'")

if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.abspath(__file__))
    input_dir = os.path.join(base_dir, "pdfs")
    output_dir = os.path.join(base_dir, "output")

    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(input_dir, exist_ok=True)

    pdf_files = [f for f in os.listdir(input_dir) if f.lower().endswith(".pdf")]

    if not pdf_files:
        print("❌ No PDF files found in 'pdfs/' folder.")
    else:
        print(f"📂 Found {len(pdf_files)} PDF file(s) in 'pdfs/': {pdf_files}")
        for pdf_file in pdf_files:
            input_pdf = os.path.join(input_dir, pdf_file)
            output_file = os.path.join(output_dir, pdf_file.replace(".pdf", ".json"))
            extract_from_pdf(input_pdf, output_file)
            raw_txt = output_file.replace(".json", ".txt")
            formatted_txt = output_file.replace(".json", "_formatted.txt")
            format_text_file(raw_txt, formatted_txt)
            parsed_json = output_file.replace(".json", "_parsed.json")
            parse_formatted_text_to_json(formatted_txt, parsed_json)