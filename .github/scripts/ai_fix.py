import os
import openpyxl
import subprocess
import difflib
from github import Github
from openai import AzureOpenAI

# Initialize OpenAI client
client = AzureOpenAI(
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    api_version="2024-05-01-preview",
)

# Clone the repos
subprocess.run(["git", "clone", "https://github.com/vigneshwaran33-vr/Buggycode.git"])
subprocess.run(["git", "clone", "https://github.com/vigneshwaran33-vr/coverityxl.git"])

# Read Excel and extract issues
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

# Extract full function from source code file
def extract_function_from_file(file_path, function_name):
    with open(file_path, 'r') as f:
        lines = f.readlines()

    func_lines = []
    inside_func = False
    brace_count = 0

    for line in lines:
        if not inside_func and f"void {function_name}" in line or f"int {function_name}" in line or function_name + "(" in line:
            inside_func = True
        
        if inside_func:
            func_lines.append(line)
            brace_count += line.count('{') - line.count('}')
            if brace_count == 0:
                break

    return ''.join(func_lines)

# Apply diff-style patch to original content
def apply_patch(original_content, fixed_content):
    original_lines = original_content.splitlines()
    fixed_lines = fixed_content.splitlines()
    patched_lines = []

    diff = difflib.unified_diff(original_lines, fixed_lines, lineterm="")
    for line in diff:
        if line.startswith("@@"):
            continue
        elif line.startswith("---") or line.startswith("+++"):
            continue
        elif line.startswith("-"):
            continue
        elif line.startswith("+"):
            patched_lines.append(line[1:])
        else:
            patched_lines.append(line)

    return '\n'.join(patched_lines)

# Main processing
for item in issues:
    cpp_path = os.path.join("Buggycode", item['filename'])
    buggy_func = extract_function_from_file(cpp_path, item['function'])

    print(f"Sending buggy function {item['function']} to OpenAI...")
    chat_prompt = [
        {"role": "system", "content": "You are an AI assistant that helps review and fix C++ code."},
        {"role": "user", "content": f"Fix the following C++ function based on the issue: {item['issue']}\n```cpp\n{buggy_func}\n```"}
    ]

    response = client.chat.completions.create(
        model=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"),
        messages=chat_prompt,
        max_tokens=800,
        temperature=0.5
    )

    fixed_code = response.choices[0].message.content.strip()
    code_start = fixed_code.find("```cpp")
    code_end = fixed_code.rfind("```")
    if code_start != -1 and code_end != -1:
        fixed_func = fixed_code[code_start + 6:code_end].strip()
    else:
        fixed_func = fixed_code

    # Replace only the function in source file
    with open(cpp_path, 'r') as f:
        full_code = f.read()

    updated_code = full_code.replace(buggy_func, fixed_func)

    with open(cpp_path, 'w') as f:
        f.write(updated_code)

# Create a PR with GitHub API
repo_url = "https://github.com/vigneshwaran33-vr/Buggycode"
repo_name = "vigneshwaran33-vr/Buggycode"
github = Github(os.getenv("GH_TOKEN"))
repo = github.get_repo(repo_name)

branch_name = "ai-fix-patch"
base = repo.get_branch("main")
repo.create_git_ref(ref=f"refs/heads/{branch_name}", sha=base.commit.sha)

subprocess.run(["git", "checkout", "-b", branch_name], cwd="Buggycode")
subprocess.run(["git", "add", "source_code.cpp"], cwd="Buggycode")
subprocess.run(["git", "commit", "-m", "AI fix for Coverity issues"], cwd="Buggycode")
subprocess.run(["git", "push", "origin", branch_name], cwd="Buggycode")

repo.create_pull(
    title="AI-generated fix for Coverity issues",
    body="This PR contains automated fixes for Coverity issues using Azure OpenAI.",
    head=branch_name,
    base="main"
)

print("✅ Pull request created successfully.")

