from flask import Flask, jsonify, render_template
import requests
from requests.auth import HTTPBasicAuth
import json
import csv
app = Flask(__name__)
domain = "parkar"
api_token = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJjb250ZXh0Ijp7ImJhc2VVcmwiOiJodHRwczovL3Bhcmthci5hdGxhc3NpYW4ubmV0IiwidXNlciI6eyJhY2NvdW50SWQiOiI3MTIwMjA6N2QxNGQ3YTMtODlkNC00Mzk3LTliODgtMDgxNjdkOTdjNGNkIn19LCJpc3MiOiJjb20ua2Fub2FoLnRlc3QtbWFuYWdlciIsInN1YiI6Ijc0ZTdlNTU4LWVkMjEtMzU5MC04YTFhLTc1ZWUxMTliNzA3OCIsImV4cCI6MTc0ODY3ODUzNiwiaWF0IjoxNzE3MTQyNTM2fQ.xxiq_15ljyqkCS70vtzRUnHJfHlAm65Cw5cqC2Lcl60"
project_key = "AITEST"
csv_filename = "issues.csv"


def fetch_existing_test_cases(api_token):
    url = "https://api.zephyrscale.smartbear.com/v2/testcases?maxResults=1000"
    headers = {"Accept": "application/json", "Content-Type": "application/json", 'Authorization': f'Bearer {api_token}'}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json()['values']
    else:
        print("Failed to fetch existing test cases")
        return []

def upload_test_steps(api_token, project_key, test_case_key, steps_data):
   url = f"https://api.zephyrscale.smartbear.com/v2/testcases/{test_case_key}/teststeps"
   headers = {"Accept": "application/json", "Content-Type": "application/json", 'Authorization': f'Bearer {api_token}'}
   payload = {
       "mode": "OVERWRITE",
       "items": steps_data
   }
   print(payload["items"])
   response = requests.post(url, headers=headers, json=payload)
   print(response)
   if response.status_code == 201:
       print(f"Successfully uploaded steps for test case '{test_case_key}'")

def fetch_and_export_issues(domain, api_token, project_key, csv_filename):
   url = f"https://{domain}.atlassian.net/rest/api/3/search"
   auth = HTTPBasicAuth("rparashar@parkar.digital", "ATATT3xFfGF0RQsxJj_EjNLJv53p-Xmosajn93nqecOy3HNfIaoZc1YWFtYALaCtzH_7v0N7b4CAQA5ArcPDRdf224jT3QUSt8_6GhdJ0f_cwrEHG3W5wDQSlyTa5bjQd709CGKaCZ_oL5jEz-OjkQI3vvajmhPyLO5Ci9qX4IAbQV0qWjnsyy0=0F1DECD2")
   headers = {"Accept": "application/json"}
   query = {'jql': f'project = {project_key}'}
   result = []
   response = requests.request(
       "GET",
       url,
       headers=headers,
       params=query,
       auth=auth
   )
   try:
       data = json.loads(response.text)
       selected_issues = data.get('issues', [])
       with open(csv_filename, mode='w', newline='', encoding='utf-8') as file:
           writer = csv.writer(file)
           writer.writerow(["Issue Key", "Summary", "Test Steps", "Expected Results"])
           for issue in selected_issues:
               issue_key = issue['key']
               summary = issue['fields'].get('summary', '')
               description = issue['fields'].get('description', {}).get('content', [])
               current_test_steps = []
               current_expected_results = []
               for item in description:
                   if item.get('type') == 'tableHeader':
                       continue
                   elif item['type'] == 'table':
                       for row in item['content']:
                           if row['type'] == 'tableRow':
                               if any(cell.get('marks', []) for cell in row['content']):
                                   continue
                               def extract_text(content):
                                   if isinstance(content, list):
                                       return ''.join([extract_text(sub_item) for sub_item in content])
                                   if isinstance(content, dict):
                                       if 'text' in content:
                                           return content['text']
                                       if 'content' in content:
                                           return extract_text(content['content'])
                                   return ''
                               test_step_description = extract_text(row['content'][1]['content'])
                               expected_result = extract_text(row['content'][2]['content'])
                               if test_step_description == 'Test Step ':
                                   continue
                               if test_step_description and expected_result:
                                   current_test_steps.append(test_step_description)
                                   current_expected_results.append(expected_result)
               for i in range(len(current_test_steps)):
                   if i > 0:
                       issue_key = ""
                       summary = ""
                   writer.writerow([issue_key, summary, current_test_steps[i], current_expected_results[i]])
                   result.append({
                   "Issue Key": issue_key,
                   "Summary": summary,
                   "Test Steps": current_test_steps[i],
                   "Expected Results": current_expected_results[i]
               })
       print(f"Issues exported to {csv_filename}")
       print(json.dumps(result))
       return json.dumps(result)
   except KeyError as e:
       print(f"Unexpected key in response: {e}")
   except Exception as e:
       print(f"An error occurred: {e}")


def import_issues_into_zephyr(api_token, project_key):
    test_case_key= str()
    url = "https://api.zephyrscale.smartbear.com/v2/testcases"
    headers = {"Accept": "application/json", "Content-Type": "application/json", 'Authorization': f'Bearer {api_token}'}
    issues_json = fetch_and_export_issues(domain, api_token, project_key, csv_filename)
    issues = json.loads(issues_json)
    existing_test_cases = fetch_existing_test_cases(api_token)
    steps_dict = {}

    for i in range(len(issues)):
        print("For i : ", i)
        issue = issues[i]
        if issue['Issue Key']:
            # Check if the test case already exists
            existing_test_case = next((tc for tc in existing_test_cases if tc['name'] == issue['Summary']), None)
            if existing_test_case:
                print(f"Test case '{issue['Summary']}' already exists. Skipping.")
                # Skip uploading test case and its steps
                while i + 1 < len(issues) and issues[i + 1].get('Issue Key') is None:
                    i += 1
                    print("while i : ", i)
                continue

            # Upload test case and its steps
            payload = {
                "ID": issue['Issue Key'],
                "name": issue['Summary'],
                "Test Script (Steps) - Step": issue['Test Steps'],
                "Test Script (Steps) - Expected Result": issue['Expected Results'],
                "type": "TEST_CASE",
                "projectKey": project_key
            }
            print(payload)
            response = requests.post(url, headers=headers, json=payload)
            print(response)
            test_case_key = response.json().get('key')
            print(type(test_case_key))
            print("Test case generated successfully for the Test Case Key : ", test_case_key)
        if test_case_key not in steps_dict:
           steps_dict[test_case_key] = []
        steps_data = {
                    "inline": {
                        "description": issues[i]['Test Steps'],
                        "testData": "",
                        "expectedResult": issues[i]['Expected Results'],
                        "customFields": {}
                    }
                }
        steps_dict[test_case_key].append(steps_data)
 
    # Move the upload_test_steps function call outside the loop
    for test_case_key, steps_data in steps_dict.items():
        upload_test_steps(api_token, project_key, test_case_key, steps_data)

@app.route('/upload_testcases', methods=['POST'])
def upload_testcases():
    import_issues_into_zephyr(api_token, project_key)
    return jsonify({"message": "Test cases and test steps uploaded successfully"}), 200



@app.route('/', methods=['GET'])
def import_issues():
   print(api_token)
   print(project_key)
#    import_issues_into_zephyr(api_token, project_key)
   return render_template('index.html')
#    return jsonify({"message": "Issues imported and test steps uploaded successfully"}), 200
if __name__ == '__main__':
   app.run(debug=True)

