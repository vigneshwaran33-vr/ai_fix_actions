import os
import openpyxl
import subprocess
from openai import AzureOpenAI

# ---- ENVIRONMENT VARIABLES ----
client = AzureOpenAI(
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    api_version="2024-05-01-preview",
)

# ---- SAFE GIT CLONE (skip if already cloned) ----
def safe_clone(repo_url, dir_name):
    if not os.path.exists(dir_name):
        subprocess.run(["git", "clone", repo_url, dir_name], check=True)
    else:
        print(f"📂 Directory '{dir_name}' already exists, skipping clone.")

safe_clone("https://github.com/vigneshwaran33-vr/Buggycode.git", "Buggycode")
safe_clone("https://github.com/vigneshwaran33-vr/coverityxl.git", "coverityxl")

# ---- READ EXCEL FOR ISSUES ----
excel_path = "coverityxl/coverity_scan.xlsx"
wb = openpyxl.load_workbook(excel_path)
sheet = wb.active

issues = []
for row in sheet.iter_rows(min_row=2, values_only=True):
    issue, function, filename = row
    if issue and function and filename:
        issues.append({
            "issue": issue.strip(),
            "function": function.strip(),
            "filename": filename.strip()
        })

# ---- FUNCTION EXTRACTOR ----
def extract_function_from_file(file_path, function_name):
    with open(file_path, 'r') as f:
        lines = f.readlines()

    func_lines = []
    inside_func = False
    brace_count = 0

    for line in lines:
        if not inside_func and (f"void {function_name}" in line or f"int {function_name}" in line or function_name + "(" in line):
            inside_func = True

        if inside_func:
            func_lines.append(line)
            brace_count += line.count('{') - line.count('}')
            if brace_count == 0:
                break

    return ''.join(func_lines)

# ---- MAIN LOGIC: JUST PROMPT + PRINT ----
for item in issues:
    cpp_path = os.path.join("Buggycode", item['filename'])
    buggy_func = extract_function_from_file(cpp_path, item['function'])

    print(f"\n🔍 Prompting OpenAI to fix function: **{item['function']}**")
    print(f"Issue: {item['issue']}")

    chat_prompt = [
        {"role": "system", "content": "You are an AI assistant that helps review and fix C++ code without comment."},
        {"role": "user", "content": f"Fix the following C++ function based on the issue: {item['issue']}\n```cpp\n{buggy_func}\n```"}
    ]

    response = client.chat.completions.create(
        model=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"),
        messages=chat_prompt,
        max_tokens=800,
        temperature=0.5
    )

    ai_reply = response.choices[0].message.content.strip()

    print("\n--- 🐛 Original Buggy Function ---")
    print(buggy_func)

    print("\n--- 🤖 AI Suggested Fix ---")
    print(ai_reply)

print("\n✅ Done! Only printed AI fixes — no files were written or PRs created.")
