"""
Author: Cody
Create Date: 05/17/2024
This Code processes the structured data from a PDF document using the Alibaba Cloud DocMind API to extract and analyze the document layout, 
and then saves the data in various formats and details to an Excel file.
"""

from alibabacloud_docmind_api20220711.client import Client as docmind_api20220711Client
from alibabacloud_tea_openapi import models as open_api_models
from alibabacloud_docmind_api20220711 import models as docmind_api20220711_models
from alibabacloud_tea_util.client import Client as UtilClient
from alibabacloud_tea_util import models as util_models
from alibabacloud_credentials.client import Client as CredClient


config = open_api_models.Config(
    # 通过credentials获取配置中的AccessKey ID
    access_key_id="LTAI5tLps2XXMUUVk4RCYpZb",
    # 通过credentials获取配置中的AccessKey Secret
    access_key_secret="2NcF5U76YR4SyHUSINA2fb0f6bydoM"
)

config.endpoint = f'docmind-api.cn-hangzhou.aliyuncs.com'
client = docmind_api20220711Client(config)
request = docmind_api20220711_models.SubmitDocStructureJobAdvanceRequest(
    file_url_object = open("./组合 3.pdf", "rb"),
    file_name_extension='pdf'
)
runtime = util_models.RuntimeOptions()

# 复制代码运行请自行打印 API 的返回值
response = client.submit_doc_structure_job_advance(request, runtime)
# API返回值格式层级为 body -> data -> 具体属性。可根据业务需要打印相应的结果。如下示例为打印返回的业务id格式
# 获取属性值均以小写开头，
print(response.body.data.id)


request = docmind_api20220711_models.GetDocStructureResultRequest(id=response.body.data.id)

import time

while True:
    response = client.get_doc_structure_result(request)
    if response.body.completed == True:
        print("Response received")
        break
    time.sleep(0.1)  # Wait

# response = client.get_doc_structure_result(request)

final_result = response.body.data


# from final_result to json format
import json
final_result_json = json.dumps(final_result, indent=2, ensure_ascii=False)

final_result_dict = json.loads(final_result_json)

print(final_result_dict.keys())
"""print(final_result_dict.keys())
dict_keys(['logics', 'docInfo', 'styles', 'layouts', 'version'])"""
# transfer to 5 dataframes based on 5 keys
import pandas as pd
logics = pd.json_normalize(final_result_dict['logics'])
docInfo = pd.json_normalize(final_result_dict['docInfo'])
styles = pd.json_normalize(final_result_dict['styles'])
layouts = pd.json_normalize(final_result_dict['layouts'])



import pandas as pd

def process_table_data(table):
    # Initialize a list to collect 'pos' and 'text' information from each cell
    cell_content_list = []
    
    for cell in table['cells']:
        for layout in cell['layouts']:
            cell_text = layout["blocks"]
            # Convert the dictionary to a string representation
            cell_text_str = str(cell_text)
            cell_content_list.append(cell_text_str)
    
    # Every cell information is separated by a semicolon
    table_content_string = ';'.join(cell_content_list)
    
    return table_content_string


selected_rows_list = []

page_texts = {}

for item in final_result_dict['layouts']:
    page_number = item['pageNum'][0]
    if item['type'] == 'table':
        string_table_text = process_table_data(item)
        selected_data = {
            'type': 'table',
            'subType': item.get('subType', 'none'),
            'text': string_table_text,
        }
        selected_rows_list.append(selected_data)
        # page_texts['pageNum'].append(item['pageNum'])
        # page_texts['text'].append(selected_data['text'])

        page_texts.setdefault(page_number, []).append(string_table_text)

    elif item['type'] in ['foot_image', 'foot']:
        continue
    else:
        selected_data = { key: item[key] for key in ['type', 'subType', 'text'] if key in item }
        selected_rows_list.append(selected_data)
        # page_texts['pageNum'].append(item['pageNum'])
        # page_texts['text'].append(item['text'])
        page_texts.setdefault(page_number, []).append(item['text'])

    
# Combine all texts for the same pageNum into one string
for pageNum in page_texts:
    page_texts[pageNum] = ' '.join(page_texts[pageNum])

# Convert the combined page texts into a list of dictionaries for the DataFrame
page_texts_list = [{'pageNum': pageNum, 'text': text} for pageNum, text in page_texts.items()]

df_selected = pd.DataFrame(selected_rows_list)
df_selected['subType'] = df_selected.get('subType', 'none')  # Set default subtype to 'none'
df_selected['text'] = df_selected.get('text', '')

page_texts_df = pd.DataFrame(page_texts_list)

with pd.ExcelWriter('layouts3_new.xlsx', engine='xlsxwriter') as writer:
    df_selected.to_excel(writer, sheet_name='Selected Data', index=False)
    page_texts_df.to_excel(writer, sheet_name='Page Texts', index=False)

print("File saved successfully!")
