import os
import openpyxl
import subprocess
import difflib
from openai import AzureOpenAI

# ==== 🔧 CONFIG ====
SOURCE_REPO_URL = "https://github.com/vigneshwaran33-vr/Buggycode.git"
SOURCE_DIR = "Buggycode"
EXCEL_REPO_URL = "https://github.com/vigneshwaran33-vr/coverityxl.git"
EXCEL_DIR = "coverityxl"
EXCEL_PATH = os.path.join(EXCEL_DIR, "coverity_scan.xlsx")

# ==== 🤖 AZURE OPENAI CLIENT ====
client = AzureOpenAI(
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    api_version="2024-05-01-preview",
)

# ==== ✅ SAFE GIT CLONE ====
def safe_clone(repo_url, dir_name):
    if not os.path.exists(dir_name):
        subprocess.run(["git", "clone", repo_url, dir_name], check=True)
    else:
        print(f"📂 Directory '{dir_name}' already exists, skipping clone.")

# ==== 📥 LOAD COVERITY EXCEL ====
def load_issues_from_excel():
    wb = openpyxl.load_workbook(EXCEL_PATH)
    sheet = wb.active
    issues = []
    for row in sheet.iter_rows(min_row=2, values_only=True):
        function, issue, filename = row
        if issue and function and filename:
            issues.append({
                "issue": issue.strip(),
                "function": function.strip(),
                "filename": filename.strip()
            })
    return issues

# ==== 🔍 FUNCTION EXTRACTOR ====
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

# ==== 🧠 ASK AZURE OPENAI ====
def get_ai_fix(buggy_func, issue_desc):
    chat_prompt = [
        {"role": "system", "content": "You are an AI assistant that helps review and fix C++ code without comment."},
        {"role": "user", "content": f"Fix the following C++ function based on the issue: {issue_desc}\n```cpp\n{buggy_func}\n```"}
    ]

    response = client.chat.completions.create(
        model=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"),
        messages=chat_prompt,
        max_tokens=800,
        temperature=0.5
    )

    return response.choices[0].message.content.strip()

# ==== 🧩 PATCH FILE WITH DIFFLIB ====
def patch_function_in_file(file_path, original_func, fixed_func):
    with open(file_path, 'r') as f:
        lines = f.readlines()

    original_lines = original_func.splitlines(keepends=True)
    fixed_lines = fixed_func.splitlines(keepends=True)

    orig_str = ''.join(original_lines)
    start_idx = None
    for i in range(len(lines)):
        if ''.join(lines[i:i + len(original_lines)]) == orig_str:
            start_idx = i
            break

    if start_idx is None:
        print("❌ Failed to locate function in file.")
        return False

    lines[start_idx:start_idx + len(original_lines)] = fixed_lines

    with open(file_path, 'w') as f:
        f.writelines(lines)

    print("✅ Function patched in file.")
    return True

# ==== 🔀 GIT BRANCH, COMMIT & PUSH ====
def commit_and_push_change(filename, function_name):
    feature_branch = f"fix/{function_name}"
    github_token = os.getenv("GH_TOKEN_FG")
    repo_url = f"https://x-access-token:{github_token}@github.com/vigneshwaran33-vr/Buggycode.git"

    subprocess.run(["git", "-C", SOURCE_DIR, "remote", "set-url", "origin", repo_url], check=True)
    subprocess.run(["git", "-C", SOURCE_DIR, "remote", "-v"])

    subprocess.run(["git", "-C", SOURCE_DIR, "config", "user.email", "vigneshwaranr053@gmail.com"], check=True)
    subprocess.run(["git", "-C", SOURCE_DIR, "config", "user.name", "vigneshwaran33-vr"], check=True)

    subprocess.run(["git", "-C", SOURCE_DIR, "checkout", "-b", feature_branch], check=True)
    subprocess.run(["git", "-C", SOURCE_DIR, "add", filename], check=True)
    subprocess.run(["git", "-C", SOURCE_DIR, "commit", "-m", f"Fix Coverity issue in {function_name}"], check=True)

    subprocess.run([
    "git", "-C", SOURCE_DIR,
    "remote", "set-url", "origin",
    f"https://x-access-token:{os.environ['GH_TOKEN_FG']}@github.com/vigneshwaran33-vr/Buggycode.git"
    ], check=True)
    
    subprocess.run(["git", "-C", SOURCE_DIR, "push", "-u", "origin", feature_branch], check=True)

    print(f"🚀 Pushed changes to branch '{feature_branch}'")

# ==== 🚀 MAIN ====
def main():
    safe_clone(SOURCE_REPO_URL, SOURCE_DIR)
    safe_clone(EXCEL_REPO_URL, EXCEL_DIR)

    issues = load_issues_from_excel()

    for item in issues:
        cpp_path = os.path.join(SOURCE_DIR, item['filename'])
        buggy_func = extract_function_from_file(cpp_path, item['function'])

        print(f"\n🔍 Prompting OpenAI to fix function: **{item['function']}**")
        print(f"Issue: {item['issue']}")

        ai_reply = get_ai_fix(buggy_func, item['issue'])

        print("\n--- 🐛 Original Buggy Function ---")
        print(buggy_func)

        print("\n--- 🤖 AI Suggested Fix ---")
        print(ai_reply)

        # Patch and commit
        updated = patch_function_in_file(cpp_path, buggy_func, ai_reply)
        if updated:
            commit_and_push_change(item['filename'], item['function'])

    print("\n✅ Done! All functions processed.")

if __name__ == "__main__":
    main()
