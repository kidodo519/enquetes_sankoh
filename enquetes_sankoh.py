from datetime import date, datetime, timedelta
import os
import time
import yaml
import re
import shutil
import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
import pyautogui
import traceback
import yaml
import csv
import glob
from tqdm import tqdm
from argparse import ArgumentParser
import jaconv
import psycopg2
from psycopg2 import extras



def post_webhook(config, content):
    requests.post(config['webhook']['url'], json={
        'text': content
    })

def make_date_text(text):
    date_list = str(text).split("-")
    year = int(date_list[0])
    month = int(date_list[1])
    day = int(date_list[2])
    return (str(year) + "/" + str(month).zfill(2) + "/" + str(day).zfill(2))

def make_date_text2(text):
    date_list = str(text).split("-")
    year = int(date_list[0])
    month = int(date_list[1])
    day = int(date_list[2])
    return (str(year) + str(month).zfill(2) + str(day).zfill(2))

def date_text_to_date(text):
    year = int(text[0:4], 10)
    month = int(text[5:7], 10)
    day = int(text[8:10], 10)

    return date(year, month, day)

def date_text_to_datetime(text):
    return datetime.strptime(text + ' +0900', '%Y-%m-%d %H:%M:%S %z')


def make_record_from_row(row, mapping):
    ret = {}
    for db_key, csv_key in mapping['string'].items():
        v = row[csv_key].strip()
        ret[db_key] = jaconv.h2z(v) if v != '' else None

    for db_key, csv_key in mapping['text'].items():
        v = row[csv_key].strip()
        v = replace_invalid_shiftjis_chars(v, replace_with = '?')
        ret[db_key] = jaconv.h2z(v) if v != '' else None
        
    for db_key, csv_key in mapping['integer'].items():
        v = row[csv_key].strip()
        ret[db_key] = int(v, 10) if v != '' else None

    for db_key, csv_key in mapping['date'].items():
        v = row[csv_key].strip()
        ret[db_key] = date_text_to_date(v) if v != '' and v != '0' else None

    for db_key, csv_key in mapping['datetime'].items():
        v = row[csv_key].strip()
        ret[db_key] = date_text_to_datetime(v) if v != '' and v != '0' else None
    return ret


def add_generate_items(row):
    facility_code = {"夢乃井": 1, "夕やけこやけ": 2, "祥吉": 3, "加里屋旅館Q": 4}
    try:
        room_code_raw = row['room_code']
        room_code_digits = re.sub(r'\D', '', str(room_code_raw)) if room_code_raw is not None else ''
        room_code_value = int(room_code_digits) if room_code_digits else 0
        return {
            **row,
            'enquete_key': '-'.join([
                str(room_code_value),
                row['start_date'].strftime('%Y%m%d'),
                str(facility_code[row['facility_name']])
            ])}

    except Exception:
        return {
            **row,
            'enquete_key': ''
        }

def add_import_date():
    return {'import_date': datetime.now()
    }   

def replace_invalid_shiftjis_chars(v, replace_with='?'):
    """
    Replace characters in the input string `v` that cannot be encoded in Shift_JIS
    with the specified `replace_with` character.

    Args:
        v (str): Input string to process.
        replace_with (str): Character to use as a replacement for invalid characters.

    Returns:
        str: Processed string with invalid characters replaced.
    """
    return ''.join(
        char if char.encode('shift_jis', errors='ignore') else replace_with
        for char in v
    )

base_path = os.path.dirname(__file__)
config_path = os.path.join(base_path, 'config.yaml')
with open(config_path, 'r', encoding='utf-8') as fp:
    config = yaml.safe_load(fp)
driver_path = config['path']['driver_path']

if config['settings']['manual_date']:
    start_date_text = config['settings']['manual_start_date']
    end_date_text = config['settings']['manual_end_date']

else:
    start_date = date.today() + timedelta(days=-7)
    end_date = date.today() + timedelta(days=-1)
    start_date_text = str(start_date)
    end_date_text =str(end_date)

start_year = start_date_text.split("-")[0]
start_month = start_date_text.split("-")[1]
start_day = start_date_text.split("-")[2]
end_year = end_date_text.split("-")[0]
end_month = end_date_text.split("-")[1]
end_day = end_date_text.split("-")[2]

if config['settings']['selenium']:
    options = Options()
    # options.add_argument('--headless')
    driver = webdriver.Chrome(service=ChromeService(driver_path))
    driver.maximize_window()

    print('--------三晃商事アンケート取得開始---------')
    driver.get(config['enquetes']['url'])

    time.sleep(10)

    pyautogui.write(config['enquetes']['id'], interval=0.1)
    time.sleep(2)
    pyautogui.press("tab")
    time.sleep(2)
    pyautogui.write(config['enquetes']['pw'], interval=0.1)
    time.sleep(2)
    pyautogui.press("enter")
    time.sleep(10)

    input_start_date = driver.find_element(By.NAME, "cre_date_fm")
    # <input type="text" name="cre_date_fm" value="" size="10" class="js-datepicker hasDatepicker" autocomplete="off" id="dp1740161641618">
    input_start_date.click()
    time.sleep(5)
    input_start_date.send_keys(start_date_text + Keys.TAB + end_date_text + Keys.ENTER)
    time.sleep(5)

    submit_button = driver.find_elements(By.ID, "submit")
    submit_button[0].click()
    time.sleep(15)

    export_button = driver.find_elements(by=By.CLASS_NAME, value="link")
    export_button[1].click()
    time.sleep(30)
    
    driver.close()

    move_path = os.path.join(base_path, config['csv']['input_directory'])
    download_path = glob.glob(os.path.join(config['path']['download_path'],'enquete_raw*.csv'))
    print(f"ダウンロードパス: {download_path}")
    for dp in download_path:
        new_path = shutil.move(dp, move_path)

    print('--------csvダウンロード完了--------')

if config['settings']['upload']:
    if __name__ == '__main__':
        arg_parser = ArgumentParser()

        base_path = os.path.dirname(__file__)
        config_path = os.path.join(base_path, 'config.yaml')

        with open(config_path, 'r', encoding='utf-8') as fp:
            config = yaml.safe_load(fp)

        conn = psycopg2.connect(
            host=config['db']['host'],
            port=config['db']['port'],
            user=config['db']['user'],
            password=config['db']['password'],
            database=config['db']['database']
        )

        generate_keys = [
            'enquete_key',
            'import_date'
        ]

        ordered_keys = [
            *config['mappings']['string'].keys(),
            *config['mappings']['text'].keys(),
            *config['mappings']['integer'].keys(),
            *config['mappings']['date'].keys(),
            *config['mappings']['datetime'].keys(),
            *generate_keys
        ]

        mapping_keys = ', '.join(ordered_keys)
        
        table_name = 'enquetes'
        table_insert_query = f'INSERT INTO {table_name}({mapping_keys}) VALUES %s'
        table_insert_query += ' ON CONFLICT (enquete_number) DO UPDATE SET '
        
        table_insert_query += ','.join([f'{c} = excluded.{c}' for c in [
            *config['mappings']['string'].keys(),
            *config['mappings']['text'].keys(),
            *config['mappings']['integer'].keys(),
            *config['mappings']['date'].keys(),
            *config['mappings']['datetime'].keys(),
        ] if c != 'enquete_number'])

        print(table_insert_query)

        try:
            cursor = conn.cursor()

            input_dir = os.path.join(base_path, config['csv']['input_directory'])
            output_dir = os.path.join(base_path, config['csv']['output_directory'])
            csv_path_list = glob.glob(os.path.join(input_dir, '*.csv'))
            n_records = 0

            for path in csv_path_list:
                with open(os.path.join(base_path, path), 'r', encoding='utf-16', errors='ignore') as fp:
                    reader = csv.DictReader(fp, delimiter='\t')
                    data = list(reader)
                    n_records = len(data)

                    buf = []
                    for row in tqdm(data):
                        record = make_record_from_row(row, config['mappings'])
                        record = add_generate_items(record)
                        record.update(add_import_date())

                        tqdm.write(', '.join([
                            str(record['enquete_number']),
                            record['answer_datetime'].isoformat() or '',
                        ]))
                        
                        buf.append([record[k] for k in ordered_keys])

                        if len(buf) >= 1000000:
                            extras.execute_values(cursor, table_insert_query, buf)
                            conn.commit()
                            buf = []
                    
                    extras.execute_values(cursor, table_insert_query, buf)
                    conn.commit()
                    buf = []
                    
                shutil.move(path, output_dir)
                if config['settings']['message']['success']:
                    post_webhook(config, f'アンケートデータ: {path} をDBにインポートしました。 (レコード数: {n_records})')
        
        except Exception as ex:
            msg = traceback.format_exc()
            if config['settings']['message']['success']:
                post_webhook(config, f'アンケートデータ: インポート実行中にエラー: {msg}')
            print(msg)
            conn.rollback()
            exit(1)

        finally:
            conn.close()

