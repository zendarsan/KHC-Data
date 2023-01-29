import requests
from bs4 import BeautifulSoup
import re
import csv
import time
from os.path import exists, realpath
from urllib.parse import quote
import json
import glob
import multiprocessing as mp
import pdfplumber
import io
import traceback
import unicodedata
current_record = 0
current_set = 0
fails = 0

headers = {
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
    'Accept-Language': 'en-GB,en;q=0.9',
    'Cache-Control': 'max-age=0',
    'Connection': 'keep-alive',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'none',
    'Sec-Fetch-User': '?1',
    'Upgrade-Insecure-Requests': '1',
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36',
    'sec-ch-ua': '"Not_A Brand";v="99", "Google Chrome";v="109", "Chromium";v="109"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"macOS"',
}
    #Create new session and set cookies by making a request


def get_case_deets(cino, case_no, court_no, state_code, dist_code, s):
    
    data = {
      '__csrf_magic': 'sid:22e25a4a3b8a2c3dd3a08f8c43e207354a236ed2,1641670946',
      'state_code': state_code,
      'dist_code': dist_code,
      'cino': cino,
      'case_no': case_no,
      'appFlag': '',
      'court_code': court_no
    }

    response = s.post('https://services.ecourts.gov.in/ecourtindia_v4_bilingual/cases/o_civil_case_history.php', headers=headers,data=data, timeout=15)
    return (response.content, 0)

def get_case_document(link, s):
    for x in range(2):
        try:
            response = s.get(link, headers=headers, timeout=15)
        except:
            s = requests.session()
            s.get(response, headers=headers)
    return (response)

def process(soup, cino):
    deets = get_all(soup)
    if len(deets[1])<1:
        return 0
    disposed_date = " "
    disposed_reason = " "
    disposed_year = " "
    filing_number= deets[0][6][15:25].split('/')[0]
    filing_date = deets[0][8][-10:]
    filing_year = filing_date[-4:]
    registration_number = deets[0][9][21:31].split('/')[0]
    registration_date = deets[0][11][19:]
    registration_year = registration_date[-4:]
    stage = deets[0][16].split(": ")[-1].strip()     
    stage = re.sub(r'[^a-zA-Z ]', '',stage)  
    
    if 'CASE DISPOSED' in stage.upper():
        disposed_date = deets[0][15].split(":")[-1].strip()
        disposed_year = disposed_date[-4:]
        disposed_reason =deets[0][17].split(":")[-1].strip()
        
        judge = deets[0][18].split(':')[-1].strip()[4:].title()
        bench = deets[0][19].split(':')[-1].strip().title()
    else:
        judge = deets[0][17].split(':')[-1].strip()[4:].title()
        bench = deets[0][18].split(':')[-1].strip().title()
    if bench == '':
        bench = ' '
    statute = deets[1][0]
    provision = deets[1][1]
    if statute == 'History of Case Hearing':
        statute = " "
        provision = " "
    try:
        first_hearing = deets[0][14].split(": ")[1]
    except IndexError:
        first_hearing = ""

    category, sub_category, sub_sub_category, *_ = get_category_details(deets[-1])

    
    party_subview = [x for x in deets[0] if x[:2]=='1)']
    #print(party_subview)
    p_advocate, p_length, p1, p2, p3, p4, *_ = clean_parties(party_subview[0])
    r_advocate, r_length, r1, r2, r3, r4, *_ = clean_parties(party_subview[1])

    

    try:
        last_hearing = soup.select("body > form > div:nth-child(2) > table.history_table > tr > td")
        last_hearing_date = last_hearing[-3].get_text()
        last_hearing_matter = last_hearing[-1].get_text()
    except IndexError:
        last_hearing_date = ""
        last_hearing_matter = ""
    
    try:
        order_link = soup.select("#secondpage > div:nth-child(13) > table.order_table > tbody > tr:nth-child(2) > td:nth-child(4) > a")['href']
    except:
        order_link = " "
    try:
        acts = soup.select("table#act_table tr")[1:]
        provisions = ""
        for act in acts:
            
            title = act.select("td")[0].get_text()
            sections = act.select("td")[1].get_text()
            if "-" in sections:
                continue
            else:
                sections = sections.replace(",", " ")
                string = f"{title}: {sections}; "
                provisions+=string

    except IndexError as e:
        provisions = "N/A"
        raise e

    FIR_details = soup.select("span.FIR_details_table label")
    try:    
        if FIR_details:
            station = FIR_details[0].get_text()
            fir_number = FIR_details[1].get_text()
            fir_year = FIR_details[2].get_text()
        else:
            station, fir_number, fir_year = ("N/A","N/A","N/A")
    except IndexError as e:
        
        station, fir_number, fir_year = ("N/A","N/A","N/A")

    try:
        case_type = soup.select(".case_details_table")[0].get_text()
        case_type = case_type.split(":")[-1].strip()
    except IndexError as e:
        case_type = ""
        raise e
    
    if p_length > 1:
        p1 += " & Ors."
    if r_length > 1:
        r1 += " & Ors."
    rows = [p1,r1, str(p_length), str(r_length), cino, case_type, filing_number, filing_year, filing_date, registration_number, registration_year, registration_date, fir_number, station, fir_year, provisions, stage, disposed_date, disposed_year, disposed_reason,]
    rows = [x.replace(":\xa0", "") for x in rows]
    #print(rows)
    return rows

def print_all(soup):
    import unicodedata
    f = open('log.txt', 'a')
    normal = lambda x: unicodedata.normalize("NFKD", x.get_text().strip())
    f.write(f"Record: {current_record}: ")
    f.write(str([normal(x) for x in soup.find_all('span')]))
    f.write('td\n')
    f.write(str([normal(x) for x in soup.find_all('td')]))
    f.write('tr\n')
    f.write(str([normal(x) for x in soup.find_all('tr')]))
    f.write('\n')
    last_hearing = soup.select("body > form > div:nth-child(2) > table.history_table > tr > td")
    f.write(str(last_hearing))
    f.write('\n\n')

    f.close()
def get_all(soup):
    import unicodedata
    normal = lambda x: unicodedata.normalize("NFKD", x.get_text().strip())
    return (([normal(x) for x in soup.find_all('span')]), [normal(x) for x in soup.find_all('td')], [normal(x) for x in soup.find_all('tr')])\



def get_category_details(items):
    temp_category = [x.split('\n')[-1] for x in items if "Category\n" in x]
    while len(temp_category)<3:
        temp_category.append(" ")
    return temp_category

def clean_parties(parties):
    parties = re.split(r'\d+\)', parties)
    clean_parties = []
    advocates = []
    for ind, party in enumerate(parties):
        if "Advocate" in party:
            advocate = party.split("Advocate")[-1]
            advocate = re.sub(r'[^a-zA-Z ]', '',advocate).strip()
            if "FOR R" in advocate:
                advocate = advocate.split("FOR")[0]
            #print(advocate)
            advocates.append(advocate)
        
        temp_party = party.split("Advocate")[0].strip()
        if temp_party:
            temp_party = re.sub(r'[^a-zA-Z \\ \)\(]', '',temp_party)
            clean_parties.append(temp_party)
           
    if not advocates:
        advocate = " "
    else:
        advocate = advocates[0]

    clean_parties.insert(0, len(clean_parties))
    clean_parties.insert(0, advocate)
    
    while len(clean_parties) < 6:
        clean_parties.append(" ")

    return clean_parties




def process_case_set(case_set):
    fails = 0
    court_code = case_set['court_no']
    cases = case_set['cases']
    court = case_set['court']
    state_code = case_set['state_code']
    dist_code = case_set['dist_code']
    disp = case_set['disp']
    section = case_set['section']
    counter = case_set['counter']
    current_record = 0
    print(f"Starting {court}, {len(cases)} pending, {fails} failed so far. Set {current_set} of {len(all_cases)}")

    filename = f"saloni/judgements_{section}_{counter}.csv"
    csv_file = open(filename,'w', encoding='utf-8', newline='')
    csvwriter = csv.writer(csv_file)
    if current_record == 0 and counter==0:
        fields = ['Petitioner','Respondent', "Petitioner Count", "Respondent Count", "Case Type", "CINO", 'Filing Number', 'Filing Year', 'Filing Date', "Registration Number", 'Registration Year','Registration Date', "FIR Number", "Station", "FIR Year", "Provisions Charged", 'Stage','Disposed Date', 'Disposed Year', 'Disposal Reason', "Court", "Extract",]
        csvwriter.writerow(fields) 
    
    orders_filename = f"saloni/orders_{section}_{counter}.csv"
    orders_csv_file = open(orders_filename,'w', encoding='utf-8', newline='')
    orders_csvwriter = csv.writer(orders_csv_file)
    if current_record == 0 and counter==0:
        fields = ['Petitioner','Respondent', "Petitioner Count", "Respondent Count", "Case Type", "CINO", 'Filing Number', 'Filing Year', 'Filing Date', "Registration Number", 'Registration Year','Registration Date', "FIR Number", "Station", "FIR Year", "Provisions Charged", 'Stage','Disposed Date', 'Disposed Year', 'Disposal Reason', "Court", "Extract",]
        orders_csvwriter.writerow(fields) 

    orders_filename = f"saloni/extras_{section}_{counter}.csv"
    extras_csv_file = open(orders_filename,'w', encoding='utf-8', newline='')
    extras_csvwriter = csv.writer(orders_csv_file)
    if current_record == 0 and counter==0:
        fields = ['Petitioner','Respondent', "Petitioner Count", "Respondent Count", "Case Type", "CINO", 'Filing Number', 'Filing Year', 'Filing Date', "Registration Number", 'Registration Year','Registration Date', "FIR Number", "Station", "FIR Year", "Provisions Charged", 'Stage','Disposed Date', 'Disposed Year', 'Disposal Reason', "Court", "Extract",]
        extras_csvwriter.writerow(fields) 
    print("starting session")
    ActNodata = {
    'court_codeArr': court_code,
    'state_code': state_code,
    'dist_code': dist_code,
    'search_act': '',
    'action_code': 'fillActType',

    }
    try:
        s = requests.session()
        response = s.post(
            'https://services.ecourts.gov.in/ecourtindia_v4_bilingual/cases/s_actwise_qry.php',
            headers=headers,
            data=ActNodata,
            timeout=5
        )
        headers['Cookie'] = f"PHPSESSID={s.cookies['PHPSESSID']}"
    except KeyError:
        headers = {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
            'Accept-Language': 'en-GB,en;q=0.9',
            'Cache-Control': 'max-age=0',
            'Connection': 'keep-alive',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Upgrade-Insecure-Requests': '1',
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36',
            'sec-ch-ua': '"Not_A Brand";v="99", "Google Chrome";v="109", "Chromium";v="109"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"macOS"',
        }
        response = s.post(
    'https://services.ecourts.gov.in/ecourtindia_v4_bilingual/cases/s_actwise_qry.php',
    headers=headers,
    data=ActNodata,
    timeout=25
)
        if 'PHPSESSID' in s.cookies:
            headers['Cookie'] = f"PHPSESSID={s.cookies['PHPSESSID']}"
        else:
            headers['Cookie'] = f"PHPSESSID=19n3gd8bgj14n85ekeu5ifhtlu"

    print("starting looping")
    for x in range(current_record, len(cases)):
        judgement_flag = False
        order_flag = False
        print(f"Processing case {current_record}")
        cino = cases[x]['cino']
        case_no = cases[x]['case_no']
        #print(current_record, cino, case_no)
        for i in range(3):
            try:
                page, downloaded = get_case_deets(cino, case_no, court_code, state_code, dist_code, s)
                soup = BeautifulSoup(page, features="html.parser")
                row = process(soup, cino)
                if isinstance(row, int):
                        s = requests.session()
                        response = s.post(
                            'https://services.ecourts.gov.in/ecourtindia_v4_bilingual/cases/s_actwise_qry.php',
                            headers=headers,
                            data=ActNodata,
                            timeout=5
                        )
                        headers['Cookie'] = f"PHPSESSID={s.cookies['PHPSESSID']}"
                        page, downloaded = get_case_deets(cino, case_no, court_code, state_code, dist_code, s)
                        soup = BeautifulSoup(page, features="html.parser")
                        row = process(soup, cino)           
                else:
                    break
            except Exception as e:
                time.sleep(0.5+i)
                print(e, "Retrying")
        else:
            current_record+=1
            fails+=1  
            continue

        try:
            if isinstance(row, int):
                continue
            row.append(court)
            orders = soup.select("table.order_table tr")
            if len(orders) <= 1:
                orders = []
            elif len(orders)<3:
                orders = [orders[-1]]
            else:
                orders = orders[-2:]
            
            for index, order in enumerate(orders):
                details = [x.get_text().strip() for x in order.select('td')]
                if not details:
                    continue
                name = details[-1]

                query = order.select('a')
                if query:
                    query = query[0]['href'].replace("  ", '%20')
                    query = query.replace(" ", "%20")
                else:
                    continue

                if 'judg' not in name.lower():
                    print("NOT JUDGEMENT", name)
                    order_flag=True
                    order_name = f"saloni/orders/{row[3]} of {row[4]}_{name.title()}_{cino}_{index}.pdf"
                else:
                    judgement_flag = True
                    order_name = f"saloni/judgements/{row[3]} of {row[4]}_{name.title()}_{cino}_{index}.pdf"
                
                link = f"https://services.ecourts.gov.in/ecourtindia_v4_bilingual/cases/{query}"
                print("getting cases")
                doc = get_case_document(link, s)
                if doc.headers['Content-Type'] == 'application/pdf':
                    with pdfplumber.open(io.BytesIO(doc.content)) as pdf:
                        texts = []
                        for page in pdf.pages:
                            text = page.extract_text()
                            texts.append(text)
                        paras = " ".join(texts)
                        paras = paras.replace("\n", " ")
                        line = re.findall("[^.?!]*(?<=[.?\s!])DNA(?=[\s.?!])[^.?!]*[.?!]", paras)
                        if line:
                            line = unicodedata.normalize("NFKD", "|".join(line))
                            print(f"DNA FOUND, {line}")
                            with open(order_name, 'wb') as f:      
                                f.write(doc.content)
                                file_name = f'=hyperlink("{order_name}", "{line}")'
                                row.extend([name, file_name])
                        else:
                            print("NO DNA")
                            with open(f"saloni/extras/{row[3]} of {row[4]}_{name.title()}_{cino}_{index}_NODNA.pdf", 'wb') as f:      
                                f.write(doc.content)
                        
                else:
                    print("No file", doc.headers['Content-Type'], link)

            if row != 0 and judgement_flag:
                print(row)
                csvwriter.writerow(row)

            elif row != 0 and order_flag:
                print(row)
                orders_csvwriter.writerow(row)

            else:
                extras_csvwriter.writerow(row)

        except Exception as e:      
            fails+=1    
            print("FAILED", traceback.format_exc(), '\n',row)
            with open(f"saloni/errors/{current_record}.html", 'w', encoding='utf-8') as f:
                f.write(str(soup))
            
        current_record+=1
    print(f"Processed {current_record} cases")
    csv_file.close()
    extras_csv_file.close()
    orders_csv_file.close()
    print(f"Completed {court}, {len(cases)} processed.")
    return(f"Completed {court}, {len(cases)} processed.")


if __name__ == '__main__':

    all_files = glob.glob("saloni/case_list/*.txt")
    all_cases = []
    counter = 0
    for file in all_files:
        with open(file, 'r') as f:
            if '_Disp' in file:
                disp="disposed"
            else:
                disp="pending"

            x = json.loads(f.read())
            
            for cases, court_code, court in zip(x['con'], x['court_code'], x['courtNameArr']):
                if(cases and court_code and court):
                    all_cases.append({
                    'court_no': court_code,
                    'cases': json.loads(cases),
                    'court': court,
                    'state_code': x['stateCode'],
                    'dist_code': x['distCode'],
                    'disp': disp,
                    'section': file[:3],
                    'counter': counter
                })
                    counter+=1
    count = 0
    for cases in all_cases:
        count+=len(cases)
    print(f"Processing {count} cases total")

    with mp.Pool(processes=4) as pool:
        parsed = pool.map(process_case_set, all_cases)
    print(parsed)
    with open("Finished", 'w') as f:
        f.write("Done")
    