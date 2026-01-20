
import json
import os
import shutil

with open('config_files/test.json', 'r') as f:
    data = json.load(f)

task_to_site = {}
for item in data:
    task_id = item['task_id']
    sites = item['sites']
    if sites:
        task_to_site[task_id] = sites[0]

print(task_to_site.get(554))
