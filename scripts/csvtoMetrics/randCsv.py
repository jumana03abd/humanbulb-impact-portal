import csv
import random
import conf
'''"Timestamp,Score,Name,"Rate your Communication Skills 
1-5","Rate your Public speaking Skills 
1-5","Rate your  Project Management Skills 
1-5","Rate your Teamwork Skills 
1-5","Rate your Research Skills 
1-5",How familiar are you with clean tech careers?,
Describe how confident you feel introducing yourself to a professional.,"
"How confident are you participating in a job interview?,"
"How confident are you taking initiative or leading a group?,
" How familiar are you with professional workplace expectations? "'''
with open("week8.csv",'w', newline='') as newFile:
    with open("week1.csv", mode = 'r',encoding='utf-8') as file:
        reader = csv.reader(file)
        spamwriter = csv.writer(newFile, delimiter=',',
                            quotechar="'", quoting=csv.QUOTE_MINIMAL)
        for row in reader:
            if row[0]=="Timestamp":
                spamwriter.writerow(row)
                continue
            appendList=[row[0],row[1],row[2],random.randint(1,5),random.randint(1,5),random.randint(1,5),random.randint(1,5),random.randint(1,5),conf.randConf(),conf.randConf(),conf.randConf(),conf.randConf(),conf.randConf()]
            spamwriter.writerow(appendList)