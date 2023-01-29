
import io
from bs4 import BeautifulSoup
from twocaptcha import TwoCaptcha
import json
import requests
import re

def get_court_complex_cases(link, section=379):
    #Get captcha and site
    print("Starting ", link)
    headers = {
    'Accept': 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
    'Accept-Language': 'en-GB,en-US;q=0.9,en;q=0.8',
    'Connection': 'keep-alive',
    'Referer': 'https://services.ecourts.gov.in/',
    'Sec-Fetch-Dest': 'image',
    'Sec-Fetch-Mode': 'no-cors',
    'Sec-Fetch-Site': 'same-origin',
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36',
    'sec-ch-ua': '"Not_A Brand";v="99", "Google Chrome";v="109", "Chromium";v="109"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"macOS"',
}
    s = requests.session()
    resp = s.get(link, headers=headers, timeout=10)

    state_code, dist_code = re.findall('=(\d{1,2})', link)
    soup = BeautifulSoup(resp.content)
    court_codes = [x.attrs['value'].split("@")[1] for x in soup.find(id='court_complex_code').find_all('option')[1:]]
    print(court_codes)
    
    for court in court_codes:
        ActNodata = {
            'court_codeArr': court,
            'state_code': state_code,
            'dist_code': dist_code,
            'search_act': '',
            'action_code': 'fillActType',

        }
        response = s.post(
            'https://services.ecourts.gov.in/ecourtindia_v4_bilingual/cases/s_actwise_qry.php',
            headers=headers,
            data=ActNodata,
            timeout=5
        )
        codes = str(response.content).split("#")
        actCode = 0
        for code in codes:
            if "ipc" in code.lower() or "indian penal" in code.lower():
                actCode = code.split("~")[0]
                print(actCode, code)

        for case_type in ['Disposed']:

            solver = TwoCaptcha('3d5411601bd36ac99dab2eeade90f405')
            for x in range(3):
                try:
                    print(f"Trying {court} and {case_type}")
                    captcha_link = "https://services.ecourts.gov.in"+soup.find(id='captcha_image').attrs['src']
                    with open('image.png', 'wb') as f:
                        f.write(s.get(captcha_link, headers=headers, timeout=10).content)
                    captcha = solver.normal('image.png')
                    data = {
                        'court_codeArr': court,
                        'state_code': state_code,
                        'dist_code': dist_code,
                        'search_act': '',
                        'actcode': actCode,
                        'f': case_type,
                        'under_sec': section,
                        'action_code': 'showRecords',
                        'captcha': captcha['code'],
                        'lang': '',
                    }
                    print(f"Data is {data}")
                    response = s.post(
                        'https://services.ecourts.gov.in/ecourtindia_v4_bilingual/cases/s_actwise_qry.php',
                        headers=headers,
                        data=data,
                        timeout=5
                    )
                    
                    data = json.loads(response.content)
                    if data['con']=='Invalid Captcha':
                        "INVALID"
                        continue
                    else: 
                        break
                except Exception as e:
                    print(e)
                    continue

            data['stateCode'] = state_code
            data['distCode'] = dist_code
            with open(f"saloni/case_list/{section}_{court}_{state_code}_{dist_code}_{case_type}.txt", 'w') as f:
                f.write(json.dumps(data))

links = """https://services.ecourts.gov.in/ecourtindia_v4_bilingual/cases/s_actwise.php?state=D&state_cd=26&dist_cd=4
https://services.ecourts.gov.in/ecourtindia_v4_bilingual/cases/s_actwise.php?state=D&state_cd=26&dist_cd=5
https://services.ecourts.gov.in/ecourtindia_v4_bilingual/cases/s_actwise.php?state=D&state_cd=26&dist_cd=2
https://services.ecourts.gov.in/ecourtindia_v4_bilingual/cases/s_actwise.php?state=D&state_cd=26&dist_cd=1
https://services.ecourts.gov.in/ecourtindia_v4_bilingual/cases/s_actwise.php?state=D&state_cd=26&dist_cd=9
https://services.ecourts.gov.in/ecourtindia_v4_bilingual/cases/s_actwise.php?state=D&state_cd=26&dist_cd=8
https://services.ecourts.gov.in/ecourtindia_v4_bilingual/cases/s_actwise.php?state=D&state_cd=26&dist_cd=3
https://services.ecourts.gov.in/ecourtindia_v4_bilingual/cases/s_actwise.php?state=D&state_cd=26&dist_cd=7
https://services.ecourts.gov.in/ecourtindia_v4_bilingual/cases/s_actwise.php?state=D&state_cd=26&dist_cd=6
https://services.ecourts.gov.in/ecourtindia_v4_bilingual/cases/s_actwise.php?state=D&state_cd=26&dist_cd=11
https://services.ecourts.gov.in/ecourtindia_v4_bilingual/cases/s_actwise.php?state=D&state_cd=26&dist_cd=10"""
links = links.split("\n")

for section in ['302', '376']:
    for link in links:
        try:
            get_court_complex_cases(link, section=section)
        except requests.Timeout:
            print("TIMEOUT")
