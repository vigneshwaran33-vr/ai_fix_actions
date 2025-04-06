import os
import shutil
import openpyxl
import subprocess
from openai import AzureOpenAI

# ========== 🔧 CONFIG ==========
SOURCE_REPO_URL = "https://github.com/vigneshwaran33-vr/Buggycode.git"
SOURCE_DIR = "Buggycode"
EXCEL_REPO_URL = "https://github.com/vigneshwaran33-vr/coverityxl.git"
EXCEL_DIR = "coverityxl"
EXCEL_PATH = os.path.join(EXCEL_DIR, "coverity_scan.xlsx")
AZURE_MODEL = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")

# ========== 🤖 AZURE OPENAI CLIENT ==========
client = AzureOpenAI(
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    api_version="2024-05-01-preview",
)

# ========== 🧹 CLEANUP ==========
def clean_repo_dirs():
    for path in [SOURCE_DIR, EXCEL_DIR]:
        if os.path.exists(path):
            shutil.rmtree(path)

# ========== 📥 LOAD EXCEL ==========
def load_issues_from_excel():
    wb = openpyxl.load_workbook(EXCEL_PATH)
    sheet = wb.active
    issues = []
    for row in sheet.iter_rows(min_row=2, values_only=True):
        function, issue, filename = row
        if function and issue and filename:
            issues.append({
                "function": function.strip(),
                "issue": issue.strip(),
                "filename": filename.strip()
            })
    return issues

# ========== ✅ SAFE CLONE ==========
def safe_clone(repo_url, dir_name):
    subprocess.run(["git", "clone", "--depth=1", repo_url, dir_name], check=True)

# ========== 🔍 EXTRACT FUNCTION ==========
def extract_function(file_path, function_name):
    with open(file_path, 'r') as f:
        lines = f.readlines()

    result = []
    inside = False
    brace_level = 0

    for line in lines:
        if not inside and function_name in line and "{" in line:
            inside = True

        if inside:
            result.append(line)
            brace_level += line.count("{") - line.count("}")
            if brace_level == 0:
                break

    return ''.join(result)

# ========== 🧠 GET AI FIX ==========
def get_ai_fix(buggy_func, issue):
    messages = [
        {
            "role": "system",
            "content": (
                "You're a C++ code fixer bot. Given a buggy C++ function and a bug description, "
                "return only the fixed function as raw code. DO NOT return anything else. "
                "NO markdown. NO comments. NO text. Preserve formatting and indent correctly."
            )
        },
        {
            "role": "user",
            "content": f"Issue: {issue}\nFunction:\n{buggy_func}"
        }
    ]

    response = client.chat.completions.create(
        model=AZURE_MODEL,
        messages=messages,
        max_tokens=2000,
        temperature=0
    )

    return response.choices[0].message.content.strip()

# ========== 🔧 PATCH FUNCTION ==========
def patch_function(file_path, old_func, new_func):
    with open(file_path, "r") as f:
        content = f.read()

    # Normalize whitespace
    old_func_stripped = "\n".join(line.strip() for line in old_func.strip().splitlines())
    new_func_lines = new_func.strip().splitlines()

    # Attempt replacing line-by-line for accuracy
    for line in content.splitlines():
        if line.strip() in old_func_stripped:
            break

    if old_func.strip() not in content:
        print("⚠️ Could not locate function in file (format mismatch).")
        return False

    updated = content.replace(old_func.strip(), new_func.strip())

    with open(file_path, "w") as f:
        f.write(updated)

    return True

# ========== 🔀 COMMIT & PUSH ==========
def commit_and_push(filename, function_name):
    branch = f"fix/{function_name}"
    token = os.getenv("GH_TOKEN")
    repo_url = f"https://x-access-token:{token}@github.com/vigneshwaran33-vr/Buggycode.git"

    subprocess.run(["git", "-C", SOURCE_DIR, "checkout", "-B", branch], check=True)
    subprocess.run(["git", "-C", SOURCE_DIR, "config", "user.email", "vigneshwaranr053@gmail.com"], check=True)
    subprocess.run(["git", "-C", SOURCE_DIR, "config", "user.name", "vigneshwaran33-vr"], check=True)
    subprocess.run(["git", "-C", SOURCE_DIR, "remote", "set-url", "origin", repo_url], check=True)

    subprocess.run(["git", "-C", SOURCE_DIR, "add", filename], check=True)
    subprocess.run(["git", "-C", SOURCE_DIR, "commit", "-m", f"Fix Coverity issue in {function_name}"], check=True)
    subprocess.run(["git", "-C", SOURCE_DIR, "push", "-u", "origin", branch], check=True)

    print(f"✅ Pushed branch: {branch}")

# ========== 🚀 MAIN ==========
def main():
    clean_repo_dirs()
    safe_clone(SOURCE_REPO_URL, SOURCE_DIR)
    safe_clone(EXCEL_REPO_URL, EXCEL_DIR)

    issues = load_issues_from_excel()

    for item in issues:
        file_path = os.path.join(SOURCE_DIR, item["filename"])
        buggy_func = extract_function(file_path, item["function"])

        if not buggy_func.strip():
            print(f"❌ Couldn't extract function: {item['function']}")
            continue

        print(f"\n🔧 Fixing {item['function']} in {item['filename']}")
        fixed_func = get_ai_fix(buggy_func, item["issue"])
        print("AI OUTPUT:\n", fixed_func)

        if patch_function(file_path, buggy_func, fixed_func):
            commit_and_push(item["filename"], item["function"])

    clean_repo_dirs()
    print("\n✅ All issues processed.")

if __name__ == "__main__":
    main()
