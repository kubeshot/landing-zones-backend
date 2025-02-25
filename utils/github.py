import requests

##not working properly, should get the proper error res, success res and should also send the same properly.
def check_repo_file(github_access_token, git_org_name, bootstrap_repo, file_path):
    url = f"https://api.github.com/repos/{git_org_name}/{bootstrap_repo}/contents/{file_path}"
    headers = {
        "Authorization": f"token {github_access_token}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    response = requests.get(url, headers=headers)

    try:
        response_data = response.json() 
    except requests.exceptions.JSONDecodeError:
        response_data = {"error": "Invalid JSON response from GitHub"}

    print(f"Status Code: {response.status_code}")
    print("Response JSON:", response_data)

    return response.status_code == 200, response_data 
