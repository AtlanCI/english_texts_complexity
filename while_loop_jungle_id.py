#! /usr/bin/env python
# -*- coding: utf-8 -*-
#ОСНОВНАЯ ПРОБЛЕМА В ТОМ ЧТО ЕСЛИ АЙДИШНИК ПОЯВИТСЯ ОДИН РАЗ В ЗАПРОСЕ ТО МЫ БУДЕМ СУДИТЬ ПРО ВЕСЬ ТЕКСТ ПО ЭТОЙ ОДНОЙ СТРАНИЦЕ ЧТО НЕ ЕСТЬ ХОРОШО
# если попытаться избежать этого и следующий итераци делать не с id+1 а с id то если текст большой и займет все страницы запроса то мы уйдем в бесконечный цикл 
from calculate_level_new import get_level_from_raw_text
import psycopg2
import json
from tqdm import tqdm
import statistics
import multiprocessing 
import time
import random

DEBUG = True 

def write_response (json_file, start_index, final_index, debug = DEBUG):
    file_name = './save_jung_id/' + str(start_index) + '-' + str(final_index) +'.json'
    if debug: print("\nNOW SAVING", file_name,'\n')
    with open(file_name, 'w', encoding = "utf-8") as outfile:
        json.dump(json_file, outfile, indent=4, separators=(',', ':'),ensure_ascii=False)

conn = psycopg2.connect(dbname='pgstage', user='linguist', password='eDQGK0GCStlYlHNV', host='192.168.122.183')
#conn = psycopg2.connect(dbname='pgprod', user='linguist', password='eDQGK0GCStlYlHNV', host='postgres.lingualeo-beta.com')
cursor = conn.cursor()
interval = 10#pages inside request
#total pages in the base  2 262 479
#max jungle_id ± 620649
#page offset 1935200 ± jungle_id 563392
level2digit = {"Beginner":'0', "Elementary/Pre-Intermediate":'1',"Intermediate":'2',"Upper-Intermediate":'3',"Advanced":'4'}
digit2level = {'0': "Beginner", '1': "Elementary/Pre-Intermediate",'2':"Intermediate",'3':"Upper-Intermediate",'4':"Advanced"}

def calculate_level_from_offset(jungle_id_offset, thread_name, thread_session_index, debug = DEBUG):
    texts_in_one_object = 0
    midle_calc_level = []
    current_text = {"text": '', 'jungle_id':0}
    conn.rollback()
       
    #request = "SELECT jdesc ->>'page_text' AS page_text, jungle_id FROM public.content_jungle_pages ORDER BY jungle_id LIMIT " + str(interval) + " OFFSET " + str(offset)
    request = "SELECT jdesc ->>'page_text' AS page_text, jungle_id FROM public.content_jungle_pages WHERE jungle_id >= " + str(jungle_id_offset) +" ORDER BY jungle_id LIMIT " + str(interval)
    if debug: print("START HANDLing ", thread_name,"session index", thread_session_index)
    if debug: print(request)
    cursor.execute(request)
    level_json = []
    #check_index = 0
    #start_index = check_index
    
    for row in cursor:
         if(row[1] != current_text['jungle_id']):
            if len(current_text['text']) > 0:
                if len(midle_calc_level) > 0:
                    int_level = int(round(statistics.mean(midle_calc_level),0))
                    level = digit2level[str(int_level)]
                    midle_calc_level = []
                elif len(midle_calc_level) == 0:
                    level  = get_level_from_raw_text(current_text['text'])
                level_json.append({"jungle_id": current_text['jungle_id'], "level":level}) #""text":current_text['text']})
                #print(current_text['text'], current_text['jungle_id'], "LEVEL CALCULATED AS",level, "\n")
                if debug:
                    print(current_text['jungle_id'], "LEVEL CALCULATED AS",level, "\n")
                    print("Handling ", thread_name,"session index", thread_session_index)
                    print("====NEW TEXT (id =",row[1] ,")(previous texts calculations are above) prev = ", current_text['jungle_id'], "====\n")
                current_text = {"text": row[0], 'jungle_id':row[1]}
                texts_in_one_object = 1
            else:
                if len(midle_calc_level) > 0:
                    int_level = int(round(statistics.mean(midle_calc_level),0))
                    level = digit2level[str(int_level)]
                    level_json.append({"jungle_id": current_text['jungle_id'], "level":level}) #" "text":"CALCULATED FROM ACCUMULATION LIST"})
                    #print(current_text['text'], current_text['jungle_id'], "LEVEL CALCULATED AS",level, "\n")
                    if debug:
                        print(current_text['jungle_id'], "LEVEL CALCULATED AS",level, "\n")
                        print("Handling ", thread_name,"session index", thread_session_index)
                        print("====NEW TEXT (id =",row[1] ,"(previous texts calculations are above FROM LIST OF COMPLEXITIES), prev = ", current_text['jungle_id'], "====\n")
                    current_text = {"text": row[0], 'jungle_id':row[1]}
                    texts_in_one_object = 1
                    midle_calc_level = []
                else:
                    if debug:
                        print("Handling ", thread_name,"session index", thread_session_index)
                        print("====FIRST ENTRY", row[1], "====\n")#в середине текста может возникнуть если предыдущий текст был пустым
                    texts_in_one_object += 1
                    current_text['jungle_id'] = row[1]
                    current_text['text'] += ' ' + row[0]
         else:
            if texts_in_one_object <3:
                if debug:
                    print("Handling ", thread_name,"session index", thread_session_index)
                    print("====ADD TEXT TO EXISTING ", row[1], "====\n")
                current_text['text'] += ' ' + row[0]
                texts_in_one_object += 1
            else:
                if debug:
                    print("Handling ", thread_name,"session index", thread_session_index)
                    print("====TOO MUCH TEXT INFO INSIDE ONE OBJECT CALCULATE AVERAGE COMPLEXITY", row[1], "====\n")
                level  = get_level_from_raw_text(current_text['text'])
                current_text['text'] = ''
                int_level = int(level2digit[level])
                midle_calc_level.append(int_level)
                if debug:
                    print("Handling ", thread_name,"session index", thread_session_index)
                    print("CURRENT COMPLEXITY LIST IS", row[1],midle_calc_level)
                texts_in_one_object = 0
        #check_index += 1
    if  len(midle_calc_level) > 0:
        int_level = int(round(statistics.mean(midle_calc_level),0))
        level = digit2level[str(int_level)]
        level_json.append({"jungle_id": current_text['jungle_id'], "level":level})
        if debug:
            print("LEVEL CALCULATED IN THE END OF ITERATION FROM LIST",current_text['jungle_id'],level )
    elif len(current_text['text']) > 0:
        level  = get_level_from_raw_text(current_text['text'])
        level_json.append({"jungle_id": current_text['jungle_id'], "level":level})
        if debug:
            print("LEVEL CALCULATED IN THE END OF ITERATION FROM SINGLE TEXT PAGE",current_text['jungle_id'], level )
    #if check_index % 250 == 0 and check_index != 0:
    write_response(level_json,jungle_id_offset, current_text['jungle_id'])
    level_json = []

    #start_index = check_index  
    if debug:
        print("FINISHED HANDLing ", thread_name,"session index", thread_session_index)
    
    return int(current_text['jungle_id'])
    
thread_one_session = 0 
thread_two_session = 0 
def calculate_level_from_range(thread_session):
    for offset_ind in tqdm(range (1082400,1500000,interval)):
        calculate_level_from_offset(offset_ind,1, thread_session)
        thread_session +=1
        time.sleep(random.uniform(0.001,0.01))

def calculate_level_from_range_two(thread_session):
    # page id 1935200,2262500
    #for jungle_id_offset_ind in tqdm(range (563392,621000)):
    jungle_id_offset_ind = 563392
    while jungle_id_offset_ind <= 621000:
        jungle_id_offset_ind = calculate_level_from_offset(jungle_id_offset_ind,2, thread_session)
        jungle_id_offset_ind += 1
        thread_session +=1
        time.sleep(random.uniform(0.001,0.01))


#pr1=multiprocessing.Process(target=calculate_level_from_range(thread_one_session))
#pr1.start()

pr2=multiprocessing.Process(target=calculate_level_from_range_two(thread_two_session))
pr2.start()
