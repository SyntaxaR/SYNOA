from bs4 import BeautifulSoup
import requests
import logging.config
import re
from threading import Timer
import json
from datetime import datetime
import traceback

last_routine_message_id = 0 #Do not edit

#Interval checking SONA (seconds)
CHECK_PERIOD = 180

#SONA PLATFORM INFO
USERNAME = "username" #Username for SONA platform
PASSWORD = "password" #Password for SONA platform
KEYWORD = "ab1601" #Keyword for the research title you want

#IFTTT API
IFTTT_SERVICE_KEY = "IFTTT_SERVICE_KEY" #Used for IFTTT push

#Telegram API
TELEGRAM_BOT = "https://api.telegram.org/yourBot:yourKey/" 
TELEGRAM_CHAT_ID = "YOUR_TELEGRAM_GROUPCHAT_ID"




ONLINE_FROM = datetime.now().strftime("%Y/%m/%d %H:%M:%S")
current_result = []

logging_cfg = {
    'version': 1,
    "disable_existing_loggers": False,
    "formatters": {
        'default': {
            'datefmt': "%Y-%m-%d %H:%M:%S",
            'format': '%(asctime)s %(levelname)s %(message)s'
        },
    },
    'handlers': {
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'default',
        },
        'file': {
            'level': 'DEBUG',
            'class': 'logging.handlers.TimedRotatingFileHandler',
            'formatter': 'default',
            'when': 'd',
            'interval': 1,
            'backupCount': 30,
            'filename': "logs/error.log",
            'encoding' : 'utf-8'
        }
    },
    'loggers': {
        'StreamLogger':{
            'handlers': ['console'],
            'level': 'DEBUG'
        },
        'FileLogger':{
            'handlers': ['console', 'file'],
            'level': 'DEBUG'
        }
    }
}
logging.config.dictConfig(logging_cfg)
logger = logging.getLogger("FileLogger")

def login():
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/110.0"})
    session.get("https://ntu-nbs.sona-systems.com/Default.aspx")
    r = session.post("https://ntu-nbs.sona-systems.com/Default.aspx", data={
        "__LASTFOCUS": "",
        "__VIEWSTATE": "/wEPDwUKLTI5MjUzMDMxNGRk2Otc2i19BoprNFG0g9KH7/pmrhxbxOYJrcYZAlJIq9o=",
        "__VIEWSTATEGENERATOR": "CA0B0334",
        "__EVENTTARGET": "",
        "__EVENTARGUMENT": "",
        "__EVENTVALIDATION": "/wEdAAZHafI2CmXQF2NpR8XBu2/3UIlPJ3shF6ZfHx5cHAdswV/FKIbOHcdhWXmQSg51JR59RrGuEKfSBTDWck9ZvzkZThj6CryUsV5edO/j1slC3ZNCGkWvNYEshf7dhO594iVt8kTIIyqClgNdmRFNN9O28VhRBniRHdn6JyB+3+a21Q==",
        "ctl00$ContentPlaceHolder1$return_experiment_id": "",
        "ctl00$ContentPlaceHolder1$return_signup_id": "",
        "ctl00$ContentPlaceHolder1$userid": USERNAME,
        "ctl00$ContentPlaceHolder1$pw": PASSWORD,
        "ctl00$ContentPlaceHolder1$default_auth_button": "Log+In"
    })
    soup = BeautifulSoup(r.content, "html.parser")
    if soup.find(id="ctl00_UserDisplayName"):
        loggedusr = soup.find(id="ctl00_UserDisplayName").string
        logger.info("USER {} LOGGED IN SUCCESSFULLY".format(loggedusr))
        return session
    else:
        logger.fatal("USER LOGGED FAILED")
        logger.info(soup)
        return None

def chkList(session: requests.Session):
    r = session.get("https://ntu-nbs.sona-systems.com/all_exp_participant.aspx")
    soup = BeautifulSoup(r.content, "html.parser")
    kwdlst = soup.find_all('a', string=re.compile(KEYWORD, re.IGNORECASE))
    result = []
    for oitem in kwdlst:
        item = oitem
        while item.name != 'tr':
            if item.parent != None:
                item = item.parent
            else:
                logger.info("<td> element not found for {}".format(oitem.string))
                break
        if item.name == 'tr':
            if chkTimeslots(item):
                logger.info("AVAILABLE TIME SLOTS FOUND FOR {}".format(oitem.string))
                result.append(oitem.string)
            else:
                logger.info("No available time slots found for {}".format(oitem.string))
        else:
            logger.info("<td> sibling not found for {}".format(oitem.string))
    return result

def logOut(session: requests.Session):
    session.get("https://ntu-nbs.sona-systems.com/default.aspx?logout=Y")
    return

def chkTimeslots(item):
    for sibling in item.find_all("td"):
        if sibling.find(attrs={"aria-label": "Timeslots Available"}):
            return True
    return False
 
def iFTTTAvailableNotify(pushinfo):
    r = requests.get("https://maker.ifttt.com/trigger/SONA_TIMESLOT_FOUND/with/key/b-e1KM527Hqx_rPfO6WQFT?value1={}".format(pushinfo))
    logger.info("IFTTT NOTIFIED: "+str(r.text))

def telegramBotNANotify():
    pushinfo = "[!SLOTS BOOKED UP!]\n目前，所有研究可用时间均已定完，请等待通知。\nAll available time slots have been booked up, please wait for futher notifications."
    r = requests.get(TELEGRAM_BOT+"sendMessage?chat_id="+str(TELEGRAM_CHAT_ID)+"&text="+pushinfo+"&protect_content=true&disable_notification=true")
    logger.info("TELEGRAM NOTIFIED: "+str(r.content))

def telegramBotAvailableNotify(pushinfo):
    pushinfo = "[!NEW SLOTS AVAILABLE!]\n目前，研究 "+pushinfo+" 有可用时间！请查看SONA网站预约。\nStudy "+pushinfo+" has available time slots, please access to SONA website to book."
    r = requests.get(TELEGRAM_BOT+"sendMessage?chat_id="+str(TELEGRAM_CHAT_ID)+"&text="+pushinfo+"&protect_content=true")
    logger.info("TELEGRAM NOTIFIED: "+str(r.content))

def chkLoginStatus(session: requests.Session):
    r = session.get("https://ntu-nbs.sona-systems.com/all_exp_participant.aspx")
    soup = BeautifulSoup(r.content, "html.parser")
    if soup.find(string=re.compile("Please log in", re.IGNORECASE)):
        return False
    elif soup.find(string=re.compile("My Profile", re.IGNORECASE)):
        return True
    else:
        return False

def reportRunning(pushinfo):
    global last_routine_message_id
    logger.info("PUSHINFO: "+str(pushinfo))
    if last_routine_message_id:
        r = requests.get(TELEGRAM_BOT+"editMessageText?chat_id="+str(TELEGRAM_CHAT_ID)+"&message_id="+str(last_routine_message_id)+"&text="+str(pushinfo))
    else:
        r = requests.get(TELEGRAM_BOT+"sendMessage?chat_id="+str(TELEGRAM_CHAT_ID)+"&text="+pushinfo+"&protect_content=true&disable_notification=true")
    result = json.loads(r.text)
    if result.get('ok'):
        logger.info("TELEGRAM NOTIFIED: "+str(r.content))
        last_routine_message_id = result.get('result').get('message_id')
    else:
        logger.info("TELEGRAM NOTIFICATION ERROR: "+str(r.content))

class LoginError(Exception):
    pass

def main(session = None):
    try:
        if session is None:
            session = login()
        else:
            if chkLoginStatus(session):
                logger.info("Logged in")
            else:
                session = login()
        pushinfo = ""
        if session:
            global current_result
            result = chkList(session)
            if len(result)!=0:
                if result == current_result:
                    logger.info("Same as previous")
                else:
                    current_result = result
                    for i in result:
                        pushinfo = pushinfo + str(i) +", "
                    pushinfo = pushinfo[:-2]
                    iFTTTAvailableNotify(pushinfo)
                    telegramBotAvailableNotify(pushinfo)
                routineinfo = "[!BOT WORKING!]\n[!NEW SLOTS AVAILABLE!]\n本轮服务启动时间 BOT Start From: "+str(ONLINE_FROM)+"\n最近一次更新数据 Last Updated At: "+datetime.now().strftime("%Y/%m/%d %H:%M:%S")+"\n目前，研究 "+pushinfo+" 有可用时间！请查看SONA网站预约。\nStudy "+pushinfo+" has available time slots, please access to SONA website to book."
                reportRunning(routineinfo)
            else:
                if len(current_result) != 0:
                    logger.info("All slots have been booked up")
                    current_result = []
                    telegramBotNANotify()
                else:
                    logger.info("Still no available slots")
                routineinfo = "[!BOT WORKING!]\n本轮服务启动时间 BOT Start From: "+str(ONLINE_FROM)+"\n最近一次更新数据 Last Updated At: "+datetime.now().strftime("%Y/%m/%d %H:%M:%S")+"\n目前没有可用时间段，请等待新时间段。\nNo Timeslots Available, Please Wait For New Slots."
                reportRunning(routineinfo)
        else:
            raise LoginError("!Login Failed!")
    
    except BaseException as err:
        reportinfo="[!BOT DOWN!]\n本轮服务启动时间 BOT Start From: {}\n服务停止时间 BOT DOWN AT: {}\n错误消息 Error: {}".format(str(ONLINE_FROM), datetime.now().strftime("%Y/%m/%d %H:%M:%S"), str(err))
        logger.fatal("ERROR: {}".format(str(err)))
        print(traceback.format_exc())
        logger.fatal("TRACEBACK: {}".format(str(traceback.format_exc())))
        reportRunning(reportinfo)
        return
    Timer(CHECK_PERIOD, main, (session,)).start()

if __name__ == '__main__':
    main()