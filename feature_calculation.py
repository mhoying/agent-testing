from flask import Flask, request, jsonify
import requests
import os
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()

app = Flask(__name__)

# Get GitHub Token from .env
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
if not GITHUB_TOKEN:
    print("WARNING: GITHUB_TOKEN not found in .env file. Agent cannot post comments to GitHub.")

# Configure Gemini with your API key
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    print("ERROR: GOOGLE_API_KEY not found in .env file. Gemini integration will not work.")
else:
    genai.configure(api_key=GOOGLE_API_KEY)
    llm_model = genai.GenerativeModel('gemini-1.5-flash')

def get_pr_diff(diff_url, github_token):
    """Fetches the raw diff content for a given Pull Request."""
    headers = {
        "Authorization": f"token {github_token}",
        "Accept": "application/vnd.github.v3.diff" # Requesting the diff format
    }
    try:
        response = requests.get(diff_url, headers=headers)
        response.raise_for_status() # Raise an exception for HTTP errors
        return response.text
    except requests.exceptions.RequestException as e:
        print(f"Error fetching PR diff from {diff_url}: {e}")
        return None

def analyze_pr_changes(pr_data, diff_content):
    """Analyzes PR using Gemini LLM and provides feedback, now with diff content."""
    if not GOOGLE_API_KEY:
        return ["🚫 LLM not configured. Check GOOGLE_API_KEY in .env."]

    title = pr_data['title']
    body = pr_data.get('body', 'No description provided.')

    # Prepare diff for the prompt
    diff_section = ""
    if diff_content:
        # IMPORTANT CHANGE HERE: Removed inner triple backticks to avoid markdown conflicts
        diff_section = f"""
Here are the actual code changes (diff):
{diff_content}
"""
    else:
        diff_section = "No code changes (diff) were provided for review."

    # --- Enhanced Prompt Engineering ---
    prompt = f"""
    You are an AI code reviewer for a professional software development team.
    Your task is to provide constructive, actionable, and polite feedback on a GitHub Pull Request.
    Review the title, description, and especially the provided code changes (diff).

    Focus on:
    - Potential bugs or logical errors.
    - Code quality, readability, and maintainability.
    - Adherence to common best practices.
    - Suggestions for improvement or alternative approaches.
    - Missing tests or documentation if applicable.

    Keep your review concise and use bullet points for clarity.
    If the changes are simple and look good, state "Looks good to me!".

    Here is the Pull Request information:
    Title: "{title}"
    Body: "{body}"
    {diff_section}

    Based on this information, what is your detailed code review?
    """

    try:
        # Send the prompt to Gemini
        response = llm_model.generate_content(prompt)
        # Extract the text from Gemini's response
        review_text = response.text.strip()
        return [review_text]
    except Exception as e:
        print(f"Error calling Gemini API: {e}")
        return [f"❌ Error during AI review: {e}. Please check LLM configuration or try a shorter PR."]

def post_comment(repo_owner, repo_name, pr_number, comment_text):
    """Post a comment on the PR using the GitHub API"""
    if not GITHUB_TOKEN:
        print("GITHUB_TOKEN is missing, cannot post comment.")
        return

    url = f"[https://api.github.com/repos/](https://api.github.com/repos/){repo_owner}/{repo_name}/issues/{pr_number}/comments"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    payload = {
        "body": comment_text
    }

    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status() # Raises HTTPError for bad responses (4xx or 5xx)
        print(f"Successfully posted comment to PR #{pr_number}")
    except requests.exceptions.HTTPError as e:
        print(f"Error posting comment: {e.response.status_code} - {e.response.text}")
    except requests.exceptions.RequestException as e:
        print(f"Network error posting comment: {e}")

@app.route('/webhook', methods=['POST'])
def github_webhook():
    print("Webhook received!")
    data = request.json

    if data.get('action') == 'opened' and 'pull_request' in data:
        pr = data['pull_request']
        print(f"New PR opened: {pr['title']}")
        print(f"By: {pr['user']['login']}")

        diff_url = pr['diff_url']
        print(f"Fetching diff from: {diff_url}")
        diff_content = get_pr_diff(diff_url, GITHUB_TOKEN)

        if diff_content is None:
            feedback = ["❌ Could not retrieve PR diff. Cannot provide full code review."]
        else:
            print(f"Diff fetched successfully. Length: {len(diff_content)} chars")
            feedback = analyze_pr_changes(pr, diff_content) # Pass diff to analysis

        if feedback:
            comment_body = "## AI Code Review (Powered by Gemini) 🤖\n\n" + "\n".join(feedback)
            post_comment(
                data['repository']['owner']['login'],
                data['repository']['name'],
                pr['number'],
                comment_body
            )
        return jsonify({'status': 'received'})

if __name__ == '__main__':
    app.run(debug=True, port=5001)
